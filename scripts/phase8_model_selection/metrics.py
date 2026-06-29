from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from scripts.project_config import REPO_ROOT, ProjectPaths, project_paths
from scripts.execution import assign_score_buckets, bucket_forward_returns, daily_long_short_from_buckets


def load_execution_costs(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "execution_costs.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_oos_predictions(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("*.parquet")) if path.is_dir() else [path]
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def rank_ic_by_date(preds: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, g in preds.groupby("date", sort=True):
        if len(g) < 2 or g["pred_score_5d"].nunique() < 2 or g["fwd_ret_5d"].nunique() < 2:
            ic = np.nan
        else:
            ic = g["pred_score_5d"].corr(g["fwd_ret_5d"], method="spearman")
        rows.append({"date": date, "row_count": len(g), "rank_ic": ic})
    return pd.DataFrame(rows)


def _score_stats(s: pd.Series) -> dict[str, float | None]:
    if s.empty:
        return {k: None for k in ["mean", "std", "min", "max", "p01", "p05", "p50", "p95", "p99"]}
    return {
        "mean": float(s.mean()),
        "std": float(s.std(ddof=0)),
        "min": float(s.min()),
        "max": float(s.max()),
        "p01": float(s.quantile(0.01)),
        "p05": float(s.quantile(0.05)),
        "p50": float(s.quantile(0.50)),
        "p95": float(s.quantile(0.95)),
        "p99": float(s.quantile(0.99)),
    }


def build_metrics(preds: pd.DataFrame, cfg: dict[str, Any]) -> tuple[dict[str, object], dict[str, pd.DataFrame]]:
    blockers: list[str] = []
    warnings: list[str] = []
    if preds.empty:
        blockers.append("missing_oos_predictions")
        return {"blockers": blockers, "warnings": warnings}, {}

    df = preds.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    missing_rows = int(df[["pred_score_5d", "fwd_ret_5d"]].isna().any(axis=1).sum())
    if missing_rows:
        warnings.append("missing_or_null_prediction_rows")
    df = df.dropna(subset=["pred_score_5d", "fwd_ret_5d"]).copy()

    deciles = int(cfg.get("decile_buckets", 10))
    quintiles = int(cfg.get("quintile_buckets", 5))
    cost_bps = float(cfg["round_trip_cost_bps"])
    outlier_threshold = float(cfg.get("score_outlier_abs_threshold", 5.0))

    names_by_date = df.groupby("date").size()
    too_few_decile_dates = int((names_by_date < deciles).sum())
    too_few_quintile_dates = int((names_by_date < quintiles).sum())
    if too_few_decile_dates:
        warnings.append("dates_with_too_few_names_for_deciles")
    if too_few_quintile_dates:
        warnings.append("dates_with_too_few_names_for_quintiles")

    df["decile"] = assign_score_buckets(df, deciles)
    df["quintile"] = assign_score_buckets(df, quintiles)
    decile_returns = bucket_forward_returns(df, "decile")
    quintile_returns = bucket_forward_returns(df, "quintile")
    daily_ls = daily_long_short_from_buckets(df, "decile", deciles, 1, cost_bps)
    ic_by_date = rank_ic_by_date(df)

    score_stats = _score_stats(df["pred_score_5d"])
    ic = ic_by_date["rank_ic"].dropna()
    rank_ic_t = float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 1 and ic.std(ddof=1) != 0 else None

    fold_rows = []
    for fold_id, g in df.groupby("fold_id", sort=True):
        fold_daily = daily_long_short_from_buckets(g.assign(decile=assign_score_buckets(g, deciles)), "decile", deciles, 1, cost_bps)
        fold_ic = rank_ic_by_date(g)["rank_ic"].dropna()
        stats = _score_stats(g["pred_score_5d"])
        outlier = bool(max(abs(stats["min"] or 0), abs(stats["max"] or 0)) > outlier_threshold)
        if outlier:
            warnings.append(f"fold_{int(fold_id)}_score_outlier")
        fold_rows.append(
            {
                "fold_id": int(fold_id),
                "row_count": int(len(g)),
                "score_mean": stats["mean"],
                "score_std": stats["std"],
                "score_min": stats["min"],
                "score_max": stats["max"],
                "mean_rank_ic": float(fold_ic.mean()) if len(fold_ic) else None,
                "long_short_gross_return": float(fold_daily["long_short_gross_return"].mean()) if not fold_daily.empty else None,
                "long_short_net_return": float(fold_daily["long_short_net_return"].mean()) if not fold_daily.empty else None,
            }
        )
    fold_metrics = pd.DataFrame(fold_rows)
    score_diag = fold_metrics[["fold_id", "row_count", "score_mean", "score_std", "score_min", "score_max"]].copy()
    score_diag["abs_score_outlier"] = score_diag[["score_min", "score_max"]].abs().max(axis=1) > outlier_threshold

    decile_mean = decile_returns.groupby("decile")["mean_fwd_ret_5d"].mean().to_dict()
    quintile_mean = quintile_returns.groupby("quintile")["mean_fwd_ret_5d"].mean().to_dict()
    summary = {
        "total_oos_rows": int(len(df)),
        "min_date": str(min(df["date"])),
        "max_date": str(max(df["date"])),
        "fold_count": int(df["fold_id"].nunique()),
        "score": score_stats,
        "missing_or_null_prediction_rows": missing_rows,
        "dates_with_too_few_names_for_decile_ranking": too_few_decile_dates,
        "dates_with_too_few_names_for_quintile_ranking": too_few_quintile_dates,
        "mean_daily_rank_ic": float(ic.mean()) if len(ic) else None,
        "rank_ic_t_stat": rank_ic_t,
        "decile_mean_forward_return": {str(int(k)): float(v) for k, v in decile_mean.items()},
        "quintile_mean_forward_return": {str(int(k)): float(v) for k, v in quintile_mean.items()},
        "top_decile_gross_return": float(daily_ls["long_gross_return"].mean()) if not daily_ls.empty else None,
        "top_decile_net_return": float(daily_ls["long_net_return"].mean()) if not daily_ls.empty else None,
        "bottom_decile_gross_short_return": float(daily_ls["short_gross_return"].mean()) if not daily_ls.empty else None,
        "bottom_decile_net_short_return": float(daily_ls["short_net_return"].mean()) if not daily_ls.empty else None,
        "long_short_gross_return": float(daily_ls["long_short_gross_return"].mean()) if not daily_ls.empty else None,
        "long_short_net_return": float(daily_ls["long_short_net_return"].mean()) if not daily_ls.empty else None,
        "long_basket_hit_rate": float(daily_ls["long_hit_rate"].mean()) if not daily_ls.empty else None,
        "short_basket_hit_rate": float(daily_ls["short_hit_rate"].mean()) if not daily_ls.empty else None,
        "round_trip_cost_bps": cost_bps,
        "blockers": blockers,
        "warnings": sorted(set(warnings)),
    }
    reports = {
        "decile_returns": decile_returns,
        "quintile_returns": quintile_returns,
        "daily_long_short": daily_ls,
        "fold_metrics": fold_metrics,
        "score_diagnostics": score_diag,
    }
    return summary, reports


def run_metrics(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_execution_costs()
    summary, reports = build_metrics(read_oos_predictions(p.oos_predictions_baseline_h5), cfg)
    p.metrics_reports.mkdir(parents=True, exist_ok=True)
    for name, df in reports.items():
        df.to_csv(p.metrics_reports / f"baseline_h5_{name}.csv", index=False)
    (p.metrics_reports / "baseline_h5_metrics_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return summary
