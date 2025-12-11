import math
from typing import Optional

from nand import NAND, PhysicalAddress


class FlashTranslationLayer:
    """
    Basic FTL implementation that maintains a LPA -> PPA mapping and sequentially allocates physical pages by striping across channels, dies, planes, and blocks.

    Assumes page-level mapping and no garbage collection for simplicity.
    """

    def __init__(
        self,
        nand: NAND,
    ):
        self.nand = nand
        self.mapping: dict[int, PhysicalAddress] = {}
        self.counter = 0  # stub counter for physical page allocation

        self.lba_size: int = 4 * 1024  # bytes

    def get_max_lba(self) -> int:
        total_pages = (
            self.nand.geometry.num_channels
            * self.nand.geometry.num_dies_per_channel
            * self.nand.geometry.num_planes_per_die
            * self.nand.geometry.blocks_per_plane
            * self.nand.geometry.pages_per_block
        )
        total_bytes = total_pages * self.nand.geometry.page_size
        return total_bytes // self.lba_size

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
        # TODO dont stripe across blocks? prioritize plane parallelism first?
        # stripe across channels, dies, planes, and blocks for maximum parallelism
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


class BlockLevelFTL(FlashTranslationLayer):
    """
    Block-level FTL implementation that maintains a LBA -> PPA mapping at block granularity.
    """

    pass


class PageLevelFTL(FlashTranslationLayer):
    """
    Page-level FTL implementation that maintains a LBA -> PPA mapping at page granularity.
    """

    def required_ram_bytes(self) -> int:
        # Each entry needs ceil(log2(max_lba)) bits to store the PPA
        entry_bytes = math.ceil(math.log2(self.get_max_lba())) / 8
        num_entries = self.get_max_lba()
        return num_entries * entry_bytes


class HybridFTL(FlashTranslationLayer):
    """
    Hybrid FTL implementation that uses block-level mapping for cold data and page-level mapping for hot data.
    """

    pass
