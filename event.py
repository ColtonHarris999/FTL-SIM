from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass(order=True)  # needs to be orderable for heapq
class Event:
    time_us: float
    callback: Callable[[Event], None] = field(compare=False)
    seq: Optional[int] = field(compare=True, default=None)
    canceled: bool = field(compare=False, default=False)
    description: str = field(compare=False, default="")
    payload: Optional[object] = field(compare=False, default=None)


class EventLoop:
    def __init__(
        self,
        timestep_handler: Optional[Callable[[Event], None]] = None,
    ) -> None:
        self.time_us: float = 0
        self._ev_heap: List[Event] = []
        self._seq: itertools.count[int] = itertools.count()
        self.handlers: dict[EventType, Callable[[Event], None]] = {}
        self.timestep_handler: Optional[Callable[[Event], None]] = timestep_handler

    def register_handler(
        self, ev_type: EventType, handler: Callable[[Event], None]
    ) -> None:
        if ev_type in self.handlers:
            raise Exception(f"Handler already registered for {ev_type}")
        self.handlers[ev_type] = handler

    def schedule_event(self, event: Event) -> None:
        event.seq = next(self._seq)
        heapq.heappush(self._ev_heap, event)
        print(
            f'+ Scheduled "{event.description}" (seq={event.seq}) at t={event.time_us} us'
        )

    def cancel_event(self, event: Event) -> None:
        event.canceled = True
        print(
            f'- Canceled "{event.description}" (seq={event.seq}) scheduled at t={event.time_us} us'
        )

    def run(self, until_us: Optional[float] = None) -> None:
        while self._ev_heap:
            event = heapq.heappop(self._ev_heap)
            if until_us is not None and event.time_us > until_us:
                # Stop but keep the event in the heap
                heapq.heappush(self._ev_heap, event)
                break

            if event.canceled:
                continue

            print(50 * "-")
            print(
                f"t={event.time_us} us: Dispatching {event.description} (seq={event.seq}) with payload={event.payload}"
            )

            self.time_us = event.time_us

            event.callback(event)
            if self.timestep_handler:
                self.timestep_handler(event)
