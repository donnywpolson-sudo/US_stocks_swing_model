from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import yaml
from sklearn.linear_model import Ridge

from scripts.project_config import REPO_ROOT, ProjectPaths, project_paths, reset_parquet_output_dir


PREDICTION_COLUMNS = [
    "fold_id",
    "date",
    "ticker",
    "raw_ticker",
    "target_class_5d",
    "fwd_ret_5d",
    "pred_score_5d",
    "pred_rank_pct_by_date",
    "pred_long_rank_5d",
    "pred_short_rank_5d",
]

FORBIDDEN_FEATURE_COLUMNS = {
    "target_class_5d",
    "fwd_ret_5d",
    "target_long_top20_5d",
    "target_short_bottom20_5d",
    "label_valid_5d",
    "next_open",
    "exit_close_5d",
    "exit_date_5d",
}


@dataclass(frozen=True)
class FoldResult:
    predictions: pd.DataFrame
    summary: dict[str, object]


def load_model_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / "baseline_model.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_json_list(path: Path) -> list[str]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_feature_cols(feature_cols: list[str], target_cols: list[str], excluded_cols: list[str], metadata_cols: list[str]) -> None:
    leakage = FORBIDDEN_FEATURE_COLUMNS | set(target_cols) | set(excluded_cols) | set(metadata_cols)
    overlap = sorted(set(feature_cols) & leakage)
    if overlap:
        raise ValueError(f"feature_cols contain leakage columns: {overlap}")


def _fit_transform_train_only(train: pd.DataFrame, test: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, np.ndarray]:
    train_x = train[feature_cols].astype("float64")
    test_x = test[feature_cols].astype("float64")
    med = train_x.median(axis=0).fillna(0.0)
    train_x = train_x.fillna(med)
    test_x = test_x.fillna(med)
    mean = train_x.mean(axis=0)
    std = train_x.std(axis=0, ddof=0).replace(0.0, 1.0).fillna(1.0)
    return ((train_x - mean) / std).to_numpy(), ((test_x - mean) / std).to_numpy()


def run_fold(
    matrix: pd.DataFrame,
    fold: pd.Series | dict[str, object],
    feature_cols: list[str],
    model_cfg: dict[str, Any],
) -> FoldResult:
    f = pd.Series(fold)
    df = matrix.copy()
    df["date"] = pd.to_datetime(df["date"])
    train_start = pd.Timestamp(f["train_start_date"])
    train_end = pd.Timestamp(f["train_end_date"])
    test_start = pd.Timestamp(f["test_start_date"])
    test_end = pd.Timestamp(f["test_end_date"])

    train = df[(df["date"] >= train_start) & (df["date"] <= train_end)].copy()
    test = df[(df["date"] >= test_start) & (df["date"] <= test_end)].copy()
    if set(train["date"]).intersection(set(test["date"])):
        raise ValueError(f"train/test date overlap in fold {f['fold_id']}")
    if not (train["date"].max() < test_start):
        raise ValueError(f"train dates not before test_start in fold {f['fold_id']}")

    x_train, x_test = _fit_transform_train_only(train, test, feature_cols)
    y_train = train[model_cfg["target_column"]].astype("float64").to_numpy()
    model = Ridge(alpha=float(model_cfg.get("ridge_alpha", 1.0)))
    model.fit(x_train, y_train)

    pred = test[["date", "ticker", "raw_ticker", "target_class_5d", "fwd_ret_5d"]].copy()
    pred.insert(0, "fold_id", int(f["fold_id"]))
    pred["pred_score_5d"] = model.predict(x_test)
    pred["pred_rank_pct_by_date"] = pred.groupby("date")["pred_score_5d"].rank(pct=True, method="average")
    pred["pred_long_rank_5d"] = pred.groupby("date")["pred_score_5d"].rank(ascending=False, method="first").astype("int64")
    pred["pred_short_rank_5d"] = pred.groupby("date")["pred_score_5d"].rank(ascending=True, method="first").astype("int64")
    pred["date"] = pred["date"].dt.date
    pred = pred[PREDICTION_COLUMNS]

    s = pred["pred_score_5d"]
    summary = {
        "fold_id": int(f["fold_id"]),
        "train_row_count": int(len(train)),
        "test_row_count": int(len(test)),
        "prediction_row_count": int(len(pred)),
        "pred_score_mean": float(s.mean()) if len(s) else None,
        "pred_score_std": float(s.std(ddof=0)) if len(s) else None,
        "pred_score_min": float(s.min()) if len(s) else None,
        "pred_score_max": float(s.max()) if len(s) else None,
        "test_start_date": str(test_start.date()),
        "test_end_date": str(test_end.date()),
    }
    return FoldResult(pred, summary)


def select_folds(plan: pd.DataFrame, max_folds: int | None = None, fold_id: int | None = None) -> pd.DataFrame:
    out = plan.copy()
    if fold_id is not None:
        out = out[out["fold_id"] == fold_id]
    if max_folds is not None:
        out = out.head(max_folds)
    return out.reset_index(drop=True)


