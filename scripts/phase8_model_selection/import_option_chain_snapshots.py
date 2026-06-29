from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

from scripts.phase8_model_selection.option_chain_snapshots import (
    import_option_chain_manifest,
    import_option_chain_snapshot,
    parse_args,
)


if __name__ == "__main__":
    args = parse_args()
    if args.manifest:
        summary = import_option_chain_manifest(args.manifest, candidates_path=args.candidates_path)
    else:
        summary = import_option_chain_snapshot(args.input_csv, candidates_path=args.candidates_path)
    print(json.dumps(summary, indent=2, default=str))
