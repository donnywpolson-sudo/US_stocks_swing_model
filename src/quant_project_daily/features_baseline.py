from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np
import pandas as pd
import polars as pl

from quant_project_daily.column_registry import build_column_registry, load_baseline_feature_config
from quant_project_daily.config import ProjectPaths, project_paths, reset_parquet_output_dir


@dataclass(frozen=True)
class FeatureBuildResult:
    data: pd.DataFrame
    summary: dict[str, object]
    registry: dict[str, list[str]]


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    return num / den.replace(0, np.nan)


def _zscore(s: pd.Series, window: int) -> pd.Series:
    roll = s.rolling(window, min_periods=window)
    return (s - roll.mean()) / roll.std(ddof=0).replace(0, np.nan)


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window, min_periods=window).mean()
    avg_loss = loss.rolling(window, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    out = out.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    out = out.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return out


def _add_ticker_features(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date", kind="mergesort").copy()
    close = g["close"]
    open_ = g["open"]
    high = g["high"]
    low = g["low"]
    volume = g["volume"].astype(float)
    dollar_volume = g["dollar_volume"].astype(float)
    prev_close = close.shift(1)

    for w in [1, 3, 5, 10, 20, 60]:
        g[f"ret_{w}d"] = close / close.shift(w) - 1
    g["gap_return"] = open_ / prev_close - 1
    g["intraday_return"] = close / open_ - 1

    ret_1d = g["ret_1d"]
    for w in [5, 10, 20, 60]:
        g[f"realized_vol_{w}d"] = ret_1d.rolling(w, min_periods=w).std(ddof=0)

    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    g["true_range_pct"] = true_range / prev_close
    g["atr_14_pct"] = g["true_range_pct"].rolling(14, min_periods=14).mean()
    g["range_pct"] = (high - low) / close
    g["range_z_20d"] = _zscore(g["range_pct"], 20)

    day_range = (high - low).replace(0, np.nan)
    g["body_pct"] = (close - open_) / close
    g["upper_wick_pct"] = (high - pd.concat([open_, close], axis=1).max(axis=1)) / close
    g["lower_wick_pct"] = (pd.concat([open_, close], axis=1).min(axis=1) - low) / close
    g["close_position_in_day_range"] = (close - low) / day_range

    for w in [10, 20, 50, 200]:
        sma = close.rolling(w, min_periods=w).mean()
        g[f"dist_sma_{w}d"] = close / sma - 1
        if w in [20, 50, 200]:
            g[f"sma_{w}d_slope"] = sma / sma.shift(5) - 1

    for w in [20, 60, 252]:
        roll_high = high.rolling(w, min_periods=w).max()
        roll_low = low.rolling(w, min_periods=w).min()
        g[f"dist_to_{w}d_high"] = close / roll_high - 1
        g[f"dist_to_{w}d_low"] = close / roll_low - 1
    g["drawdown_from_60d_high"] = g["dist_to_60d_high"]
    g["drawdown_from_252d_high"] = g["dist_to_252d_high"]
    g["bounce_from_20d_low"] = g["dist_to_20d_low"]
    g["bounce_from_60d_low"] = g["dist_to_60d_low"]

    g["rsi_14"] = _rsi(close, 14)
    g["rsi_30"] = _rsi(close, 30)
    for w in [20, 60]:
        roll_high = high.rolling(w, min_periods=w).max()
        roll_low = low.rolling(w, min_periods=w).min()
        g[f"close_position_in_{w}d_range"] = (close - roll_low) / (roll_high - roll_low).replace(0, np.nan)

    g["volume_z_20d"] = _zscore(volume, 20)
    g["volume_z_60d"] = _zscore(volume, 60)
    g["dollar_volume_z_20d"] = _zscore(dollar_volume, 20)
    g["dollar_volume_z_60d"] = _zscore(dollar_volume, 60)
    g["volume_ratio_5d_20d"] = volume.rolling(5, min_periods=5).mean() / volume.rolling(20, min_periods=20).mean()
    g["dollar_volume_ratio_5d_20d"] = (
        dollar_volume.rolling(5, min_periods=5).mean() / dollar_volume.rolling(20, min_periods=20).mean()
    )
    return g


def build_baseline_features(labeled: pd.DataFrame, cfg: dict[str, object] | None = None) -> FeatureBuildResult:
    cfg = cfg or load_baseline_feature_config()
    if labeled.empty:
        registry = build_column_registry([], cfg)
        return FeatureBuildResult(pd.DataFrame(), {}, registry)

    df = labeled.copy()
    df["date"] = pd.to_datetime(df["date"])
    input_rows = len(df)
    df = df.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    df = pd.concat((_add_ticker_features(g) for _, g in df.groupby("ticker", sort=False)), ignore_index=True)
    df["day_of_week"] = df["date"].dt.dayofweek.astype("int8")
    df["month"] = df["date"].dt.month.astype("int8")

    rank_inputs = [
        "ret_20d",
        "rsi_14",
        "drawdown_from_60d_high",
        "dist_to_60d_low",
        "volume_z_20d",
        "dollar_volume_z_20d",
    ]
    for col in rank_inputs:
        df[f"rank_{col}"] = df.groupby("date", sort=False)[col].rank(pct=True, method="average")

    df["year"] = df["date"].dt.year.astype("int64")
    df["date"] = df["date"].dt.date
    out = df.loc[df["label_valid_20d"]].copy().reset_index(drop=True)

    registry = build_column_registry(list(out.columns), cfg)
    feature_cols = registry["feature_cols"]
    ordered_cols = registry["metadata_cols"] + registry["excluded_cols"] + registry["target_cols"] + feature_cols
    out = out[[c for c in ordered_cols if c in out.columns]]
    rows_by_year = out.groupby("year", sort=True).size().astype(int).to_dict() if not out.empty else {}
    summary = {
        "input_rows": int(input_rows),
        "output_rows": int(len(out)),
        "feature_count": len(feature_cols),
        "target_column_count": len(registry["target_cols"]),
        "metadata_column_count": len(registry["metadata_cols"]),
        "min_date": str(min(out["date"])) if not out.empty else None,
        "max_date": str(max(out["date"])) if not out.empty else None,
        "tickers": int(out["ticker"].nunique()) if not out.empty else 0,
        "rows_by_year": {str(k): int(v) for k, v in rows_by_year.items()},
        "null_counts": {c: int(out[c].isna().sum()) for c in feature_cols},
        "feature_columns": feature_cols,
    }
    return FeatureBuildResult(out, summary, registry)


def run_baseline_features(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_baseline_feature_config()
    data, summary, registry = _build_baseline_features_polars(p, cfg)
    reset_parquet_output_dir(p.feature_matrix_baseline_h20)
    if data.height:
        data.write_parquet(str(p.feature_matrix_baseline_h20 / "baseline_h20.parquet"))

    for name, values in registry.items():
        (p.feature_matrix_baseline_h20 / f"{name}.json").write_text(json.dumps(values, indent=2), encoding="utf-8")

    p.feature_reports.mkdir(parents=True, exist_ok=True)
    (p.feature_reports / "baseline_h20_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return summary


def _build_baseline_features_polars(p: ProjectPaths, cfg: dict[str, object]) -> tuple[pl.DataFrame, dict[str, object], dict[str, list[str]]]:
    feature_cols = list(cfg["feature_columns"])
    target_cols = list(cfg["target_columns"])
    metadata_cols = list(cfg["metadata_columns"])
    excluded_cols = list(cfg["excluded_columns"])

    df = pl.read_parquet(str(p.labeled_target_h20)).with_columns(pl.col("date").cast(pl.Date, strict=False))
    input_rows = df.height
    df = df.sort(["ticker", "date"])
    c = pl.col

    df = df.with_columns(
        c("close").shift(1).over("ticker").alias("_prev_close"),
    )
    df = df.with_columns(
        *[(c("close") / c("close").shift(w).over("ticker") - 1).alias(f"ret_{w}d") for w in [1, 3, 5, 10, 20, 60]],
        (c("open") / c("_prev_close") - 1).alias("gap_return"),
        (c("close") / c("open") - 1).alias("intraday_return"),
        pl.max_horizontal(
            c("high") - c("low"),
            (c("high") - c("_prev_close")).abs(),
            (c("low") - c("_prev_close")).abs(),
        ).alias("_true_range"),
        ((c("high") - c("low")) / c("close")).alias("range_pct"),
        ((c("close") - c("open")) / c("close")).alias("body_pct"),
        ((c("high") - pl.max_horizontal(c("open"), c("close"))) / c("close")).alias("upper_wick_pct"),
        ((pl.min_horizontal(c("open"), c("close")) - c("low")) / c("close")).alias("lower_wick_pct"),
        ((c("close") - c("low")) / (c("high") - c("low"))).alias("close_position_in_day_range"),
        c("date").dt.weekday().sub(1).alias("day_of_week"),
        c("date").dt.month().alias("month"),
    )
    df = df.with_columns(
        (c("_true_range") / c("_prev_close")).alias("true_range_pct"),
        *[c("ret_1d").rolling_std(w, min_samples=w, ddof=0).over("ticker").alias(f"realized_vol_{w}d") for w in [5, 10, 20, 60]],
        (
            (c("range_pct") - c("range_pct").rolling_mean(20, min_samples=20).over("ticker"))
            / c("range_pct").rolling_std(20, min_samples=20, ddof=0).over("ticker")
        ).alias("range_z_20d"),
    )
    df = df.with_columns(c("true_range_pct").rolling_mean(14, min_samples=14).over("ticker").alias("atr_14_pct"))
    for w in [10, 20, 50, 200]:
        df = df.with_columns(c("close").rolling_mean(w, min_samples=w).over("ticker").alias(f"_sma_{w}d"))
    df = df.with_columns(
        *[(c("close") / c(f"_sma_{w}d") - 1).alias(f"dist_sma_{w}d") for w in [10, 20, 50, 200]],
        *[(c(f"_sma_{w}d") / c(f"_sma_{w}d").shift(5).over("ticker") - 1).alias(f"sma_{w}d_slope") for w in [20, 50, 200]],
    )
    for w in [20, 60, 252]:
        df = df.with_columns(
            c("high").rolling_max(w, min_samples=w).over("ticker").alias(f"_high_{w}d"),
            c("low").rolling_min(w, min_samples=w).over("ticker").alias(f"_low_{w}d"),
        )
    df = df.with_columns(
        *[(c("close") / c(f"_high_{w}d") - 1).alias(f"dist_to_{w}d_high") for w in [20, 60, 252]],
        *[(c("close") / c(f"_low_{w}d") - 1).alias(f"dist_to_{w}d_low") for w in [20, 60, 252]],
        (c("close") / c("_high_60d") - 1).alias("drawdown_from_60d_high"),
        (c("close") / c("_high_252d") - 1).alias("drawdown_from_252d_high"),
        (c("close") / c("_low_20d") - 1).alias("bounce_from_20d_low"),
        (c("close") / c("_low_60d") - 1).alias("bounce_from_60d_low"),
        ((c("close") - c("_low_20d")) / (c("_high_20d") - c("_low_20d"))).alias("close_position_in_20d_range"),
        ((c("close") - c("_low_60d")) / (c("_high_60d") - c("_low_60d"))).alias("close_position_in_60d_range"),
    )
    df = df.with_columns(
        c("close").diff().over("ticker").alias("_delta"),
    ).with_columns(
        pl.when(c("_delta") > 0).then(c("_delta")).otherwise(0.0).alias("_gain"),
        pl.when(c("_delta") < 0).then(-c("_delta")).otherwise(0.0).alias("_loss"),
    )
    for w in [14, 30]:
        avg_gain = c("_gain").rolling_mean(w, min_samples=w).over("ticker")
        avg_loss = c("_loss").rolling_mean(w, min_samples=w).over("ticker")
        df = df.with_columns(
            pl.when((avg_loss == 0) & (avg_gain > 0))
            .then(100.0)
            .when((avg_loss == 0) & (avg_gain == 0))
            .then(50.0)
            .otherwise(100 - (100 / (1 + (avg_gain / avg_loss))))
            .alias(f"rsi_{w}")
        )
    for col in ["volume", "dollar_volume"]:
        for w in [20, 60]:
            df = df.with_columns(
                ((c(col) - c(col).rolling_mean(w, min_samples=w).over("ticker")) / c(col).rolling_std(w, min_samples=w, ddof=0).over("ticker")).alias(
                    f"{col}_z_{w}d"
                )
            )
    df = df.with_columns(
        (c("volume").rolling_mean(5, min_samples=5).over("ticker") / c("volume").rolling_mean(20, min_samples=20).over("ticker")).alias(
            "volume_ratio_5d_20d"
        ),
        (
            c("dollar_volume").rolling_mean(5, min_samples=5).over("ticker")
            / c("dollar_volume").rolling_mean(20, min_samples=20).over("ticker")
        ).alias("dollar_volume_ratio_5d_20d"),
    )
    for col in ["ret_20d", "rsi_14", "drawdown_from_60d_high", "dist_to_60d_low", "volume_z_20d", "dollar_volume_z_20d"]:
        df = df.with_columns((c(col).rank("average").over("date") / c(col).count().over("date")).alias(f"rank_{col}"))

    df = df.with_columns(c("date").dt.year().alias("year")).filter(c("label_valid_20d") == True)
    keep_cols = [col for col in metadata_cols + excluded_cols + target_cols + feature_cols if col in df.columns]
    df = df.select(keep_cols)

    registry = build_column_registry(df.columns, cfg)
    rows_by_year = {str(r["year"]): int(r["len"]) for r in df.group_by("year").len().sort("year").to_dicts()}
    null_counts = df.select([pl.col(col).null_count().alias(col) for col in feature_cols]).to_dicts()[0]
    summary = {
        "input_rows": int(input_rows),
        "output_rows": int(df.height),
        "feature_count": len(registry["feature_cols"]),
        "target_column_count": len(registry["target_cols"]),
        "metadata_column_count": len(registry["metadata_cols"]),
        "min_date": str(df.select(pl.col("date").min()).item()) if df.height else None,
        "max_date": str(df.select(pl.col("date").max()).item()) if df.height else None,
        "tickers": int(df.select(pl.col("ticker").n_unique()).item()) if df.height else 0,
        "rows_by_year": rows_by_year,
        "null_counts": {k: int(v) for k, v in null_counts.items()},
        "feature_columns": registry["feature_cols"],
    }
    return df, summary, registry
