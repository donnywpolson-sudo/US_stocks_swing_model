from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.project_config import ProjectPaths, project_paths


@dataclass(frozen=True)
class GapImpactResult:
    summary: dict[str, object]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_research_status(path: Path) -> pd.DataFrame:
    cols = ["ticker", "date", "model_eligible", "tradable", "year"]
    if not path.exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_parquet(path, columns=cols)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.drop_duplicates(["ticker", "date"], keep="last")


def build_gap_impact(
    gaps: pd.DataFrame,
    research: pd.DataFrame,
    research_summary: dict[str, object],
) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    blockers: list[str] = []
    research_start = pd.Timestamp(research_summary.get("research_start_date", "2010-01-01"))

    if gaps.empty:
        blockers.append("missing_or_empty_split_like_gaps")
        gaps = pd.DataFrame(columns=["ticker", "date", "prev_close", "open", "close", "gap_pct"])
    if research.empty:
        blockers.append("missing_or_empty_research_universe")

    gaps = gaps.copy()
    if "date" in gaps.columns:
        gaps["date"] = pd.to_datetime(gaps["date"], errors="coerce").dt.date
    if "gap_pct" in gaps.columns:
        gaps["abs_gap_pct"] = gaps["gap_pct"].abs()
    else:
        gaps["gap_pct"] = pd.NA
        gaps["abs_gap_pct"] = pd.NA

    joined = gaps.merge(research, on=["ticker", "date"], how="left", indicator=True)
    joined["in_research_dataset"] = joined["_merge"].eq("both")
    joined = joined.drop(columns=["_merge"])
    joined["model_eligible"] = joined["model_eligible"].fillna(False).astype(bool)
    joined["tradable"] = joined["tradable"].fillna(False).astype(bool)
    joined["gap_year"] = pd.to_datetime(joined["date"], errors="coerce").dt.year.astype("Int64")
    joined["before_research_start_date"] = pd.to_datetime(joined["date"], errors="coerce") < research_start

    in_research = joined["in_research_dataset"]
    eligible = joined["model_eligible"]
    ineligible_research = in_research & ~eligible

    by_year = (
        joined.groupby("gap_year", dropna=False)
        .agg(
            split_like_gap_count=("ticker", "size"),
            in_research_dataset_count=("in_research_dataset", "sum"),
            model_eligible_split_like_gap_count=("model_eligible", "sum"),
        )
        .reset_index()
        .rename(columns={"gap_year": "year"})
    )
    by_year["model_ineligible_research_split_like_gap_count"] = (
        by_year["in_research_dataset_count"] - by_year["model_eligible_split_like_gap_count"]
    )
    eligible_by_year = research_summary.get("model_eligible_rows_by_year", {})
    if isinstance(eligible_by_year, dict):
        by_year["research_model_eligible_rows"] = by_year["year"].astype(str).map(eligible_by_year).fillna(0).astype("int64")

    by_ticker = (
        joined.groupby("ticker", dropna=False)
        .agg(
            split_like_gap_count=("ticker", "size"),
            in_research_dataset_count=("in_research_dataset", "sum"),
            model_eligible_split_like_gap_count=("model_eligible", "sum"),
        )
        .reset_index()
    )
    by_ticker["model_ineligible_research_split_like_gap_count"] = (
        by_ticker["in_research_dataset_count"] - by_ticker["model_eligible_split_like_gap_count"]
    )
    by_ticker = by_ticker.sort_values(
        ["split_like_gap_count", "model_eligible_split_like_gap_count", "ticker"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    largest = joined.sort_values(["abs_gap_pct", "ticker", "date"], ascending=[False, True, True]).reset_index(drop=True)

    research_gap_count = int(in_research.sum())
    model_ineligible_count = int(ineligible_research.sum())
    summary = {
        "total_split_like_gaps_input": int(len(gaps)),
        "split_like_gaps_inside_research_dataset": research_gap_count,
        "split_like_gaps_before_research_start_date": int(joined["before_research_start_date"].sum()),
        "split_like_gaps_model_eligible_true": int((in_research & eligible).sum()),
        "split_like_gaps_model_eligible_false": model_ineligible_count,
        "pct_research_window_split_like_gaps_not_model_eligible": (
            model_ineligible_count / research_gap_count if research_gap_count else None
        ),
        "top_tickers_by_split_like_gap_count": by_ticker.head(10).to_dict(orient="records"),
        "top_tickers_by_model_eligible_split_like_gap_count": by_ticker.sort_values(
            ["model_eligible_split_like_gap_count", "split_like_gap_count", "ticker"],
            ascending=[False, False, True],
        )
        .head(10)
        .to_dict(orient="records"),
        "blockers": blockers,
    }
    return summary, {
        "with_status": joined,
        "by_year": by_year,
        "by_ticker": by_ticker,
        "largest_abs": largest,
    }


def run_gap_impact_diagnostics(paths: ProjectPaths | None = None) -> GapImpactResult:
    p = paths or project_paths()
    p.validation_reports.mkdir(parents=True, exist_ok=True)

    gaps_path = p.validation_reports / "split_like_gaps.csv"
    summary_path = p.validation_reports / "research_universe_summary.json"
    gaps = _read_csv(gaps_path)
    research = _read_research_status(p.research_ohlcv_daily)
    research_summary = _read_json(summary_path)
    if not summary_path.exists():
        research_summary = {"research_start_date": "2010-01-01"}

    summary, reports = build_gap_impact(gaps, research, research_summary)
    if not gaps_path.exists():
        summary["blockers"].append("missing_split_like_gaps_csv")
    if not p.research_ohlcv_daily.exists():
        summary["blockers"].append("missing_research_ohlcv_daily")
    if not summary_path.exists():
        summary["blockers"].append("missing_research_universe_summary_json")

    reports["with_status"].to_csv(p.validation_reports / "split_like_gaps_with_model_status.csv", index=False)
    reports["by_year"].to_csv(p.validation_reports / "split_like_gaps_by_year.csv", index=False)
    reports["by_ticker"].to_csv(p.validation_reports / "split_like_gaps_by_ticker.csv", index=False)
    reports["largest_abs"].to_csv(p.validation_reports / "split_like_gaps_largest_abs.csv", index=False)
    (p.validation_reports / "split_like_gaps_tradable_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return GapImpactResult(summary=summary)
