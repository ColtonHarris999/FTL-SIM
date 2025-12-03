from abc import ABC, abstractmethod
from typing import List

from event import Event, EventLoop
from nand import NAND, NANDTransaction, NANDTransactionType


class NANDScheduler:
    def submit(self, transaction: NANDTransaction) -> None: ...
    def try_dispatch(self) -> None: ...


class MockScheduler(NANDScheduler):
    def __init__(self, event_loop: EventLoop, nand: NAND) -> None:
        self.event_loop: EventLoop = event_loop
        self.nand: NAND = nand

        self.queue: List[NANDTransaction] = []

        self.num_reads: int = 0
        self.num_writes: int = 0

    def submit(self, transaction: NANDTransaction) -> None:
        print(f"! Submitting {transaction} to NAND scheduler")
        self.queue.append(transaction)

    def try_dispatch(self) -> None:
        print("Running NAND scheduler...")
        if not self.queue:
            return

        transaction: NANDTransaction = self.queue[0]
        if self.nand.is_ready(transaction.pa):
            print(f"! Dispatching {transaction} to NAND")
            self.queue.pop(0)
            transaction.start_time = self.event_loop.time_us
            match transaction.type:
                case NANDTransactionType.WRITE:
                    self.nand.write_page(transaction)
                case NANDTransactionType.READ:
                    self.nand.read_page(transaction)
                case _:
                    raise NotImplementedError
        else:
            print(f"! NAND not ready for {transaction}")

    def _handle_nand_read_complete(self, event: Event) -> None:
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        print(f"! NAND read complete for {transaction}")

        assert transaction.callback is not None
        transaction.callback(transaction)

    def _handle_nand_write_complete(self, event: Event) -> None:
        assert isinstance(event.payload, NANDTransaction)
        transaction: NANDTransaction = event.payload

        print(f"! NAND write complete for {transaction}")

        assert transaction.callback is not None
        transaction.callback(transaction)


# class NANDScheduler(ABC):
#     """
#     Scheduler interface

#     Schedulers manage a queue of tasks and decide which to issue next based on
#     their scheduling policy.
#     """

#     def __init__(self, event_loop: EventLoop, nand: NAND):
#         """
#         Create a new Scheduler instance.
#         """
#         self.event_loop = event_loop
#         self.nand = nand
#         self.queue: List[NANDTransaction] = []
#         self.outstanding: set[NANDTransaction] = set()
#         self.done_tags: set[int] = set()
#         self.metrics = SchedulerMetrics()

#     @abstractmethod
#     def callback_task_complete(self, task: NANDTransaction):
#         """
#         Called by NAND when a task is complete.
#         Must call _record_metrics to log task metrics.
#         """
#         pass

#     @abstractmethod
#     def schedule(self):
#         """Schedule next task from the queue according to the policy."""
#         pass

#     def enqueue(self, task: NANDTransaction):
#         """Add a task to the scheduler's queue."""
#         self.queue.append(task)

#     def dequeue(self, task: NANDTransaction):
#         """Remove a task from the scheduler's queue."""
#         self.queue.remove(task)

#     def done(self) -> set[int]:
#         """Returns the set of all tags done since last call."""
#         done = self.done_tags
#         self.done_tags = set()
#         return done

#     def _dispatch(self, task: NANDTransaction):
#         task.in_progress = True
#         task.call_back = self.callback_task_complete
#         self.nand.commit(task, self.callback_task_complete)

#     def _record_metrics(self, task: NANDTransaction):
#         self.metrics.record_task_scheduled


# class FIFOScheduler(NANDScheduler):
#     """
#     Naive FIFO scheduler
#     Schedules the oldest task(s) in the queue if NAND resources are available
#     and all tasks in the previouse tag are complete.
#     """

#     def __init__(self, event_loop: EventLoop, nand: NAND):
#         super().__init__(event_loop, nand)
#         self.cur_tag = None

#     def callback_task_complete(self, task):
#         """
#         Called by NAND when a task is complete.
#         Updates the current tag to be None once all tasks of the current tag are done.
#         """
#         self.outstanding.remove(task)
#         if not self.outstanding and self.queue[0].tag != task.tag:
#             self.done_tags.add(task.tag)
#             self.cur_tag = None

#     def schedule(self):
#         """
#         Schedule tasks in FIFO order, ensuring no resource conflicts and tag ordering.
#         Tasks are only dispatched if they belong to the current tag or if no tag is active.
#         Tasks are parallelized across different channels/dies/planes until a confict occurs.
#         """
#         if not self.queue:
#             return
#         task = self.queue[0]
#         if self.cur_tag is None:
#             self.cur_tag = task.tag
#         while self.queue and self.queue[0].tag == self.cur_tag:
#             next_task = self.queue[0]
#             if self.nand.commitable(next_task):
#                 self._dispatch(next_task)
#                 self.dequeue(task)
#             else:
#                 break  # wait for task to be commitable


# class NOOPScheduler(NANDScheduler):
#     """
#     NOOP scheduler
#     Schedules all non-hazard tasks that can be scheudled in FIFO order.
#     """

