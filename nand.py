from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Optional

from event import Event, EventLoop


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

        self.channels: list[Channel] = [
            Channel(event_loop, num_dies_per_channel) for _ in range(num_channels)
        ]

    def is_ready(self, physical_addr: PhysicalAddress) -> bool:
        return self.channels[physical_addr.channel].is_ready(physical_addr)

    def read_page(self, transaction: NANDTransaction):
        self.num_reads += 1
        self.channels[transaction.pa.channel].read_page(transaction)

    def write_page(self, transaction: NANDTransaction):
        self.num_writes += 1
        self.channels[transaction.pa.channel].write_page(transaction)


class Channel:
    """Represents a single channel in the SSD"""

    def __init__(self, event_loop: EventLoop, num_dies_per_channel: int = 2) -> None:
        self.event_loop = event_loop

        self.dma_queue: list[NANDTransaction] = []
        self.busy: bool = False

        self.dies: list[Die] = [Die() for _ in range(num_dies_per_channel)]

        self.read_us: int = 50
        self.program_us: int = 200
        self.dma_us: int = 5

    def is_ready(self, physical_addr: PhysicalAddress) -> bool:
        return not self.dies[physical_addr.die].busy

    def do_dma(self, transaction: NANDTransaction):
        if self.busy:
            self.dma_queue.append(transaction)
        else:
            self.busy = True
            self.event_loop.schedule_event(
                Event(
                    self.event_loop.time_us + self.dma_us,
                    description="DMA_COMPLETE",
                    payload=transaction,
                    callback=self._handle_dma_complete,
                )
            )

    def _handle_dma_complete(self, event: Event):
        """
        Handle the completion of a DMA operation for the given request.
        """
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        # Start next DMA if any
        if self.dma_queue:
            next_req = self.dma_queue.pop(0)
            self.event_loop.schedule_event(
                Event(
                    self.event_loop.time_us + self.dma_us,
                    description="DMA_COMPLETE",
                    payload=next_req,
                    callback=self._handle_dma_complete,
                )
            )
        else:
            self.busy = False

        if transaction.type == NANDTransactionType.READ:
            self._read_transfer_done_callback(transaction)
        elif transaction.type == NANDTransactionType.WRITE:
            self._write_transfer_done_callback(transaction)

    # -------------------------------------------------------
    # Write flow
    # -------------------------------------------------------
    def write_page(self, transaction: NANDTransaction):
        assert self.is_ready(transaction.pa), "NAND die is busy"

        self.dies[transaction.pa.die].busy = True

        # Queue DMA transfer on appropriate channel
        self.do_dma(transaction)

    def _write_transfer_done_callback(self, transaction: NANDTransaction):
        self.event_loop.schedule_event(
            Event(
                self.event_loop.time_us + self.program_us,
                description="NAND_WRITE_COMPLETE",
                payload=transaction,
                callback=self._write_done_callback,
            )
        )

    def _write_done_callback(self, event: Event):
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        self.dies[transaction.pa.die].busy = False

        assert transaction.callback is not None
        transaction.callback(transaction)

    # -------------------------------------------------------
    # Read flow
    # -------------------------------------------------------
    def read_page(self, transaction: NANDTransaction):
        assert self.is_ready(transaction.pa), "NAND die is busy"
        self.dies[transaction.pa.die].busy = True

        self.event_loop.schedule_event(
            Event(
                self.event_loop.time_us + self.read_us,
                description="NAND_READ_COMPLETE",
                payload=transaction,
                callback=self._read_done_callback,
            )
        )

    def _read_done_callback(self, event: Event):
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        self.do_dma(transaction)

    def _read_transfer_done_callback(self, transaction: NANDTransaction):
        self.dies[transaction.pa.die].busy = False

        assert transaction.callback is not None
        transaction.callback(transaction)


class Die:
    def __init__(self):
        self.busy: bool = False


# -------------------------------------------------------
# Old stuff
# -------------------------------------------------------
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
