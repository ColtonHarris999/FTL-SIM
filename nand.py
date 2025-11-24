from enum import Enum


class PageState(Enum):
    FREE = "free"
    VALID = "valid"
    INVALID = "invalid"


class Page:
    def __init__(self, page_id):
        self.page_id = page_id
        self.state = PageState.FREE
        self.logical_address = None

    def write(self, logical_addr):
        if self.state != PageState.FREE:
            raise Exception(f"Cannot write to non-free page {self.page_id}")
        self.state = PageState.VALID
        self.logical_address = logical_addr

    def invalidate(self):
        self.state = PageState.INVALID

    def is_valid(self):
        return self.state == PageState.VALID


class Block:
    def __init__(self, block_id, pages_per_block=64):
        self.block_id = block_id
        self.pages = [Page(f"{block_id}_{i}") for i in range(pages_per_block)]
        self.erase_count = 0

    def erase(self):
        for page in self.pages:
            page.state = PageState.FREE
            page.logical_address = None
        self.erase_count += 1

    def get_free_page(self):
        for page in self.pages:
            if page.state == PageState.FREE:
                return page
        return None

    def get_valid_count(self):
        return sum(1 for p in self.pages if p.is_valid())

    def get_invalid_count(self):
        return sum(1 for p in self.pages if p.state == PageState.INVALID)


class Plane:
    def __init__(self) -> None:
        pass
