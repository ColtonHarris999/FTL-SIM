"""
SSD/Flash Simulator with Request Scheduling and Coalescing
Simulates concurrent requests with queuing, scheduling policies, and request coalescing
"""

import random

from nand import Block, PageState
from request import Request, RequestType
from scheduler import RequestScheduler


class TimingConfig:
    """Flash timing parameters (in microseconds)"""

    def __init__(self):
        # Typical SLC NAND timings
        self.page_read_us = 25
        self.page_write_us = 200
        self.block_erase_us = 1500

        # Controller overhead
        self.ftl_lookup_us = 1
        self.data_transfer_us = 10

        # Queue and scheduling overhead
        self.scheduling_overhead_us = 0.5

        self.variability = 0.1

    def get_read_latency(self):
        base = self.page_read_us + self.ftl_lookup_us + self.data_transfer_us
        return base * (1 + random.uniform(-self.variability, self.variability))

    def get_write_latency(self):
        base = self.page_write_us + self.ftl_lookup_us + self.data_transfer_us
        return base * (1 + random.uniform(-self.variability, self.variability))

    def get_erase_latency(self):
        base = self.block_erase_us
        return base * (1 + random.uniform(-self.variability, self.variability))


class FlashTranslationLayer:
    def __init__(self):
        self.mapping = {}

    def map(self, logical_addr, page):
        self.mapping[logical_addr] = page

    def get_physical(self, logical_addr):
        return self.mapping.get(logical_addr)


