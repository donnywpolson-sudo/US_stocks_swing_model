from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from scripts.phase7_wfa.baseline_wfa import (
    _load_json_list,
    _read_matrix_for_fold,
    load_model_config,
    run_fold,
    select_folds,
    validate_feature_cols,
)
from scripts.phase4_features.column_registry import build_column_registry
from scripts.project_config import REPO_ROOT, ProjectPaths, project_paths, reset_parquet_output_dir
from scripts.phase4_features.features_baseline import _add_baseline_feature_columns_polars, _feature_summary
from scripts.phase3_labels.targets_vol_norm import vol_norm60_target_path


VOL_NORM60_FEATURE_SET = "long_only_h5_vol_norm60_target"
VOL_NORM60_FEATURE_CONFIG = REPO_ROOT / "configs" / f"{VOL_NORM60_FEATURE_SET}_features.yaml"
VOL_NORM60_MODEL_CONFIG = REPO_ROOT / "configs" / f"{VOL_NORM60_FEATURE_SET}_model.yaml"
VOL_NORM60_TARGET_COLUMN = "target_class_5d_vol_norm60"
VOL_NORM60_RETURN_COLUMN = "fwd_ret_5d_vol_norm60"
VOL_NORM60_LABEL_VALID_COLUMN = "label_valid_5d_vol_norm60"


def load_vol_norm60_target_feature_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or VOL_NORM60_FEATURE_CONFIG
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base_config_path = cfg.get("base_config_path")
    if base_config_path:
        with (REPO_ROOT / str(base_config_path)).open("r", encoding="utf-8") as f:
            base = yaml.safe_load(f)
        return {
            **base,
            **cfg,
            "feature_columns": list(cfg.get("feature_columns", base["feature_columns"])),
            "target_columns": list(cfg.get("target_columns", base["target_columns"])),
            "metadata_columns": list(cfg.get("metadata_columns", base["metadata_columns"])),
            "excluded_columns": list(cfg.get("excluded_columns", base["excluded_columns"])),
        }
    return cfg


def vol_norm60_feature_matrix_path(paths: ProjectPaths | None = None) -> Path:
    p = paths or project_paths()
    return p.repo_root / "data" / "feature_matrices" / VOL_NORM60_FEATURE_SET


def vol_norm60_oos_prediction_path(paths: ProjectPaths | None = None) -> Path:
    p = paths or project_paths()
    return p.repo_root / "data" / "oos_predictions" / VOL_NORM60_FEATURE_SET


def _feature_set_parquet_name() -> str:
    return f"{VOL_NORM60_FEATURE_SET}.parquet"


def _feature_set_summary_name() -> str:
    return f"{VOL_NORM60_FEATURE_SET}_summary.json"


def _feature_set_oos_summary_name() -> str:
    return f"{VOL_NORM60_FEATURE_SET}_oos_summary.json"


def _feature_set_fold_summary_name() -> str:
    return f"{VOL_NORM60_FEATURE_SET}_fold_summary.csv"


def _build_vol_norm60_target_features_polars(
    p: ProjectPaths,
    cfg: dict[str, Any],
) -> tuple[Any, dict[str, object], dict[str, list[str]]]:
    import polars as pl

    feature_cols = list(cfg["feature_columns"])
    target_cols = list(cfg["target_columns"])
    metadata_cols = list(cfg["metadata_columns"])
    excluded_cols = list(cfg["excluded_columns"])
    label_valid_col = str(cfg.get("filter_label_valid_column", VOL_NORM60_LABEL_VALID_COLUMN))

    df = pl.read_parquet(str(vol_norm60_target_path(p))).with_columns(pl.col("date").cast(pl.Date, strict=False))
    input_rows = df.height
    required = set(target_cols + [label_valid_col])
    missing_required = sorted(required - set(df.columns))
    if missing_required:
        raise ValueError(f"missing required experimental target columns: {missing_required}")

    df = _add_baseline_feature_columns_polars(df).filter(pl.col(label_valid_col) == True)
    keep_cols = [col for col in metadata_cols + excluded_cols + target_cols + feature_cols if col in df.columns]
    df = df.select(keep_cols)

    registry = build_column_registry(df.columns, cfg)
    summary = _feature_summary(
        df,
        input_rows=input_rows,
        feature_cols=feature_cols,
        registry=registry,
        extra={
            "feature_set": VOL_NORM60_FEATURE_SET,
            "input_path": str(vol_norm60_target_path(p)),
            "output_path": str(vol_norm60_feature_matrix_path(p)),
            "target_column": VOL_NORM60_TARGET_COLUMN,
            "official_baseline_replaced": False,
        },
    )
    return df, summary, registry


