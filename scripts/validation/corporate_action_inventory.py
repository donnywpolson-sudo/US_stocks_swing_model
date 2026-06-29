from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.project_config import ProjectPaths, project_paths


REQUIRED_EVENT_COLUMNS = ("raw_ticker", "ticker", "event_date", "action_type", "source", "source_asof_date")
OPTIONAL_EVENT_COLUMNS = ("ex_date", "record_date", "pay_date", "split_ratio", "cash_amount", "currency", "distribution_type", "adjustment_factor")
POLICY_REQUIRED_FIELDS = (
    "source",
    "source_asof_date",
    "ohlcv_source",
    "price_adjustment_policy",
    "volume_adjustment_policy",
    "split_adjustment_status",
    "dividend_adjustment_status",
    "distribution_adjustment_status",
    "official_documentation_reference",
)
DATE_COLUMNS = ("event_date", "source_asof_date", "ex_date", "record_date", "pay_date")
NUMERIC_COLUMNS = ("cash_amount", "adjustment_factor")
SUPPORTED_ACTION_TYPES = {"split", "cash_dividend", "stock_dividend", "distribution", "merger", "spinoff"}
MODELING_GATE_DECISION = "do_not_run_new_model_work"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _parse_date(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    return pd.to_datetime(text.mask(text.eq("")), format="%Y-%m-%d", errors="coerce")


def _read_symbols(paths: ProjectPaths) -> tuple[set[str], set[str]]:
    raw = {p.stem.upper() for p in paths.raw_txt.glob("*.txt")} if paths.raw_txt.exists() else set()
    if paths.research_ohlcv_daily.exists():
        try:
            research = {str(v).upper() for v in pd.read_parquet(paths.research_ohlcv_daily, columns=["ticker"])["ticker"].dropna()}
        except Exception:
            research = set()
    else:
        research = set()
    return raw, research


def _validate_events(path: Path) -> tuple[dict[str, Any], pd.DataFrame | None]:
    if not path.exists():
        return {"row_count": 0, "columns": [], "missing_columns": list(REQUIRED_EVENT_COLUMNS), "blockers": ["missing_input_file"], "warnings": [], "source_count": 0, "numeric_invalid_counts": {}, "date_invalid_counts": {}}, None
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [col for col in REQUIRED_EVENT_COLUMNS if col not in df.columns]
    blockers: list[str] = []
    if missing:
        blockers.append("missing_required_columns")
    non_empty = {col: int(_empty_mask(df[col]).sum()) for col in REQUIRED_EVENT_COLUMNS if col in df.columns and int(_empty_mask(df[col]).sum())}
    if non_empty:
        blockers.append("empty_required_values")
    date_invalid = {}
    for col in DATE_COLUMNS:
        if col in df.columns:
            invalid = _parse_date(df[col]).isna() & ~_empty_mask(df[col])
            if col in REQUIRED_EVENT_COLUMNS:
                invalid = invalid | _empty_mask(df[col])
            if int(invalid.sum()):
                date_invalid[col] = int(invalid.sum())
    if date_invalid:
        blockers.append("invalid_date_values")
    numeric_invalid = {}
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            text = df[col].astype(str).str.strip()
            numeric = pd.to_numeric(text.mask(text.eq("")), errors="coerce")
            invalid = numeric.notna() & (numeric <= 0)
            invalid = invalid | (numeric.isna() & ~text.eq(""))
            if int(invalid.sum()):
                numeric_invalid[col] = int(invalid.sum())
    if "split_ratio" in df.columns:
        invalid_split = df["split_ratio"].astype(str).str.strip().eq("0")
        if int(invalid_split.sum()):
            numeric_invalid["split_ratio"] = int(invalid_split.sum())
    if numeric_invalid:
        blockers.append("invalid_numeric_values")
    if "action_type" in df.columns:
        unsupported = ~df["action_type"].astype(str).str.strip().str.lower().isin(SUPPORTED_ACTION_TYPES)
        if int(unsupported.sum()):
            blockers.append("unsupported_action_types")
    return {
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "missing_columns": missing,
        "blockers": sorted(set(blockers)),
        "warnings": [],
        "source_count": int(df["source"].replace("", pd.NA).dropna().nunique()) if "source" in df.columns else 0,
        "numeric_invalid_counts": numeric_invalid,
        "date_invalid_counts": date_invalid,
    }, df


def _validate_policy(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"blockers": ["missing_policy_file"], "missing_fields": list(POLICY_REQUIRED_FIELDS), "empty_fields": [], "invalid_date_fields": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    missing = [field for field in POLICY_REQUIRED_FIELDS if field not in payload]
    empty = [field for field in POLICY_REQUIRED_FIELDS if field in payload and str(payload.get(field, "")).strip() == ""]
    invalid_date = []
    if "source_asof_date" in payload:
        try:
            datetime.strptime(str(payload["source_asof_date"]), "%Y-%m-%d")
        except ValueError:
            invalid_date.append("source_asof_date")
    blockers = []
    if missing:
        blockers.append("missing_policy_fields")
    if empty:
        blockers.append("empty_policy_fields")
    if invalid_date:
        blockers.append("invalid_policy_date_values")
    return {"blockers": blockers, "missing_fields": missing, "empty_fields": empty, "invalid_date_fields": invalid_date}


def build_corporate_action_inventory(paths: ProjectPaths | None = None, *, generated_at_utc: str | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    root = p.repo_root
    events_path = root / "data" / "reference" / "corporate_actions.csv"
    policy_path = root / "data" / "reference" / "ohlcv_adjustment_policy.json"
    events_validation, events_df = _validate_events(events_path)
    policy_validation = _validate_policy(policy_path)
    event_status = "missing" if not events_path.exists() else ("unverified" if events_validation["blockers"] else "proven")
    policy_status = "missing" if not policy_path.exists() else ("unverified" if policy_validation["blockers"] else "proven")
    adjustment_status = "proven" if event_status == "proven" and policy_status == "proven" else "accepted_limitation"
    raw_symbols, research_symbols = _read_symbols(p)
    coverage = {}
    if events_df is not None and {"raw_ticker", "ticker"} <= set(events_df.columns):
        event_raw = {str(v).strip().upper() for v in events_df["raw_ticker"] if str(v).strip()}
        event_tickers = {str(v).strip().upper() for v in events_df["ticker"] if str(v).strip()}
        coverage = {
            "event_raw_tickers_in_raw_count": len(event_raw & raw_symbols),
            "event_tickers_in_research_count": len(event_tickers & research_symbols),
            "research_symbols_missing_from_events_count": len(research_symbols - event_tickers),
        }
    split_status = "proven" if (p.validation_reports / "raw_split_like_gaps.csv").exists() else "missing"
    h5_status = "proven" if (p.label_reports / "target_h5_summary.json").exists() else "missing"
    items = [
        {"id": "h5_target_window_invalidation_mechanics", "status": h5_status, "implication": "Split-like h5 invalidation is mechanics only, not corporate-action adjustment proof."},
        {"id": "corporate_action_adjustment_proof_sufficiency", "status": adjustment_status, "implication": "Event rows and heuristic split detection do not prove OHLCV adjustment policy without official policy evidence."},
    ]
    return {
        "generated_at_utc": generated_at_utc or _utc_now(),
        "accepted_inputs": {"corporate_actions": "data/reference/corporate_actions.csv", "ohlcv_adjustment_policy": "data/reference/ohlcv_adjustment_policy.json"},
        "modeling_gate_decision": MODELING_GATE_DECISION,
        "status_summary": {
            "corporate_action_events": event_status,
            "ohlcv_adjustment_policy": policy_status,
            "corporate_action_adjustment_proof": adjustment_status,
            "split_like_gap_detection": split_status,
            "h5_target_window_invalidation": h5_status,
        },
        "validation": {"corporate_actions": events_validation, "ohlcv_adjustment_policy": policy_validation},
        "coverage_summary": coverage,
        "inventory_items": items,
    }


def build_corporate_action_markdown(inventory: dict[str, Any]) -> str:
    status = inventory["status_summary"]
    return "\n".join(
        [
            "# Corporate Action Inventory",
            "",
            "This is a research-ready and walk-forward-ready inventory for the active h5 / 5d daily OHLCV pipeline. It is not investment advice and does not imply profitability, option liquidity, option P&L, paper readiness, production readiness, or live-trading readiness.",
            "",
            f"- Corporate-action events: `{status['corporate_action_events']}`.",
            f"- OHLCV adjustment policy: `{status['ohlcv_adjustment_policy']}`.",
            "- Preserve timing: prediction after completed bar, entry at `next_open`, exit at `exit_close_5d`.",
        ]
    ) + "\n"


def write_corporate_action_inventory(paths: ProjectPaths | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    inventory = build_corporate_action_inventory(p)
    audit_dir = p.repo_root / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / "corporate_action_inventory.json"
    md_path = audit_dir / "corporate_action_inventory.md"
    json_path.write_text(json.dumps(inventory, indent=2, default=str), encoding="utf-8")
    md_path.write_text(build_corporate_action_markdown(inventory), encoding="utf-8")
    return {
        "artifacts": {"json": str(json_path), "markdown": str(md_path)},
        "modeling_gate_decision": MODELING_GATE_DECISION,
        "corporate_action_events_status": inventory["status_summary"]["corporate_action_events"],
        "ohlcv_adjustment_policy_status": inventory["status_summary"]["ohlcv_adjustment_policy"],
        "corporate_action_adjustment_proof_status": inventory["status_summary"]["corporate_action_adjustment_proof"],
        "event_blockers": inventory["validation"]["corporate_actions"]["blockers"],
        "policy_blockers": inventory["validation"]["ohlcv_adjustment_policy"]["blockers"],
    }
