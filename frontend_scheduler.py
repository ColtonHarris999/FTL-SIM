from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from cache import CachePage, WriteCache
from event import Event, EventLoop, EventType
from ftl import FlashTranslationLayer
from nand import NANDTransaction, NANDTransactionType, PhysicalAddress
from nand_scheduler import NANDScheduler
from request import Request, RequestStatus, RequestType

if TYPE_CHECKING:
    from simulator import SSDSimulator

"""
Frontend scheduler manages the NCQ and issues ready requests to the cache or FTL/NAND. Writes always go to the cache whereas reads may go to the cache or FTL/NAND, depending on whether they are cached. The frontend scheduler is responsible for handling LBA-level hazards.

Request types and their handling:
- cached READ: issue to cache if not busy, otherwise wait
- uncached READ: issue to FTL/NAND instantly
- WRITE: issue to cache if not busy, otherwise wait
- RAW: reads must wait for prior writes to the same LBA to complete before being issued to the cache
- WAW: writes to the same LBA must be issued to the cache in order
- WAR: read must be issued (= assign PA) before later writes to the same LBA
"""


class FrontendScheduler:
    def __init__(
        self,
        event_loop: EventLoop,
        sim: SSDSimulator,
        cache: WriteCache,
        ftl: FlashTranslationLayer,
        nand_scheduler: NANDScheduler,
        ncq_size: int = 32,
    ) -> None:
        self.event_loop: EventLoop = event_loop
        self.sim: SSDSimulator = sim
        self.cache: WriteCache = cache
        self.ftl: FlashTranslationLayer = ftl
        self.nand_scheduler: NANDScheduler = nand_scheduler

        self.ncq_size: int = ncq_size
        self.ncq: List[Request] = []
        self.flush_events: List[Event] = []

        # Register event handlers
        self.event_loop.register_handler(
            EventType.REQUEST_ARRIVAL, self._handle_arrival
        )
        self.event_loop.register_handler(EventType.FRONTEND_SCHEDULE, self._schedule)
        self.event_loop.register_handler(
            EventType.CACHE_FLUSH_START, self._handle_flush_event
        )
        self.event_loop.register_handler(
            EventType.REQUEST_COMPLETE, self._handle_completion
        )

    def has_space(self) -> bool:
        return len(self.ncq) < self.ncq_size

    def _schedule(self, _: Event) -> None:
        if self.flush_events and not self.cache.is_busy():
            event: Event = self.flush_events.pop(0)
            assert isinstance(event.payload, CachePage)
            page: CachePage = event.payload
            self.cache.writeback(page.lpa)

        dirty_lbas: set[int] = set()
        for request in self.ncq:
            match request.type:
                case RequestType.READ:
                    if (
                        request.status != RequestStatus.READY
                        or request.lba in dirty_lbas
                    ):
                        continue
                    if self.cache.contains(request.lba):
                        if self.cache.is_busy():
                            continue
                        request.status = RequestStatus.IN_PROGRESS
                        self.cache.get(request)
                    else:
                        request.status = RequestStatus.IN_PROGRESS
                        pa: Optional[PhysicalAddress] = self.ftl.lpa_to_ppa(request.lba)
                        assert pa is not None
                        transaction: NANDTransaction = NANDTransaction(
                            type=NANDTransactionType.READ,
                            pa=pa,
                            completed_requests=[request],
                        )
                        self.nand_scheduler.enqueue(transaction)
                case RequestType.WRITE:
                    dirty_lbas.add(request.lba)
                    # TODO: check if cache has space?
                    if request.status != RequestStatus.READY or self.cache.is_busy():
                        continue
                    request.status = RequestStatus.IN_PROGRESS
                    self.cache.put(request)
                case RequestType.FLUSH:
                    # TODO: implement flush handling
                    # probably just stop issuing new requests until NAND scheduler queue is empty
                    raise NotImplementedError
                case _:
                    raise NotImplementedError

    def _handle_flush_event(self, event: Event) -> None:
        self.flush_events.append(event)

    def _handle_arrival(self, event: Event):
        assert self.has_space(), "NCQ is full"
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        request.enqueue_time = self.event_loop.time_us  # TODO: replace with trace
        self.ncq.append(request)
        self._schedule(event)

    def _handle_completion(self, event: Event):
        assert isinstance(event.payload, Request)
        request: Request = event.payload

        request.completion_time = self.event_loop.time_us  # TODO: replace with trace
        request.status = RequestStatus.COMPLETED
        self.ncq.remove(request)
        self.sim.complete(request)
        self._schedule(event)  # TODO: check if needed
