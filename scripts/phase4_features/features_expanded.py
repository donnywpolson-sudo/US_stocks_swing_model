from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import yaml

from scripts.phase4_features.column_registry import build_column_registry, load_baseline_feature_config
from scripts.project_config import REPO_ROOT, ProjectPaths, project_paths, reset_parquet_output_dir


@dataclass(frozen=True)
class ExpandedFeatureResult:
    data: pd.DataFrame
    summary: dict[str, object]
    registry: dict[str, list[str]]


def load_expanded_feature_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "expanded_features.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base = load_baseline_feature_config()
    cfg["baseline_feature_columns"] = base["feature_columns"]
    cfg["feature_columns"] = base["feature_columns"] + cfg["new_feature_columns"]
    cfg["target_columns"] = base["target_columns"]
    cfg["metadata_columns"] = base["metadata_columns"]
    cfg["excluded_columns"] = base["excluded_columns"]
    return cfg


def _z(s: pd.Series, w: int) -> pd.Series:
    r = s.rolling(w, min_periods=w)
    return (s - r.mean()) / r.std(ddof=0).replace(0, np.nan)


def _days_since_min(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=1).apply(lambda x: len(x) - 1 - int(np.argmin(x)), raw=True)


def _days_since_max(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=1).apply(lambda x: len(x) - 1 - int(np.argmax(x)), raw=True)


def _add_expanded_pandas(g: pd.DataFrame) -> pd.DataFrame:
    g = g.sort_values("date", kind="mergesort").copy()
    c, h, l, v, dv = g["close"], g["high"], g["low"], g["volume"].astype(float), g["dollar_volume"].astype(float)
    for w in [2, 4, 15, 30, 120, 252]:
        g[f"ret_{w}d"] = c / c.shift(w) - 1
    for w in [1, 5, 20]:
        g[f"log_ret_{w}d"] = np.log(c / c.shift(w))
    g["ret_5d_z_60d"] = _z(g["ret_5d"], 60)
    g["ret_20d_z_252d"] = _z(g["ret_20d"], 252)
    g["reversal_5d_20d"] = g["ret_5d"] - g["ret_20d"]
    g["momentum_20d_60d"] = g["ret_20d"] - g["ret_60d"]
    for w in [20, 120]:
        g[f"drawdown_from_{w}d_high"] = c / h.rolling(w, min_periods=w).max() - 1
    for w in [120, 252]:
        g[f"bounce_from_{w}d_low"] = c / l.rolling(w, min_periods=w).min() - 1
        hi, lo = h.rolling(w, min_periods=w).max(), l.rolling(w, min_periods=w).min()
        g[f"close_position_in_{w}d_range"] = (c - lo) / (hi - lo).replace(0, np.nan)
    for w in [20, 60]:
        g[f"days_since_{w}d_low"] = _days_since_min(l, w)
        g[f"days_since_{w}d_high"] = _days_since_max(h, w)
    for w in [10, 20, 50, 100, 200]:
        g[f"_sma_{w}d"] = c.rolling(w, min_periods=w).mean()
    g["dist_sma_100d"] = c / g["_sma_100d"] - 1
    g["sma_10d_slope"] = g["_sma_10d"] / g["_sma_10d"].shift(5) - 1
    g["sma_100d_slope"] = g["_sma_100d"] / g["_sma_100d"].shift(5) - 1
    g["sma_20_50_spread"] = g["_sma_20d"] / g["_sma_50d"] - 1
    g["sma_50_200_spread"] = g["_sma_50d"] / g["_sma_200d"] - 1
    g["trend_consistency_20d"] = (g["ret_1d"] > 0).rolling(20, min_periods=20).mean()
    for w in [120, 252]:
        g[f"realized_vol_{w}d"] = g["ret_1d"].rolling(w, min_periods=w).std(ddof=0)
    g["vol_ratio_20d_60d"] = g["realized_vol_20d"] / g["realized_vol_60d"]
    g["vol_ratio_20d_252d"] = g["realized_vol_20d"] / g["realized_vol_252d"]
    g["atr_14_z_252d"] = _z(g["atr_14_pct"], 252)
    g["downside_vol_20d"] = g["ret_1d"].where(g["ret_1d"] < 0, 0).rolling(20, min_periods=20).std(ddof=0)
    g["upside_vol_20d"] = g["ret_1d"].where(g["ret_1d"] > 0, 0).rolling(20, min_periods=20).std(ddof=0)
    g["downside_upside_vol_ratio_20d"] = g["downside_vol_20d"] / g["upside_vol_20d"].replace(0, np.nan)
    g["volume_z_120d"] = _z(v, 120)
    g["dollar_volume_z_120d"] = _z(dv, 120)
    g["volume_ratio_20d_60d"] = v.rolling(20, min_periods=20).mean() / v.rolling(60, min_periods=60).mean()
    g["dollar_volume_ratio_20d_60d"] = dv.rolling(20, min_periods=20).mean() / dv.rolling(60, min_periods=60).mean()
    g["price_volume_trend_20d"] = (g["ret_1d"] * v).rolling(20, min_periods=20).sum()
    for col, out in [
        ("lower_wick_pct", "lower_wick_z_60d"),
        ("upper_wick_pct", "upper_wick_z_60d"),
        ("body_pct", "body_z_60d"),
        ("gap_return", "gap_z_60d"),
    ]:
        g[out] = _z(g[col], 60)
    g["large_down_day_20d_count"] = (g["ret_1d"] < -2 * g["realized_vol_20d"]).rolling(20, min_periods=20).sum()
    g["large_up_day_20d_count"] = (g["ret_1d"] > 2 * g["realized_vol_20d"]).rolling(20, min_periods=20).sum()
    return g


