from random import Random

from request import Request, RequestType
from simulator import SSDSimulator

if __name__ == "__main__":
    ssd = SSDSimulator()

    print("=== Example 1: Synchronous reads ===")
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

    print("=== Example 4: Read/write mix ===")
    requests = (
        [
            Request(RequestType.WRITE, 0, 1),
            Request(RequestType.WRITE, 1, 2),
            Request(RequestType.WRITE, 1, 3),
            Request(RequestType.READ, 2, 1),
            Request(RequestType.READ, 1, 2),
            Request(RequestType.WRITE, 1, 3),
            Request(RequestType.READ, 1, 2000),
            Request(RequestType.WRITE, 1, 2099),
            Request(RequestType.READ, 1, 2100),
        ]
        + [Request(RequestType.WRITE, i % 4, i * 10) for i in range(8)]
        + [Request(RequestType.READ, i % 4, i * 10 + 5) for i in range(8)]
    )
    ssd.run_simulation(requests)
    ssd.print_statistics()
