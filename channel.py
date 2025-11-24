from typing import List

from event import EventLoop, EventType
from request import Request


class Channel:
    """Represents a single channel in the SSD"""

    def __init__(self, event_loop: "EventLoop"):
        self.event_loop = event_loop
        self.dma_queue: List[Request] = []
        self.busy: bool = False

        self.dma_us = 5

    def do_dma(self, req: Request):
        if self.busy:
            self.dma_queue.append(req)
        else:
            self.busy = True
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.dma_us,
                EventType.DMA_COMPLETE,
                req,
            )

    def complete(self):
        if self.dma_queue:
            next_req = self.dma_queue.pop(0)
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.dma_us,
                EventType.DMA_COMPLETE,
                next_req,
            )
        else:
            self.busy = False
