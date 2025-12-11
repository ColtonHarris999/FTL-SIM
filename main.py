from random import sample

from request import Request, RequestType
from simulator import SSDSimulator
from pathlib import Path
from typing import Any, Dict
import yaml
import argparse

DEFAULT_CONFIG_PATH = Path("configurations/default_config.yaml")

SSD = None # type: SSDSimulator | None

def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """
    Load the simulator configuration from a YAML file and store it
    in the global CONFIG dict. Returns the loaded config.
    """
    CONFIG: Dict[str, Any] = {}
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        CONFIG = yaml.safe_load(f) or {}
    return CONFIG



def sequential_write(size: int):
    print("Running sequential write test...")
    ssd = SSD

    writes = [Request(RequestType.WRITE, i, 0) for i in range(size)]
    ssd.run_simulation(writes)

    ssd.print_statistics()


def random_write(size: int):
    print("Running random write test...")
    ssd = SSD

    max_lba = ssd.ftl.get_max_lba()

    random_lbas = sample(range(max_lba), k=size)

    writes = [Request(RequestType.WRITE, lba, 0) for lba in random_lbas]
    ssd.run_simulation(writes)

    ssd.print_statistics()


def parallelism():
    print("Running parallelism test...")
    ssd = SSD

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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c", "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to YAML config file (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    SSD = SSDSimulator(config)
    # sequential_write(1000)
    random_write(50)
    # parallelism()