def run_vol_norm60_target_features(paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_vol_norm60_target_feature_config()
    data, summary, registry = _build_vol_norm60_target_features_polars(p, cfg)
    out_path = vol_norm60_feature_matrix_path(p)
    reset_parquet_output_dir(out_path)
    if data.height:
        data.write_parquet(str(out_path / _feature_set_parquet_name()))

    for name, values in registry.items():
        (out_path / f"{name}.json").write_text(json.dumps(values, indent=2), encoding="utf-8")

    p.feature_reports.mkdir(parents=True, exist_ok=True)
    (p.feature_reports / _feature_set_summary_name()).write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return summary


def run_vol_norm60_target_wfa(
    max_folds: int | None = None,
    fold_id: int | None = None,
    start_fold: int | None = None,
    end_fold: int | None = None,
    resume: bool = False,
    paths: ProjectPaths | None = None,
) -> dict[str, object]:
    total_started = time.perf_counter()
    p = paths or project_paths()
    feature_path = vol_norm60_feature_matrix_path(p)
    oos_path = vol_norm60_oos_prediction_path(p)
    model_cfg = load_model_config(VOL_NORM60_MODEL_CONFIG)
    feature_cols = _load_json_list(feature_path / "feature_cols.json")
    target_cols = _load_json_list(feature_path / "target_cols.json")
    metadata_cols = _load_json_list(feature_path / "metadata_cols.json")
    excluded_cols = _load_json_list(feature_path / "excluded_cols.json")
    validate_feature_cols(feature_cols, target_cols, excluded_cols, metadata_cols)

    plan = pd.read_csv(p.wfa_reports / "baseline_h5_split_plan.csv")
    requested = select_folds(plan, max_folds=max_folds, fold_id=fold_id)
    if start_fold is not None:
        requested = requested[requested["fold_id"].astype(int) >= int(start_fold)]
    if end_fold is not None:
        requested = requested[requested["fold_id"].astype(int) <= int(end_fold)]
    requested = requested.reset_index(drop=True)
    if not resume:
        reset_parquet_output_dir(oos_path)
    else:
        oos_path.mkdir(parents=True, exist_ok=True)
    p.wfa_reports.mkdir(parents=True, exist_ok=True)

    need_cols = sorted(
        set(
            feature_cols
            + [
                "date",
                "ticker",
                "raw_ticker",
                "target_class_5d",
                "fwd_ret_5d",
                VOL_NORM60_TARGET_COLUMN,
                VOL_NORM60_RETURN_COLUMN,
            ]
        )
    )
    fold_summaries: list[dict[str, object]] = []
    failed: list[dict[str, object]] = []
    summary_path = p.wfa_reports / _feature_set_oos_summary_name()
    fold_summary_path = p.wfa_reports / _feature_set_fold_summary_name()

    for _, fold in requested.iterrows():
        fold_started = time.perf_counter()
        fold_output = oos_path / f"fold_{int(fold['fold_id']):03d}.parquet"
        if resume and fold_output.exists():
            existing = pd.read_parquet(fold_output, columns=["date", "pred_score_5d"])
            summary = {
                "fold_id": int(fold["fold_id"]),
                "train_row_count": int(fold["train_row_count"]),
                "test_row_count": int(fold["test_row_count"]),
                "prediction_row_count": int(len(existing)),
                "pred_score_mean": float(existing["pred_score_5d"].mean()) if len(existing) else None,
                "pred_score_std": float(existing["pred_score_5d"].std(ddof=0)) if len(existing) else None,
                "pred_score_min": float(existing["pred_score_5d"].min()) if len(existing) else None,
                "pred_score_max": float(existing["pred_score_5d"].max()) if len(existing) else None,
                "test_start_date": str(pd.to_datetime(existing["date"]).min().date()) if len(existing) else str(fold["test_start_date"]),
                "test_end_date": str(pd.to_datetime(existing["date"]).max().date()) if len(existing) else str(fold["test_end_date"]),
                "resumed_existing_output": True,
            }
            fold_summaries.append(summary)
            _write_wfa_summaries(summary_path, fold_summary_path, requested, fold_summaries, failed, feature_cols, model_cfg)
            continue

        try:
            print(
                "[long_only_h5_vol_norm60_target_wfa] fold_start "
                f"fold_id={int(fold['fold_id'])} "
                f"train_rows={int(fold['train_row_count'])} "
                f"test_rows={int(fold['test_row_count'])}",
                flush=True,
            )
            matrix = _read_matrix_for_fold(feature_path, fold, need_cols)
            result = run_fold(matrix, fold, feature_cols, model_cfg)
            result.predictions.to_parquet(fold_output, index=False)
            fold_summaries.append(result.summary)
            _write_wfa_summaries(summary_path, fold_summary_path, requested, fold_summaries, failed, feature_cols, model_cfg)
            print(
                "[long_only_h5_vol_norm60_target_wfa] fold_done "
                f"fold_id={result.summary['fold_id']} "
                f"elapsed_seconds={time.perf_counter() - fold_started:.1f} "
                f"oos_rows_written={result.summary['prediction_row_count']}",
                flush=True,
            )
            del matrix, result
        except Exception as exc:
            failed.append({"fold_id": int(fold["fold_id"]), "error": str(exc)})
            _write_wfa_summaries(summary_path, fold_summary_path, requested, fold_summaries, failed, feature_cols, model_cfg)
            print(
                "[long_only_h5_vol_norm60_target_wfa] fold_failed "
                f"fold_id={int(fold['fold_id'])} "
                f"elapsed_seconds={time.perf_counter() - fold_started:.1f} "
                f"error={exc}",
                flush=True,
            )
            break

    summary = _vol_norm60_wfa_summary(
        requested=requested,
        fold_summaries=fold_summaries,
        failed=failed,
        feature_cols=feature_cols,
        model_cfg=model_cfg,
    )
    _write_wfa_summaries(summary_path, fold_summary_path, requested, fold_summaries, failed, feature_cols, model_cfg)
    print(
        "[long_only_h5_vol_norm60_target_wfa] all_folds_done "
        f"total_elapsed_seconds={time.perf_counter() - total_started:.1f}",
        flush=True,
    )
    if failed:
        failed_ids = [f["fold_id"] for f in failed]
        raise RuntimeError(f"{len(failed)} fold(s) failed: {failed_ids}")
    return summary


def _write_wfa_summaries(
    summary_path: Path,
    fold_summary_path: Path,
    requested: pd.DataFrame,
    fold_summaries: list[dict[str, object]],
    failed: list[dict[str, object]],
    feature_cols: list[str],
    model_cfg: dict[str, Any],
) -> None:
    pd.DataFrame(fold_summaries).to_csv(fold_summary_path, index=False)
    summary_path.write_text(
        json.dumps(
            _vol_norm60_wfa_summary(
                requested=requested,
                fold_summaries=fold_summaries,
                failed=failed,
                feature_cols=feature_cols,
                model_cfg=model_cfg,
            ),
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def _vol_norm60_wfa_summary(
    *,
    requested: pd.DataFrame,
    fold_summaries: list[dict[str, object]],
    failed: list[dict[str, object]],
    feature_cols: list[str],
    model_cfg: dict[str, Any],
) -> dict[str, object]:
    row_count = int(sum(int(s.get("prediction_row_count", 0)) for s in fold_summaries))
    starts = [str(s["test_start_date"]) for s in fold_summaries if s.get("prediction_row_count")]
    ends = [str(s["test_end_date"]) for s in fold_summaries if s.get("prediction_row_count")]
    return {
        "feature_set": VOL_NORM60_FEATURE_SET,
        "folds_requested": int(len(requested)),
        "folds_completed": int(len(fold_summaries)),
        "folds_failed": int(len(failed)),
        "total_oos_rows": row_count,
        "feature_count": int(len(feature_cols)),
        "model_type": model_cfg["model_type"],
        "target_column": model_cfg["target_column"],
        "min_prediction_date": min(starts) if starts else None,
        "max_prediction_date": max(ends) if ends else None,
        "official_baseline_replaced": False,
        "per_fold": fold_summaries,
        "blockers": failed,
        "warnings": [],
    }
