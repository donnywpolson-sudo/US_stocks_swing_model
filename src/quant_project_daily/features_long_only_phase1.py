from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import yaml

from quant_project_daily.baseline_wfa import (
    _load_json_list,
    _read_matrix_for_fold,
    load_model_config,
    run_fold,
    select_folds,
    validate_feature_cols,
)
from quant_project_daily.column_registry import build_column_registry
from quant_project_daily.config import REPO_ROOT, ProjectPaths, project_paths, reset_parquet_output_dir
from quant_project_daily.features_baseline import _add_baseline_feature_columns_polars, _feature_summary


PHASE1_FEATURE_SET = "long_only_h5_phase1"
PHASE1_PARQUET_NAME = "long_only_h5_phase1.parquet"
PHASE1_SUMMARY_NAME = "long_only_h5_phase1_summary.json"
PHASE1_OOS_SUMMARY_NAME = "long_only_h5_phase1_oos_summary.json"
PHASE1_FOLD_SUMMARY_NAME = "long_only_h5_phase1_fold_summary.csv"


def load_long_only_h5_phase1_feature_config(path: Path | None = None) -> dict[str, Any]:
    return load_long_only_h5_feature_config(PHASE1_FEATURE_SET, path=path)


def load_long_only_h5_feature_config(feature_set: str, path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or REPO_ROOT / "configs" / f"{feature_set}_features.yaml"
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    base_config_path = cfg.get("base_config_path")
    if base_config_path:
        base_path = REPO_ROOT / str(base_config_path)
        with base_path.open("r", encoding="utf-8") as f:
            base = yaml.safe_load(f)
        exclude = set(cfg.get("exclude_feature_columns", []))
        include = cfg.get("include_feature_columns")
        feature_columns = list(include) if include else [c for c in base["feature_columns"] if c not in exclude]
        resolved = {
            **base,
            **cfg,
            "feature_columns": feature_columns,
            "target_columns": list(cfg.get("target_columns", base["target_columns"])),
            "metadata_columns": list(cfg.get("metadata_columns", base["metadata_columns"])),
            "excluded_columns": list(cfg.get("excluded_columns", base["excluded_columns"])),
        }
        return resolved
    return cfg


def _experimental_feature_path(p: ProjectPaths) -> Path:
    return p.feature_matrix_long_only_h5_phase1 or p.repo_root / "data" / "feature_matrices" / PHASE1_FEATURE_SET


def _experimental_oos_path(p: ProjectPaths) -> Path:
    return p.oos_predictions_long_only_h5_phase1 or p.repo_root / "data" / "oos_predictions" / PHASE1_FEATURE_SET


def _feature_set_matrix_path(p: ProjectPaths, feature_set: str) -> Path:
    if feature_set == PHASE1_FEATURE_SET:
        return _experimental_feature_path(p)
    return p.repo_root / "data" / "feature_matrices" / feature_set


def _feature_set_oos_path(p: ProjectPaths, feature_set: str) -> Path:
    if feature_set == PHASE1_FEATURE_SET:
        return _experimental_oos_path(p)
    return p.repo_root / "data" / "oos_predictions" / feature_set


def _feature_set_parquet_name(feature_set: str) -> str:
    return f"{feature_set}.parquet"


def _feature_set_summary_name(feature_set: str) -> str:
    return f"{feature_set}_summary.json"


def _feature_set_oos_summary_name(feature_set: str) -> str:
    return f"{feature_set}_oos_summary.json"


def _feature_set_fold_summary_name(feature_set: str) -> str:
    return f"{feature_set}_fold_summary.csv"


def _safe_ratio(num: pl.Expr, den: pl.Expr) -> pl.Expr:
    return pl.when((den == 0) | den.is_null()).then(None).otherwise(num / den)


def _add_phase1_feature_columns_polars(df: pl.DataFrame) -> pl.DataFrame:
    c = pl.col
    df = df.with_columns(
        _safe_ratio(c("ret_20d"), c("realized_vol_20d")).alias("mom_20d_vol_adj"),
        _safe_ratio(c("ret_60d"), c("realized_vol_60d")).alias("mom_60d_vol_adj"),
        (c("ret_1d") > 0)
        .cast(pl.Float64)
        .rolling_mean(20, min_samples=20)
        .over("ticker")
        .alias("trend_pos_ret_frac_20d"),
        (c("ret_5d") - c("ret_60d")).alias("pullback_5d_vs_60d"),
        _safe_ratio(c("realized_vol_5d"), c("realized_vol_20d")).alias("vol_ratio_5d_20d"),
        _safe_ratio(c("realized_vol_20d"), c("realized_vol_60d")).alias("vol_ratio_20d_60d"),
        _safe_ratio(c("atr_14_pct"), c("realized_vol_20d")).alias("atr14_to_vol20"),
        _safe_ratio(
            c("dollar_volume").rolling_mean(20, min_samples=20).over("ticker"),
            c("dollar_volume").rolling_mean(60, min_samples=60).over("ticker"),
        ).alias("dollar_volume_ratio_20d_60d"),
    )
    df = df.with_columns(
        _safe_ratio(c("realized_vol_10d"), c("realized_vol_60d")).alias("vol_ratio_10d_60d"),
        _safe_ratio(
            c("true_range_pct").rolling_mean(20, min_samples=20).over("ticker"),
            c("true_range_pct").rolling_mean(60, min_samples=60).over("ticker"),
        ).alias("range_compression_20d_60d"),
        (
            (c("sma_20d_slope") > 0).cast(pl.Int8)
            + (c("sma_50d_slope") > 0).cast(pl.Int8)
            - 1
        )
        .cast(pl.Float64)
        .alias("sma_slope_agreement_20_50"),
        (
            (c("dist_sma_20d") > 0).cast(pl.Int8)
            + (c("dist_sma_50d") > 0).cast(pl.Int8)
            + (c("dist_sma_200d") > 0).cast(pl.Int8)
        )
        .cast(pl.Float64)
        .alias("sma_stack_score_20_50_200"),
        _safe_ratio(
            c("dollar_volume").rolling_mean(10, min_samples=10).over("ticker"),
            c("dollar_volume").rolling_mean(60, min_samples=60).over("ticker"),
        ).alias("dollar_volume_accel_10d_60d"),
    )
    return df.with_columns(
        c("vol_ratio_10d_60d")
        .rank(method="average")
        .over("date")
        .truediv(pl.len().over("date"))
        .alias("vol_regime_rank_by_date")
    )


def _build_long_only_h5_phase1_features_polars(
    p: ProjectPaths,
    cfg: dict[str, Any],
) -> tuple[pl.DataFrame, dict[str, object], dict[str, list[str]]]:
    return _build_long_only_h5_features_polars(p, cfg)


def _build_long_only_h5_features_polars(
    p: ProjectPaths,
    cfg: dict[str, Any],
) -> tuple[pl.DataFrame, dict[str, object], dict[str, list[str]]]:
    feature_set = str(cfg.get("feature_set", PHASE1_FEATURE_SET))
    feature_cols = list(cfg["feature_columns"])
    target_cols = list(cfg["target_columns"])
    metadata_cols = list(cfg["metadata_columns"])
    excluded_cols = list(cfg["excluded_columns"])

    df = pl.read_parquet(str(p.labeled_target_h5)).with_columns(pl.col("date").cast(pl.Date, strict=False))
    input_rows = df.height
    df = _add_baseline_feature_columns_polars(df)
    df = _add_phase1_feature_columns_polars(df).filter(pl.col("label_valid_5d") == True)
    keep_cols = [col for col in metadata_cols + excluded_cols + target_cols + feature_cols if col in df.columns]
    df = df.select(keep_cols)

    registry = build_column_registry(df.columns, cfg)
    summary = _feature_summary(
        df,
        input_rows=input_rows,
        feature_cols=feature_cols,
        registry=registry,
        extra={
            "feature_set": feature_set,
            "output_path": str(_feature_set_matrix_path(p, feature_set)),
            "official_baseline_replaced": False,
        },
    )
    return df, summary, registry


def run_long_only_h5_phase1_features(paths: ProjectPaths | None = None) -> dict[str, object]:
    return run_long_only_h5_feature_set(PHASE1_FEATURE_SET, paths=paths)


def run_long_only_h5_feature_set(feature_set: str, paths: ProjectPaths | None = None) -> dict[str, object]:
    p = paths or project_paths()
    cfg = load_long_only_h5_feature_config(feature_set)
    data, summary, registry = _build_long_only_h5_features_polars(p, cfg)
    out_path = _feature_set_matrix_path(p, feature_set)
    reset_parquet_output_dir(out_path)
    if data.height:
        data.write_parquet(str(out_path / _feature_set_parquet_name(feature_set)))

    for name, values in registry.items():
        (out_path / f"{name}.json").write_text(json.dumps(values, indent=2), encoding="utf-8")

    p.feature_reports.mkdir(parents=True, exist_ok=True)
    (p.feature_reports / _feature_set_summary_name(feature_set)).write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )
    return summary


