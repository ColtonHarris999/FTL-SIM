from typing import List

from cache import WriteCache
from channel import Channel
from event import EventLoop, EventType
from ftl import FlashTranslationLayer
from nand import Timing
from request import Request, RequestStatus, RequestType
from scheduler import FIFOScheduler, NaiveReadScheduler, Scheduler


class SSDSimulator:
    """Main SSD simulator with request scheduling"""

    def __init__(self, ncq_size: int = 32):
        # event queue
        self.event_loop = EventLoop(dispatch_callback=self.dispatch_event)

        # Components
        self.ftl: FlashTranslationLayer = FlashTranslationLayer()
        self.write_cache = WriteCache()
        self.channel = Channel(self.event_loop)
        self.scheduler: Scheduler = NaiveReadScheduler(self.event_loop, self.channel)

        # NCQ (Native Command Queue)
        self.ncq_size: int = ncq_size
        self.ncq: List[Request] = []

        # Request tracking
        self.requests: List[Request] = []
        self.completed_requests: List[Request] = []

        # TODO replace with proper die/plane datastructure
        self.nand_ready = True

    def dispatch_event(self, ev_type, payload):
        print(
            f"========= T={self.event_loop.time_us}: Dispatching {ev_type} for {payload} ========="
        )
        match ev_type:
            case EventType.ARRIVAL:
                self.handle_arrival(payload)
            case EventType.DMA_COMPLETE:
                self.handle_dma_complete(payload)
            case EventType.NAND_READ_COMPLETE:
                self.channel.do_dma(payload)
            case EventType.NAND_PROGRAM_COMPLETE:
                self.handle_completion(payload)
            # case EventType.CACHE_FLUSH:
            #     self.handle_cache_flush()
            case _:
                raise NotImplementedError

    def handle_arrival(self, req: Request):
        """
        Handle the arrival of a new request by enqueuing it into the NCQ.
        Arrival events are only created when there is space in the NCQ.
        """
        print(f"Request arrived: {req}, time: {self.event_loop.time_us} us")
        req.enqueue_time = self.event_loop.time_us
        self.ncq.append(req)

        # run NCQ scheduler
        self.scheduler.schedule(self.ncq, self.nand_ready)

    def handle_dma_complete(self, req: Request):
        """
        Handle the completion of a DMA operation for the given request.
        """
        print(f"DMA complete for {req}")
        if req.type == RequestType.READ:
            # read operation is done after DMA transfer
            self.handle_completion(req)
        elif req.type == RequestType.WRITE:
            # schedule NAND program
            self.event_loop.schedule_event(
                self.event_loop.time_us + Timing.PROGRAM_US,
                EventType.NAND_PROGRAM_COMPLETE,
                req,
            )

        # Execute queued DMA requests if any, otherwise mark DMA as not busy
        self.channel.complete()

    def handle_completion(self, req: Request):
        """
        Handle the completion of a request by updating its status,
        removing it from the NCQ, and adding it to the completed requests list.

        Furthermore, free up any resources associated with the request and
        create an event for the arrival of the next request if available.
        """
        print(f"Completed {req}")
        req.completion_time = self.event_loop.time_us
        req.status = RequestStatus.COMPLETED
        self.ncq.remove(req)
        self.completed_requests.append(req)

        # free resources
        if req.type in [RequestType.READ, RequestType.WRITE]:
            self.nand_ready = True

        # add event for next request
        if self.requests:
            next_req = self.requests.pop(0)
            arrival_time = max(next_req.arrival_time, self.event_loop.time_us)
            self.event_loop.schedule_event(arrival_time, EventType.ARRIVAL, next_req)

        # run NCQ scheduler
        self.scheduler.schedule(self.ncq, self.nand_ready)

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
