from dataclasses import dataclass
from enum import Enum
import enum
from typing import List

from event import EventLoop, EventType
from request import Request, RequestType


@dataclass
class PhysicalAddress:
    channel: int
    die: int
    plane: int
    block: int
    page: int


class NANDTransactionType(enum.Enum):
    READ = enum.auto()
    WRITE = enum.auto()


@dataclass
class NANDTransaction:
    type: NANDTransactionType
    pa: PhysicalAddress
    completed_requests: list[Request]
    depends_on: "NANDTransaction | None" = None


# TODO allow heterogeneous geometry?
class NAND:
    """Represents a NAND flash device"""

    def __init__(
        self,
        event_loop: EventLoop,
        num_channels=2,
        num_dies_per_channel=2,
        num_planes_per_die=1,
        blocks_per_plane=1024,
        pages_per_block=64,
        page_size=16 * 1024,
        read_us=50,
        program_us=200,
        dma_us=5,
    ):
        self.event_loop = event_loop

        # NAND geometry
        self.num_channels = num_channels
        self.num_dies_per_channel = num_dies_per_channel
        self.num_planes_per_die = num_planes_per_die
        self.blocks_per_plane = blocks_per_plane
        self.pages_per_block = pages_per_block
        self.page_size = page_size

        # Timing parameters
        self.read_us = read_us
        self.program_us = program_us
        # self.dma_us = dma_us

        # Actual NAND structure
        self.channels: List[Channel] = [
            Channel(event_loop, dma_us) for _ in range(num_channels)
        ]
        self.dies = [Plane() for _ in range(num_channels * num_dies_per_channel)]

    def handle_event(self, ev_type, payload):
        match ev_type:
            case EventType.NAND_READ_COMPLETE:
                pass
            case EventType.NAND_WRITE_COMPLETE:
                pass
            case EventType.DMA_COMPLETE:
                pass
            case _:
                raise NotImplementedError

    def is_ready(self, physical_addr: PhysicalAddress) -> bool:
        return not self.dies[physical_addr.die].busy

    def write_page(self, req: Request):
        if not req.physical_addr:
            raise Exception("Request has no physical address assigned")
        if not self.is_ready(req.physical_addr):
            raise Exception(f"NAND die {req.physical_addr.die} is busy")

        # Queue DMA transfer on appropriate channel
        channel_idx = req.physical_addr.channel
        self.channels[channel_idx].do_dma(req, callback=self._write_done_callback)

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
        self.dies[req.physical_addr.die].busy = True

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
        self.blocks: List[Block] = [Block() for i in range(blocks_per_plane)]
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

        self.dma_queue: List[Request] = []
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
