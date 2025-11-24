from dataclasses import dataclass


@dataclass
class PhysicalAddress:
    # channel: int
    # chip: int
    die: int
    plane: int
    block: int
    page: int
    offset: int


class FlashTranslationLayer:
    def __init__(
        self,
        page_size: int,
        pages_per_block: int,
        blocks_per_plane: int,
        planes_per_die: int,
    ):
        self.page_size: int = page_size
        self.pages_per_block: int = pages_per_block
        self.blocks_per_plane: int = blocks_per_plane
        self.planes_per_die: int = planes_per_die
        self.mapping: dict[int, PhysicalAddress] = {}

    def clear(self):
        self.mapping.clear()

    def map(self, lba: int, page: PhysicalAddress):
        self.mapping[lba] = page

    def get_physical(self, lba: int) -> PhysicalAddress:
        return self.mapping.get(lba)