def build_expanded_features(matrix: pd.DataFrame, cfg: dict[str, Any] | None = None) -> ExpandedFeatureResult:
    cfg = cfg or load_expanded_feature_config()
    if matrix.empty:
        return ExpandedFeatureResult(pd.DataFrame(), {}, build_column_registry([], cfg))
    df = matrix.copy()
    df["date"] = pd.to_datetime(df["date"])
    input_rows = len(df)
    df = pd.concat((_add_expanded_pandas(g) for _, g in df.groupby("ticker", sort=False)), ignore_index=True)
    for col in cfg["new_feature_columns"]:
        if col.startswith("rank_"):
            base = col.removeprefix("rank_")
            df[col] = df.groupby("date", sort=False)[base].rank(pct=True, method="average")
    df["year"] = df["date"].dt.year.astype("int64")
    df["date"] = df["date"].dt.date
    out = df.loc[df["label_valid_5d"]].copy().reset_index(drop=True)
    registry = build_column_registry(list(out.columns), cfg)
    keep = registry["metadata_cols"] + registry["excluded_cols"] + registry["target_cols"] + registry["feature_cols"]
    out = out[[x for x in keep if x in out.columns]]
    summary = _summary(out, input_rows, cfg, registry)
    return ExpandedFeatureResult(out, summary, registry)


def _summary(df: pd.DataFrame, input_rows: int, cfg: dict[str, Any], registry: dict[str, list[str]]) -> dict[str, object]:
    null_counts = {c: int(df[c].isna().sum()) for c in registry["feature_cols"]}
    top_null = dict(sorted(null_counts.items(), key=lambda kv: kv[1], reverse=True)[:30])
    rows_by_year = df.groupby("year", sort=True).size().astype(int).to_dict() if not df.empty else {}
    return {
        "input_rows": int(input_rows),
        "output_rows": int(len(df)),
        "baseline_feature_count": len(cfg["baseline_feature_columns"]),
        "new_feature_count": len(cfg["new_feature_columns"]),
        "total_feature_count": len(registry["feature_cols"]),
        "target_column_count": len(registry["target_cols"]),
        "metadata_column_count": len(registry["metadata_cols"]),
        "excluded_column_count": len(registry["excluded_cols"]),
        "min_date": str(min(df["date"])) if not df.empty else None,
        "max_date": str(max(df["date"])) if not df.empty else None,
        "ticker_count": int(df["ticker"].nunique()) if not df.empty else 0,
        "rows_by_year": {str(k): int(v) for k, v in rows_by_year.items()},
        "null_counts": null_counts,
        "top_30_highest_null_features": top_null,
    }


