from enum import Enum
from typing import Optional

from nand import NAND, PhysicalAddress


class FlashTranslationLayer:
    def __init__(
        self,
        nand: NAND,
    ):
        self.nand = nand
        self.mapping: dict[int, PhysicalAddress] = {}
        self.counter = 0  # stub counter for physical page allocation

        self.lba_size: int = 4096  # bytes

    def lbas_per_page(self) -> int:
        return self.nand.geometry.page_size // self.lba_size

    def lba_to_lpa(self, lba: int) -> int:
        return lba // self.lbas_per_page()

    def lpa_to_ppa(self, lpa: int) -> Optional[PhysicalAddress]:
        return self.mapping.get(lpa)

    def lba_to_ppa(self, lba: int) -> Optional[PhysicalAddress]:
        lpa: int = self.lba_to_lpa(lba)
        return self.lpa_to_ppa(lpa)

    def allocate(self, lpa: int) -> PhysicalAddress:
        # TODO call GC if needed
        # TODO dont stripe across blocks?
        channel = self.counter % self.nand.geometry.num_channels
        remaining = self.counter // self.nand.geometry.num_channels
        die = remaining % self.nand.geometry.num_dies_per_channel
        remaining = remaining // self.nand.geometry.num_dies_per_channel
        plane = remaining % self.nand.geometry.num_planes_per_die
        remaining = remaining // self.nand.geometry.num_planes_per_die
        block = remaining % self.nand.geometry.blocks_per_plane
        remaining = remaining // self.nand.geometry.blocks_per_plane
        page = remaining % self.nand.geometry.pages_per_block

        pa = PhysicalAddress(channel, die, plane, block, page)
        self.counter += 1
        self.mapping[lpa] = pa
        return pa


# -------------------------------------------------------
# Old stuff
# -------------------------------------------------------
class Plane:
    def __init__(self, blocks_per_plane=1024):
        self.busy: bool = False
        self.blocks: list[Block] = [Block() for i in range(blocks_per_plane)]
        self.next_free_block: int = 0


class PageState(Enum):
    FREE = "free"
    VALID = "valid"
    INVALID = "invalid"


# What data is actually required?
# Write pages sequentially in each block:
# - next free page index per block
# - erase `count per block
# - inverse FTL mapping if we implement GC
class Block:
    def __init__(self, pages_per_block=64):
        self.num_pages = pages_per_block
        self.num_free = pages_per_block
        self.num_invalid = 0
        self.erase_count = 0

    def erase(self):
        self.num_free = self.num_pages
        self.num_invalid = 0
        self.erase_count += 1
