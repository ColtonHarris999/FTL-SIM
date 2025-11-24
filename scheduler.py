from abc import ABC, abstractmethod
from collections import deque
from enum import Enum
from typing import List

from request import Request, RequestStatus, RequestType


class ActionType(Enum):
    READ = "read"
    WRITE = "write"
    FORWARD = "forward"


class Scheduler(ABC):
    """Scheduler interface"""

    latency: float = 0.0  # time taken to make scheduling decision

    @abstractmethod
    def schedule(self, ncq: List[Request], nand_ready: bool) -> List[Request]:
        pass


class FIFOScheduler(Scheduler):
    """
    Naive FIFO scheduler
    Always schedules the oldest request in the queue
    """

    latency: float = 0.1  # us

    def schedule(self, ncq: List[Request], nand_ready: bool) -> List[Request]:
        req = ncq[0]
        if nand_ready and req.status == RequestStatus.READY:
            print(f"FIFOScheduler: scheduling {req}")
            return [req]
        return []


class NaiveReadScheduler(Scheduler):
    """
    Naive read scheduler
    Similar to FIFOScheduler but always prioritizes read requests
    """

    latency: float = 0.5  # us

    def schedule(self, ncq: List[Request], nand_ready: bool) -> List[Request]:
        if nand_ready:
            # try to find read with no RAW conflicts
            for req in ncq:
                if (
                    req.status == RequestStatus.READY
                    and req.type == RequestType.READ
                    and all(
                        write.logical_addr != req.logical_addr
                        for write in ncq[: ncq.index(req)]
                        if write.type == RequestType.WRITE
                    )
                ):
                    return [req]

            # no read found, schedule oldest write instead
            for req in ncq:
                if req.status == RequestStatus.READY and req.type == RequestType.WRITE:
                    return [req]

        return []


# class CoalescingReadScheduler(Scheduler):
#     """
#     Coalescing read scheduler
#     Similar to FIFOScheduler but always prioritizes read requests
#     """

#     def __init__(self, window_size: int) -> None:
#         self.window_size = window_size

#     def schedule(self, ncq: List[Request]) -> List[Action]:
#         # Greedy batching: scan available requests for coalescable ones
#         last_addr = first_req.logical_addr

#         for req in ncq[: self.window_size]::
#             # Check if this request can join the batch

#             if can_coalesce:
#                 batch.append(req)  # EXITS queue - added to batch
#                 last_addr = req.logical_addr
#             else:
#                 # Put back in queue - doesn't meet criteria
#                 self.read_queue.append(req)

#         return batch


# old stuff -----------------


# class RequestScheduler:
#     """Schedules and coalesces requests"""

#     def __init__(self, policy="fifo", coalesce_window_us=10, max_batch_size=32):
#         self.policy = policy  # "fifo", "locality", "deadline"
#         self.coalesce_window_us = coalesce_window_us
#         self.max_batch_size = max_batch_size
#         self.read_queue = deque()
#         self.write_queue = deque()

#     def add_request(self, request):
#         """Add request to appropriate queue"""
#         if request.type == RequestType.READ:
#             self.read_queue.append(request)
#         else:
#             self.write_queue.append(request)

#     def get_next_batch(self, current_time):
#         """
#         Get next batch of requests to process.
#         Requests EXIT the queue when:
#         1. They are selected for the current batch (immediate removal)
#         2. Batch is finalized and returned

#         A request stays in queue if:
#         1. Not yet considered (still behind in queue)
#         2. Considered but doesn't meet coalescing criteria (put back temporarily)
#         """
#         # Prioritize reads over writes (typical SSD behavior)
#         if self.read_queue:
#             return self._get_coalesced_reads(current_time)
#         elif self.write_queue:
#             return self._get_coalesced_writes(current_time)
#         return []

#     def _get_coalesced_reads(self, current_time):
#         """
#         Coalesce sequential/nearby reads using a greedy batching approach.
#         Only considers requests that have actually arrived (arrival_time <= current_time).
#         """
#         if not self.read_queue:
#             return []

#         # Only look at requests that have arrived
#         available = [req for req in self.read_queue if req.arrival_time <= current_time]
#         if not available:
#             return []

#         # Remove available requests from queue temporarily
#         self.read_queue = deque(
#             [req for req in self.read_queue if req.arrival_time > current_time]
#         )

#         batch = []
#         first_req = available.pop(0)  # EXITS queue here
#         batch.append(first_req)

#         if self.policy == "fifo":
#             # Put non-selected requests back
#             self.read_queue.extend(available)
#             return batch

#         elif self.policy == "locality":
#             # Greedy batching: scan available requests for coalescable ones
#             last_addr = first_req.logical_addr

#             for req in available:
#                 # Check if this request can join the batch
#                 time_diff = req.arrival_time - first_req.arrival_time
#                 addr_diff = abs(req.logical_addr - last_addr)

#                 can_coalesce = (
#                     time_diff < self.coalesce_window_us
#                     and addr_diff <= 8
#                     and len(batch) < self.max_batch_size
#                 )

#                 if can_coalesce:
#                     batch.append(req)  # EXITS queue - added to batch
#                     last_addr = req.logical_addr
#                 else:
#                     # Put back in queue - doesn't meet criteria
#                     self.read_queue.append(req)

#         return batch

#     def _get_coalesced_writes(self, current_time):
#         """
#         Coalesce sequential/nearby writes using a greedy batching approach.
#         Only considers requests that have actually arrived (arrival_time <= current_time).
#         """
#         if not self.write_queue:
#             return []

#         # Only look at requests that have arrived
#         available = [
#             req for req in self.write_queue if req.arrival_time <= current_time
#         ]
#         if not available:
#             return []

#         # Remove available requests from queue temporarily
#         self.write_queue = deque(
#             [req for req in self.write_queue if req.arrival_time > current_time]
#         )

#         batch = []
#         first_req = available.pop(0)  # EXITS queue here
#         batch.append(first_req)

#         if self.policy == "fifo":
#             self.write_queue.extend(available)
#             return batch

#         elif self.policy == "locality":
#             last_addr = first_req.logical_addr

#             for req in available:
#                 time_diff = req.arrival_time - first_req.arrival_time
#                 addr_diff = abs(req.logical_addr - last_addr)

#                 can_coalesce = (
#                     time_diff < self.coalesce_window_us
#                     and addr_diff <= 8
#                     and len(batch) < self.max_batch_size
#                 )

#                 if can_coalesce:
#                     batch.append(req)  # EXITS queue - added to batch
#                     last_addr = req.logical_addr
#                 else:
#                     # Put back in queue - doesn't meet criteria
#                     self.write_queue.append(req)

#         return batch

#     def has_requests(self):
#         return len(self.read_queue) > 0 or len(self.write_queue) > 0

#     def queue_depth(self):
#         return len(self.read_queue) + len(self.write_queue)
