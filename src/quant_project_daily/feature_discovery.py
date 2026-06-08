from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
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
    valid_target = target.notna()
    features = features.loc[valid_target]
    target = target.loc[valid_target]
    dates = dates.loc[valid_target]
    ranked_x = features.groupby(dates, sort=False).rank(method="average")
    ranked_y = target.groupby(dates, sort=False).rank(method="average")
    x_dev = ranked_x - ranked_x.groupby(dates, sort=False).transform("mean")
    y_dev = ranked_y - ranked_y.groupby(dates, sort=False).transform("mean")
    cov = x_dev.mul(y_dev, axis=0).groupby(dates, sort=False).sum(min_count=2)
    x_ss = x_dev.pow(2).groupby(dates, sort=False).sum(min_count=2)
    y_ss = y_dev.pow(2).groupby(dates, sort=False).sum(min_count=2)
    corr = cov.div(np.sqrt(x_ss.mul(y_ss, axis=0)), axis=0).replace([np.inf, -np.inf], np.nan)
    return corr.mean(skipna=True)


def discover_features_for_folds(
    matrix: pd.DataFrame,
    split_plan: pd.DataFrame,
    feature_cols: list[str],
    cfg: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_col = cfg["target_column"]
    tokens = cfg["leakage_tokens"]
    usable_features = [f for f in feature_cols if f in matrix.columns and not _is_leakage_col(f, tokens)]
    df = matrix.copy()
    df["date"] = pd.to_datetime(df["date"])
    fold_rows: list[dict[str, object]] = []
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
        return by_fold, pd.DataFrame()
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
    return by_fold, agg


def _load_matrix_for_plan(paths: ProjectPaths, folds: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    path = paths.feature_matrix_expanded_h20 / "expanded_h20.parquet"
    if not path.exists():
        files = sorted(paths.feature_matrix_expanded_h20.glob("*.parquet"))
        if not files:
            raise FileNotFoundError(f"missing expanded parquet under {paths.feature_matrix_expanded_h20}")
        path = files[0]
    start = str(pd.to_datetime(folds["train_start_date"]).min().date())
    end = str(pd.to_datetime(folds["train_end_date"]).max().date())
    df = pd.read_parquet(path, columns=columns)
    df["date"] = pd.to_datetime(df["date"])
    return df[(df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))]


def run_feature_discovery(max_folds: int | None = None, paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_feature_selection_config()
    feature_cols = _load_json_list(p.feature_matrix_expanded_h20 / "feature_cols.json")
    plan = pd.read_csv(p.wfa_reports / "baseline_h20_split_plan.csv").sort_values("fold_id")
    if max_folds is not None:
        plan = plan.head(max_folds)
    cols = ["date", cfg["target_column"]] + feature_cols
    matrix = _load_matrix_for_plan(p, plan, cols)
    by_fold, discovery = discover_features_for_folds(matrix, plan, feature_cols, cfg)
    p.feature_reports.mkdir(parents=True, exist_ok=True)
    discovery_path = p.feature_reports / "expanded_h20_feature_discovery.csv"
    discovery.to_csv(discovery_path, index=False)
    by_fold.to_csv(p.feature_reports / "expanded_h20_feature_discovery_by_fold.csv", index=False)
    summary = {
        "folds_used": int(plan["fold_id"].nunique()),
        "features_scored": int(len(discovery)),
        "train_rows_loaded": int(len(matrix)),
        "min_train_date": str(matrix["date"].min().date()) if not matrix.empty else None,
        "max_train_date": str(matrix["date"].max().date()) if not matrix.empty else None,
        "source_matrix": str(p.feature_matrix_expanded_h20 / "expanded_h20.parquet"),
        "discovery_path": str(discovery_path),
        "blockers": [],
        "warnings": [],
    }
    (p.feature_reports / "expanded_h20_feature_discovery_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-folds", type=int, default=None)
    return ap.parse_args()
