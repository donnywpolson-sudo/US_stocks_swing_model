from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from quant_project_daily.config import ProjectPaths, load_project_config, project_paths, reset_parquet_output_dir


OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "raw_ticker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "dollar_volume",
    "model_eligible",
    "next_open",
    "exit_close_5d",
    "exit_date_5d",
    "fwd_ret_5d",
    "has_split_like_gap_in_target_window_5d",
    "label_valid_5d",
    "target_class_5d",
    "target_long_top20_5d",
    "target_short_bottom20_5d",
]


@dataclass(frozen=True)
class TargetResult:
    data: pd.DataFrame
    summary: dict[str, object]
    by_year: pd.DataFrame
    by_date: pd.DataFrame


def _read_research(path: Path) -> pd.DataFrame:
    columns = [
        "date",
        "ticker",
        "raw_ticker",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "dollar_volume",
        "model_eligible",
    ]
    if not path.exists():
        return pd.DataFrame(columns=columns)
    return pd.read_parquet(path, columns=columns)


def _read_split_gaps(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame(columns=["ticker", "date"])
    gaps = pd.read_csv(path, usecols=lambda c: c in {"ticker", "date"})
    gaps["date"] = pd.to_datetime(gaps["date"], errors="coerce").dt.date
    return gaps.dropna(subset=["ticker", "date"]).drop_duplicates(["ticker", "date"])


def _future_window_any(s: pd.Series, horizon_days: int) -> pd.Series:
    return (
        s.iloc[::-1]
        .shift(1)
        .rolling(horizon_days, min_periods=1)
        .max()
        .iloc[::-1]
        .fillna(False)
        .astype(bool)
    )


def _assign_date_classes(returns: pd.Series, quantile: float) -> pd.Series:
    out = pd.Series(0, index=returns.index, dtype="int8")
    n = len(returns)
    bucket_n = int(np.floor(n * quantile))
    if n < 5 or bucket_n < 1:
        return out
    ordered = returns.sort_values(kind="mergesort")
    out.loc[ordered.index[:bucket_n]] = -1
    out.loc[ordered.index[-bucket_n:]] = 1
    return out


def generate_targets(
    research: pd.DataFrame,
    split_gaps: pd.DataFrame,
    *,
    research_start_date: str = "2010-01-01",
    horizon_days: int = 5,
    top_bottom_quantile: float = 0.20,
    excluded_tickers: list[str] | tuple[str, ...] = ("ZVZZT",),
) -> TargetResult:
    if research.empty:
        empty = pd.DataFrame(columns=OUTPUT_COLUMNS)
        summary = {
            "total_rows": 0,
            "label_valid_rows": 0,
            "invalid_reason_counts_are_overlapping": True,
            "invalid_reason_counts": {},
            "mutually_exclusive_invalid_reason_counts": {},
            "class_counts": {},
            "date_count": 0,
            "min_date": None,
            "max_date": None,
            "excluded_ticker_rows": 0,
            "otherwise_valid_rows_invalidated_by_split_like_target_window_gaps": 0,
            "rows_invalidated_by_split_like_target_window_gaps": 0,
        }
        return TargetResult(empty, summary, pd.DataFrame(), pd.DataFrame())

    df = research.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df["model_eligible"] = df["model_eligible"].fillna(False).astype(bool)

    grp = df.groupby("ticker", sort=False)
    df["next_open"] = grp["open"].shift(-1)
    df["exit_close_5d"] = grp["close"].shift(-horizon_days)
    df["exit_date_5d"] = grp["date"].shift(-horizon_days)
    df["fwd_ret_5d"] = (df["exit_close_5d"] / df["next_open"]) - 1.0

    if split_gaps.empty:
        df["_split_gap_row"] = False
    else:
        gaps = split_gaps.copy()
        gaps["ticker"] = gaps["ticker"].astype(str).str.upper()
        gaps["date"] = pd.to_datetime(gaps["date"], errors="coerce")
        gaps["_split_gap_row"] = True
        df = df.merge(gaps[["ticker", "date", "_split_gap_row"]], on=["ticker", "date"], how="left")
        df["_split_gap_row"] = df["_split_gap_row"].fillna(False).astype(bool)

    df["has_split_like_gap_in_target_window_5d"] = (
        df.groupby("ticker", sort=False)["_split_gap_row"].transform(lambda s: _future_window_any(s, horizon_days))
    )

    research_start = pd.Timestamp(research_start_date)
    excluded = {t.upper() for t in excluded_tickers}
    is_pre_research = df["date"] < research_start
    is_non_model = ~df["model_eligible"]
    is_missing_future = df["next_open"].isna() | df["exit_close_5d"].isna()
    is_excluded = df["ticker"].isin(excluded)
    has_split_window = df["has_split_like_gap_in_target_window_5d"]

    df["label_valid_5d"] = ~(is_pre_research | is_non_model | is_missing_future | is_excluded | has_split_window)

    df["target_class_5d"] = 0
    valid_idx = df["label_valid_5d"]
    if valid_idx.any():
        classes = df.loc[valid_idx].groupby("date", group_keys=False)["fwd_ret_5d"].apply(
            lambda s: _assign_date_classes(s, top_bottom_quantile)
        )
        df.loc[classes.index, "target_class_5d"] = classes.astype("int8")

    df["target_long_top20_5d"] = df["target_class_5d"].eq(1)
    df["target_short_bottom20_5d"] = df["target_class_5d"].eq(-1)
    df["_valid_target_class"] = df["target_class_5d"].where(df["label_valid_5d"])
    df["exit_date_5d"] = pd.to_datetime(df["exit_date_5d"]).dt.date
    df["year"] = df["date"].dt.year.astype("int64")
    df["date"] = df["date"].dt.date

    invalid_reason_counts = {
        "before_research_start_date": int(is_pre_research.sum()),
        "non_model_eligible": int(is_non_model.sum()),
        "missing_next_open_or_exit_close_5d": int(is_missing_future.sum()),
        "excluded_ticker": int(is_excluded.sum()),
        "split_like_gap_in_target_window_5d": int(has_split_window.sum()),
    }
    mutually_exclusive_invalid_reason_counts = {
        "before_research_start_date": int(is_pre_research.sum()),
        "excluded_ticker": int((~is_pre_research & is_excluded).sum()),
        "non_model_eligible": int((~is_pre_research & ~is_excluded & is_non_model).sum()),
        "missing_next_open_or_exit_close_5d": int(
            (~is_pre_research & ~is_excluded & ~is_non_model & is_missing_future).sum()
        ),
        "split_like_gap_in_target_window_5d": int(
            (~is_pre_research & ~is_excluded & ~is_non_model & ~is_missing_future & has_split_window).sum()
        ),
    }
    split_invalidated = ~(is_pre_research | is_non_model | is_missing_future | is_excluded) & has_split_window

    by_year = (
        df.groupby("year", sort=True)
        .agg(
            total_rows=("ticker", "size"),
            label_valid_rows=("label_valid_5d", "sum"),
            class_neg1=("_valid_target_class", lambda s: int((s == -1).sum())),
            class_0=("_valid_target_class", lambda s: int((s == 0).sum())),
            class_pos1=("_valid_target_class", lambda s: int((s == 1).sum())),
        )
        .reset_index()
    )
    by_date = (
        df.groupby("date", sort=True)
        .agg(
            total_rows=("ticker", "size"),
            label_valid_rows=("label_valid_5d", "sum"),
            class_neg1=("_valid_target_class", lambda s: int((s == -1).sum())),
            class_0=("_valid_target_class", lambda s: int((s == 0).sum())),
            class_pos1=("_valid_target_class", lambda s: int((s == 1).sum())),
        )
        .reset_index()
    )

    class_counts = {str(int(k)): int(v) for k, v in df.loc[df["label_valid_5d"], "target_class_5d"].value_counts().sort_index().items()}
    class_counts_by_year = {
        str(int(row["year"])): {"-1": int(row["class_neg1"]), "0": int(row["class_0"]), "1": int(row["class_pos1"])}
        for _, row in by_year.iterrows()
    }
    summary = {
        "total_rows": int(len(df)),
        "label_valid_rows": int(df["label_valid_5d"].sum()),
        "invalid_reason_counts_are_overlapping": True,
        "invalid_reason_counts": invalid_reason_counts,
        "mutually_exclusive_invalid_reason_counts": mutually_exclusive_invalid_reason_counts,
        "class_counts": class_counts,
        "class_counts_by_year": class_counts_by_year,
        "date_count": int(df["date"].nunique()),
        "min_date": str(min(df["date"])),
        "max_date": str(max(df["date"])),
        "excluded_ticker_rows": int(is_excluded.sum()),
        "otherwise_valid_rows_invalidated_by_split_like_target_window_gaps": int(split_invalidated.sum()),
        "rows_invalidated_by_split_like_target_window_gaps": int(split_invalidated.sum()),
    }
    return TargetResult(df[OUTPUT_COLUMNS].copy(), summary, by_year, by_date)


def run_targets(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_project_config()["targets"]
    gaps_path = p.validation_reports / "raw_split_like_gaps.csv"
    result = generate_targets(_read_research(p.research_ohlcv_daily), _read_split_gaps(gaps_path), **cfg)

    reset_parquet_output_dir(p.labeled_target_h5)
    if not result.data.empty:
        result.data.to_parquet(p.labeled_target_h5 / "targets.parquet", engine="pyarrow", index=False)

    p.label_reports.mkdir(parents=True, exist_ok=True)
    (p.label_reports / "target_h5_summary.json").write_text(
        json.dumps(result.summary, indent=2, default=str),
        encoding="utf-8",
    )
    result.by_year.to_csv(p.label_reports / "target_h5_by_year.csv", index=False)
    result.by_date.to_csv(p.label_reports / "target_h5_by_date.csv", index=False)
    return result.summary
