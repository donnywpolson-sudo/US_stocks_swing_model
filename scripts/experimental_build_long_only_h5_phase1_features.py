from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.features_long_only_phase1 import run_long_only_h5_phase1_features


if __name__ == "__main__":
    print(json.dumps(run_long_only_h5_phase1_features(), indent=2, default=str))
