from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase1B_convert.raw_parquet_export import run_raw_parquet_export


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export raw Stooq txt OHLCV and Alpha Vantage supplemental listing status to parquet."
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional raw txt file limit for smoke tests.")
    parser.add_argument("--progress-every", type=int, default=250)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    print(json.dumps(run_raw_parquet_export(limit=args.limit, progress_every=args.progress_every), indent=2, default=str))