def _read_matrix_for_fold(feature_path: Path, fold: pd.Series, cols: list[str]) -> pd.DataFrame:
    files = sorted(feature_path.rglob("*.parquet")) if feature_path.is_dir() else [feature_path]
    start = min(pd.Timestamp(fold["train_start_date"]), pd.Timestamp(fold["test_start_date"])).date()
    end = max(pd.Timestamp(fold["train_end_date"]), pd.Timestamp(fold["test_end_date"])).date()
    lf = pl.scan_parquet([str(f) for f in files]).with_columns(pl.col("date").cast(pl.Date, strict=False))
    df = lf.filter((pl.col("date") >= start) & (pl.col("date") <= end)).select(cols).collect()
    return df.to_pandas()


def _log_fold_start(fold: pd.Series) -> None:
    print(
        "[stage15] fold_start "
        f"fold_id={int(fold['fold_id'])} "
        f"train_rows={int(fold['train_row_count'])} "
        f"test_rows={int(fold['test_row_count'])} "
        f"train_dates={fold['train_start_date']}..{fold['train_end_date']} "
        f"test_dates={fold['test_start_date']}..{fold['test_end_date']}",
        flush=True,
    )


def _log_fold_done(summary: dict[str, object], elapsed_seconds: float) -> None:
    print(
        "[stage15] fold_done "
        f"fold_id={summary['fold_id']} "
        f"elapsed_seconds={elapsed_seconds:.1f} "
        f"pred_score_mean={summary['pred_score_mean']} "
        f"pred_score_std={summary['pred_score_std']} "
        f"pred_score_min={summary['pred_score_min']} "
        f"pred_score_max={summary['pred_score_max']} "
        f"oos_rows_written={summary['prediction_row_count']}",
        flush=True,
    )


def run_baseline_wfa(max_folds: int | None = None, fold_id: int | None = None, paths: ProjectPaths | None = None) -> dict[str, object]:
    total_started = time.perf_counter()
    p = paths or project_paths()
    model_cfg = load_model_config()
    feature_cols = _load_json_list(p.feature_matrix_baseline_h5 / "feature_cols.json")
    target_cols = _load_json_list(p.feature_matrix_baseline_h5 / "target_cols.json")
    metadata_cols = _load_json_list(p.feature_matrix_baseline_h5 / "metadata_cols.json")
    excluded_cols = _load_json_list(p.feature_matrix_baseline_h5 / "excluded_cols.json")
    validate_feature_cols(feature_cols, target_cols, excluded_cols, metadata_cols)

    plan = pd.read_csv(p.wfa_reports / "baseline_h5_split_plan.csv")
    requested = select_folds(plan, max_folds=max_folds, fold_id=fold_id)
    reset_parquet_output_dir(p.oos_predictions_baseline_h5)
    p.wfa_reports.mkdir(parents=True, exist_ok=True)

    need_cols = sorted(set(feature_cols + ["date", "ticker", "raw_ticker", "target_class_5d", "fwd_ret_5d"]))
    fold_summaries = []
    failed = []
    all_preds = []
    for _, fold in requested.iterrows():
        _log_fold_start(fold)
        fold_started = time.perf_counter()
        try:
            matrix = _read_matrix_for_fold(p.feature_matrix_baseline_h5, fold, need_cols)
            result = run_fold(matrix, fold, feature_cols, model_cfg)
            result.predictions.to_parquet(p.oos_predictions_baseline_h5 / f"fold_{int(fold['fold_id']):03d}.parquet", index=False)
            all_preds.append(result.predictions)
            fold_summaries.append(result.summary)
            _log_fold_done(result.summary, time.perf_counter() - fold_started)
        except Exception as exc:
            failed.append({"fold_id": int(fold["fold_id"]), "error": str(exc)})
            print(
                "[stage15] fold_failed "
                f"fold_id={int(fold['fold_id'])} "
                f"elapsed_seconds={time.perf_counter() - fold_started:.1f} "
                f"error={exc}",
                flush=True,
            )

    fold_df = pd.DataFrame(fold_summaries)
    fold_df.to_csv(p.wfa_reports / "baseline_h5_fold_summary.csv", index=False)
    preds = pd.concat(all_preds, ignore_index=True) if all_preds else pd.DataFrame(columns=PREDICTION_COLUMNS)
    summary = {
        "folds_requested": int(len(requested)),
        "folds_completed": int(len(fold_summaries)),
        "folds_failed": int(len(failed)),
        "total_oos_rows": int(len(preds)),
        "feature_count": int(len(feature_cols)),
        "model_type": model_cfg["model_type"],
        "min_prediction_date": str(min(preds["date"])) if not preds.empty else None,
        "max_prediction_date": str(max(preds["date"])) if not preds.empty else None,
        "per_fold": fold_summaries,
        "blockers": failed,
        "warnings": [],
    }
    (p.wfa_reports / "baseline_h5_oos_summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"[stage15] all_folds_done total_elapsed_seconds={time.perf_counter() - total_started:.1f}", flush=True)
    if failed:
        failed_ids = [f["fold_id"] for f in failed]
        raise RuntimeError(f"{len(failed)} fold(s) failed: {failed_ids}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=None)
    parser.add_argument("--fold-id", type=int, default=None)
    return parser.parse_args()
