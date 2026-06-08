from __future__ import annotations

import json

import pandas as pd

from quant_project_daily.config import project_paths, reset_parquet_output_dir


def read_validated() -> pd.DataFrame:
    paths = project_paths()
    if not paths.validated.exists():
        return pd.DataFrame()
    return pd.read_parquet(paths.validated)


def normalize_daily(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    out["dollar_volume"] = out["close"] * out["volume"]
    return out


def run_normalize() -> dict[str, object]:
    paths = project_paths()
    out = normalize_daily(read_validated())
    reset_parquet_output_dir(paths.normalized)
    if not out.empty:
        out.to_parquet(paths.normalized, engine="pyarrow", partition_cols=["year"], index=False)
    summary = {"rows": int(len(out)), "tickers": int(out["ticker"].nunique()) if not out.empty else 0, "output_path": str(paths.normalized)}
    paths.validation_reports.mkdir(parents=True, exist_ok=True)
    (paths.validation_reports / "normalize_daily_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
