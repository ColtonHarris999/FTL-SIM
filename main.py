from request import Request, RequestType
from simulator import SSDSimulator


def sequential_write(size: int):
    print("Running sequential write test...")
    ssd = SSDSimulator()

    writes = [Request(RequestType.WRITE, i, 0) for i in range(size)]
    ssd.run_simulation(writes)

    reads = [Request(RequestType.READ, i, ssd.event_loop.time_us) for i in range(size)]
    ssd.run_simulation(reads)

    ssd.print_statistics()


def idk():
    pass
    # print("=== Example 1: Synchronous reads ===")
    # requests = [Request(RequestType.READ, i, i) for i in range(10)]
    # ssd.reset()
    # ssd.run_simulation(requests)
    # ssd.print_statistics()

    # print("=== Example 2: Staggered reads ===")
    # requests = [Request(RequestType.READ, i, 20 * i) for i in range(10)]
    # ssd.reset()
    # ssd.run_simulation(requests)

    # print("=== Example 3: Read/write mix ===")
    # requests = [
    #     Request(Random().choice([RequestType.READ, RequestType.WRITE]), i % 2, 0)
    #     for i in range(10)
    # ]
    # ssd.reset()
    # ssd.run_simulation(requests)

    # print("=== Example 4: Read/write mix ===")
    # requests = [
    #     Request(RequestType.WRITE, 0, 1),
    #     Request(RequestType.WRITE, 1, 2),
    #     Request(RequestType.WRITE, 1, 3),
    #     Request(RequestType.READ, 2, 1),
    #     Request(RequestType.READ, 1, 2),
    #     Request(RequestType.WRITE, 1, 3),
    #     Request(RequestType.READ, 1, 2000),
    #     Request(RequestType.WRITE, 1, 2099),
    #     Request(RequestType.READ, 1, 2100),
    # ]


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
    ssd.plot_traces()
    # print(ssd.ftl.mapping)


if __name__ == "__main__":
    # sequential_write(8)
    parallelism()
