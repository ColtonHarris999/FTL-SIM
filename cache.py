from collections import defaultdict
from typing import Dict

from request import Request


class WriteCache:
    def __init__(self, page_size=16384, max_bytes=4 * 1024 * 1024):
        self.page_size = page_size
        self.max_bytes = max_bytes
        self.bytes_used = 0
        # coalesce buffers: key -> dict(lba->data_placeholder)
        # key could be chosen by controller algorithm; we use "virtual page id"
        self.buffers: Dict[int, Dict[int, None]] = defaultdict(dict)
        self.virtual_next = 0

    def add_write(self, req: Request):
        # naive: put each LBA in its own virtual page until buffer full or coalesce opportunity found
        # realistic controllers decide which LBAs to pack; here we just put into a current buffer
        v = self.virtual_next
        self.buffers[v][req.lba] = None
        self.bytes_used += req.length
        # if buffer full (by page), move to next buffer
        if len(self.buffers[v]) * 4096 >= self.page_size:
            self.virtual_next += 1
            return v  # returns buffer id where data is
        return v

    def ready_to_flush(self, threshold_bytes):
        return self.bytes_used >= threshold_bytes

    def flush_buffer(self, buffer_id):
        lbs = list(self.buffers.pop(buffer_id).keys())
        # reduce bytes_used (approx)
        self.bytes_used -= len(lbs) * 4096
        return lbs  # returns list of LBAs to program to flash
