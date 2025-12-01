from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, List, Optional


class EventType(Enum):
    REQUEST_ARRIVAL = auto()
    REQUEST_COMPLETE = auto()

    DMA_COMPLETE = auto()

    NAND_READ_COMPLETE = auto()
    NAND_WRITE_COMPLETE = auto()

    CACHE_READ_COMPLETE = auto()
    CACHE_WRITE_COMPLETE = auto()
    CACHE_FLUSH_START = auto()
    CACHE_FLUSH_COMPLETE = auto()

    FRONTEND_SCHEDULE = auto()
    NAND_SCHEDULE = auto()


@dataclass(order=True)  # needs to be orderable for heapq
class Event:
    time_us: float
    ev_type: EventType = field(compare=False)
    seq: Optional[int] = field(compare=True, default=None)
    payload: Optional[object] = field(compare=False, default=None)
    canceled: bool = field(compare=False, default=False)
    dispatched: bool = field(compare=False, default=False)


class EventLoop:
    def __init__(self) -> None:
        self.time_us: float = 0
        self._ev_heap: List[Event] = []
        self._seq: itertools.count[int] = itertools.count()
        self.handlers: dict[EventType, Callable[[Event], None]] = {}

    def register_handler(
        self, ev_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        if ev_type in self.handlers:
            raise Exception(f"Handler already registered for {ev_type}")
        self.handlers[ev_type] = handler

    def schedule_event(self, event: Event) -> None:
        # Assign a sequence number if not already set
        if event.seq is None:
            event.seq = next(self._seq)
        heapq.heappush(self._ev_heap, event)
        print(f"Scheduled event {event.ev_type} at {event.time_us} us")

    def cancel_event(self, event: Event) -> None:
        event.canceled = True
        print(f"Canceled event {event.ev_type} scheduled at {event.time_us} us")

    def run(self, until_us: Optional[float] = None) -> None:
        while self._ev_heap:
            event = heapq.heappop(self._ev_heap)
            if until_us is not None and event.time_us > until_us:
                # Stop but keep the event in the heap
                heapq.heappush(self._ev_heap, event)
                break

            if event.canceled:
                continue  # Skip canceled events

            print(
                f"========= T={event.time_us}: Dispatching {event.ev_type} for {event.payload} ========="
            )
            self.time_us = event.time_us
            event.dispatched = True
            handler = self.handlers.get(event.ev_type)
            if handler:
                handler(event)