class SSDSimulator:
    """Main SSD simulator with request scheduling"""

    def __init__(
        self,
        num_blocks=100,
        pages_per_block=64,
        timing_config=None,
        scheduler_policy="locality",
    ):
        self.blocks = [Block(i, pages_per_block) for i in range(num_blocks)]
        self.ftl = FlashTranslationLayer()
        self.current_block_idx = 0
        self.timing = timing_config or TimingConfig()
        self.scheduler = RequestScheduler(policy=scheduler_policy)

        self.current_time = 0.0  # Simulated time in microseconds
        self.completed_requests = []

        # Statistics
        self.stats = {
            "reads": 0,
            "writes": 0,
            "erases": 0,
            "gc_count": 0,
            "coalesced_batches": 0,
            "total_coalesced_requests": 0,
            "total_read_latency_us": 0.0,
            "total_write_latency_us": 0.0,
            "total_erase_latency_us": 0.0,
            "total_gc_latency_us": 0.0,
        }

    def submit_request(self, req_type, logical_addr, arrival_time=None):
        """
        Submit a request to the scheduler.
        If arrival_time is None, uses current_time (synchronous submission).
        If arrival_time is provided, request arrives at that future time (async).
        """
        if arrival_time is None:
            arrival_time = self.current_time

        req = Request(req_type, logical_addr, arrival_time)
        self.scheduler.add_request(req)
        return req

    def process_requests(self, num_requests=None, until_time=None):
        """
        Process queued requests.

        Args:
            num_requests: Max number of requests to process (None = all available)
            until_time: Process only requests that have arrived by this time

        Only processes requests whose arrival_time <= current_time (have actually arrived).
        """
        processed = 0

        while self.scheduler.has_requests():
            if num_requests and processed >= num_requests:
                break

            if until_time and self.current_time >= until_time:
                break

            # Get next batch from scheduler (only considers arrived requests)
            batch = self.scheduler.get_next_batch(self.current_time)
            if not batch:
                break

            # Check if batch head has actually arrived yet
            if batch[0].arrival_time > self.current_time:
                # No requests have arrived yet, advance time to next arrival
                next_arrival = min(
                    req.arrival_time
                    for req in list(self.scheduler.read_queue)
                    + list(self.scheduler.write_queue)
                )
                self.current_time = next_arrival
                continue

            # Track coalescing
            if len(batch) > 1:
                self.stats["coalesced_batches"] += 1
                self.stats["total_coalesced_requests"] += len(batch)

            # Process batch
            batch_latency = self._process_batch(batch)
            self.current_time += batch_latency

            processed += len(batch)

        return processed

    def run_simulation(self, duration_us):
        """
        Run simulation for a specific duration.
        Processes all requests that arrive within the time window.
        """
        end_time = self.current_time + duration_us

        while self.current_time < end_time and self.scheduler.has_requests():
            batch = self.scheduler.get_next_batch(self.current_time)
            if not batch:
                break

            # Check if first request has arrived
            if batch[0].arrival_time > self.current_time:
                # Jump to next arrival or end of simulation window
                next_arrival = min(
                    req.arrival_time
                    for req in list(self.scheduler.read_queue)
                    + list(self.scheduler.write_queue)
                )
                self.current_time = min(next_arrival, end_time)
                continue

            if len(batch) > 1:
                self.stats["coalesced_batches"] += 1
                self.stats["total_coalesced_requests"] += len(batch)

            batch_latency = self._process_batch(batch)
            self.current_time += batch_latency

    def _process_batch(self, batch):
        """Process a batch of requests"""
        if not batch:
            return 0.0

        batch_start_time = self.current_time
        max_latency = 0.0

        # Sort batch by address for sequential access
        batch.sort(key=lambda r: r.logical_addr)

        for req in batch:
            req.start_time = self.current_time

            if req.type == RequestType.READ:
                latency = self._do_read(req)
            else:
                latency = self._do_write(req)

            req.completion_time = self.current_time + latency
            req.result = True
            self.completed_requests.append(req)

            # For coalesced requests, assume some parallelism
            max_latency = max(max_latency, latency)

        # If coalesced, benefit from parallel operation
        if len(batch) > 1:
            # Parallel reads/writes reduce total time
            return max_latency + (len(batch) - 1) * self.timing.scheduling_overhead_us
        else:
            return max_latency

    def _do_read(self, request):
        """Execute a read operation"""
        latency = self.timing.get_read_latency()

        self.stats["reads"] += 1
        self.stats["total_read_latency_us"] += latency

        # page = self.ftl.get_physical(request.logical_addr)
        # if page and page.is_valid():
        #     request.result = page.data
        # else:
        #     request.result = None

        return latency

    def _do_write(self, request):
        """Execute a write operation"""
        total_latency = 0.0

        # Invalidate old mapping
        old_page = self.ftl.get_physical(request.logical_addr)
        if old_page:
            old_page.invalidate()

        # Get free page
        free_page = self._get_free_page()
        if not free_page:
            gc_latency = self._garbage_collect()
            total_latency += gc_latency
            free_page = self._get_free_page()
            if not free_page:
                raise Exception("No free pages after GC")

        # Write
        write_latency = self.timing.get_write_latency()
        free_page.write(request.logical_addr, request.data)
        self.ftl.map(request.logical_addr, free_page)

        total_latency += write_latency

        self.stats["writes"] += 1
        self.stats["total_write_latency_us"] += total_latency

        return total_latency

    def _get_free_page(self):
        block = self.blocks[self.current_block_idx]
        page = block.get_free_page()
        if page:
            return page

        for i in range(len(self.blocks)):
            idx = (self.current_block_idx + i + 1) % len(self.blocks)
            block = self.blocks[idx]
            page = block.get_free_page()
            if page:
                self.current_block_idx = idx
                return page
        return None

    def _garbage_collect(self):
        self.stats["gc_count"] += 1
        gc_latency = 0.0

        victim = max(self.blocks, key=lambda b: b.get_invalid_count())
        if victim.get_invalid_count() == 0:
            victim = min(self.blocks, key=lambda b: b.erase_count)

        for page in victim.pages:
            if page.is_valid():
                gc_latency += self.timing.get_read_latency()
                gc_latency += self.timing.get_write_latency()

                free_page = self._get_free_page()
                if free_page:
                    free_page.write(page.logical_address, page.data)
                    self.ftl.map(page.logical_address, free_page)

        erase_latency = self.timing.get_erase_latency()
        gc_latency += erase_latency

        victim.erase()
        self.stats["erases"] += 1
        self.stats["total_erase_latency_us"] += erase_latency
        self.stats["total_gc_latency_us"] += gc_latency

        return gc_latency

    def get_stats(self):
        total_pages = sum(len(b.pages) for b in self.blocks)
        free_pages = sum(
            1 for b in self.blocks for p in b.pages if p.state == PageState.FREE
        )
        valid_pages = sum(1 for b in self.blocks for p in b.pages if p.is_valid())

        # Response time statistics
        response_times = [
            r.get_response_time()
            for r in self.completed_requests
            if r.get_response_time() is not None
        ]
        avg_response = (
            sum(response_times) / len(response_times) if response_times else 0
        )

        return {
            "reads": self.stats["reads"],
            "writes": self.stats["writes"],
            "erases": self.stats["erases"],
            "gc_count": self.stats["gc_count"],
            "coalesced_batches": self.stats["coalesced_batches"],
            "total_coalesced_requests": self.stats["total_coalesced_requests"],
            "queue_depth": self.scheduler.queue_depth(),
            "completed_requests": len(self.completed_requests),
            "utilization": valid_pages / total_pages * 100,
            "avg_response_time_us": avg_response,
            "total_simulated_time_ms": self.current_time / 1000,
        }


