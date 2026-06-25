from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.targets_vol_norm import run_vol_norm60_targets


if __name__ == "__main__":
    print(json.dumps(run_vol_norm60_targets(), indent=2, default=str))
