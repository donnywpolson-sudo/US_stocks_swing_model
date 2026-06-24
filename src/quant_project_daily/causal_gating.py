from __future__ import annotations

import json

import pandas as pd

from quant_project_daily.config import load_project_config, project_paths, reset_parquet_output_dir


UNDERLYING_PROXY_LOOKBACK = 60


def read_normalized() -> pd.DataFrame:
    paths = project_paths()
    if not paths.normalized.exists():
        return pd.DataFrame()
    return pd.read_parquet(paths.normalized)


def apply_causal_gating(
    df: pd.DataFrame,
    *,
    min_history_bars: int = 252,
    price_min: float = 5.0,
    median_dollar_volume_lookback: int = 20,
    median_dollar_volume_min: float = 1_000_000.0,
    zero_volume_lookback: int = 20,
) -> pd.DataFrame:
    if df.empty:
        out = df.copy()
        out["history_bars"] = pd.Series(dtype="int64")
        out["median_dollar_volume_20"] = pd.Series(dtype="float64")
        out["zero_volume_count_20"] = pd.Series(dtype="float64")
        out["median_dollar_volume_60"] = pd.Series(dtype="float64")
        out["zero_volume_count_60"] = pd.Series(dtype="float64")
        out["tradable"] = pd.Series(dtype=bool)
        return out

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.date
    out = out.sort_values(["ticker", "date"], kind="mergesort").reset_index(drop=True)
    grp = out.groupby("ticker", sort=False)
    out["history_bars"] = grp.cumcount()
    out["median_dollar_volume_20"] = grp["dollar_volume"].transform(
        lambda s: s.rolling(median_dollar_volume_lookback, min_periods=median_dollar_volume_lookback).median()
    )
    out["zero_volume_count_20"] = grp["volume"].transform(
        lambda s: (s == 0).rolling(zero_volume_lookback, min_periods=zero_volume_lookback).sum()
    )
    out["median_dollar_volume_60"] = grp["dollar_volume"].transform(
        lambda s: s.rolling(UNDERLYING_PROXY_LOOKBACK, min_periods=UNDERLYING_PROXY_LOOKBACK).median()
    )
    out["zero_volume_count_60"] = grp["volume"].transform(
        lambda s: (s == 0).rolling(UNDERLYING_PROXY_LOOKBACK, min_periods=UNDERLYING_PROXY_LOOKBACK).sum()
    )
    out["tradable"] = (
        (out["history_bars"] >= min_history_bars)
        & (out["close"] >= price_min)
        & (out["median_dollar_volume_20"] >= median_dollar_volume_min)
        & (out["zero_volume_count_20"] == 0)
    )
    return out


def run_causal_gating() -> dict[str, object]:
    cfg = load_project_config()["causal_gating"]
    paths = project_paths()
    out = apply_causal_gating(read_normalized(), **cfg)
    reset_parquet_output_dir(paths.causal)
    if not out.empty:
        out.to_parquet(paths.causal, engine="pyarrow", partition_cols=["year"], index=False)
    summary = {
        "rows": int(len(out)),
        "tradable_rows": int(out["tradable"].sum()) if not out.empty else 0,
        "output_path": str(paths.causal),
        "config": cfg,
        "underlying_proxy_fields": ["median_dollar_volume_60", "zero_volume_count_60", "history_bars"],
    }
    paths.validation_reports.mkdir(parents=True, exist_ok=True)
    (paths.validation_reports / "causal_gating_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
