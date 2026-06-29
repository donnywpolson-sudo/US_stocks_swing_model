from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase3_labels.targets import run_targets


if __name__ == "__main__":
    print(json.dumps(run_targets(), indent=2, default=str))
