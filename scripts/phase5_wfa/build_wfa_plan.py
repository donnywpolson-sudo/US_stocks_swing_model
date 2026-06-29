from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase5_wfa.wfa_splits import run_wfa_plan


if __name__ == "__main__":
    print(json.dumps(run_wfa_plan(), indent=2, default=str))
