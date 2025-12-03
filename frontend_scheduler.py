from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from cache import WriteCache
from event import EventLoop
from ftl import FlashTranslationLayer
from nand import NANDTransaction, NANDTransactionType, PhysicalAddress
from nand_scheduler import NANDScheduler
from request import Request, RequestStatus, RequestType, TraceEvent

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

# TODO: allow multiple sectors per request?


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

    def submit(self, request: Request) -> None:
        assert len(self.ncq) < self.ncq_size, "NCQ is full"
        request.trace[TraceEvent.ARRIVAL] = self.event_loop.time_us
        self.ncq.append(request)

    def try_dispatch(self) -> None:
        print("Running frontend scheduler...")
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
                        request.callback = self._handle_cache_read_complete
                        if self.cache.get(request):
                            request.status = RequestStatus.IN_PROGRESS
                    else:
                        request.status = RequestStatus.IN_PROGRESS
                        pa: Optional[PhysicalAddress] = self.ftl.lpa_to_ppa(request.lba)
                        assert pa is not None
                        transaction: NANDTransaction = NANDTransaction(
                            type=NANDTransactionType.READ,
                            pa=pa,
                            payload=request,
                            callback=self._handle_nand_read_complete,
                        )
                        self.nand_scheduler.submit(transaction)
                case RequestType.WRITE:
                    dirty_lbas.add(request.lba)
                    if request.status == RequestStatus.READY:
                        request.callback = self._handle_cache_write_complete
                        if self.cache.put(request):
                            request.status = RequestStatus.IN_PROGRESS
                case RequestType.FLUSH:
                    # TODO: implement flush handling
                    # probably just stop issuing new requests until NAND scheduler queue is empty
                    raise NotImplementedError
                case _:
                    raise NotImplementedError

    def _handle_nand_read_complete(self, transaction: NANDTransaction) -> None:
        assert isinstance(transaction.payload, Request)
        request: Request = transaction.payload

        request.trace[TraceEvent.NAND_READ_START] = transaction.start_time
        request.trace[TraceEvent.NAND_READ_COMPLETE] = self.event_loop.time_us
        request.trace[TraceEvent.COMPLETION] = self.event_loop.time_us
        request.status = RequestStatus.COMPLETED
        self.ncq.remove(request)
        self.sim.complete(request)

    def _handle_cache_read_complete(self, request: Request) -> None:
        request.trace[TraceEvent.COMPLETION] = self.event_loop.time_us
        request.status = RequestStatus.COMPLETED
        self.ncq.remove(request)
        self.sim.complete(request)

    def _handle_cache_write_complete(self, request: Request) -> None:
        # TODO: what if FUA flag is set?
        request.trace[TraceEvent.COMPLETION] = self.event_loop.time_us
        request.status = RequestStatus.COMPLETED
        self.ncq.remove(request)
        self.sim.complete(request)
