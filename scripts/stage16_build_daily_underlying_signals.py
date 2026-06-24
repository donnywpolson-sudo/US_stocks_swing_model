from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.daily_underlying_signals import parse_args, run_daily_underlying_signals


if __name__ == "__main__":
    args = parse_args()
    summary = run_daily_underlying_signals(score_date=args.score_date, rebuild_scoring=not args.no_rebuild_scoring)
    print(json.dumps(summary, indent=2, default=str))
