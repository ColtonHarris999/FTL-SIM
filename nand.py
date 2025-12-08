from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional

from event import Event, EventLoop
from request import TraceEvent


@dataclass(frozen=True)
class NANDGeometry:
    num_channels: int = 2
    num_dies_per_channel: int = 2
    num_planes_per_die: int = 1
    blocks_per_plane: int = 1024
    pages_per_block: int = 64
    page_size: int = 16 * 1024


@dataclass(frozen=True)
class NANDTimings:
    read_us: int = 50
    program_us: int = 200
    erase_us: int = 1500
    dma_us: int = 5


@dataclass(frozen=True)
class PhysicalAddress:
    channel: int
    die: int
    plane: int
    block: int
    page: int


class NANDTransactionType(Enum):
    READ = auto()
    WRITE = auto()
    FLUSH = auto()
    ERASE = auto()


@dataclass
class NANDTransaction:
    type: NANDTransactionType
    pa: PhysicalAddress
    callback: Optional[Callable[[NANDTransaction], None]] = None
    payload: Optional[object] = None
    trace: dict[TraceEvent, float] = field(default_factory=dict)


# TODO: allow heterogeneous geometry?
class NAND:
    def __init__(
        self,
        event_loop: EventLoop,
        geometry: NANDGeometry,
        timings: NANDTimings,
    ) -> None:
        self.event_loop: EventLoop = event_loop

        self.geometry: NANDGeometry = geometry
        self.timings: NANDTimings = timings

        # Statistics
        self.num_reads: int = 0
        self.num_writes: int = 0

        self.channels: list[Channel] = [
            Channel(event_loop, geometry, timings) for _ in range(geometry.num_channels)
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
    def __init__(
        self, event_loop: EventLoop, geometry: NANDGeometry, timings: NANDTimings
    ) -> None:
        self.event_loop = event_loop

        self.geometry = geometry
        self.timings = timings

        self.dma_queue: list[NANDTransaction] = []
        self.busy: bool = False

        self.dies_busy: list[bool] = [
            False for _ in range(geometry.num_dies_per_channel)
        ]

    def is_ready(self, physical_addr: PhysicalAddress) -> bool:
        return not self.dies_busy[physical_addr.die]

    def do_dma(self, transaction: NANDTransaction):
        transaction.trace[TraceEvent.DMA_QUEUED] = self.event_loop.time_us
        if self.busy:
            self.dma_queue.append(transaction)
        else:
            transaction.trace[TraceEvent.DMA_START] = self.event_loop.time_us
            self.busy = True
            self.event_loop.schedule_event(
                Event(
                    self.event_loop.time_us + self.timings.dma_us,
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
            next_transaction = self.dma_queue.pop(0)
            next_transaction.trace[TraceEvent.DMA_START] = self.event_loop.time_us

            self.event_loop.schedule_event(
                Event(
                    self.event_loop.time_us + self.timings.dma_us,
                    description="DMA_COMPLETE",
                    payload=next_transaction,
                    callback=self._handle_dma_complete,
                )
            )
        else:
            self.busy = False

        transaction.trace[TraceEvent.DMA_COMPLETE] = self.event_loop.time_us

        if transaction.type == NANDTransactionType.READ:
            self._read_transfer_done_callback(transaction)
        elif transaction.type == NANDTransactionType.WRITE:
            self._write_transfer_done_callback(transaction)

    # -------------------------------------------------------
    # Write flow
    # -------------------------------------------------------
    def write_page(self, transaction: NANDTransaction):
        assert self.is_ready(transaction.pa), "NAND die is busy"

        transaction.trace[TraceEvent.NAND_WRITE_START] = self.event_loop.time_us
        self.dies_busy[transaction.pa.die] = True

        # Queue DMA transfer on appropriate channel
        self.do_dma(transaction)

    def _write_transfer_done_callback(self, transaction: NANDTransaction):
        self.event_loop.schedule_event(
            Event(
                self.event_loop.time_us + self.timings.program_us,
                description="NAND_WRITE_COMPLETE",
                payload=transaction,
                callback=self._write_done_callback,
            )
        )

    def _write_done_callback(self, event: Event):
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        transaction.trace[TraceEvent.NAND_WRITE_COMPLETE] = self.event_loop.time_us
        self.dies_busy[transaction.pa.die] = False

        assert transaction.callback is not None
        transaction.callback(transaction)

    # -------------------------------------------------------
    # Read flow
    # -------------------------------------------------------
    def read_page(self, transaction: NANDTransaction):
        assert self.is_ready(transaction.pa), "NAND die is busy"

        transaction.trace[TraceEvent.NAND_READ_START] = self.event_loop.time_us
        self.dies_busy[transaction.pa.die] = True

        self.event_loop.schedule_event(
            Event(
                self.event_loop.time_us + self.timings.read_us,
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
        self.dies_busy[transaction.pa.die] = False
        transaction.trace[TraceEvent.NAND_READ_COMPLETE] = self.event_loop.time_us

        assert transaction.callback is not None
        transaction.callback(transaction)
