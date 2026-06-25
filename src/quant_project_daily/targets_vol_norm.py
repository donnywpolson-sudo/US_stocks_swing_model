from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quant_project_daily.config import ProjectPaths, project_paths, reset_parquet_output_dir
from quant_project_daily.targets import _assign_date_classes


VOL_NORM60_TARGET_SET = "target_h5_vol_norm60_experimental"
VOL_NORM60_TARGET_PATH = Path("data") / "labeled" / VOL_NORM60_TARGET_SET
VOL_NORM60_PARQUET_NAME = "targets.parquet"
VOL_NORM60_SUMMARY_NAME = f"{VOL_NORM60_TARGET_SET}_summary.json"
VOL_NORM60_BY_YEAR_NAME = f"{VOL_NORM60_TARGET_SET}_by_year.csv"
VOL_NORM60_BY_DATE_NAME = f"{VOL_NORM60_TARGET_SET}_by_date.csv"
VOL_NORM60_EPSILON = 1.0e-6

VOL_NORM60_COLUMNS = [
    "fwd_ret_5d_vol_norm60",
    "label_valid_5d_vol_norm60",
    "target_class_5d_vol_norm60",
    "target_long_top20_5d_vol_norm60",
    "target_short_bottom20_5d_vol_norm60",
]

REQUIRED_INPUT_COLUMNS = [
    "date",
    "ticker",
    "close",
    "fwd_ret_5d",
    "label_valid_5d",
    "target_class_5d",
]


@dataclass(frozen=True)
class VolNormTargetResult:
    data: pd.DataFrame
    summary: dict[str, object]
    by_year: pd.DataFrame
    by_date: pd.DataFrame


def vol_norm60_target_path(paths: ProjectPaths | None = None) -> Path:
    p = paths or project_paths()
    return p.repo_root / VOL_NORM60_TARGET_PATH


def _read_labeled_target(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing active h5 target input: {path}")
    return pd.read_parquet(path)


def _validate_required_columns(df: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_INPUT_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"missing required columns for vol-normalized target: {missing}")


def _compute_trailing_vol_60d(df: pd.DataFrame) -> pd.Series:
    returns = df.groupby("ticker", sort=False)["close"].pct_change()
    return returns.groupby(df["ticker"], sort=False).transform(lambda s: s.rolling(60, min_periods=60).std(ddof=0))


def generate_vol_norm60_targets(
    labeled: pd.DataFrame,
    *,
    top_bottom_quantile: float = 0.20,
    epsilon: float = VOL_NORM60_EPSILON,
) -> VolNormTargetResult:
    if labeled.empty:
        empty = labeled.copy()
        for col in VOL_NORM60_COLUMNS:
            empty[col] = pd.Series(dtype="float64" if col == "fwd_ret_5d_vol_norm60" else "object")
        return VolNormTargetResult(empty, _empty_summary(), pd.DataFrame(), pd.DataFrame())

    _validate_required_columns(labeled)
    df = labeled.copy()
    original_columns = list(df.columns)
    df["date"] = pd.to_datetime(df["date"])
    df["ticker"] = df["ticker"].astype(str).str.upper()
    df = df.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)

    realized_vol_60d = _compute_trailing_vol_60d(df)
    valid_denominator = realized_vol_60d.notna() & np.isfinite(realized_vol_60d) & (realized_vol_60d > epsilon)
    base_valid = df["label_valid_5d"].fillna(False).astype(bool)
    valid_norm = base_valid & valid_denominator & df["fwd_ret_5d"].notna()

    df["fwd_ret_5d_vol_norm60"] = np.nan
    df.loc[valid_denominator, "fwd_ret_5d_vol_norm60"] = (
        df.loc[valid_denominator, "fwd_ret_5d"] / realized_vol_60d.loc[valid_denominator]
    )
    df["label_valid_5d_vol_norm60"] = valid_norm
    df["target_class_5d_vol_norm60"] = 0
    if valid_norm.any():
        classes = df.loc[valid_norm].groupby("date", group_keys=False)["fwd_ret_5d_vol_norm60"].apply(
            lambda s: _assign_date_classes(s, top_bottom_quantile)
        )
        df.loc[classes.index, "target_class_5d_vol_norm60"] = classes.astype("int8")

    df["target_long_top20_5d_vol_norm60"] = df["target_class_5d_vol_norm60"].eq(1)
    df["target_short_bottom20_5d_vol_norm60"] = df["target_class_5d_vol_norm60"].eq(-1)
    df["_valid_vol_norm_class"] = df["target_class_5d_vol_norm60"].where(df["label_valid_5d_vol_norm60"])
    df["year"] = df["date"].dt.year.astype("int64") if "year" not in df.columns else df["year"].astype("int64")

    by_year = _build_group_summary(df, "year")
    df["date"] = df["date"].dt.date
    by_date = _build_group_summary(df, "date")
    summary = _build_summary(df, by_year, base_valid=base_valid, valid_denominator=valid_denominator)

    output_columns = original_columns + [c for c in VOL_NORM60_COLUMNS if c not in original_columns]
    return VolNormTargetResult(df[output_columns].copy(), summary, by_year, by_date)