# Example usage
if __name__ == "__main__":
    print("=== SSD Simulator with Request Scheduling ===\n")

    # Create simulator with locality-based scheduling
    ssd = SSDSimulator(num_blocks=10, pages_per_block=32, scheduler_policy="locality")

    print("=== Example 1: Synchronous submission (all arrive immediately) ===")
    for i in range(20):
        ssd.submit_request(RequestType.WRITE, i, f"data_{i}")

    print(f"Queue depth: {ssd.scheduler.queue_depth()}")
    ssd.process_requests()
    print(f"Completed: {len(ssd.completed_requests)} requests")
    print(f"Simulated time: {ssd.current_time / 1000:.2f}ms\n")

    # print("=== Example 2: Requests with staggered arrival times ===")
    # ssd2 = SSDSimulator(num_blocks=10, pages_per_block=32, scheduler_policy="locality")

    # # Generate requests with realistic arrival times (Poisson-like)
    # current_time = 0.0
    # for i in range(50):
    #     # Random inter-arrival time (10-50μs between requests)
    #     inter_arrival = random.uniform(10, 50)
    #     current_time += inter_arrival

    #     # Mix of sequential and random addresses
    #     if i < 25:
    #         addr = i  # Sequential
    #     else:
    #         addr = random.randint(0, 24)  # Random

    #     ssd2.submit_request(
    #         RequestType.WRITE, addr, f"data_{i}", arrival_time=current_time
    #     )

    # print(f"Requests span {current_time / 1000:.2f}ms of arrival time")
    # print(f"Initial queue depth: {ssd2.scheduler.queue_depth()}")

    # # Process requests as they arrive
    # ssd2.run_simulation(duration_us=current_time + 1000)

    # print(f"Completed: {len(ssd2.completed_requests)} requests")
    # print(f"Final simulated time: {ssd2.current_time / 1000:.2f}ms")

    # print("\n=== Example 3: Burst of sequential requests (good coalescing) ===")
    # ssd3 = SSDSimulator(num_blocks=10, pages_per_block=32, scheduler_policy="locality")

    # # Submit a burst of sequential requests that arrive close together
    # base_time = 0.0
    # for i in range(20):
    #     # All arrive within 5μs window - should coalesce well
    #     arrival = base_time + random.uniform(0, 5)
    #     ssd3.submit_request(RequestType.READ, i, arrival_time=arrival)

    # print("20 sequential reads arriving within 5μs window")
    # ssd3.run_simulation(duration_us=10000)

    # stats3 = ssd3.get_stats()
    # print(f"Coalesced batches: {stats3['coalesced_batches']}")
    # print(f"Total coalesced requests: {stats3['total_coalesced_requests']}")

    # # Statistics
    # print("\n=== Final Statistics (Example 2) ===")
    # stats = ssd2.get_stats()
    # for key, value in stats.items():
    #     if "time" in key and "avg" in key:
    #         print(f"{key}: {value:.2f}μs")
    #     elif "time" in key and "total" in key:
    #         print(f"{key}: {value:.2f}ms")
    #     elif key == "utilization":
    #         print(f"{key}: {value:.2f}%")
    #     else:
    #         print(f"{key}: {value}")

    # # Show queue wait time vs service time
    # print("\n=== Sample Request Breakdown (Example 2) ===")
    # for req in ssd2.completed_requests[:5]:
    #     queue_wait = req.start_time - req.arrival_time
    #     service_time = req.completion_time - req.start_time
    #     response_time = req.get_response_time()
    #     print(f"Request {req.id} ({req.type.value} addr={req.logical_addr}):")
    #     print(f"  Arrived: {req.arrival_time:.2f}μs")
    #     print(f"  Queue wait: {queue_wait:.2f}μs")
    #     print(f"  Service time: {service_time:.2f}μs")
    #     print(f"  Response time: {response_time:.2f}μs")
