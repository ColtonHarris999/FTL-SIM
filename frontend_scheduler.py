from typing import List, Optional

from cache import WriteCache
from event import Event
from ftl import FlashTranslationLayer
from nand import NANDTransaction, NANDTransactionType, PhysicalAddress
from nand_scheduler import NANDScheduler
from request import Request, RequestStatus, RequestType

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
        cache: WriteCache,
        ftl: FlashTranslationLayer,
        nand_scheduler: NANDScheduler,
        ncq_size: int = 32,
    ) -> None:
        self.cache: WriteCache = cache
        self.ftl: FlashTranslationLayer = ftl
        self.nand_scheduler: NANDScheduler = nand_scheduler
        self.ncq_size: int = ncq_size
        self.ncq: List[Request] = []

        self.flush_events: List[Event] = []

    def has_space(self) -> bool:
        return len(self.ncq) < self.ncq_size

    def enqueue(self, request: Request) -> None:
        assert self.has_space(), "NCQ is full"
        self.ncq.append(request)

    def remove(self, request: Request) -> None:
        assert request in self.ncq, "Request not in NCQ"
        self.ncq.remove(request)

    def schedule(self) -> None:
        # TODO: prioritize flushes
        if not self.ncq:
            return

        dirty_lbas: set[int] = set()
        for request in self.ncq:
            if request.status != RequestStatus.READY:
                continue

            match request.type:
                case RequestType.READ:
                    if request.lba not in dirty_lbas:
                        if self.cache.contains(request.lba):
                            if not self.cache.is_busy():
                                request.status = RequestStatus.IN_PROGRESS
                                self.cache.get(request)
                        else:
                            request.status = RequestStatus.IN_PROGRESS
                            pa: Optional[PhysicalAddress] = self.ftl.lpa_to_ppa(
                                request.lba
                            )
                            assert pa is not None
                            transaction: NANDTransaction = NANDTransaction(
                                type=NANDTransactionType.READ,
                                pa=pa,
                                completed_requests=[request],
                            )
                            self.nand_scheduler.enqueue(transaction)
                case RequestType.WRITE:
                    dirty_lbas.add(request.lba)
                    if not self.cache.is_busy():
                        request.status = RequestStatus.IN_PROGRESS
                        self.cache.put(request)
                case RequestType.FLUSH:
                    # TODO: implement flush handling
                    # probably just stop issuing new requests until NAND scheduler queue is empty
                    raise NotImplementedError
                case _:
                    raise NotImplementedError
