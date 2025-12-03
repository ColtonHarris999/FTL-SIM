from cache import WriteCache
from event import Event, EventLoop, EventType
from frontend_scheduler import FrontendScheduler
from ftl import FlashTranslationLayer
from nand import NAND
from nand_scheduler import MockScheduler
from request import Request, RequestType, TraceEvent


class SSDSimulator:
    def __init__(self):
        self.event_loop = EventLoop(self._timestep)

        # Logical components
        self.nand = NAND(self.event_loop)
        self.ftl = FlashTranslationLayer(self.nand)
        self.nand_scheduler = MockScheduler(self.event_loop)
        self.write_cache = WriteCache(self.event_loop, self.ftl, self.nand_scheduler)
        self.frontend_scheduler = FrontendScheduler(
            self.event_loop, self, self.write_cache, self.ftl, self.nand_scheduler
        )

        # Request bookkeeping
        self.requests: list[Request] = []
        self.completed_requests: list[Request] = []

        self.event_loop.register_handler(
            EventType.REQUEST_ARRIVAL, self._handle_arrival
        )

    def complete(self, request: Request):
        """Handle completion of a request."""
        self.completed_requests.append(request)

        # add arrival event for next request
        if self.requests:
            next_req = self.requests.pop(0)
            ready_time = max(next_req.ready_time, self.event_loop.time_us)
            new_event = Event(
                time_us=ready_time,
                description="REQUEST_ARRIVAL",
                payload=next_req,
                callback=self._handle_arrival,
            )
            self.event_loop.schedule_event(new_event)

    def _timestep(self, event: Event) -> None:
        """Called at each timestep of the event loop."""
        self.frontend_scheduler.try_dispatch()
        self.nand_scheduler.try_dispatch()

    def _handle_arrival(self, event: Event) -> None:
        assert isinstance(event.payload, Request)
        request: Request = event.payload
        self.frontend_scheduler.submit(request)

    def run_simulation(self, requests: list[Request]):
        # create arrival events for requests to initially fill the NCQ
        for request in requests[: self.frontend_scheduler.ncq_size]:
            event = Event(
                time_us=request.ready_time,
                description="REQUEST_ARRIVAL",
                payload=request,
                callback=self._handle_arrival,
            )
            self.event_loop.schedule_event(event)
        self.requests = requests[self.frontend_scheduler.ncq_size :]

        # run simulation
        print("==================================================")
        print("Starting simulation")
        print("==================================================")

        self.event_loop.run()

        print("==================================================")
        print(f"Simulation done in {self.event_loop.time_us} us")
        print("==================================================")

    def print_statistics(self):
        # TODO compute more statistics
        avg_write_response_time: float = 0
        avg_read_response_time: float = 0
        for req in sorted(self.completed_requests, key=lambda r: r.id):
            print(
                f"{req}: Response time = {req.get_response_time()} us, Trace = ({req.trace_str()})"
            )
            match req.type:
                case RequestType.WRITE:
                    avg_write_response_time += req.get_response_time() or 0
                case RequestType.READ:
                    avg_read_response_time += req.get_response_time() or 0
                case _:
                    pass
        print(f"Avg. write latency: {avg_write_response_time} us")
        print(f"Avg. read latency: {avg_read_response_time} us")

        # Calculate cache hit rate
        total_read_requests = sum(
            1 for req in self.completed_requests if req.type == RequestType.READ
        )
        cache_hits = sum(
            1
            for req in self.completed_requests
            if req.type == RequestType.READ and TraceEvent.CACHE_READ_START in req.trace
        )

        cache_hit_rate = (
            (cache_hits / total_read_requests) * 100 if total_read_requests > 0 else 0
        )
        print(f"# reads: {self.nand_scheduler.num_reads}")
        print(f"Cache hit rate: {cache_hit_rate:.2f}%")

        # Calculate write amplification
        total_logical_writes = sum(
            1 for req in self.completed_requests if req.type == RequestType.WRITE
        )
        write_amplification = (
            (
                self.nand_scheduler.num_writes
                * self.ftl.lbas_per_page
                / total_logical_writes
            )
            if total_logical_writes > 0
            else 0
        )
        print(f"# writes: {self.nand_scheduler.num_writes}")
        print(f"Write amplification factor: {write_amplification:.2f}")
