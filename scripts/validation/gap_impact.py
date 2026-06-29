from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.validation.gap_impact_diagnostics import run_gap_impact_diagnostics


if __name__ == "__main__":
    print(json.dumps(run_gap_impact_diagnostics().summary, indent=2, default=str))
