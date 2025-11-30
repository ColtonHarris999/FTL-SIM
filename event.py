from enum import Enum, auto
import heapq
import itertools
from typing import Optional


class EventType(Enum):
    ARRIVAL = auto()

    DMA_COMPLETE = auto()

    NAND_READ_COMPLETE = auto()
    NAND_WRITE_COMPLETE = auto()

    CACHE_READ_COMPLETE = auto()
    CACHE_WRITE_COMPLETE = auto()

    CACHE_FLUSH_START = auto()
    CACHE_FLUSH_COMPLETE = auto()

    REQUEST_COMPLETE = auto()


class EventLoop:
    """Handles event scheduling and dispatching for the SSD simulator."""

    def __init__(self, dispatch_callback=None):
        self.time_us = 0
        self._ev_heap = []
        self.seq = itertools.count()
        self.dispatch_callback = dispatch_callback

    def schedule_event(
        self, time_us: float, ev_type: EventType, payload=None, callback=None
    ):
        print(f"Scheduling event {ev_type} at {time_us} us")
        heapq.heappush(
            self._ev_heap, (time_us, next(self.seq), ev_type, payload, callback)
        )

    def run(self, until_us: Optional[int] = None):
        while self._ev_heap:
            time_us, _, ev_type, payload, callback = heapq.heappop(self._ev_heap)
            if until_us is not None and time_us > until_us:
                break
            print(
                f"========= T={time_us}: Dispatching {ev_type} for {payload} ========="
            )
            self.time_us = time_us
            if callback:
                callback(ev_type, payload)
            elif self.dispatch_callback:
                self.dispatch_callback(ev_type, payload)
