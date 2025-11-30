from typing import List

from cache import WriteCache
from event import EventLoop, EventType
from ftl import FlashTranslationLayer
from nand import NAND
from request import Request, RequestStatus, RequestType
from scheduler import FIFOScheduler, NaiveReadScheduler


class SSDSimulator:
    """Main SSD simulator with request scheduling"""

    def __init__(self, ncq_size: int = 32):
        self.event_loop = EventLoop(dispatch_callback=self.dispatch_event)

        # Components
        self.nand = NAND(self.event_loop)
        self.ftl = FlashTranslationLayer(self.nand)
        self.scheduler = FIFOScheduler(self.event_loop, self.nand)
        self.write_cache = WriteCache(self.event_loop, self.ftl, self.scheduler)

        # NCQ (Native Command Queue)
        self.ncq_size: int = ncq_size
        self.ncq: List[Request] = []

        # Request tracking
        self.requests: List[Request] = []
        self.completed_requests: List[Request] = []

    def dispatch_event(self, ev_type, payload):
        match ev_type:
            case EventType.ARRIVAL:
                self.handle_arrival(payload)
            case EventType.REQUEST_COMPLETE:
                self.handle_completion(payload)
            case EventType.CACHE_READ_COMPLETE:
                self.write_cache.handle_event(ev_type, payload)
            case EventType.CACHE_WRITE_COMPLETE:
                self.write_cache.handle_event(ev_type, payload)
            case EventType.NAND_READ_COMPLETE:
                self.nand.handle_event(ev_type, payload)
            case EventType.NAND_WRITE_COMPLETE:
                self.nand.handle_event(ev_type, payload)
            case EventType.DMA_COMPLETE:
                self.nand.handle_event(ev_type, payload)
            case _:
                raise NotImplementedError

    def handle_arrival(self, req: Request):
        """
        Handle the arrival of a new request by enqueuing it into the NCQ.
        Arrival events are only created when there is free space in the NCQ.
        """
        print(f"Request arrived: {req}, time: {self.event_loop.time_us} us")
        req.enqueue_time = self.event_loop.time_us
        self.ncq.append(req)

        # forward WRITE and cached READ requests to the cache
        match req.type:
            case RequestType.WRITE:
                self.write_cache.put(req)
            case RequestType.READ:
                if self.write_cache.will_contain(req.lba):
                    self.write_cache.get(req)
                else:
                    req.physical_addr = self.ftl.lookup(req.lba)
                    self.scheduler.enqueue(req)
                    self.scheduler.schedule()
            case RequestType.FLUSH:
                raise NotImplementedError
            case _:
                raise NotImplementedError

    def handle_completion(self, req: Request):
        """
        Handle the completion of a request by updating its status,
        removing it from the NCQ, and adding it to the completed requests list.

        Furthermore, free up any resources associated with the request and
        create an event for the arrival of the next request if available.
        """
        print(f"Completed {req}")

        # update request status and move to completed list
        # if not req.status == RequestStatus.COMPLETED:
        req.completion_time = self.event_loop.time_us
        req.status = RequestStatus.COMPLETED
        self.ncq.remove(req)
        self.completed_requests.append(req)

        # add event for next request
        if self.requests:
            next_req = self.requests.pop(0)
            arrival_time = max(next_req.arrival_time, self.event_loop.time_us)
            self.event_loop.schedule_event(arrival_time, EventType.ARRIVAL, next_req)

        # run NCQ scheduler because NAND die is freed
        self.scheduler.schedule()

    def run_simulation(self, requests: List[Request]):
        """
        Run the SSD simulation with the given sequence of requests.
        """
        print("Starting simulation...")

        # create arrival events for requests to initially fill the NCQ
        for req in requests[: self.ncq_size]:
            self.event_loop.schedule_event(req.arrival_time, EventType.ARRIVAL, req)
        self.requests = requests[self.ncq_size :]

        # run event loop
        self.event_loop.run()

    def print_statistics(self):
        # TODO compute more statistics
        print(
            f"================= Simulation done in {self.event_loop.time_us} us ================="
        )
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
