from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.features_vol_norm_target import run_vol_norm60_target_features


if __name__ == "__main__":
    print(json.dumps(run_vol_norm60_target_features(), indent=2, default=str))
