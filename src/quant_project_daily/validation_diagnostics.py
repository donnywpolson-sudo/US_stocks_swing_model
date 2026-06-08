from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from quant_project_daily.config import ProjectPaths, project_paths


@dataclass(frozen=True)
class DiagnosticsResult:
    summary: dict[str, object]


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_errors(manifest: pd.DataFrame) -> pd.DataFrame:
    cols = ["source_file", "error_message"]
    if manifest.empty or "parse_status" not in manifest.columns:
        return pd.DataFrame(columns=cols)
    out = manifest.loc[manifest["parse_status"] != "ok", cols].copy()
    return out.sort_values("source_file").reset_index(drop=True)


def split_like_gaps(validated: pd.DataFrame, persisted: pd.DataFrame | None = None) -> pd.DataFrame:
    cols = ["ticker", "date", "prev_close", "open", "close", "gap_pct"]
    if persisted is not None and not persisted.empty:
        keep = [c for c in cols if c in persisted.columns]
        return persisted[keep].sort_values(["ticker", "date"]).reset_index(drop=True)
    if validated.empty:
        return pd.DataFrame(columns=cols)
    df = validated.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"], kind="mergesort")
    df["prev_close"] = df.groupby("ticker", sort=False)["close"].shift(1)
    ratio = df["open"] / df["prev_close"]
    mask = ((ratio <= 0.55) | (ratio >= 1.8)).fillna(False)
    out = df.loc[mask, ["ticker", "date", "prev_close", "open", "close"]].copy()
    out["date"] = out["date"].dt.date
    out["gap_pct"] = ((out["open"] / out["prev_close"]) - 1.0) * 100.0
    return out[cols].reset_index(drop=True)


def zero_volume_by_ticker(validated: pd.DataFrame, persisted: pd.DataFrame | None = None) -> pd.DataFrame:
    cols = ["ticker", "zero_volume_rows", "total_rows", "zero_volume_pct"]
    if validated.empty:
        return pd.DataFrame(columns=cols)
    total = validated.groupby("ticker", sort=False).size().rename("total_rows")
    if persisted is not None and not persisted.empty and "ticker" in persisted.columns:
        zero = persisted.groupby("ticker", sort=False).size().rename("zero_volume_rows")
    else:
        zero = validated.loc[validated["volume"] == 0].groupby("ticker", sort=False).size().rename("zero_volume_rows")
    out = pd.concat([total, zero], axis=1).fillna(0).reset_index()
    out["zero_volume_rows"] = out["zero_volume_rows"].astype("int64")
    out["total_rows"] = out["total_rows"].astype("int64")
    out["zero_volume_pct"] = out["zero_volume_rows"] / out["total_rows"]
    return out.loc[out["zero_volume_rows"] > 0, cols].sort_values(
        ["zero_volume_rows", "ticker"], ascending=[False, True]
    ).reset_index(drop=True)


def tradable_coverage_by_year(causal: pd.DataFrame) -> pd.DataFrame:
    cols = ["year", "total_rows", "tradable_rows", "tradable_pct"]
    if causal.empty:
        return pd.DataFrame(columns=cols)
    df = causal.copy()
    if "year" not in df.columns:
        df["year"] = pd.to_datetime(df["date"]).dt.year
    out = df.groupby("year", sort=True).agg(total_rows=("ticker", "size"), tradable_rows=("tradable", "sum")).reset_index()
    out["tradable_rows"] = out["tradable_rows"].astype("int64")
    out["tradable_pct"] = out["tradable_rows"] / out["total_rows"]
    return out[cols]


def tradable_coverage_by_ticker(causal: pd.DataFrame) -> pd.DataFrame:
    cols = ["ticker", "total_rows", "tradable_rows", "tradable_pct"]
    if causal.empty:
        return pd.DataFrame(columns=cols)
    out = causal.groupby("ticker", sort=False).agg(total_rows=("ticker", "size"), tradable_rows=("tradable", "sum")).reset_index()
    out["tradable_rows"] = out["tradable_rows"].astype("int64")
    out["tradable_pct"] = out["tradable_rows"] / out["total_rows"]
    return out[cols].sort_values(["tradable_pct", "ticker"]).reset_index(drop=True)


def run_validation_diagnostics(paths: ProjectPaths | None = None) -> DiagnosticsResult:
    p = paths or project_paths()
    p.validation_reports.mkdir(parents=True, exist_ok=True)

    manifest = _read_parquet(p.raw_manifest)
    validated = _read_parquet(p.validated)
    causal = _read_parquet(p.causal)
    persisted_rejected = _read_csv(p.validation_reports / "raw_rejected_rows.csv")
    persisted_zero = _read_csv(p.validation_reports / "raw_zero_volume_rows.csv")
    persisted_splits = _read_csv(p.validation_reports / "raw_split_like_gaps.csv")
    raw_summary = _read_json(p.validation_reports / "raw_validation_summary.json")

    parse_df = parse_errors(manifest)
    rejected_df = persisted_rejected.copy()
    splits_df = split_like_gaps(validated, persisted_splits)
    zero_df = zero_volume_by_ticker(validated, persisted_zero)
    year_df = tradable_coverage_by_year(causal)
    ticker_df = tradable_coverage_by_ticker(causal)

    parse_df.to_csv(p.validation_reports / "parse_errors.csv", index=False)
    rejected_df.to_csv(p.validation_reports / "rejected_rows.csv", index=False)
    splits_df.to_csv(p.validation_reports / "split_like_gaps.csv", index=False)
    zero_df.to_csv(p.validation_reports / "zero_volume_by_ticker.csv", index=False)
    year_df.to_csv(p.validation_reports / "tradable_coverage_by_year.csv", index=False)
    ticker_df.to_csv(p.validation_reports / "tradable_coverage_by_ticker.csv", index=False)

    blockers = []
    stage03_rejected_rows = int(raw_summary.get("rejected_rows", 0) or 0)
    stage03_warnings = raw_summary.get("warning_reasons", {}) if isinstance(raw_summary.get("warning_reasons", {}), dict) else {}
    stage03_zero_volume_rows = int(stage03_warnings.get("zero_volume_bar", 0) or 0)
    if stage03_rejected_rows and not (p.validation_reports / "raw_rejected_rows.csv").exists():
        blockers.append("row_level_rejections_missing_rerun_stage03")
    if stage03_zero_volume_rows and not (p.validation_reports / "raw_zero_volume_rows.csv").exists():
        blockers.append("row_level_zero_volume_warnings_missing_recomputed_from_validated")

    summary = {
        "parse_error_files": int(len(parse_df)),
        "rejected_rows": int(len(rejected_df)),
        "stage03_rejected_rows": stage03_rejected_rows,
        "row_level_rejections_available": bool((p.validation_reports / "raw_rejected_rows.csv").exists()),
        "split_like_gaps": int(len(splits_df)),
        "zero_volume_rows": int(zero_df["zero_volume_rows"].sum()) if not zero_df.empty else 0,
        "stage03_zero_volume_warning_rows": stage03_zero_volume_rows,
        "zero_volume_tickers": int(len(zero_df)),
        "causal_rows": int(len(causal)),
        "tradable_rows": int(causal["tradable"].sum()) if not causal.empty and "tradable" in causal.columns else 0,
        "tradable_years": int(year_df["year"].nunique()) if not year_df.empty else 0,
        "tradable_tickers": int(ticker_df["ticker"].nunique()) if not ticker_df.empty else 0,
        "blockers": blockers,
    }
    (p.validation_reports / "validation_diagnostics_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return DiagnosticsResult(summary=summary)
