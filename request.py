from enum import Enum, auto
from typing import Optional

from nand import PhysicalAddress


class RequestType(Enum):
    READ = auto()
    WRITE = auto()
    FLUSH = auto()


class RequestStatus(Enum):
    READY = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()


class Request:
    """Represents an I/O request"""

    _id_counter = 0

    def __init__(self, req_type: RequestType, lba: int, arrival_time: float = 0.0):
        # Assign unique ID
        self.id = Request._id_counter
        Request._id_counter += 1

        # Request attributes
        self.type = req_type
        self.status = RequestStatus.READY
        self.fua = False  # Force Unit Access flag
        self.lba = lba
        self.physical_addr: Optional[PhysicalAddress] = None

        # Timing info
        self.arrival_time = arrival_time
        self.enqueue_time: Optional[float] = None  # When it was enqueued in the NCQ
        self.start_time: Optional[float] = None  # When processing begins
        self.completion_time: Optional[float] = None  # When processing completes
        self.device_latency = 0.0  # Actual flash operation time
        self.ftl_latency = 0.0  # FTL lookup/mapping time
        self.gc_latency = 0.0  # Garbage collection time (if triggered)

    def __str__(self):
        return f"(Request {self.id})"

    def get_response_time(self):
        """Total response time: arrival to completion"""
        if self.completion_time is not None:
            return self.completion_time - self.arrival_time
        return None

    def get_queue_wait_time(self):
        """Time spent waiting in queue"""
        if self.start_time is not None:
            return self.start_time - self.arrival_time
        return None

    def get_service_time(self):
        """Time spent being serviced (not waiting in queue)"""
        if self.completion_time is not None and self.start_time is not None:
            return self.completion_time - self.start_time
        return None

    def get_latency_breakdown(self):
        """Get detailed latency breakdown"""
        return {
            "arrival_time": self.arrival_time,
            "enqueue_time": self.enqueue_time,
            "start_time": self.start_time,
            "completion_time": self.completion_time,
            # "queue_wait": self.get_queue_wait_time(),
            "service_time": self.get_service_time(),
            # "ftl_latency": self.ftl_latency,
            # "device_latency": self.device_latency,
            # "gc_latency": self.gc_latency,
            "response_time": self.get_response_time(),
        }
