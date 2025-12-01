from cache import WriteCache
from event import Event, EventLoop, EventType
from frontend_scheduler import FrontendScheduler
from ftl import FlashTranslationLayer
from nand import NAND
from nand_scheduler import FIFOScheduler
from request import Request, RequestStatus, RequestType


class SSDSimulator:
    def __init__(self):
        self.event_loop = EventLoop()

        # Logical components
        self.nand = NAND(self.event_loop)
        self.ftl = FlashTranslationLayer(self.nand)
        self.nand_scheduler = FIFOScheduler(self.event_loop, self.nand)
        self.write_cache = WriteCache(self.event_loop, self.ftl, self.nand_scheduler)
        self.frontend_scheduler = FrontendScheduler(
            self.write_cache, self.ftl, self.nand_scheduler
        )

        # Request tracking
        self.requests: list[Request] = []
        self.completed_requests: list[Request] = []

        # Register event handlers
        self.event_loop.register_handler(EventType.ARRIVAL, self._handle_arrival)
        self.event_loop.register_handler(
            EventType.REQUEST_COMPLETE, self._handle_completion
        )

    def _handle_arrival(self, event: Event):
        assert isinstance(event.payload, Request)
        req: Request = event.payload
        print(f"Request arrived: {req}, time: {self.event_loop.time_us} us")
        req.enqueue_time = self.event_loop.time_us
        self.frontend_scheduler.enqueue(req)
        self.frontend_scheduler.schedule()

    def _handle_completion(self, event: Event):
        assert isinstance(event.payload, Request)
        req: Request = event.payload
        print(f"Completed {req}")

        # update request status and move to completed list
        req.completion_time = self.event_loop.time_us
        req.status = RequestStatus.COMPLETED
        self.frontend_scheduler.remove(req)
        self.completed_requests.append(req)

        # add event for next request
        if self.requests:
            next_req = self.requests.pop(0)
            arrival_time = max(next_req.arrival_time, self.event_loop.time_us)
            new_event = Event(
                time_us=arrival_time,
                ev_type=EventType.ARRIVAL,
                payload=next_req,
            )
            self.event_loop.schedule_event(new_event)

        # TODO: move somewhere else? maybe into separate event and the same for frontend scheduler
        # run NCQ scheduler because NAND die is freed
        self.nand_scheduler.schedule()

    def run_simulation(self, requests: list[Request]):
        print("Starting simulation...")

        # create arrival events for requests to initially fill the NCQ
        while requests and self.frontend_scheduler.has_space():
            request = requests.pop(0)
            event = Event(
                time_us=request.arrival_time,
                ev_type=EventType.ARRIVAL,
                payload=request,
            )
            self.event_loop.schedule_event(event)

        # run event loop
        self.event_loop.run()

    def print_statistics(self):
        # TODO compute more statistics
        print(
            f"================= Simulation done in {self.event_loop.time_us} us ================="
        )
        avg_write_response_time: float = 0
        avg_read_response_time: float = 0
        for req in sorted(self.completed_requests, key=lambda r: r.id):
            print(f"{req}: {req.get_latency_breakdown()}")
            match req.type:
                case RequestType.WRITE:
                    avg_write_response_time += req.get_response_time() or 0
                case RequestType.READ:
                    avg_read_response_time += req.get_response_time() or 0
        print(f"Avg. write latency: {avg_write_response_time} us")
        print(f"Avg. read latency: {avg_read_response_time} us")
