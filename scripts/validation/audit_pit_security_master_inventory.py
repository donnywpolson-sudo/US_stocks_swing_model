from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.pit_security_master_inventory import write_pit_security_master_inventory


if __name__ == "__main__":
    print(json.dumps(write_pit_security_master_inventory(), indent=2, default=str))
