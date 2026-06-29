from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.corporate_action_inventory import write_corporate_action_inventory


if __name__ == "__main__":
    print(json.dumps(write_corporate_action_inventory(), indent=2, default=str))
