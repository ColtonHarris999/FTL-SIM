from typing import List

from request import Request, RequestStatus, RequestType
from scheduler import Scheduler


class SSDSimulator:
    """Main SSD simulator with request scheduling"""

    def __init__(self, scheduler: Scheduler, ncq_size: int = 32):
        self.scheduler: Scheduler = scheduler
        self.ncq_size: int = ncq_size
        self.ncq: List[Request] = []
        self.current_time_us: float = 0.0
        self.completed_requests: List[Request] = []
        self.nand_ready = True  # TODO replace with die/plane datastructure

    def reset(self):
        self.ncq.clear()
        self.current_time_us = 0.0
        self.completed_requests.clear()
        self.nand_ready = True

    def run_simulation(self, requests: List[Request]):
        print("Starting simulation...")

        # run event loop while there are requests in the system
        while len(requests) > 0 or len(self.ncq) > 0:
            # find next event
            # it might be the next completion of any requests in progress
            next_event = float("inf")
            for req in self.ncq:
                if req.status == RequestStatus.IN_PROGRESS:
                    next_event = min(next_event, req.completion_time)

            # next event might also be a new request arriving in the NCQ
            if requests and len(self.ncq) < self.ncq_size:
                next_event = min(next_event, requests[0].arrival_time)

            # advance global time to next event
            print(f"================= Timestep {next_event} us =================")
            self.current_time_us = max(self.current_time_us, next_event)

            # handle completed requests
            i = 0
            while i < len(self.ncq):
                req = self.ncq[i]
                if (
                    req.status == RequestStatus.IN_PROGRESS
                    and req.completion_time <= self.current_time_us
                ):
                    req.status = RequestStatus.COMPLETED
                    self.completed_requests.append(req)
                    self.ncq.pop(i)  # remove from queue
                    print(f"Completed {req}")
                    if req.type in [RequestType.READ, RequestType.WRITE]:
                        self.nand_ready = True
                    # do not increment i, because the next item shifts into current index
                else:
                    i += 1

            # add requests that have arrived to the NCQ if there is free space
            while (
                requests
                and requests[0].arrival_time <= self.current_time_us
                and len(self.ncq) < self.ncq_size
            ):
                req = requests.pop(0)
                req.enqueue_time = self.current_time_us
                self.ncq.append(req)

            # run scheduler
            if self.ncq:
                scheduled_requests = self.scheduler.schedule(self.ncq, self.nand_ready)
                # TODO scheduling latency should be hidden by the pipeline in most cases
                self.current_time_us += self.scheduler.latency
                for req in scheduled_requests:
                    print(f"Scheduled {req}")
                    # TODO check if scheduler actions are legal
                    if not self.nand_ready:
                        raise ValueError("Scheduler scheduled illegal action")
                    self.nand_ready = False
                    req.status = RequestStatus.IN_PROGRESS
                    req.start_time = self.current_time_us
                    req.completion_time = req.start_time + 10

        print(
            f"================= Simulation done in {self.current_time_us} us ================="
        )
        # TODO compute more statistics
        avg_write_response_time = 0
        avg_read_response_time = 0
        for req in sorted(self.completed_requests, key=lambda r: r.id):
            print(f"{req}: {req.get_latency_breakdown()}")
            match req.type:
                case RequestType.WRITE:
                    avg_write_response_time += req.get_response_time()
                case RequestType.READ:
                    avg_read_response_time += req.get_response_time()
        print(f"Avg. write latency: {avg_write_response_time} us")
        print(f"Avg. read latency: {avg_read_response_time} us")
