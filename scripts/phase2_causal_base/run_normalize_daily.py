from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase2_causal_base.normalize_daily import run_normalize


if __name__ == "__main__":
    print(json.dumps(run_normalize(), indent=2))
