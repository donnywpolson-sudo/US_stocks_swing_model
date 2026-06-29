from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase4_features.features_baseline import run_baseline_features


if __name__ == "__main__":
    print(json.dumps(run_baseline_features(), indent=2, default=str))
