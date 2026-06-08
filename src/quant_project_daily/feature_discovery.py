from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import yaml

from quant_project_daily.config import REPO_ROOT, ProjectPaths, project_paths


def load_feature_selection_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "feature_selection.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json_list(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_leakage_col(name: str, tokens: list[str]) -> bool:
    low = name.lower()
    return any(tok in low for tok in tokens)


def _sign_stability(values: pd.Series) -> float:
    s = values.dropna()
    if s.empty:
        return 0.0
    sign = np.sign(s.mean())
    if sign == 0:
        return 0.0
    return float((np.sign(s) == sign).mean())


def _daily_spearman(features: pd.DataFrame, target: pd.Series, dates: pd.Series) -> pd.Series:
    rows: list[pd.Series] = []
    work = features.copy()
    work["_target"] = target
    work["_date"] = pd.to_datetime(dates).to_numpy()
    feature_cols = list(features.columns)
    for _, g in work.groupby("_date", sort=False):
        y = g["_target"]
        valid = y.notna()
        if valid.sum() < 3 or y[valid].nunique(dropna=True) < 2:
            continue
        x_rank = g.loc[valid, feature_cols].rank(method="average")
        y_rank = y[valid].rank(method="average")
        rows.append(x_rank.corrwith(y_rank))
    if not rows:
        return pd.Series(index=feature_cols, dtype=float)
    return pd.concat(rows, axis=1).mean(axis=1, skipna=True)


def _spearman_corr_sample(x: pd.DataFrame, fold_id: int, cfg: dict[str, Any]) -> pd.DataFrame:
    max_rows = int(cfg.get("correlation_sample_rows_per_fold", 0) or 0)
    if max_rows > 0 and len(x) > max_rows:
        x = x.sample(n=max_rows, random_state=fold_id)
    return x.corr(method="spearman").abs()