def run_long_only_h5_phase1_wfa(
    max_folds: int | None = None,
    fold_id: int | None = None,
    start_fold: int | None = None,
    end_fold: int | None = None,
    resume: bool = False,
    paths: ProjectPaths | None = None,
) -> dict[str, object]:
    return run_long_only_h5_feature_set_wfa(
        PHASE1_FEATURE_SET,
        max_folds=max_folds,
        fold_id=fold_id,
        start_fold=start_fold,
        end_fold=end_fold,
        resume=resume,
        paths=paths,
    )


def run_long_only_h5_feature_set_wfa(
    feature_set: str,
    max_folds: int | None = None,
    fold_id: int | None = None,
    start_fold: int | None = None,
    end_fold: int | None = None,
    resume: bool = False,
    paths: ProjectPaths | None = None,
) -> dict[str, object]:
    total_started = time.perf_counter()
    p = paths or project_paths()
    feature_path = _feature_set_matrix_path(p, feature_set)
    oos_path = _feature_set_oos_path(p, feature_set)
    model_cfg = load_model_config()
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

    need_cols = sorted(set(feature_cols + ["date", "ticker", "raw_ticker", "target_class_5d", "fwd_ret_5d"]))
    fold_summaries = []
    failed = []
    summary_path = p.wfa_reports / _feature_set_oos_summary_name(feature_set)
    fold_summary_path = p.wfa_reports / _feature_set_fold_summary_name(feature_set)
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
            pd.DataFrame(fold_summaries).to_csv(fold_summary_path, index=False)
            summary_path.write_text(
                json.dumps(
                    _phase1_wfa_summary(
                        feature_set=feature_set,
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
            print(
                "[long_only_h5_phase1_wfa] fold_skip_existing "
                f"feature_set={feature_set} "
                f"fold_id={int(fold['fold_id'])} "
                f"oos_rows_present={summary['prediction_row_count']}",
                flush=True,
            )
            continue
        try:
            print(
                "[long_only_h5_phase1_wfa] fold_start "
                f"feature_set={feature_set} "
                f"fold_id={int(fold['fold_id'])} "
                f"train_rows={int(fold['train_row_count'])} "
                f"test_rows={int(fold['test_row_count'])} "
                f"train_dates={fold['train_start_date']}..{fold['train_end_date']} "
                f"test_dates={fold['test_start_date']}..{fold['test_end_date']}",
                flush=True,
            )
            matrix = _read_matrix_for_fold(feature_path, fold, need_cols)
            result = run_fold(matrix, fold, feature_cols, model_cfg)
            result.predictions.to_parquet(fold_output, index=False)
            fold_summaries.append(result.summary)
            pd.DataFrame(fold_summaries).to_csv(fold_summary_path, index=False)
            summary_path.write_text(
                json.dumps(
                    _phase1_wfa_summary(
                        feature_set=feature_set,
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
            print(
                "[long_only_h5_phase1_wfa] fold_done "
                f"feature_set={feature_set} "
                f"fold_id={result.summary['fold_id']} "
                f"elapsed_seconds={time.perf_counter() - fold_started:.1f} "
                f"oos_rows_written={result.summary['prediction_row_count']}",
                flush=True,
            )
            del matrix, result
        except Exception as exc:
            failed.append({"fold_id": int(fold["fold_id"]), "error": str(exc)})
            pd.DataFrame(fold_summaries).to_csv(fold_summary_path, index=False)
            summary_path.write_text(
                json.dumps(
                    _phase1_wfa_summary(
                        feature_set=feature_set,
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
            print(
                "[long_only_h5_phase1_wfa] fold_failed "
                f"feature_set={feature_set} "
                f"fold_id={int(fold['fold_id'])} "
                f"elapsed_seconds={time.perf_counter() - fold_started:.1f} "
                f"error={exc}",
                flush=True,
            )
            break

    fold_df = pd.DataFrame(fold_summaries)
    fold_df.to_csv(fold_summary_path, index=False)
    summary = _phase1_wfa_summary(
        feature_set=feature_set,
        requested=requested,
        fold_summaries=fold_summaries,
        failed=failed,
        feature_cols=feature_cols,
        model_cfg=model_cfg,
    )
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(
        f"[long_only_h5_phase1_wfa] all_folds_done feature_set={feature_set} "
        f"total_elapsed_seconds={time.perf_counter() - total_started:.1f}",
        flush=True,
    )
    if failed:
        failed_ids = [f["fold_id"] for f in failed]
        raise RuntimeError(f"{len(failed)} fold(s) failed: {failed_ids}")
    return summary


def _phase1_wfa_summary(
    *,
    feature_set: str,
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
        "feature_set": feature_set,
        "folds_requested": int(len(requested)),
        "folds_completed": int(len(fold_summaries)),
        "folds_failed": int(len(failed)),
        "total_oos_rows": row_count,
        "feature_count": int(len(feature_cols)),
        "model_type": model_cfg["model_type"],
        "min_prediction_date": min(starts) if starts else None,
        "max_prediction_date": max(ends) if ends else None,
        "official_baseline_replaced": False,
        "per_fold": fold_summaries,
        "blockers": failed,
        "warnings": [],
    }
