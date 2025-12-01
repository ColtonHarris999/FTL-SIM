from abc import ABC, abstractmethod
from typing import List

from event import EventLoop, EventType
from nand import NAND, NANDTransaction
from request import Request, RequestStatus, RequestType


class NANDScheduler(ABC):
    """Scheduler interface"""

    def __init__(self, event_loop: EventLoop, nand: NAND):
        self.event_loop = event_loop
        self.nand = nand
        self.queue: List[NANDTransaction] = []

    @abstractmethod
    def schedule(self):
        pass

    def enqueue(self, req: NANDTransaction):
        self.queue.append(req)


class FIFOScheduler(NANDScheduler):
    """
    Naive FIFO scheduler
    Always schedules the oldest request in the queue
    """

    def schedule(self):
        if not self.queue:
            return
        req = self.queue[0]
        if req.status == RequestStatus.READY:
            req.start_time = self.event_loop.time_us
            req.status = RequestStatus.IN_PROGRESS

            match req.type:
                case RequestType.WRITE:
                    self.nand.write_page(req)
                case RequestType.READ:
                    self.nand.read_page(req)


class NaiveReadScheduler(NANDScheduler):
    """
    Naive read scheduler
    Similar to FIFOScheduler but always prioritizes read requests
    """

    def schedule(self):
        # try to find reads with no RAW conflicts
        hazards = set()
        for req in self.queue:
            if req.type == RequestType.READ:
                if not req.status == RequestStatus.READY:
                    continue
                if req.lba in hazards:
                    continue

                if not req.physical_addr.ready:
                    continue

                req.start_time = self.event_loop.time_us
                req.status = RequestStatus.IN_PROGRESS
                self.nand.read_page(req)
            elif req.type == RequestType.WRITE:
                hazards.add(req.lba)

        # no read found, schedule oldest write instead
        for req in ncq:
            if req.status == RequestStatus.READY and req.type == RequestType.WRITE:
                req.start_time = self.event_loop.time_us
                req.status = RequestStatus.IN_PROGRESS
                self.nand_ready = False
                self.channel.do_dma(req)


class WriteBackScheduler(NANDScheduler):
    def schedule(self, ncq: List[Request]):
        for req in self.ncq:
            if req.status != RequestStatus.READY:
                continue

            req.status = RequestStatus.IN_PROGRESS
            if req.type == RequestType.WRITE:
                # For writes, always start DMA -> cache
                self.cache.add_write(req)
                # mark host completion: we assume write-back cache -> complete to host now
                # TODO cache write time
                self.event_loop.schedule_event(
                    self.event_loop.time_us, EventType.COMPLETE_TO_HOST, req
                )
                # maybe trigger cache flush if threshold met
                if self.cache.ready_to_flush(threshold_bytes=64 * 1024):
                    self.event_loop.schedule_event(
                        self.event_loop.time_us, EventType.CACHE_FLUSH, None
                    )
            elif req.type == RequestType.READ:
                # simple read path: if mapping in cache, return quickly; else schedule NAND read
                if self.cache.has_pending_write(req.lba):
                    # Serve read from cache immediately
                    self.event_loop.schedule_event(
                        self.event_loop.time_us, EventType.COMPLETE_TO_HOST, req
                    )
                elif self.pending_write_in_ncq(req.lba):
                    # Delay this read: do not start NAND read yet
                    continue
                else:
                    phys = self.ftl.lookup(req.lba)
                    if phys is None:
                        self.event_loop.schedule_event(
                            self.event_loop.time_us, EventType.COMPLETE_TO_HOST, req
                        )
                    else:
                        self.event_loop.schedule_event(
                            self.event_loop.time_us + self.read_us,
                            EventType.COMPLETE_TO_HOST,
                            req,
                        )
