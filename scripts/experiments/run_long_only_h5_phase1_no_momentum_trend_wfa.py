from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase9_research.features_long_only_phase1 import run_long_only_h5_feature_set_wfa


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--fold-id", type=int, default=None)
    parser.add_argument("--start-fold", type=int, default=None)
    parser.add_argument("--end-fold", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(
        json.dumps(
            run_long_only_h5_feature_set_wfa(
                "long_only_h5_phase1_no_momentum_trend",
                max_folds=args.max_folds,
                fold_id=args.fold_id,
                start_fold=args.start_fold,
                end_fold=args.end_fold,
                resume=args.resume,
            ),
            indent=2,
            default=str,
        )
    )
