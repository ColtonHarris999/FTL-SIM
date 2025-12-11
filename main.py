from random import sample

from request import Request, RequestType
from simulator import SSDSimulator


def sequential_write(size: int):
    print("Running sequential write test...")
    ssd = SSDSimulator()

    writes = [Request(RequestType.WRITE, i, 0) for i in range(size)]
    ssd.run_simulation(writes)

    ssd.print_statistics()


def random_write(size: int):
    print("Running random write test...")
    ssd = SSDSimulator()

    max_lba = ssd.ftl.get_max_lba()

    random_lbas = sample(range(max_lba), k=size)

    writes = [Request(RequestType.WRITE, lba, 0) for lba in random_lbas]
    ssd.run_simulation(writes)

    ssd.print_statistics()


def parallelism():
    print("Running parallelism test...")
    ssd = SSDSimulator()

    lbas_per_page = ssd.ftl.lbas_per_page()

    writes = [Request(RequestType.WRITE, i * lbas_per_page, 0) for i in range(8)]
    ssd.run_simulation(writes)
    # print(ssd.ftl.mapping)

    reads = [
        Request(RequestType.READ, i * lbas_per_page, ssd.event_loop.time_us)
        for i in [0, 4, 1, 5, 2, 6, 3, 7]
    ]
    ssd.run_simulation(reads)

    ssd.print_statistics()


if __name__ == "__main__":
    # sequential_write(1000)
    random_write(50)
    # parallelism()
