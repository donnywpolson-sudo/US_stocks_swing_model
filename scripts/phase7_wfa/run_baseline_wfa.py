from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase7_wfa.baseline_wfa import parse_args, run_baseline_wfa


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run_baseline_wfa(max_folds=args.max_folds, fold_id=args.fold_id), indent=2, default=str))
