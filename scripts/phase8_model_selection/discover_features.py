from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase8_model_selection.feature_discovery import parse_args, run_feature_discovery


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run_feature_discovery(max_folds=args.max_folds, fold_id=args.fold_id), indent=2, default=str))
