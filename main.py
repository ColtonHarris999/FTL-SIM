from random import Random
from request import Request, RequestType
from simulator import SSDSimulator
from scheduler import FIFOScheduler, NaiveReadScheduler

if __name__ == "__main__":
    scheduler = FIFOScheduler()
    ssd = SSDSimulator(scheduler=scheduler, ncq_size=32)

    print("=== Example 1: Synchronous reads ===")
    requests = [Request(RequestType.READ, i, 0) for i in range(10)]
    ssd.reset()
    ssd.run_simulation(requests)

    print("=== Example 2: Staggered reads ===")
    requests = [Request(RequestType.READ, i, 20 * i) for i in range(10)]
    ssd.reset()
    ssd.run_simulation(requests)

    print("=== Example 3: Read/write mix ===")
    requests = [
        Request(Random().choice([RequestType.READ, RequestType.WRITE]), i % 2, 0)
        for i in range(10)
    ]
    ssd.reset()
    ssd.run_simulation(requests)

    print("=== Example 4: Read/write mix ===")
    requests = [
        Request(RequestType.WRITE, 0, 0),
        Request(RequestType.READ, 0, 0),
        Request(RequestType.READ, 1, 0),
        Request(RequestType.WRITE, 1, 0),
        Request(RequestType.READ, 1, 0),
        Request(RequestType.READ, 2, 0),
    ]
    ssd.reset()
    ssd.run_simulation(requests)
