from __future__ import annotations

import pandas as pd


def cost_bps_to_return(round_trip_cost_bps: float) -> float:
    return float(round_trip_cost_bps) / 10_000.0


def assign_score_buckets(preds: pd.DataFrame, buckets: int, score_col: str = "pred_score_5d") -> pd.Series:
    ranks = preds.groupby("date", sort=False)[score_col].rank(method="first", ascending=True)
    counts = preds.groupby("date", sort=False)[score_col].transform("count")
    bucket = ((ranks - 1) * buckets / counts).astype(int) + 1
    return bucket.clip(1, buckets).astype("int64")


def bucket_forward_returns(preds: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    return (
        preds.groupby(["date", bucket_col], sort=True)
        .agg(row_count=("ticker", "size"), mean_fwd_ret_5d=("fwd_ret_5d", "mean"))
        .reset_index()
    )


def daily_long_short_from_buckets(
    preds: pd.DataFrame,
    bucket_col: str,
    top_bucket: int,
    bottom_bucket: int,
    round_trip_cost_bps: float,
) -> pd.DataFrame:
    cost = cost_bps_to_return(round_trip_cost_bps)
    long_leg = (
        preds.loc[preds[bucket_col] == top_bucket]
        .groupby("date", sort=True)
        .agg(long_count=("ticker", "size"), long_gross_return=("fwd_ret_5d", "mean"), long_hit_rate=("fwd_ret_5d", lambda s: float((s > 0).mean())))
    )
    short_leg = (
        preds.loc[preds[bucket_col] == bottom_bucket]
        .assign(short_leg_return=lambda d: -d["fwd_ret_5d"])
        .groupby("date", sort=True)
        .agg(short_count=("ticker", "size"), short_gross_return=("short_leg_return", "mean"), short_hit_rate=("short_leg_return", lambda s: float((s > 0).mean())))
    )
    out = long_leg.join(short_leg, how="inner").reset_index()
    out["long_net_return"] = out["long_gross_return"] - cost
    out["short_net_return"] = out["short_gross_return"] - cost
    out["long_short_gross_return"] = 0.5 * out["long_gross_return"] + 0.5 * out["short_gross_return"]
    out["long_short_net_return"] = 0.5 * out["long_net_return"] + 0.5 * out["short_net_return"]
    return out
