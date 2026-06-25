from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


ROOT = Path(__file__).resolve().parents[1]
COST_BPS = 25
PROFILE_BAND = "fixed_top_25"
PROFILE_FILTER = "mdv60_ge_25m"


def _read_preds(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("fold_*.parquet"))
    if len(files) != 45:
        raise ValueError(f"expected 45 OOS fold files under {path}, found {len(files)}")
    df = pd.concat(
        [
            pd.read_parquet(
                f,
                columns=[
                    "fold_id",
                    "date",
                    "ticker",
                    "fwd_ret_5d",
                    "pred_score_5d",
                    "pred_rank_pct_by_date",
                    "pred_long_rank_5d",
                ],
            )
            for f in files
        ],
        ignore_index=True,
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _attach_proxy(df: pd.DataFrame) -> pd.DataFrame:
    min_date = min(df["date"])
    max_date = max(df["date"])
    proxy = (
        pl.scan_parquet(str(ROOT / "data" / "research_ohlcv_daily"))
        .select(["date", "ticker", "median_dollar_volume_60"])
        .with_columns(pl.col("date").cast(pl.Date, strict=False))
        .filter((pl.col("date") >= min_date) & (pl.col("date") <= max_date))
        .collect()
        .to_pandas()
    )
    proxy["date"] = pd.to_datetime(proxy["date"]).dt.date
    out = df.merge(proxy, on=["date", "ticker"], how="left", validate="many_to_one")
    missing = int(out["median_dollar_volume_60"].isna().sum())
    if missing:
        raise ValueError(f"missing median_dollar_volume_60 rows after proxy join: {missing}")
    return out


def _rank_ic(df: pd.DataFrame) -> tuple[float, float | None, int]:
    rows = []
    for _, g in df.groupby("date", sort=True):
        if len(g) < 2 or g["pred_score_5d"].nunique() < 2 or g["fwd_ret_5d"].nunique() < 2:
            rows.append(np.nan)
        else:
            rows.append(g["pred_score_5d"].corr(g["fwd_ret_5d"], method="spearman"))
    ic = pd.Series(rows).dropna()
    t_stat = float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 1 and ic.std(ddof=1) else None
    return float(ic.mean()), t_stat, int(len(ic))


def _focus_daily(df: pd.DataFrame) -> pd.DataFrame:
    mask = (df["pred_long_rank_5d"] <= 25) & (df["median_dollar_volume_60"] >= 25_000_000)
    sel = df.loc[mask, ["date", "fold_id", "fwd_ret_5d"]].copy()
    return (
        sel.groupby(["date", "fold_id"], sort=True)
        .agg(gross_return=("fwd_ret_5d", "mean"), candidate_count=("fwd_ret_5d", "size"))
        .reset_index()
    )


def _profile_stats(daily: pd.DataFrame) -> dict[str, object]:
    d = daily.copy()
    d["net_25bps"] = d["gross_return"] - COST_BPS / 10000
    d["year"] = pd.to_datetime(d["date"]).dt.year
    by_year = d.groupby("year", sort=True)["net_25bps"].mean()
    by_fold = d.groupby("fold_id", sort=True)["net_25bps"].mean()
    return {
        "gross_return": float(d["gross_return"].mean()),
        "net_return_25bps": float(d["net_25bps"].mean()),
        "break_even_bps": float(d["gross_return"].mean() * 10000),
        "avg_candidates_per_day": float(d["candidate_count"].mean()),
        "positive_years_25bps": int((by_year > 0).sum()),
        "total_years": int(len(by_year)),
        "positive_folds_25bps": int((by_fold > 0).sum()),
        "total_folds": int(len(by_fold)),
        "worst_year": int(by_year.idxmin()),
        "worst_year_net_25bps": float(by_year.min()),
        "worst_fold": int(by_fold.idxmin()),
        "worst_fold_net_25bps": float(by_fold.min()),
    }


def _turnover(daily_members: pd.DataFrame) -> dict[str, float]:
    by_date = {
        date: set(g["ticker"])
        for date, g in daily_members.groupby("date", sort=True)
    }
    prev = None
    vals = []
    for members in by_date.values():
        if prev is not None and members:
            overlap = len(prev & members)
            vals.append(1 - overlap / len(members))
        prev = members
    return {"one_way_turnover_proxy": float(np.mean(vals)) if vals else np.nan}


def _model_summary(name: str, path: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    df = _attach_proxy(_read_preds(path))
    mean_ic, t_stat, ic_days = _rank_ic(df)
    daily = _focus_daily(df)
    stats = _profile_stats(daily)
    members = df.loc[
        (df["pred_long_rank_5d"] <= 25) & (df["median_dollar_volume_60"] >= 25_000_000),
        ["date", "ticker"],
    ]
    stats.update(_turnover(members))
    stats.update({"model": name, "row_count": int(len(df)), "mean_daily_rank_ic": mean_ic, "rank_ic_t_stat": t_stat, "rank_ic_days": ic_days})
    by_year = daily.assign(year=pd.to_datetime(daily["date"]).dt.year, net_return_25bps=daily["gross_return"] - COST_BPS / 10000)
    by_year = by_year.groupby("year", sort=True).agg(
        net_return_25bps=("net_return_25bps", "mean"),
        gross_return=("gross_return", "mean"),
        avg_candidates_per_day=("candidate_count", "mean"),
        active_days=("date", "size"),
    ).reset_index()
    by_year.insert(0, "model", name)
    by_fold = daily.assign(net_return_25bps=daily["gross_return"] - COST_BPS / 10000)
    by_fold = by_fold.groupby("fold_id", sort=True).agg(
        net_return_25bps=("net_return_25bps", "mean"),
        gross_return=("gross_return", "mean"),
        avg_candidates_per_day=("candidate_count", "mean"),
        active_days=("date", "size"),
    ).reset_index()
    by_fold.insert(0, "model", name)
    return stats, by_year, by_fold


def run_comparison(variant: str) -> dict[str, object]:
    paths = {
        "baseline_h5": ROOT / "data" / "oos_predictions" / "baseline_h5",
        "long_only_h5_phase1": ROOT / "data" / "oos_predictions" / "long_only_h5_phase1",
        variant: ROOT / "data" / "oos_predictions" / variant,
    }
    summaries = []
    years = []
    folds = []
    for name, path in paths.items():
        summary, by_year, by_fold = _model_summary(name, path)
        summaries.append(summary)
        years.append(by_year)
        folds.append(by_fold)

    summary_df = pd.DataFrame(summaries)
    baseline = summary_df.loc[summary_df["model"] == "baseline_h5"].iloc[0]
    phase1 = summary_df.loc[summary_df["model"] == "long_only_h5_phase1"].iloc[0]
    variant_row = summary_df.loc[summary_df["model"] == variant].iloc[0]
    summary_df["net_25bps_delta_vs_baseline"] = summary_df["net_return_25bps"] - float(baseline["net_return_25bps"])
    summary_df["net_25bps_delta_vs_phase1"] = summary_df["net_return_25bps"] - float(phase1["net_return_25bps"])
    summary_df["rank_ic_delta_vs_baseline"] = summary_df["mean_daily_rank_ic"] - float(baseline["mean_daily_rank_ic"])
    summary_df["rank_ic_delta_vs_phase1"] = summary_df["mean_daily_rank_ic"] - float(phase1["mean_daily_rank_ic"])

    out = ROOT / "reports" / "metrics"
    out.mkdir(parents=True, exist_ok=True)
    prefix = f"{variant}_vs_baseline_phase1"
    summary_df.to_csv(out / f"{prefix}_summary.csv", index=False)
    pd.concat(years, ignore_index=True).to_csv(out / f"{prefix}_by_year.csv", index=False)
    pd.concat(folds, ignore_index=True).to_csv(out / f"{prefix}_by_fold.csv", index=False)

    verdict = "needs_review"
    if (
        variant_row["positive_folds_25bps"] > phase1["positive_folds_25bps"]
        and variant_row["positive_years_25bps"] >= phase1["positive_years_25bps"]
        and variant_row["avg_candidates_per_day"] >= 10
        and variant_row["net_return_25bps"] >= phase1["net_return_25bps"]
    ):
        verdict = "continue_review"
    elif variant_row["net_return_25bps"] < phase1["net_return_25bps"] and variant_row["positive_folds_25bps"] <= phase1["positive_folds_25bps"]:
        verdict = "reject_variant"

    md = f"""# {variant} vs Baseline and Full Phase 1

This is an experimental read-only comparison from existing OOS predictions. It does not change official gates, does not claim readiness, and does not use option data.

Focus profile: `fixed_top_25 + median_dollar_volume_60 >= 25m`.

| Model | Rank IC | Net 25 bps | Break-even bps | Positive years | Positive folds | Avg candidates/day | Turnover proxy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for _, r in summary_df.iterrows():
        md += (
            f"| {r['model']} | {r['mean_daily_rank_ic']:.6f} | {r['net_return_25bps']:.6f} | "
            f"{r['break_even_bps']:.6f} | {int(r['positive_years_25bps'])}/{int(r['total_years'])} | "
            f"{int(r['positive_folds_25bps'])}/{int(r['total_folds'])} | {r['avg_candidates_per_day']:.6f} | "
            f"{r['one_way_turnover_proxy']:.6f} |\n"
        )
    md += f"""
Recommended variant status: `{verdict}`.

Do not change official gates from this report. Continue only if stability improves, not just one headline metric.
"""
    (out / f"{prefix}_diagnostic.md").write_text(md, encoding="utf-8")
    return {"variant": variant, "verdict": verdict, "summary": summary_df.to_dict(orient="records")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print(json.dumps(run_comparison(args.variant), indent=2, default=str))
