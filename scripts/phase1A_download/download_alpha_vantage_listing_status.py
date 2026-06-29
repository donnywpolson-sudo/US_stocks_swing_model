from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.phase1A_download.alpha_vantage_listing_status import (
    ALLOWED_STATES,
    DEFAULT_OUTPUT_PATH,
    download_alpha_vantage_listing_status,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Alpha Vantage LISTING_STATUS as supplemental survivorship evidence."
    )
    parser.add_argument("--api-key", default=os.environ.get("ALPHAVANTAGE_API_KEY", ""))
    parser.add_argument("--date", default=None, help="Optional YYYY-MM-DD historical query date, supported after 2010-01-01 by Alpha Vantage.")
    parser.add_argument("--state", choices=(*ALLOWED_STATES, "both"), default="both")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--pause-seconds", type=float, default=15.0, help="Pause between active/delisted requests to respect free-tier pacing.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if not args.api_key.strip():
        raise SystemExit("Set ALPHAVANTAGE_API_KEY or pass --api-key. Do not commit API keys.")
    states = ALLOWED_STATES if args.state == "both" else (args.state,)
    result = download_alpha_vantage_listing_status(
        args.api_key,
        states=states,
        query_date=args.date,
        output_path=args.output,
        pause_seconds=args.pause_seconds,
    )
    print(json.dumps(result, indent=2))
