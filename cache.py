import enum
from event import EventLoop, EventType
from ftl import FlashTranslationLayer
from nand import NANDTransactionType, PhysicalAddress, NANDTransaction
from request import Request, RequestType
from scheduler import Scheduler

"""
- serialize read and writes using internal queue
- coalesce writes to same LBA
- coalesce writes if LBA is smaller than physical page size

write:
- after write, schedule writeback event with x us coalesce delay
- on writeback event, mark as in progress and issue to NAND
- on write complete, mark as complete and free cache space

- if next write before writeback event, reschedule writeback event
- otherwise use new slots in cache

read:
- on read, check if in cache and schedule read complete event
"""


class CachePageState(enum.Enum):
    DIRTY = enum.auto()
    FLUSH_SCHEDULED = enum.auto()
    FLUSHING = enum.auto()


class CachePage:
    def __init__(self, lpa: int):
        self.lpa = lpa  # logical page address (= lba // lbas_per_page)
        self.status = CachePageState.DIRTY
        self.flush_event = None
        self.requests: list[Request] = []


class WriteCache:
    def __init__(
        self,
        event_loop: EventLoop,
        ftl: FlashTranslationLayer,
        scheduler: Scheduler,
        num_pages: int = 4,
    ):
        self.event_loop = event_loop
        self.ftl = ftl
        self.scheduler = scheduler

        self.num_pages = num_pages
        self.cache: dict[int, CachePage] = {}

        self.cached_lbas = set()

        self.queue = []
        self.busy = False

        # Timing parameters
        self.write_us = 10
        self.read_us = 10
        self.writeback_delay = 200  # coalesce delay before writeback

        self.lbas_per_page = 2  # TODO: move to correct place

    def handle_event(self, ev_type, payload):
        match ev_type:
            case EventType.CACHE_READ_COMPLETE:
                self._handle_cache_transfer_complete(payload)
            case EventType.CACHE_WRITE_COMPLETE:
                self._handle_cache_transfer_complete(payload)
            case EventType.NAND_WRITE_COMPLETE:
                self._handle_writeback_complete(payload)
            case _:
                raise NotImplementedError

    def get(self, request: Request):
        if request.lba not in self.cached_lbas:
            raise Exception(f"Cache miss for LBA {request.lba}")

        if self.busy:
            # enqueue request if cache is busy
            self.queue.append(request)
        else:
            # directly serve from cache
            self.busy = True
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.read_us,
                EventType.CACHE_READ_COMPLETE,
                request,
            )

    def put(self, request: Request):
        """
        Start writing if cache not busy and has space, otherwise enqueue write.
        """
        # directly insert for `will_contain()` to work
        self.cached_lbas.add(request.lba)

        if self.busy or len(self.cache) >= self.num_pages:
            # enqueue write request if cache is busy or full
            self.queue.append(request)
        else:
            # TODO: coalesce writes to same LBA if writeback not already in progress
            self.busy = True
            self.event_loop.schedule_event(
                self.event_loop.time_us + self.write_us,
                EventType.CACHE_WRITE_COMPLETE,
                request,
            )

    def will_contain(self, lba: int):
        return lba in self.cache or lba in self.queue

    def _handle_cache_transfer_complete(self, payload):
        """
        Complete request to host and start next cache transfer if any enqueued.
        """
        if self.queue:
            # TODO: start next transfer
            # next_lba = self.queue.pop(0)
            # self.cache[next_lba.logical_addr] = next_lba
            pass
        else:
            self.busy = False

        if payload.type == RequestType.WRITE:
            # complete to host if not FUA
            if not payload.fua:
                self.event_loop.schedule_event(
                    self.event_loop.time_us,
                    EventType.REQUEST_COMPLETE,
                    payload,
                )

            # put request in correct cache page
            lpa = payload.lba // self.lbas_per_page
            if lpa not in self.cache:
                self.cache[lpa] = CachePage(lpa)
            page = self.cache[lpa]
            page.requests.append(payload)

            # schedule writeback after coalesce delay
            page.flush_event = self.event_loop.schedule_event(
                self.event_loop.time_us + self.writeback_delay,
                EventType.CACHE_FLUSH_START,
                payload,
            )

    def _handle_writeback_start(self, page: CachePage):
        """
        Handler for starting writeback/flush after coalesce delay.
        Issue NAND write via scheduler that eventually completes all currently coalesced requests. If not all subpages are written at least once,
        issue NAND read first.
        """
        page.status = CachePageState.FLUSHING

        # issue NAND read first if not all subpages written
        read_transaction = None
        if len(set([req.lba for req in page.requests])) < self.lbas_per_page:
            read_transaction = NANDTransaction(
                type=NANDTransactionType.READ,
                pa=self.ftl.lookup(page.lpa),
                completed_requests=[],
            )
            self.scheduler.enqueue(read_transaction)

        # allocate physical address and issue NAND write
        transaction = NANDTransaction(
            type=NANDTransactionType.WRITE,
            pa=self.ftl.allocate(page.lpa),
            completed_requests=[],  # TODO: fill requests with FUA bit set
            depends_on=read_transaction,
        )
        self.scheduler.enqueue(transaction)

        self.scheduler.schedule()

    def _handle_writeback_complete(self, transaction: NANDTransaction):
        # TODO: check if pending read?

        # workaround to get page
        lpa = transaction.completed_requests[0].lba // self.lbas_per_page
        page = self.cache[lpa]

        # complete flushed requests from cache page
        for req in transaction.completed_requests:
            page.requests.remove(req)
            if req.fua:
                self.event_loop.schedule_event(
                    self.event_loop.time_us,
                    EventType.REQUEST_COMPLETE,
                    req,
                )

        # remove page from cache if empty
        if not page.requests:
            del self.cache[lpa]
            # TODO: how to handle cached_lbas
