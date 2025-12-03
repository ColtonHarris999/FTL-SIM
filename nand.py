from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from event import EventLoop, EventType
from request import Request, RequestType


@dataclass(frozen=True)
class PhysicalAddress:
    channel: int
    die: int
    plane: int
    block: int
    page: int


# TODO: merge with NANDTransaction
# @dataclass
# class Task:
#     task_type: NANDTransactionType
#     phys_adr: PhysicalAddress
#     request: Request
#     priority: int
#     in_progress: bool = False
#     issue_time: float = 0.0  # When task is given to scheduler
#     start_time: float = 0.0  # When NAND starts processing task
#     call_back = None


class NANDTransactionType(Enum):
    READ = auto()
    WRITE = auto()
    FLUSH = auto()
    # ERASE = auto()
    # GC = auto()


@dataclass
class NANDTransaction:
    type: NANDTransactionType
    pa: PhysicalAddress
    # lpa: int  # TODO: check if needed
    # priority: int = 0
    start_time: float = 0
    callback: Optional[Callable[[NANDTransaction], None]] = None
    payload: Optional[object] = None


# TODO: allow heterogeneous geometry?
class NAND:
    """Represents a NAND flash device"""

    def __init__(
        self,
        event_loop: EventLoop,
        num_channels: int = 2,
        num_dies_per_channel: int = 2,
        num_planes_per_die: int = 1,
        blocks_per_plane: int = 1024,
        pages_per_block: int = 64,
        page_size: int = 16 * 1024,
        read_us: int = 50,
        program_us: int = 200,
        dma_us: int = 5,
    ) -> None:
        self.event_loop: EventLoop = event_loop

        # NAND geometry
        self.num_channels: int = num_channels
        self.num_dies_per_channel: int = num_dies_per_channel
        self.num_planes_per_die: int = num_planes_per_die
        self.blocks_per_plane: int = blocks_per_plane
        self.pages_per_block: int = pages_per_block
        self.page_size: int = page_size

        # Timing parameters
        self.read_us: int = read_us
        self.program_us: int = program_us

        # Statistics
        self.num_reads: int = 0
        self.num_writes: int = 0

        # Actual NAND structure
        self.channels: list[Channel] = [
            Channel(event_loop, dma_us) for _ in range(num_channels)
        ]
        self.dies: list[Plane] = [
            Plane(blocks_per_plane) for _ in range(num_channels * num_dies_per_channel)
        ]

    def is_ready(self, physical_addr: PhysicalAddress) -> bool:
        return not self.dies[physical_addr.die].busy

    def write_page(self, req: Request):
        if not req.physical_addr:
            raise Exception("Request has no physical address assigned")
        if not self.is_ready(req.physical_addr):
            raise Exception(f"NAND die {req.physical_addr.die} is busy")

        # Queue DMA transfer on appropriate channel
        channel_idx = req.physical_addr.channel
        self.channels[channel_idx].do_dma(req)

    def _write_done_callback(self, req: Request):
        self.event_loop.schedule_event(
            self.event_loop.time_us,
            EventType.REQUEST_COMPLETE,
            req,
        )

    def read_page(self, req: Request):
        # 1. Schedule NAND read complete after read_us
        # 2. On NAND read complete, schedule DMA complete after dma_us
        # 3. On DMA complete, invoke req_complete event
        # self.dies[req.physical_addr.die].busy = True

        self.event_loop.schedule_event(
            self.event_loop.time_us + self.read_us,
            EventType.NAND_READ_COMPLETE,
            req,
        )

    def _read_done_callback(self, req: Request):
        self.event_loop.schedule_event(
            self.event_loop.time_us,
            EventType.REQUEST_COMPLETE,
            req,
        )


class Plane:
    def __init__(self, blocks_per_plane=1024):
        self.busy: bool = False
        self.blocks: list[Block] = [Block() for i in range(blocks_per_plane)]
        self.next_free_block: int = 0


class PageState(Enum):
    FREE = "free"
    VALID = "valid"
    INVALID = "invalid"


# What data is actually required?
# Write pages sequentially in each block:
# - next free page index per block
# - erase count per block
# - inverse FTL mapping if we implement GC
class Block:
    def __init__(self, pages_per_block=64):
        self.num_pages = pages_per_block
        self.num_free = pages_per_block
        self.num_invalid = 0
        self.erase_count = 0

    def erase(self):
        self.num_free = self.num_pages
        self.num_invalid = 0
        self.erase_count += 1


class Channel:
    """Represents a single channel in the SSD"""

    def __init__(self, event_loop: EventLoop, dma_us: int):
        self.event_loop = event_loop

        self.dma_queue: list[Request] = []
        self.busy: bool = False

        self.dma_us = dma_us

    def do_dma(self, req: Request):
        if self.busy:
            self.dma_queue.append(req)
        else:
            self.busy = True
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.dma_us,
                EventType.DMA_COMPLETE,
                req,
                callback=self._handle_dma_complete,
            )

    def _handle_dma_complete(self, req: Request):
        """
        Handle the completion of a DMA operation for the given request.
        """
        print(f"DMA complete for {req}")
        if req.type == RequestType.READ:
            # read operation is done after DMA transfer
            self.event_loop.schedule_event(
                self.event_loop.time_us,
                EventType.REQUEST_COMPLETE,
                req,
            )
        elif req.type == RequestType.WRITE:
            # TODO call NAND program callback
            pass

        # Start next DMA if any
        if self.dma_queue:
            next_req = self.dma_queue.pop(0)
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.dma_us,
                EventType.DMA_COMPLETE,
                next_req,
                callback=self._handle_dma_complete,
            )
        else:
            self.busy = False
