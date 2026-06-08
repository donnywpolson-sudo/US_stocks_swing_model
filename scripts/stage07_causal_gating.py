from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.causal_gating import run_causal_gating


if __name__ == "__main__":
    print(json.dumps(run_causal_gating(), indent=2))
