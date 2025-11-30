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

    def clear(self):
        self.mapping.clear()

    def lookup(self, lpa: int) -> Optional[PhysicalAddress]:
        return self.mapping.get(lpa)

    def allocate(self, lpa: int) -> PhysicalAddress:
        # TODO implement
        # TODO call GC if needed
        pa = PhysicalAddress(0, 0, 0, 0, self.counter)
        self.counter += 1
        self.mapping[lpa] = pa
        return pa