def _run_polars(paths: ProjectPaths, cfg: dict[str, Any]) -> tuple[pl.DataFrame, dict[str, object], dict[str, list[str]]]:
    c = pl.col
    baseline_files = sorted(paths.feature_matrix_baseline_h5.glob("*.parquet"))
    if not baseline_files:
        raise FileNotFoundError(f"missing baseline parquet files under {paths.feature_matrix_baseline_h5}")
    df = pl.read_parquet([str(p) for p in baseline_files]).with_columns(pl.col("date").cast(pl.Date, strict=False)).sort(["ticker", "date"])
    input_rows = df.height
    for w in [2, 4, 15, 30, 120, 252]:
        df = df.with_columns((c("close") / c("close").shift(w).over("ticker") - 1).alias(f"ret_{w}d"))
    df = df.with_columns(*[(c("close") / c("close").shift(w).over("ticker")).log().alias(f"log_ret_{w}d") for w in [1, 5, 20]])
    df = df.with_columns(
        ((c("ret_5d") - c("ret_5d").rolling_mean(60, min_samples=60).over("ticker")) / c("ret_5d").rolling_std(60, min_samples=60, ddof=0).over("ticker")).alias("ret_5d_z_60d"),
        ((c("ret_20d") - c("ret_20d").rolling_mean(252, min_samples=252).over("ticker")) / c("ret_20d").rolling_std(252, min_samples=252, ddof=0).over("ticker")).alias("ret_20d_z_252d"),
        (c("ret_5d") - c("ret_20d")).alias("reversal_5d_20d"),
        (c("ret_20d") - c("ret_60d")).alias("momentum_20d_60d"),
    )
    for w in [20, 60, 120, 252]:
        df = df.with_columns(
            c("high").rolling_max(w, min_samples=w).over("ticker").alias(f"_high_{w}d"),
            c("low").rolling_min(w, min_samples=w).over("ticker").alias(f"_low_{w}d"),
        )
    df = df.with_columns(
        (c("close") / c("_high_20d") - 1).alias("drawdown_from_20d_high"),
        (c("close") / c("_high_120d") - 1).alias("drawdown_from_120d_high"),
        (c("close") / c("_low_120d") - 1).alias("bounce_from_120d_low"),
        (c("close") / c("_low_252d") - 1).alias("bounce_from_252d_low"),
        ((c("close") - c("_low_120d")) / (c("_high_120d") - c("_low_120d"))).alias("close_position_in_120d_range"),
        ((c("close") - c("_low_252d")) / (c("_high_252d") - c("_low_252d"))).alias("close_position_in_252d_range"),
    )
    days_since = df.select(["ticker", "date", "low", "high"]).group_by("ticker", maintain_order=True).map_groups(_days_since_group)
    df = df.join(days_since, on=["ticker", "date"], how="left")
    for w in [10, 20, 50, 100, 200]:
        df = df.with_columns(c("close").rolling_mean(w, min_samples=w).over("ticker").alias(f"_sma_{w}d"))
    df = df.with_columns(
        (c("close") / c("_sma_100d") - 1).alias("dist_sma_100d"),
        (c("_sma_10d") / c("_sma_10d").shift(5).over("ticker") - 1).alias("sma_10d_slope"),
        (c("_sma_100d") / c("_sma_100d").shift(5).over("ticker") - 1).alias("sma_100d_slope"),
        (c("_sma_20d") / c("_sma_50d") - 1).alias("sma_20_50_spread"),
        (c("_sma_50d") / c("_sma_200d") - 1).alias("sma_50_200_spread"),
        (c("ret_1d") > 0).cast(pl.Float64).rolling_mean(20, min_samples=20).over("ticker").alias("trend_consistency_20d"),
    )
    df = df.with_columns(
        c("ret_1d").rolling_std(120, min_samples=120, ddof=0).over("ticker").alias("realized_vol_120d"),
        c("ret_1d").rolling_std(252, min_samples=252, ddof=0).over("ticker").alias("realized_vol_252d"),
    ).with_columns(
        (c("realized_vol_20d") / c("realized_vol_60d")).alias("vol_ratio_20d_60d"),
        (c("realized_vol_20d") / c("realized_vol_252d")).alias("vol_ratio_20d_252d"),
        ((c("atr_14_pct") - c("atr_14_pct").rolling_mean(252, min_samples=252).over("ticker")) / c("atr_14_pct").rolling_std(252, min_samples=252, ddof=0).over("ticker")).alias("atr_14_z_252d"),
        pl.when(c("ret_1d") < 0).then(c("ret_1d")).otherwise(0.0).rolling_std(20, min_samples=20, ddof=0).over("ticker").alias("downside_vol_20d"),
        pl.when(c("ret_1d") > 0).then(c("ret_1d")).otherwise(0.0).rolling_std(20, min_samples=20, ddof=0).over("ticker").alias("upside_vol_20d"),
    ).with_columns((c("downside_vol_20d") / c("upside_vol_20d")).alias("downside_upside_vol_ratio_20d"))
    for col in ["volume", "dollar_volume"]:
        df = df.with_columns(((c(col) - c(col).rolling_mean(120, min_samples=120).over("ticker")) / c(col).rolling_std(120, min_samples=120, ddof=0).over("ticker")).alias(f"{col}_z_120d"))
    df = df.with_columns(
        (c("volume").rolling_mean(20, min_samples=20).over("ticker") / c("volume").rolling_mean(60, min_samples=60).over("ticker")).alias("volume_ratio_20d_60d"),
        (c("dollar_volume").rolling_mean(20, min_samples=20).over("ticker") / c("dollar_volume").rolling_mean(60, min_samples=60).over("ticker")).alias("dollar_volume_ratio_20d_60d"),
        (c("ret_1d") * c("volume")).rolling_sum(20, min_samples=20).over("ticker").alias("price_volume_trend_20d"),
    )
    for col, out in [("lower_wick_pct", "lower_wick_z_60d"), ("upper_wick_pct", "upper_wick_z_60d"), ("body_pct", "body_z_60d"), ("gap_return", "gap_z_60d")]:
        df = df.with_columns(((c(col) - c(col).rolling_mean(60, min_samples=60).over("ticker")) / c(col).rolling_std(60, min_samples=60, ddof=0).over("ticker")).alias(out))
    df = df.with_columns(
        (c("ret_1d") < -2 * c("realized_vol_20d")).cast(pl.Int64).rolling_sum(20, min_samples=20).over("ticker").alias("large_down_day_20d_count"),
        (c("ret_1d") > 2 * c("realized_vol_20d")).cast(pl.Int64).rolling_sum(20, min_samples=20).over("ticker").alias("large_up_day_20d_count"),
    )
    for col in ["ret_5d_z_60d", "ret_20d_z_252d", "drawdown_from_120d_high", "bounce_from_120d_low", "close_position_in_252d_range", "vol_ratio_20d_252d", "lower_wick_z_60d", "upper_wick_z_60d"]:
        df = df.with_columns((c(col).rank("average").over("date") / c(col).count().over("date")).alias(f"rank_{col}"))
    registry = build_column_registry(df.columns, cfg)
    keep = [x for x in registry["metadata_cols"] + registry["excluded_cols"] + registry["target_cols"] + registry["feature_cols"] if x in df.columns]
    df = df.select(keep)
    null_counts = df.select([pl.col(col).null_count().alias(col) for col in registry["feature_cols"]]).to_dicts()[0]
    rows_by_year = {str(r["year"]): int(r["len"]) for r in df.group_by("year").len().sort("year").to_dicts()}
    top_null = dict(sorted({k: int(v) for k, v in null_counts.items()}.items(), key=lambda kv: kv[1], reverse=True)[:30])
    summary = {
        "input_rows": int(input_rows),
        "output_rows": int(df.height),
        "baseline_feature_count": len(cfg["baseline_feature_columns"]),
        "new_feature_count": len(cfg["new_feature_columns"]),
        "total_feature_count": len(registry["feature_cols"]),
        "target_column_count": len(registry["target_cols"]),
        "metadata_column_count": len(registry["metadata_cols"]),
        "excluded_column_count": len(registry["excluded_cols"]),
        "min_date": str(df.select(pl.col("date").min()).item()) if df.height else None,
        "max_date": str(df.select(pl.col("date").max()).item()) if df.height else None,
        "ticker_count": int(df.select(pl.col("ticker").n_unique()).item()) if df.height else 0,
        "rows_by_year": rows_by_year,
        "null_counts": {k: int(v) for k, v in null_counts.items()},
        "top_30_highest_null_features": top_null,
    }
    return df, summary, registry


