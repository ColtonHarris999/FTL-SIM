from dataclasses import dataclass


@dataclass
class PhysicalAddress:
    chip: int
    die: int
    plane: int
    block: int
    page: int
    offset: int


class FlashTranslationLayer:
    def __init__(
        self,
        page_size: int = 4 * 1024,
        pages_per_block: int = 256,
        blocks_per_plane: int = 1024,
        planes_per_die: int = 1,
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

    def lookup(self, lba: int) -> PhysicalAddress:
        return self.mapping.get(lba)
