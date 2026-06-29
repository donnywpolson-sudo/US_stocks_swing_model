from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase4_features.column_registry import write_column_registry


if __name__ == "__main__":
    print(json.dumps(write_column_registry(), indent=2))
