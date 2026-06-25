from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.features_vol_norm_target import run_vol_norm60_target_wfa


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
            run_vol_norm60_target_wfa(
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
