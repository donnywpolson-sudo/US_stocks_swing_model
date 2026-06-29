from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import pandas as pd

from scripts.project_config import ProjectPaths, load_project_config, project_paths, reset_parquet_output_dir


@dataclass(frozen=True)
class ResearchUniverseResult:
    data: pd.DataFrame
    summary: dict[str, object]


def read_causal(paths: ProjectPaths | None = None) -> pd.DataFrame:
    p = paths or project_paths()
    if not p.causal.exists():
        return pd.DataFrame()
    return pd.read_parquet(p.causal)


def build_research_universe(
    causal: pd.DataFrame,
    *,
    warmup_start_date: str | date = "2009-01-01",
    research_start_date: str | date = "2010-01-01",
) -> ResearchUniverseResult:
    warmup_start = pd.Timestamp(warmup_start_date)
    research_start = pd.Timestamp(research_start_date)

    if causal.empty:
        out = causal.copy()
        out["model_eligible"] = pd.Series(dtype=bool)
    else:
        out = causal.copy()
        out["date"] = pd.to_datetime(out["date"])
        total_rows = len(out)
        out = out.loc[out["date"] >= warmup_start].copy()
        out = out.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
        out["year"] = out["date"].dt.year.astype("int64")
        out["model_eligible"] = (out["date"] >= research_start) & (out["tradable"] == True)
        out["date"] = out["date"].dt.date
        summary_total_rows = total_rows
    if causal.empty:
        summary_total_rows = 0

    rows_by_year = out.groupby("year", sort=True).size().astype(int).to_dict() if not out.empty else {}
    eligible_by_year = (
        out.loc[out["model_eligible"]].groupby("year", sort=True).size().astype(int).to_dict() if not out.empty else {}
    )
    summary = {
        "warmup_start_date": str(pd.Timestamp(warmup_start).date()),
        "research_start_date": str(pd.Timestamp(research_start).date()),
        "total_input_rows": int(summary_total_rows),
        "rows_kept": int(len(out)),
        "rows_dropped_before_warmup_start_date": int(summary_total_rows - len(out)),
        "model_eligible_rows": int(out["model_eligible"].sum()) if not out.empty else 0,
        "tickers_kept": int(out["ticker"].nunique()) if not out.empty else 0,
        "model_eligible_tickers": int(out.loc[out["model_eligible"], "ticker"].nunique()) if not out.empty else 0,
        "rows_by_year": {str(k): int(v) for k, v in rows_by_year.items()},
        "model_eligible_rows_by_year": {str(k): int(v) for k, v in eligible_by_year.items()},
    }
    return ResearchUniverseResult(data=out, summary=summary)


def run_research_universe(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_project_config()["research_universe"]
    result = build_research_universe(read_causal(p), **cfg)

    reset_parquet_output_dir(p.research_ohlcv_daily)
    if not result.data.empty:
        result.data.to_parquet(p.research_ohlcv_daily, engine="pyarrow", partition_cols=["year"], index=False)

    p.validation_reports.mkdir(parents=True, exist_ok=True)
    (p.validation_reports / "research_universe_summary.json").write_text(
        json.dumps(result.summary, indent=2, default=str),
        encoding="utf-8",
    )
    return result.summary