#     def __init__(self, event_loop: EventLoop, nand: NAND):
#         super().__init__(event_loop, nand)
#         self.cur_tag = None

#     def callback_task_complete(self, task):
#         """
#         Called by NAND when a task is complete.
#         Updates the current tag to be None once all tasks of the current tag are done.
#         """
#         self.outstanding.remove(task)
#         if not self.outstanding and self.queue[0].tag != task.tag:
#             self.done_tags.add(task.tag)
#             self.cur_tag = None
#             self.dequeue(task)

#     def schedule(self):
#         """
#         Schedule tasks in FIFO order, but allowing out-of-order execution by skipping
#         tasks that cannot be scheduled due to resource conflicts or RAW hazards.
#         """
#         # Identify ongoing writes
#         pending_write_lbas = set()

#         for task in list(self.queue):
#             if task.in_progress:
#                 if task.task_type == NANDTransactionType.WRITE:
#                     pending_write_lbas.add(task.request.lba)
#                 continue
#             # If read check for hazards
#             # If write add to pending set
#             if task.task_type == NANDTransactionType.READ:
#                 if task.request.lba in pending_write_lbas:
#                     continue  # RAW hazard: do not insert this task yet
#             else:
#                 pending_write_lbas.add(task.request.lba)  # Add write to pending set
#             # Attempt to dispatch
#             if self.nand.commitable(task):
#                 self._dispatch(task)
#             else:
#                 continue  # NAND is busy, move on to next task


# class PAQScheduler(NANDScheduler):
#     """
#     Physical Address Queue (PAQ) scheduler.

#     - Issues tasks out-of-order to maximize channel/die/plane parallelism.
#     - Avoids RAW hazards: reads cannot pass earlier writes to the same LBA.
#     """

#     def __init__(self, event_loop: EventLoop, nand: NAND):
#         # Call parent constructor
#         super().__init__(event_loop, nand)

#         self.num_channels = nand.num_channels
#         self.num_packages = nand.num_packages

#         self.clump_table = self.clump_table = [
#             [[] for _ in range(self.num_packages)] for _ in range(self.num_channels)
#         ]

#     def callback_task_complete(self, task):
#         """
#         Called by NAND when a task is complete.
#         """
#         self.dequeue(task)
#         task.in_progress = False

#     def _alogorithm1(self, task: NANDTransaction):
#         """
#         Insert task into its clump-table queue based purely on its PPA.
#         (From PAQ paper)
#         """
#         ppa = task.phys_addr  # The physical page/block/plane address
#         ch = ppa.ch  # NAND Channel
#         pk = ppa.pk  # NAND Package (way)
#         # Insert into clump-table
#         self.clump_table[ch][pk].append(task)  # List of tasks for (channel, way)

#     def _algorithm2(self):
#         """
#         Select ready tasks from the clump_table and dispatch them using PAQ rules.
#         (From PAQ paper)
#         """
#         for ch in range(self.num_channels):
#             for pk in range(self.num_packages):
#                 # Get tasks to same channel & package
#                 bucket = self.clump_table[ch][pk]

#                 # Skip if no tasks or channel & package busy
#                 if not bucket or self.nand.is_busy(ch, pk):
#                     continue

#                 # Get oldest task in bucket
#                 base_task = bucket.pop(0)
#                 self.dequeue(base_task)

#                 # Attempt multi-plane packing
#                 assoc_tasks = []
#                 assoc_tasks.append(base_task)
#                 for t in list(bucket):
#                     p1, p2 = base_task.phys_addr, t.phys_addr
#                     if (
#                         p1.die == p2.die
#                         and p1.plane == p2.plane
#                         and p1.task_type == t.task_type
#                     ):
#                         assoc_tasks.append(t)
#                         bucket.remove(t)

#                 # Dispatch to NAND
#                 self._dispatch_packed(ch, pk, assoc_tasks)

#                 # Dispatch tasks
#                 for t in assoc_tasks:
#                     self._dispatch(t)

#     # ---- PAQ-style scheduling -----------------------------------------
#     def schedule(self):
#         """
#         Scheuldes tasks using PAQ algorithm:
#         1. Build clump table from non-in-progress and RAW hazard-free tasks.
#         2. Dispatch tasks from clump table using multi-plane packing.
#         """

#         # Identify ongoing writes
#         pending_write_lbas = set()

#         # Create clump table from non-in-progress and RAW hazard tasks
#         for task in list(self.queue):
#             if task.in_progress:
#                 if task.task_type == NANDTransactionType.WRITE:
#                     pending_write_lbas.add(task.request.lba)
#                 continue  # skip in-progress tasks

#             if task.task_type == NANDTransactionType.READ:
#                 if task.request.lba in pending_write_lbas:
#                     continue  # RAW hazard: do not insert this task yet
#             else:
#                 pending_write_lbas.add(task.request.lba)  # Add write to pending set

#             # safe to insert
#             self.algorithm1(task)

#         # Dispatch tasks from clump table
#         self._alogorithm2()
