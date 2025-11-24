from enum import Enum, auto
import heapq
import itertools


class EventType(Enum):
    ARRIVAL = auto()
    NCQ_SCHEDULE = auto()
    DMA_COMPLETE = auto()
    NAND_READ_COMPLETE = auto()
    NAND_PROGRAM_COMPLETE = auto()

    CACHE_FLUSH = auto()
    COMPLETE_TO_HOST = auto()


class EventLoop:
    """Handles event scheduling and dispatching for the SSD simulator."""

    def __init__(self, dispatch_callback=None):
        self.time_us = 0
        self._ev_heap = []
        self.seq = itertools.count()
        self.dispatch_callback = dispatch_callback

    def schedule_event(self, time_us: int, ev_type: EventType, payload=None):
        print(f"Scheduling event {ev_type} at {time_us} us")
        heapq.heappush(self._ev_heap, (time_us, next(self.seq), ev_type, payload))

    def run(self, until_us: int = None):
        while self._ev_heap:
            time_us, _, ev_type, payload = heapq.heappop(self._ev_heap)
            if until_us is not None and time_us > until_us:
                break
            self.time_us = time_us
            self.dispatch_callback(ev_type, payload)
