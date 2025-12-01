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
        self.lbas_per_page: int = 2  # TODO: compute from NAND geometry

    def clear(self):
        self.mapping.clear()

    def lpa_to_ppa(self, lpa: int) -> Optional[PhysicalAddress]:
        # TODO: remove this shit
        if lpa not in self.mapping:
            self.allocate(lpa)
        return self.mapping.get(lpa)

    def allocate(self, lpa: int) -> PhysicalAddress:
        # TODO implement
        # TODO call GC if needed
        pa = PhysicalAddress(0, 0, 0, 0, self.counter)
        self.counter += 1
        self.mapping[lpa] = pa
        # TODO: invalidate previous physical page
        return pa

    def lba_to_lpa(self, lba: int) -> int:
        return lba // self.lbas_per_page
