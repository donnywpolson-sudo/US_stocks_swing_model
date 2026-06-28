from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_project_daily.audit_remediation import run_audit_remediation


if __name__ == "__main__":
    print(json.dumps(run_audit_remediation(), indent=2, default=str))
