from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.column_registry import write_column_registry


if __name__ == "__main__":
    print(json.dumps(write_column_registry(), indent=2))