def _empty_summary() -> dict[str, object]:
    return {
        "target_set": VOL_NORM60_TARGET_SET,
        "input_rows": 0,
        "output_rows": 0,
        "base_label_valid_rows": 0,
        "label_valid_5d_vol_norm60_rows": 0,
        "missing_or_invalid_vol60_rows": 0,
        "class_counts": {},
        "class_churn_vs_target_class_5d": None,
        "long_label_agreement_vs_target_class_5d": None,
        "short_label_agreement_vs_target_class_5d": None,
        "official_target_replaced": False,
    }


def _build_group_summary(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    return (
        df.groupby(group_col, sort=True)
        .agg(
            total_rows=("ticker", "size"),
            base_label_valid_rows=("label_valid_5d", "sum"),
            label_valid_5d_vol_norm60_rows=("label_valid_5d_vol_norm60", "sum"),
            class_neg1=("_valid_vol_norm_class", lambda s: int((s == -1).sum())),
            class_0=("_valid_vol_norm_class", lambda s: int((s == 0).sum())),
            class_pos1=("_valid_vol_norm_class", lambda s: int((s == 1).sum())),
        )
        .reset_index()
    )


def _build_summary(
    df: pd.DataFrame,
    by_year: pd.DataFrame,
    *,
    base_valid: pd.Series,
    valid_denominator: pd.Series,
) -> dict[str, object]:
    valid_norm = df["label_valid_5d_vol_norm60"].astype(bool)
    overlap = base_valid & valid_norm
    churn = None
    long_agreement = None
    short_agreement = None
    if overlap.any():
        churn = float((df.loc[overlap, "target_class_5d"] != df.loc[overlap, "target_class_5d_vol_norm60"]).mean())
        raw_long = df.loc[overlap, "target_class_5d"].eq(1)
        raw_short = df.loc[overlap, "target_class_5d"].eq(-1)
        long_agreement = float(df.loc[overlap & raw_long, "target_class_5d_vol_norm60"].eq(1).mean()) if raw_long.any() else None
        short_agreement = float(df.loc[overlap & raw_short, "target_class_5d_vol_norm60"].eq(-1).mean()) if raw_short.any() else None

    class_counts = {
        str(int(k)): int(v)
        for k, v in df.loc[valid_norm, "target_class_5d_vol_norm60"].value_counts().sort_index().items()
    }
    class_counts_by_year = {
        str(int(row["year"])): {"-1": int(row["class_neg1"]), "0": int(row["class_0"]), "1": int(row["class_pos1"])}
        for _, row in by_year.iterrows()
    } if not by_year.empty and "year" in by_year.columns else {}

    return {
        "target_set": VOL_NORM60_TARGET_SET,
        "input_rows": int(len(df)),
        "output_rows": int(len(df)),
        "base_label_valid_rows": int(base_valid.sum()),
        "label_valid_5d_vol_norm60_rows": int(valid_norm.sum()),
        "missing_or_invalid_vol60_rows": int((base_valid & ~valid_denominator).sum()),
        "epsilon": VOL_NORM60_EPSILON,
        "class_counts": class_counts,
        "class_counts_by_year": class_counts_by_year,
        "class_churn_vs_target_class_5d": churn,
        "long_label_agreement_vs_target_class_5d": long_agreement,
        "short_label_agreement_vs_target_class_5d": short_agreement,
        "min_date": str(min(df["date"])) if len(df) else None,
        "max_date": str(max(df["date"])) if len(df) else None,
        "official_target_replaced": False,
    }


def run_vol_norm60_targets(paths: ProjectPaths | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    result = generate_vol_norm60_targets(_read_labeled_target(p.labeled_target_h5))
    out_path = vol_norm60_target_path(p)
    reset_parquet_output_dir(out_path)
    if not result.data.empty:
        result.data.to_parquet(out_path / VOL_NORM60_PARQUET_NAME, engine="pyarrow", index=False)

    p.label_reports.mkdir(parents=True, exist_ok=True)
    (p.label_reports / VOL_NORM60_SUMMARY_NAME).write_text(
        json.dumps(result.summary, indent=2, default=str),
        encoding="utf-8",
    )
    result.by_year.to_csv(p.label_reports / VOL_NORM60_BY_YEAR_NAME, index=False)
    result.by_date.to_csv(p.label_reports / VOL_NORM60_BY_DATE_NAME, index=False)
    return result.summary