def _days_since(values: np.ndarray, window: int, *, find_max: bool) -> list[int]:
    q: deque[int] = deque()
    out: list[int] = []
    for i, value in enumerate(values):
        while q and q[0] <= i - window:
            q.popleft()
        if find_max:
            while q and values[q[-1]] <= value:
                q.pop()
        else:
            while q and values[q[-1]] >= value:
                q.pop()
        q.append(i)
        out.append(i - q[0])
    return out


def _days_since_group(g: pl.DataFrame) -> pl.DataFrame:
    low = g["low"].to_numpy()
    high = g["high"].to_numpy()
    return pl.DataFrame(
        {
            "ticker": g["ticker"],
            "date": g["date"],
            "days_since_20d_low": _days_since(low, 20, find_max=False),
            "days_since_60d_low": _days_since(low, 60, find_max=False),
            "days_since_20d_high": _days_since(high, 20, find_max=True),
            "days_since_60d_high": _days_since(high, 60, find_max=True),
        }
    )


def run_expanded_features(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_expanded_feature_config()
    data, summary, registry = _run_polars(p, cfg)
    reset_parquet_output_dir(p.feature_matrix_expanded_h5)
    if data.height:
        data.write_parquet(str(p.feature_matrix_expanded_h5 / "expanded_h5.parquet"))
    for name, values in registry.items():
        (p.feature_matrix_expanded_h5 / f"{name}.json").write_text(json.dumps(values, indent=2), encoding="utf-8")
    p.feature_reports.mkdir(parents=True, exist_ok=True)
    (p.feature_reports / "expanded_h5_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    return summary
