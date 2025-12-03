from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from typing import Optional

    from nand import PhysicalAddress


class RequestType(Enum):
    READ = auto()
    WRITE = auto()
    FLUSH = auto()


class RequestStatus(Enum):
    READY = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()


class TraceEvent(Enum):
    READY = auto()
    ARRIVAL = auto()
    START = auto()
    COMPLETION = auto()

    CACHE_READ_START = auto()
    CACHE_READ_COMPLETE = auto()
    CACHE_WRITE_START = auto()
    CACHE_WRITE_COMPLETE = auto()

    NAND_READ_START = auto()
    NAND_READ_COMPLETE = auto()
    NAND_WRITE_START = auto()
    NAND_WRITE_COMPLETE = auto()


class Request:
    """Represents an I/O request"""

    _id_counter = 0

    def __init__(self, req_type: RequestType, lba: int, ready_time: float = 0.0):
        # Assign unique ID
        self.id = Request._id_counter
        Request._id_counter += 1

        # Request attributes
        self.type = req_type
        self.status = RequestStatus.READY
        # self.fua = False  # TODO: implement Force Unit Access flag
        self.lba = lba
        self.physical_addr: Optional[PhysicalAddress] = None
        self.ready_time: float = ready_time
        self.trace: dict[TraceEvent, float] = {TraceEvent.READY: ready_time}
        self.callback: Optional[Callable[[Request], None]] = None

    def __str__(self) -> str:
        return f"Req[{self.id}, {self.type.name} #{self.lba}]"

    def trace_str(self) -> str:
        return "  →  ".join(
            f"{event.name} @ {time} us" for event, time in self.trace.items()
        )

    def get_response_time(self):
        return self.trace[TraceEvent.COMPLETION] - self.trace[TraceEvent.ARRIVAL]
