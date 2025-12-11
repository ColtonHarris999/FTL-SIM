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

    NCQ_QUEUED = auto()
    NCQ_DISPATCHED = auto()
    NCQ_COMPLETE = auto()

    BACKEND_QUEUED = auto()
    BACKEND_DISPATCHED = auto()
    # BACKEND_COMPLETE = auto()

    CACHE_READ_START = auto()
    CACHE_READ_COMPLETE = auto()
    CACHE_WRITE_START = auto()
    CACHE_WRITE_COMPLETE = auto()

    NAND_READ_START = auto()
    NAND_READ_COMPLETE = auto()
    NAND_WRITE_START = auto()
    NAND_WRITE_COMPLETE = auto()

    DMA_QUEUED = auto()
    DMA_START = auto()
    DMA_COMPLETE = auto()


class Request:
    _tag_counter = 0

    def __init__(
        self,
        req_type: RequestType,
        starting_lba: int,
        size: int = 1,
        ready_time: float = 0.0,
    ):
        # Assign unique ID
        self.tag = Request._tag_counter
        Request._tag_counter += 1

        # Request attributes
        self.type = req_type
        self.status = RequestStatus.READY
        # self.fua = False  # TODO: implement Force Unit Access flag

        self.starting_lba = starting_lba  # starting LBA
        self.size = size  # number of LBAs
        self.next_lba = starting_lba  # next LBA to process

        self.physical_addr: Optional[PhysicalAddress] = None
        self.ready_time: float = ready_time
        self.trace: dict[TraceEvent, float] = {TraceEvent.READY: ready_time}
        self.callback: Optional[Callable[[Request], None]] = None

    def __str__(self) -> str:
        return f"Req[{self.tag}, {self.type.name} #{self.starting_lba}, {self.physical_addr}]"

    def trace_str(self) -> str:
        return "  →  ".join(
            f"{event.name} @ {time} us" for event, time in self.trace.items()
        )

    def get_response_time(self):
        return self.trace[TraceEvent.NCQ_COMPLETE] - self.trace[TraceEvent.NCQ_QUEUED]
