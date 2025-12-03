from dataclasses import dataclass, field
from typing import Optional

from event import Event, EventLoop
from ftl import FlashTranslationLayer
from nand import NANDTransaction, NANDTransactionType, PhysicalAddress
from nand_scheduler import NANDScheduler
from request import Request, TraceEvent

"""
Write cache buffers and potentially coalesces/merges writes before flushing to NAND. It is logically indexed and operates on physical page size. If the physical page size is larger than the logical page size, multiple LBAs map to the same (cache) page which is addressed by an LPA (logical page address). The cache serializes all accesses and can only handle one request at a time.

Cache has one port to frontend and one port to each channel.

write:
- after write, schedule writeback event with x us coalesce delay
- on writeback event, mark as in progress and issue to NAND
- on write complete, mark as complete and free cache space

- if next write before writeback event, reschedule writeback event
- otherwise use new slots in cache??

read:
- on read schedule read complete event

TODO: also start writeback after threshold reached?
"""


@dataclass
class CachePage:
    lpa: int
    lbas: set[int] = field(default_factory=set)
    num_outstanding_flushes: int = 0


class WriteCache:
    def __init__(
        self,
        event_loop: EventLoop,
        ftl: FlashTranslationLayer,
        scheduler: NANDScheduler,
        num_pages: int = 1,
    ) -> None:
        self.event_loop: EventLoop = event_loop
        self.ftl: FlashTranslationLayer = ftl
        self.nand_scheduler: NANDScheduler = scheduler

        self.num_pages: int = num_pages
        self.cache: dict[int, CachePage] = {}
        self.busy: bool = False

        # Timing parameters
        self.write_us: float = 10
        self.read_us: float = 10
        self.flush_delay: float = 500  # timeframe for coalescing before writeback

    def contains(self, lba: int) -> bool:
        lpa: int = self.ftl.lba_to_lpa(lba)
        return lpa in self.cache and lba in self.cache[lpa].lbas

    def get(self, request: Request) -> bool:
        """
        Attempt to read request from cache. Returns True if read is scheduled, False otherwise. Caller must check if LBA is in cache first.
        """
        assert self.contains(request.lba), "LBA not in cache"

        if self.busy:
            return False

        print(f"! Reading {request} from cache")
        request.trace[TraceEvent.CACHE_READ_START] = self.event_loop.time_us

        self.busy = True

        event: Event = Event(
            time_us=self.event_loop.time_us + self.read_us,
            description="CACHE_READ_COMPLETE",
            payload=request,
            callback=self._handle_cache_read_complete,
        )
        self.event_loop.schedule_event(event)
        return True

    def put(self, request: Request) -> bool:
        """
        Attempt to write request to cache. Returns True if write is scheduled, False otherwise. A request is not scheduled if the cache is busy or there is insufficient space.
        """
        if self.busy or not self._can_hold(request.lba):
            return False

        print(f"! Writing {request} to cache")
        request.trace[TraceEvent.CACHE_WRITE_START] = self.event_loop.time_us

        self.busy = True

        lpa: int = self.ftl.lba_to_lpa(request.lba)
        if lpa not in self.cache:
            self.cache[lpa] = CachePage(lpa)
        page: CachePage = self.cache[lpa]
        page.num_outstanding_flushes += 1

        event: Event = Event(
            time_us=self.event_loop.time_us + self.write_us,
            description="CACHE_WRITE_COMPLETE",
            payload=request,
            callback=self._handle_cache_write_complete,
        )
        self.event_loop.schedule_event(event)
        return True

    def _can_hold(self, lba: int) -> bool:
        lpa: int = self.ftl.lba_to_lpa(lba)
        return lpa in self.cache or len(self.cache) < self.num_pages

    def _handle_cache_read_complete(self, event: Event) -> None:
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        request.trace[TraceEvent.CACHE_READ_COMPLETE] = self.event_loop.time_us

        self.busy = False

        assert request.callback is not None
        request.callback(request)

    def _handle_cache_write_complete(self, event: Event) -> None:
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        request.trace[TraceEvent.CACHE_WRITE_COMPLETE] = self.event_loop.time_us

        self.busy = False

        # coalesce LBA into cache page
        lpa: int = self.ftl.lba_to_lpa(request.lba)
        page: CachePage = self.cache[lpa]
        page.lbas.add(request.lba)

        # schedule flush after coalesce delay
        self.event_loop.schedule_event(
            Event(
                time_us=self.event_loop.time_us + self.flush_delay,
                description="CACHE_FLUSH_START",
                payload=page,
                callback=self._handle_flush_start,
            )
        )

        assert request.callback is not None
        request.callback(request)

    def _handle_flush_start(self, event: Event) -> None:
        """
        Handler for starting writeback/flush after coalesce delay.
        Issue NAND write via scheduler that eventually completes all currently coalesced requests. If not all subpages are written at least once,
        issue NAND read first.
        """
        assert isinstance(event.payload, CachePage)
        page: CachePage = event.payload

        page.num_outstanding_flushes -= 1
        if page.num_outstanding_flushes > 0:
            return  # another flush already scheduled

        # issue NAND read first if not all LOGICAL pages written
        if len(page.lbas) < self.ftl.lbas_per_page:
            pa: Optional[PhysicalAddress] = self.ftl.lpa_to_ppa(page.lpa)
            assert pa is not None
            transaction: NANDTransaction = NANDTransaction(
                type=NANDTransactionType.READ,
                pa=pa,
                payload=page,
                callback=self._handle_flush_read_complete,
            )
            self.nand_scheduler.submit(transaction)
        else:
            # all logical pages written, directly issue NAND write
            self._flush_write_start(page)

    def _handle_flush_read_complete(self, transaction: NANDTransaction) -> None:
        assert isinstance(transaction.payload, CachePage)
        page: CachePage = transaction.payload

        # mark all LBAs belonging to this page as cached
        page.lbas.update(
            range(
                page.lpa * self.ftl.lbas_per_page,
                (page.lpa + 1) * self.ftl.lbas_per_page,
            )
        )

        if page.num_outstanding_flushes == 0:
            self._flush_write_start(page)

    def _flush_write_start(self, page: CachePage) -> None:
        # allocate physical address and issue NAND write
        write_transaction: NANDTransaction = NANDTransaction(
            type=NANDTransactionType.WRITE,
            pa=self.ftl.allocate(page.lpa),
            payload=page,
            callback=self._handle_flush_complete,
        )
        self.nand_scheduler.submit(write_transaction)

    def _handle_flush_complete(self, transaction: NANDTransaction) -> None:
        assert isinstance(transaction.payload, CachePage)
        page: CachePage = transaction.payload

        # TODO: delay eviction if cache page is currently being read
        # there could be multiple flush transactions in the system
        # -> only evict if latest one completes and cache is not dirty again
        if page.num_outstanding_flushes == 0:
            del self.cache[page.lpa]
