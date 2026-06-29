from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scripts.project_config import ProjectPaths
from scripts.phase8_model_selection.feature_discovery import _load_matrix_for_plan, discover_features_for_folds
from scripts.phase8_model_selection.feature_selection import freeze_feature_set, run_feature_selection, select_features


def _cfg() -> dict[str, object]:
    return {
        "version": "expanded_h5_v1",
        "target_column": "fwd_ret_5d",
        "class_target_column": "target_class_5d",
        "max_selected_features": 2,
        "min_non_null_pct": 0.50,
        "min_finite_pct": 0.99,
        "min_std": 1.0e-12,
        "min_abs_mean_rank_ic": 0.001,
        "min_sign_stability": 0.50,
        "correlation_prune_threshold": 0.95,
        "correlation_sample_rows_per_fold": 250000,
        "correlation_sample_date_stride": 20,
        "leakage_tokens": ["target", "label", "fwd_ret", "next_open", "exit_close", "exit_date"],
    }


def _paths(tmp_path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily",
        labeled_target_h5=tmp_path / "data" / "labeled" / "target_h5",
        feature_matrix_baseline_h5=tmp_path / "data" / "feature_matrices" / "baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "data" / "feature_matrices" / "expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "data" / "frozen_features" / "expanded_h5_v1",
        oos_predictions_baseline_h5=tmp_path / "data" / "oos_predictions" / "baseline_h5",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def test_discovery_uses_train_dates_only_not_test_dates() -> None:
    dates = pd.date_range("2020-01-01", periods=6)
    rows = []
    for date_i, date in enumerate(dates):
        for ticker_i, ticker in enumerate(["A", "B", "C"]):
            train_value = 3 - ticker_i
            test_value = ticker_i + 1
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "x": train_value if date_i < 3 else test_value,
                    "fwd_ret_5d": ticker_i + 1,
                }
            )
    matrix = pd.DataFrame(rows)
    plan = pd.DataFrame(
        {
            "fold_id": [1],
            "train_start_date": ["2020-01-01"],
            "train_end_date": ["2020-01-03"],
            "test_start_date": ["2020-01-04"],
            "test_end_date": ["2020-01-06"],
        }
    )

    by_fold, discovery, _ = discover_features_for_folds(matrix, plan, ["x"], _cfg())

    assert by_fold.loc[0, "fold_rank_ic"] < 0
    assert discovery.loc[0, "mean_daily_rank_ic"] < 0


def test_selection_rejects_leakage_null_constant_and_prunes_correlated() -> None:
    discovery = pd.DataFrame(
        [
            {"feature": "strong", "folds_scored": 2, "non_null_pct": 1.0, "finite_pct": 1.0, "std": 1.0, "mean_daily_rank_ic": 0.20, "mean_fold_rank_ic": 0.20, "abs_mean_rank_ic": 0.20, "sign_stability": 1.0},
            {"feature": "redundant", "folds_scored": 2, "non_null_pct": 1.0, "finite_pct": 1.0, "std": 1.0, "mean_daily_rank_ic": 0.19, "mean_fold_rank_ic": 0.19, "abs_mean_rank_ic": 0.19, "sign_stability": 1.0},
            {"feature": "target_leak", "folds_scored": 2, "non_null_pct": 1.0, "finite_pct": 1.0, "std": 1.0, "mean_daily_rank_ic": 0.99, "mean_fold_rank_ic": 0.99, "abs_mean_rank_ic": 0.99, "sign_stability": 1.0},
            {"feature": "mostly_null", "folds_scored": 2, "non_null_pct": 0.4, "finite_pct": 1.0, "std": 1.0, "mean_daily_rank_ic": 0.30, "mean_fold_rank_ic": 0.30, "abs_mean_rank_ic": 0.30, "sign_stability": 1.0},
            {"feature": "constant", "folds_scored": 2, "non_null_pct": 1.0, "finite_pct": 1.0, "std": 0.0, "mean_daily_rank_ic": 0.30, "mean_fold_rank_ic": 0.30, "abs_mean_rank_ic": 0.30, "sign_stability": 1.0},
            {"feature": "weak", "folds_scored": 2, "non_null_pct": 1.0, "finite_pct": 1.0, "std": 1.0, "mean_daily_rank_ic": 0.0, "mean_fold_rank_ic": 0.0, "abs_mean_rank_ic": 0.0, "sign_stability": 1.0},
        ]
    )
    corr = pd.DataFrame(np.eye(2), index=["strong", "redundant"], columns=["strong", "redundant"])
    corr.loc["strong", "redundant"] = corr.loc["redundant", "strong"] = 0.99

    _, selected, rejected, summary = select_features(discovery, _cfg(), corr)

    assert selected["feature"].tolist() == ["strong"]
    assert summary["selected_feature_count"] <= _cfg()["max_selected_features"]
    reasons = dict(zip(rejected["feature"], rejected["reject_reason"]))
    assert reasons["redundant"] == "correlation_pruned"
    assert reasons["target_leak"] == "leakage_name"
    assert reasons["mostly_null"] == "excessive_nulls"
    assert reasons["constant"] == "near_zero_variance"
    assert reasons["weak"] == "weak_rank_ic"


def test_freeze_feature_set_writes_manifest_and_schema_outputs(tmp_path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    paths.feature_reports.mkdir(parents=True)
    pd.DataFrame([{"feature": "strong", "selected": True}]).to_csv(paths.feature_reports / "expanded_h5_selected_features.csv", index=False)
    pd.DataFrame([{"feature": "weak", "selected": False, "reject_reason": "weak_rank_ic"}]).to_csv(
        paths.feature_reports / "expanded_h5_rejected_features.csv", index=False
    )
    monkeypatch.setattr("scripts.phase8_model_selection.feature_selection.load_feature_selection_config", lambda: _cfg())

    manifest = freeze_feature_set(paths)

    assert manifest["selected_feature_count"] == 1
    assert json.loads((paths.frozen_features_expanded_h5_v1 / "feature_cols.json").read_text()) == ["strong"]
    assert "train-fold-only" in (paths.frozen_features_expanded_h5_v1 / "manifest.json").read_text()


def test_load_matrix_filters_date_typed_parquet_with_split_strings(tmp_path) -> None:
    paths = _paths(tmp_path)
    paths.feature_matrix_expanded_h5.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2019-12-31", "2020-01-01", "2020-01-02"]).date,
            "fwd_ret_5d": [0.0, 0.1, 0.2],
            "x": [1.0, 2.0, 3.0],
        }
    ).to_parquet(paths.feature_matrix_expanded_h5 / "expanded_h5.parquet", index=False)
    folds = pd.DataFrame({"train_start_date": ["2020-01-01"], "train_end_date": ["2020-01-02"]})

    out = _load_matrix_for_plan(paths, folds, ["date", "fwd_ret_5d", "x"])

    assert out["date"].dt.strftime("%Y-%m-%d").tolist() == ["2020-01-01", "2020-01-02"]


def test_stage22_missing_discovery_has_clear_error(tmp_path) -> None:
    paths = _paths(tmp_path)
    try:
        run_feature_selection(paths)
    except FileNotFoundError as exc:
        assert "missing Stage21 discovery output" in str(exc)
    else:
        raise AssertionError("expected missing Stage21 output error")