def _discover_features_for_folds_lazy(
    parquet_path: Path,
    split_plan: pd.DataFrame,
    feature_cols: list[str],
    cfg: dict[str, Any],
    log_progress: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    target_col = cfg["target_column"]
    usable_features = [f for f in feature_cols if not _is_leakage_col(f, cfg["leakage_tokens"])]
    lf = pl.scan_parquet(str(parquet_path)).select(["date", target_col] + usable_features).with_columns(pl.col("date").cast(pl.Date))
    fold_rows: list[dict[str, object]] = []
    corr_frames: list[pd.DataFrame] = []
    train_rows_loaded = 0
    min_train_date = None
    max_train_date = None
    total_start = time.perf_counter()
    for _, fold in split_plan.sort_values("fold_id").iterrows():
        fold_start = time.perf_counter()
        fold_id = int(fold["fold_id"])
        start = pd.Timestamp(fold["train_start_date"]).date()
        end = pd.Timestamp(fold["train_end_date"]).date()
        planned_train_rows = int(fold["train_row_count"]) if "train_row_count" in fold and pd.notna(fold["train_row_count"]) else None
        if log_progress:
            rows_text = planned_train_rows if planned_train_rows is not None else "unknown"
            print(
                f"[stage21] fold_start fold_id={fold_id} train_start_date={start} "
                f"train_end_date={end} train_row_count={rows_text} feature_count={len(usable_features)}",
                file=sys.stderr,
                flush=True,
            )
        train_lf = lf.filter((pl.col("date") >= start) & (pl.col("date") <= end))
        stat_exprs = [pl.len().alias("__train_row_count")]
        for f in usable_features:
            fc = pl.col(f).cast(pl.Float64)
            stat_exprs.extend(
                [
                    pl.col(f).is_not_null().mean().alias(f"{f}__non_null_pct"),
                    (pl.col(f).is_not_null() & fc.is_finite()).mean().alias(f"{f}__finite_pct"),
                    fc.std(ddof=0).alias(f"{f}__std"),
                ]
            )
        stats = train_lf.select(stat_exprs).collect().to_dicts()[0]
        train_n = int(stats["__train_row_count"])
        train_rows_loaded += train_n
        min_train_date = start if min_train_date is None else min(min_train_date, start)
        max_train_date = end if max_train_date is None else max(max_train_date, end)
        rank_exprs = [pl.col(f).cast(pl.Float64).rank("average").alias(f) for f in usable_features]
        fold_corr = (
            train_lf.select(rank_exprs + [pl.col(target_col).cast(pl.Float64).rank("average").alias("__target_rank")])
            .select([pl.corr(pl.col(f), pl.col("__target_rank")).alias(f) for f in usable_features])
            .collect()
            .to_dicts()[0]
        )
        daily_corr = (
            train_lf.select(
                [pl.col("date")]
                + [pl.col(f).cast(pl.Float64).rank("average").over("date").alias(f) for f in usable_features]
                + [pl.col(target_col).cast(pl.Float64).rank("average").over("date").alias("__target_rank")]
            )
            .group_by("date")
            .agg([pl.corr(pl.col(f), pl.col("__target_rank")).alias(f) for f in usable_features])
            .select([pl.col(f).mean().alias(f) for f in usable_features])
            .collect()
            .to_dicts()[0]
        )
        for f in usable_features:
            fold_rows.append(
                {
                    "fold_id": fold_id,
                    "feature": f,
                    "train_start_date": str(start),
                    "train_end_date": str(end),
                    "train_row_count": train_n,
                    "non_null_pct": float(stats[f"{f}__non_null_pct"]),
                    "finite_pct": float(stats[f"{f}__finite_pct"]),
                    "std": stats[f"{f}__std"],
                    "mean_daily_rank_ic": daily_corr[f],
                    "fold_rank_ic": fold_corr[f],
                }
            )
        mean_abs_rank_ic = pd.Series(daily_corr, dtype="float64").abs().mean(skipna=True)
        date_stride = max(1, int(cfg.get("correlation_sample_date_stride", 20) or 20))
        sample_dates = train_lf.select("date").unique().sort("date").collect()["date"].to_list()[::date_stride]
        sample = (
            train_lf.filter(pl.col("date").is_in(sample_dates))
            .select([pl.col(f).cast(pl.Float64).alias(f) for f in usable_features])
            .collect()
            .to_pandas()
        )
        corr = _spearman_corr_sample(sample, fold_id, cfg)
        pairs = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack().reset_index()
        pairs.columns = ["feature_a", "feature_b", "abs_corr"]
        pairs["fold_id"] = fold_id
        corr_frames.append(pairs)
        if log_progress:
            elapsed = time.perf_counter() - fold_start
            ic_text = "nan" if pd.isna(mean_abs_rank_ic) else f"{float(mean_abs_rank_ic):.6g}"
            print(
                f"[stage21] fold_done fold_id={fold_id} elapsed_seconds={elapsed:.1f} "
                f"features_scored={len(usable_features)} mean_abs_rank_ic={ic_text}",
                file=sys.stderr,
                flush=True,
            )
    by_fold = pd.DataFrame(fold_rows)
    if by_fold.empty:
        return by_fold, pd.DataFrame(), pd.DataFrame(), {"train_rows_loaded": 0, "min_train_date": None, "max_train_date": None}
    agg = (
        by_fold.groupby("feature", sort=False)
        .agg(
            folds_scored=("fold_id", "nunique"),
            non_null_pct=("non_null_pct", "mean"),
            finite_pct=("finite_pct", "mean"),
            std=("std", "mean"),
            mean_daily_rank_ic=("mean_daily_rank_ic", "mean"),
            mean_fold_rank_ic=("fold_rank_ic", "mean"),
            abs_mean_rank_ic=("mean_daily_rank_ic", lambda s: float(abs(s.dropna().mean())) if not s.dropna().empty else np.nan),
            sign_stability=("fold_rank_ic", _sign_stability),
        )
        .reset_index()
    )
    fold_maps = by_fold.pivot(index="feature", columns="fold_id", values="fold_rank_ic")
    agg["fold_rank_ic_by_fold"] = agg["feature"].map(lambda f: json.dumps({str(k): None if pd.isna(v) else float(v) for k, v in fold_maps.loc[f].items()}))
    corr_by_pair = pd.concat(corr_frames, ignore_index=True) if corr_frames else pd.DataFrame()
    if not corr_by_pair.empty:
        corr_by_pair = (
            corr_by_pair.groupby(["feature_a", "feature_b"], sort=False)
            .agg(folds=("fold_id", "nunique"), mean_abs_corr=("abs_corr", "mean"), max_abs_corr=("abs_corr", "max"))
            .reset_index()
            .sort_values(["max_abs_corr", "feature_a", "feature_b"], ascending=[False, True, True], kind="mergesort")
        )
    stats = {"train_rows_loaded": int(train_rows_loaded), "min_train_date": str(min_train_date), "max_train_date": str(max_train_date)}
    if log_progress:
        print(
            f"[stage21] all_folds_done total_elapsed_seconds={time.perf_counter() - total_start:.1f} "
            f"folds_used={int(split_plan['fold_id'].nunique())} features_scored={int(len(agg))}",
            file=sys.stderr,
            flush=True,
        )
    return by_fold, agg, corr_by_pair, stats


def discover_features_for_folds(
    matrix: pd.DataFrame,
    split_plan: pd.DataFrame,
    feature_cols: list[str],
    cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    target_col = cfg["target_column"]
    tokens = cfg["leakage_tokens"]
    usable_features = [f for f in feature_cols if f in matrix.columns and not _is_leakage_col(f, tokens)]
    df = matrix.copy()
    df["date"] = pd.to_datetime(df["date"])
    fold_rows: list[dict[str, object]] = []
    corr_frames: list[pd.DataFrame] = []
    for _, fold in split_plan.sort_values("fold_id").iterrows():
        start = pd.Timestamp(fold["train_start_date"])
        end = pd.Timestamp(fold["train_end_date"])
        train = df[(df["date"] >= start) & (df["date"] <= end)]
        if train.empty:
            continue
        raw_x = train[usable_features].apply(pd.to_numeric, errors="coerce")
        non_null_pct = raw_x.notna().mean()
        finite_mask = np.isfinite(raw_x)
        finite_pct = finite_mask.mean()
        x = raw_x.where(finite_mask)
        y = pd.to_numeric(train[target_col], errors="coerce").replace([np.inf, -np.inf], np.nan)
        std = x.std(ddof=0)
        fold_rank_ic = x.corrwith(y, method="spearman")
        mean_daily_rank_ic = _daily_spearman(x, y, train["date"])
        corr = _spearman_corr_sample(x, int(fold["fold_id"]), cfg)
        pairs = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack().reset_index()
        pairs.columns = ["feature_a", "feature_b", "abs_corr"]
        pairs["fold_id"] = int(fold["fold_id"])
        corr_frames.append(pairs)
        for feature in usable_features:
            fold_rows.append(
                {
                    "fold_id": int(fold["fold_id"]),
                    "feature": feature,
                    "train_start_date": str(start.date()),
                    "train_end_date": str(end.date()),
                    "train_row_count": int(len(train)),
                    "non_null_pct": float(non_null_pct[feature]),
                    "finite_pct": float(finite_pct[feature]),
                    "std": float(std[feature]) if pd.notna(std[feature]) else np.nan,
                    "mean_daily_rank_ic": float(mean_daily_rank_ic[feature]) if pd.notna(mean_daily_rank_ic[feature]) else np.nan,
                    "fold_rank_ic": float(fold_rank_ic[feature]) if pd.notna(fold_rank_ic[feature]) else np.nan,
                }
            )
    by_fold = pd.DataFrame(fold_rows)
    if by_fold.empty:
        return by_fold, pd.DataFrame(), pd.DataFrame()
    agg = (
        by_fold.groupby("feature", sort=False)
        .agg(
            folds_scored=("fold_id", "nunique"),
            non_null_pct=("non_null_pct", "mean"),
            finite_pct=("finite_pct", "mean"),
            std=("std", "mean"),
            mean_daily_rank_ic=("mean_daily_rank_ic", "mean"),
            mean_fold_rank_ic=("fold_rank_ic", "mean"),
            abs_mean_rank_ic=("mean_daily_rank_ic", lambda s: float(abs(s.dropna().mean())) if not s.dropna().empty else np.nan),
            sign_stability=("fold_rank_ic", _sign_stability),
        )
        .reset_index()
    )
    fold_maps = by_fold.pivot(index="feature", columns="fold_id", values="fold_rank_ic")
    agg["fold_rank_ic_by_fold"] = agg["feature"].map(lambda f: json.dumps({str(k): None if pd.isna(v) else float(v) for k, v in fold_maps.loc[f].items()}))
    corr_by_pair = pd.concat(corr_frames, ignore_index=True) if corr_frames else pd.DataFrame()
    if not corr_by_pair.empty:
        corr_by_pair = (
            corr_by_pair.groupby(["feature_a", "feature_b"], sort=False)
            .agg(folds=("fold_id", "nunique"), mean_abs_corr=("abs_corr", "mean"), max_abs_corr=("abs_corr", "max"))
            .reset_index()
            .sort_values(["max_abs_corr", "feature_a", "feature_b"], ascending=[False, True, True], kind="mergesort")
        )
    return by_fold, agg, corr_by_pair


def _load_matrix_for_plan(paths: ProjectPaths, folds: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    path = paths.feature_matrix_expanded_h20 / "expanded_h20.parquet"
    if not path.exists():
        files = sorted(paths.feature_matrix_expanded_h20.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"missing expanded parquet under {paths.feature_matrix_expanded_h20}")
        path = files[0]
    start = pd.to_datetime(folds["train_start_date"]).min().date()
    end = pd.to_datetime(folds["train_end_date"]).max().date()
    df = pd.read_parquet(path, columns=columns, filters=[("date", ">=", start), ("date", "<=", end)])
    df["date"] = pd.to_datetime(df["date"])
    return df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]


def run_feature_discovery(max_folds: int | None = None, fold_id: int | None = None, paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_feature_selection_config()
    feature_cols = _load_json_list(p.feature_matrix_expanded_h20 / "feature_cols.json")
    plan = pd.read_csv(p.wfa_reports / "baseline_h20_split_plan.csv").sort_values("fold_id")
    if fold_id is not None:
        plan = plan[plan["fold_id"] == fold_id]
    if max_folds is not None:
        plan = plan.head(max_folds)
    if plan.empty:
        raise ValueError(f"no WFA folds selected for fold_id={fold_id} max_folds={max_folds}")
    parquet_path = p.feature_matrix_expanded_h20 / "expanded_h20.parquet"
    if not parquet_path.exists():
        files = sorted(p.feature_matrix_expanded_h20.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"missing expanded parquet under {p.feature_matrix_expanded_h20}")
        parquet_path = files[0]
    by_fold, discovery, corr_by_pair, load_stats = _discover_features_for_folds_lazy(parquet_path, plan, feature_cols, cfg)
    p.feature_reports.mkdir(parents=True, exist_ok=True)
    discovery_path = p.feature_reports / "expanded_h20_feature_discovery.csv"
    discovery.to_csv(discovery_path, index=False)
    by_fold.to_csv(p.feature_reports / "expanded_h20_feature_discovery_by_fold.csv", index=False)
    corr_by_pair.to_csv(p.feature_reports / "expanded_h20_feature_correlations.csv", index=False)
    summary = {
        "folds_used": int(plan["fold_id"].nunique()),
        "features_scored": int(len(discovery)),
        "train_rows_loaded": load_stats["train_rows_loaded"],
        "min_train_date": load_stats["min_train_date"],
        "max_train_date": load_stats["max_train_date"],
        "source_matrix": str(parquet_path),
        "discovery_path": str(discovery_path),
        "blockers": [],
        "warnings": [],
    }
    if int(cfg.get("correlation_sample_rows_per_fold", 0) or 0) > 0 or int(cfg.get("correlation_sample_date_stride", 0) or 0) > 1:
        summary["warnings"].append("feature correlation pruning diagnostics use deterministic train-date/train-row samples per fold")
    (p.feature_reports / "expanded_h20_feature_discovery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-folds", type=int, default=None)
    ap.add_argument("--fold-id", type=int, default=None)
    return ap.parse_args()
