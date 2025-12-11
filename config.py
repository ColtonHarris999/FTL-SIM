from typing import Any, Dict
import yaml
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("configurations/default_config.yaml")

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