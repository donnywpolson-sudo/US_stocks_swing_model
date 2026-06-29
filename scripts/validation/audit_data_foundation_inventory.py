from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.data_foundation_inventory import write_data_foundation_inventory


if __name__ == "__main__":
    print(json.dumps(write_data_foundation_inventory(), indent=2, default=str))
