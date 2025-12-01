import enum
from dataclasses import dataclass, field
from typing import Optional

from event import Event, EventLoop, EventType
from ftl import FlashTranslationLayer
from nand import NANDTransaction, NANDTransactionType, PhysicalAddress
from nand_scheduler import NANDScheduler
from request import Request

"""
Write cache buffers and potentially coalesces/merges writes before flushing to NAND. It is logically indexed and operates on physical page size. If the physical page size is larger than the logical page size, multiple LBAs map to the same (cache) page which is addressed by an LPA (logical page address). The cache serializes all accesses and can only handle one request at a time.

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


class CachePageState(enum.Enum):
    DIRTY = enum.auto()
    FLUSH_SCHEDULED = enum.auto()
    FLUSHING = enum.auto()


@dataclass
class CachePage:
    lpa: int
    status: CachePageState = CachePageState.DIRTY
    flush_event: Optional[Event] = None
    requests: list[Request] = field(default_factory=list)


class WriteCache:
    def __init__(
        self,
        event_loop: EventLoop,
        ftl: FlashTranslationLayer,
        scheduler: NANDScheduler,
        num_pages: int = 2,
    ) -> None:
        self.event_loop: EventLoop = event_loop
        self.ftl: FlashTranslationLayer = ftl
        self.scheduler: NANDScheduler = scheduler

        self.num_pages: int = num_pages
        self.cache: dict[int, CachePage] = {}
        self.cached_lbas: set[int] = set()
        self.busy: bool = False

        # Timing parameters
        self.write_us: float = 10
        self.read_us: float = 10
        self.writeback_delay: float = 500  # timeframe for coalescing before writeback

        # Register event handlers
        self.event_loop.register_handler(
            EventType.CACHE_READ_COMPLETE, self._handle_cache_read_complete
        )
        self.event_loop.register_handler(
            EventType.CACHE_WRITE_COMPLETE, self._handle_cache_write_complete
        )
        self.event_loop.register_handler(
            EventType.NAND_WRITE_COMPLETE, self._handle_writeback_complete
        )

    def is_busy(self) -> bool:
        return self.busy

    def contains(self, lba: int) -> bool:
        return lba in self.cached_lbas

    def can_hold(self, lba: int) -> bool:
        lpa: int = self.ftl.lba_to_lpa(lba)
        return lpa in self.cache or len(self.cache) < self.num_pages

    def get(self, request: Request) -> None:
        assert not self.busy, "Cache is busy"
        assert request.lba in self.cached_lbas, "LBA not in cache"

        self.busy = True

        event: Event = Event(
            time_us=self.event_loop.time_us + self.read_us,
            ev_type=EventType.CACHE_READ_COMPLETE,
            payload=request,
        )
        self.event_loop.schedule_event(event)

    def put(self, request: Request) -> None:
        assert not self.busy, "Cache is busy"
        assert self.can_hold(request.lba), "Cache is full"

        self.busy = True

        event: Event = Event(
            time_us=self.event_loop.time_us + self.write_us,
            ev_type=EventType.CACHE_WRITE_COMPLETE,
            payload=request,
        )
        self.event_loop.schedule_event(event)

        # TODO: cancel previous flush event and reschedule?

    def _handle_cache_read_complete(self, event: Event) -> None:
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        self.busy = False

        # complete read request to host
        new_event: Event = Event(
            time_us=self.event_loop.time_us,
            ev_type=EventType.REQUEST_COMPLETE,
            payload=request,
        )
        self.event_loop.schedule_event(new_event)

        # TODO: check
        # Cache is ready, run frontend scheduler
        self.event_loop.schedule_event(
            Event(
                time_us=self.event_loop.time_us,
                ev_type=EventType.FRONTEND_SCHEDULE,
            )
        )

    def _handle_cache_write_complete(self, event: Event) -> None:
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        self.busy = False

        # complete write request to host
        if not request.fua:
            new_event: Event = Event(
                time_us=self.event_loop.time_us,
                ev_type=EventType.REQUEST_COMPLETE,
                payload=request,
            )
            self.event_loop.schedule_event(new_event)

        # TODO: check
        # Cache is ready, run frontend scheduler
        self.event_loop.schedule_event(
            Event(
                time_us=self.event_loop.time_us,
                ev_type=EventType.FRONTEND_SCHEDULE,
            )
        )

        # coalesce request into cache page
        self.cached_lbas.add(request.lba)
        lpa: int = self.ftl.lba_to_lpa(request.lba)
        if lpa not in self.cache:
            self.cache[lpa] = CachePage(lpa)
        page: CachePage = self.cache[lpa]
        page.requests.append(request)

        # schedule writeback after coalesce delay
        page.status = CachePageState.FLUSH_SCHEDULED
        new_event: Event = Event(
            time_us=self.event_loop.time_us + self.writeback_delay,
            ev_type=EventType.CACHE_FLUSH_START,
            payload=page,
        )
        self.event_loop.schedule_event(new_event)

    def writeback(self, lpa: int) -> None:
        """
        Handler for starting writeback/flush after coalesce delay.
        Issue NAND write via scheduler that eventually completes all currently coalesced requests. If not all subpages are written at least once,
        issue NAND read first.
        """

        assert not self.busy, "Cache is busy"
        assert lpa in self.cache, "LPA not in cache"

        page: CachePage = self.cache[lpa]

        # issue NAND read first if not all LOGICAL pages written
        read_transaction: Optional[NANDTransaction] = None
        if len(set([req.lba for req in page.requests])) < self.ftl.lbas_per_page:
            pa: Optional[PhysicalAddress] = self.ftl.lpa_to_ppa(page.lpa)
            assert pa is not None
            read_transaction = NANDTransaction(
                type=NANDTransactionType.READ,
                pa=pa,
                completed_requests=[],
            )
            self.scheduler.enqueue(read_transaction)

        # allocate physical address and issue NAND write
        transaction = NANDTransaction(
            type=NANDTransactionType.WRITE,
            pa=self.ftl.allocate(page.lpa),
            completed_requests=[],  # TODO: fill requests with FUA bit set
            depends_on=read_transaction,
        )
        self.scheduler.enqueue(transaction)
        self.scheduler.schedule()

    def _handle_writeback_complete(self, event: Event):
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        # TODO: check if pending read?

        # workaround to get page
        lpa = self.ftl.lba_to_lpa(transaction.completed_requests[0].lba)
        page = self.cache[lpa]

        # complete flushed requests from cache page
        for req in transaction.completed_requests:
            page.requests.remove(req)
            if req.fua:
                self.event_loop.schedule_event(
                    self.event_loop.time_us,
                    EventType.REQUEST_COMPLETE,
                    req,
                )

        # remove page from cache if empty
        if not page.requests:
            del self.cache[lpa]
            # TODO: how to handle cached_lbas
