from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.metrics import run_metrics


if __name__ == "__main__":
    print(json.dumps(run_metrics(), indent=2, default=str))
