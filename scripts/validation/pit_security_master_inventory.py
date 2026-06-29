from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.project_config import ProjectPaths, project_paths


REQUIRED_COLUMNS = (
    "permanent_id",
    "raw_ticker",
    "ticker",
    "security_type",
    "listing_date",
    "delisting_date",
    "ticker_start_date",
    "ticker_end_date",
    "exchange",
    "is_otc",
    "is_common_stock",
    "is_etf",
    "is_etn",
    "is_adr",
    "source",
    "source_asof_date",
)
BOOLEAN_COLUMNS = ("is_otc", "is_common_stock", "is_etf", "is_etn", "is_adr")
DATE_COLUMNS = ("listing_date", "delisting_date", "ticker_start_date", "ticker_end_date", "source_asof_date")
NULLABLE_DATE_COLUMNS = {"delisting_date", "ticker_end_date"}
NON_EMPTY_COLUMNS = ("permanent_id", "raw_ticker", "ticker", "security_type", "listing_date", "ticker_start_date", "exchange", "source", "source_asof_date")
IDENTITY_COLUMNS = ("permanent_id", "ticker", "ticker_start_date")
TRUE_VALUES = {"true", "1", "yes", "y"}
FALSE_VALUES = {"false", "0", "no", "n"}
MODELING_GATE_DECISION = "do_not_run_new_model_work"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _empty_mask(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _parse_date_series(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    return pd.to_datetime(text.mask(text.eq("")), format="%Y-%m-%d", errors="coerce")


def _normalize_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return None


def _coverage_summary(df: pd.DataFrame, paths: ProjectPaths) -> dict[str, Any]:
    raw_symbols = sorted({p.stem.upper() for p in paths.raw_txt.glob("*.txt")}) if paths.raw_txt.exists() else []
    if paths.research_ohlcv_daily.exists():
        try:
            research = pd.read_parquet(paths.research_ohlcv_daily, columns=["ticker"])
            research_symbols = sorted({str(v).upper() for v in research["ticker"].dropna()})
        except Exception:
            research_symbols = []
    else:
        research_symbols = []
    raw_tickers = {str(v).strip().upper() for v in df["raw_ticker"] if str(v).strip()}
    tickers = {str(v).strip().upper() for v in df["ticker"] if str(v).strip()}
    raw_set = set(raw_symbols)
    research_set = set(research_symbols)
    return {
        "metadata_raw_ticker_count": len(raw_tickers),
        "metadata_clean_ticker_count": len(tickers),
        "raw_symbol_source_status": "proven" if raw_symbols else "missing",
        "raw_symbol_count": len(raw_symbols),
        "metadata_raw_tickers_in_raw_count": len(raw_tickers & raw_set) if raw_set else None,
        "metadata_raw_tickers_not_in_raw_count": len(raw_tickers - raw_set) if raw_set else None,
        "raw_symbols_missing_from_metadata_count": len(raw_set - raw_tickers) if raw_set else None,
        "research_symbol_source_status": "proven" if research_symbols else "missing",
        "research_symbol_count": len(research_symbols),
        "metadata_tickers_in_research_count": len(tickers & research_set) if research_set else None,
        "metadata_tickers_not_in_research_count": len(tickers - research_set) if research_set else None,
        "research_symbols_missing_from_metadata_count": len(research_set - tickers) if research_set else None,
    }


def _validate_master(df: pd.DataFrame) -> dict[str, Any]:
    columns = list(df.columns)
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in columns]
    blockers: list[str] = []
    warnings: list[str] = []
    row_count = int(len(df))
    if row_count == 0:
        blockers.append("empty_pit_security_master")
    if missing_columns:
        blockers.append("missing_required_columns")
    non_empty_violations = {col: int(_empty_mask(df[col]).sum()) for col in NON_EMPTY_COLUMNS if col in df.columns and int(_empty_mask(df[col]).sum())}
    if non_empty_violations:
        blockers.append("empty_required_values")
    parsed_dates = {col: _parse_date_series(df[col]) for col in DATE_COLUMNS if col in df.columns}
    date_invalid_counts = {}
    for col, parsed in parsed_dates.items():
        source_empty = _empty_mask(df[col])
        invalid = parsed.isna() & ~source_empty
        if col not in NULLABLE_DATE_COLUMNS:
            invalid = invalid | source_empty
        if int(invalid.sum()):
            date_invalid_counts[col] = int(invalid.sum())
    if date_invalid_counts:
        blockers.append("invalid_date_values")
    boolean_invalid_counts = {col: int(df[col].map(_normalize_bool).isna().sum()) for col in BOOLEAN_COLUMNS if col in df.columns and int(df[col].map(_normalize_bool).isna().sum())}
    if boolean_invalid_counts:
        blockers.append("invalid_boolean_values")
    duplicate_identity_count = int(df.duplicated(list(IDENTITY_COLUMNS), keep=False).sum()) if all(col in df.columns for col in IDENTITY_COLUMNS) else 0
    if duplicate_identity_count:
        blockers.append("duplicate_identity_rows")
    listing_delisting_order_violations = 0
    ticker_interval_order_violations = 0
    if {"listing_date", "delisting_date"} <= parsed_dates.keys():
        listing_delisting_order_violations = int((parsed_dates["delisting_date"].notna() & (parsed_dates["listing_date"] > parsed_dates["delisting_date"])).sum())
    if {"ticker_start_date", "ticker_end_date"} <= parsed_dates.keys():
        ticker_interval_order_violations = int((parsed_dates["ticker_end_date"].notna() & (parsed_dates["ticker_start_date"] > parsed_dates["ticker_end_date"])).sum())
    if listing_delisting_order_violations or ticker_interval_order_violations:
        blockers.append("reversed_date_intervals")
    delisted_row_count = int((~_empty_mask(df["delisting_date"])).sum()) if "delisting_date" in df.columns else 0
    if row_count and not delisted_row_count:
        warnings.append("no_delisting_dates_present")
    return {
        "row_count": row_count,
        "columns": columns,
        "missing_columns": missing_columns,
        "extra_columns": [col for col in columns if col not in REQUIRED_COLUMNS],
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "non_empty_violations": non_empty_violations,
        "date_invalid_counts": date_invalid_counts,
        "boolean_invalid_counts": boolean_invalid_counts,
        "duplicate_identity_row_count": duplicate_identity_count,
        "listing_delisting_order_violations": listing_delisting_order_violations,
        "ticker_interval_order_violations": ticker_interval_order_violations,
        "delisted_row_count": delisted_row_count,
        "source_count": int(df["source"].replace("", pd.NA).dropna().nunique()) if "source" in df.columns else 0,
        "source_asof_date_count": int(df["source_asof_date"].replace("", pd.NA).dropna().nunique()) if "source_asof_date" in df.columns else 0,
    }


def build_pit_security_master_inventory(paths: ProjectPaths | None = None, *, generated_at_utc: str | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    root = p.repo_root
    input_path = root / "data" / "reference" / "pit_security_master.csv"
    if input_path.exists():
        df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
        validation = _validate_master(df)
        coverage = _coverage_summary(df, p) if not validation["missing_columns"] else {}
    else:
        validation = {"row_count": 0, "columns": [], "missing_columns": list(REQUIRED_COLUMNS), "extra_columns": [], "blockers": ["missing_input_file"], "warnings": [], "non_empty_violations": {}, "date_invalid_counts": {}, "boolean_invalid_counts": {}, "duplicate_identity_row_count": 0, "listing_delisting_order_violations": 0, "ticker_interval_order_violations": 0, "delisted_row_count": 0, "source_count": 0, "source_asof_date_count": 0}
        coverage = {}
    pit_status = "missing" if not input_path.exists() else ("unverified" if validation["blockers"] or validation["row_count"] == 0 else "proven")
    survivorship = "proven" if pit_status == "proven" and validation["delisted_row_count"] > 0 else ("missing" if not input_path.exists() else "unverified")
    return {
        "generated_at_utc": generated_at_utc or _utc_now(),
        "input_path": _rel(input_path, root),
        "input_exists": input_path.exists(),
        "accepted_input": "data/reference/pit_security_master.csv",
        "required_columns": list(REQUIRED_COLUMNS),
        "status_summary": {"pit_security_metadata": pit_status, "survivorship_delisting_coverage": survivorship, "modeling_gate_decision": MODELING_GATE_DECISION},
        "validation": validation,
        "coverage_summary": coverage,
    }


def build_pit_security_master_markdown(inventory: dict[str, Any]) -> str:
    status = inventory["status_summary"]
    validation = inventory["validation"]
    return "\n".join(
        [
            "# PIT Security Master Inventory",
            "",
            "This is a research-ready and walk-forward-ready inventory for the active h5 / 5d pipeline. It is not investment advice and does not imply profitability, option liquidity, option P&L, paper readiness, production readiness, or live-trading readiness.",
            "",
            f"- PIT security metadata status: `{status['pit_security_metadata']}`.",
            f"- Survivorship/delisting coverage status: `{status['survivorship_delisting_coverage']}`.",
            "- Preserve h5 / 5d timing: prediction after the completed daily bar, entry at `next_open`, and exit at `exit_close_5d`.",
            f"- Rows: {validation['row_count']}",
        ]
    ) + "\n"


def write_pit_security_master_inventory(paths: ProjectPaths | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    inventory = build_pit_security_master_inventory(p)
    audit_dir = p.repo_root / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / "pit_security_master_inventory.json"
    md_path = audit_dir / "pit_security_master_inventory.md"
    json_path.write_text(json.dumps(inventory, indent=2, default=str), encoding="utf-8")
    md_path.write_text(build_pit_security_master_markdown(inventory), encoding="utf-8")
    return {
        "artifacts": {"json": str(json_path), "markdown": str(md_path)},
        "modeling_gate_decision": MODELING_GATE_DECISION,
        "pit_security_metadata_status": inventory["status_summary"]["pit_security_metadata"],
        "survivorship_delisting_coverage_status": inventory["status_summary"]["survivorship_delisting_coverage"],
        "blockers": inventory["validation"]["blockers"],
    }
