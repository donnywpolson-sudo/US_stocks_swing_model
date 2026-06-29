"""Tests for Stage 21 feature discovery file handoff."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.project_config import ProjectPaths
from scripts.phase8_model_selection.feature_discovery import run_feature_discovery


def _tiny_cfg() -> dict[str, object]:
    return {
        "target_column": "target_class_5d",
        "leakage_tokens": ["target", "fwd", "future", "label", "exit", "next"],
        "correlation_sample_rows_per_fold": 0,
        "correlation_sample_date_stride": 1,
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


def _create_synthetic_data(paths: ProjectPaths) -> None:
    """Create synthetic expanded parquet and supporting files under temp paths."""
    paths.feature_matrix_expanded_h5.mkdir(parents=True, exist_ok=True)
    paths.wfa_reports.mkdir(parents=True, exist_ok=True)

    # feature_cols.json with non-leakage names
    feature_cols = ["alpha_a", "alpha_b"]
    (paths.feature_matrix_expanded_h5 / "feature_cols.json").write_text(
        json.dumps(feature_cols), encoding="utf-8"
    )

    # split plan: one fold
    split_plan = pd.DataFrame(
        {
            "fold_id": [1],
            "train_start_date": ["2020-01-01"],
            "train_end_date": ["2020-01-05"],
            "test_start_date": ["2020-01-06"],
            "test_end_date": ["2020-01-07"],
        }
    )
    split_plan.to_csv(paths.wfa_reports / "baseline_h5_split_plan.csv", index=False)

    # synthetic expanded parquet
    dates = pd.date_range("2020-01-01", periods=7)
    rows: list[dict] = []
    rng = np.random.default_rng(42)
    for date in dates:
        for i, ticker in enumerate(["A", "B", "C", "D", "E"]):
            # alternate target within each date group to guarantee variance
            target = i % 2
            alpha_a = target + rng.normal(0, 0.5)
            alpha_b = 1.0 - target + rng.normal(0, 0.5)
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "target_class_5d": target,
                    "alpha_a": alpha_a,
                    "alpha_b": alpha_b,
                }
            )
    df = pd.DataFrame(rows)
    df.to_parquet(paths.feature_matrix_expanded_h5 / "expanded_h5.parquet", index=False)


class TestStage21FeatureDiscoveryHandoff:
    """Focused tests for Stage 21 run_feature_discovery file handoff."""

    def test_run_feature_discovery_with_synthetic_data(self, tmp_path, monkeypatch) -> None:
        paths = _paths(tmp_path)
        _create_synthetic_data(paths)
        monkeypatch.setattr(
            "scripts.phase8_model_selection.feature_discovery.load_feature_selection_config",
            lambda: _tiny_cfg(),
        )

        summary = run_feature_discovery(max_folds=1, paths=paths)

        assert summary["folds_used"] == 1
        assert summary["features_scored"] > 0
        assert summary["blockers"] == []

        # Assert output files exist
        assert (paths.feature_reports / "expanded_h5_feature_discovery.csv").exists()
        assert (paths.feature_reports / "expanded_h5_feature_discovery_by_fold.csv").exists()
        assert (paths.feature_reports / "expanded_h5_feature_correlations.csv").exists()
        assert (paths.feature_reports / "expanded_h5_feature_discovery_summary.json").exists()

    def test_run_feature_discovery_missing_parquet_raises(self, tmp_path, monkeypatch) -> None:
        paths = _paths(tmp_path)
        paths.feature_matrix_expanded_h5.mkdir(parents=True, exist_ok=True)
        paths.wfa_reports.mkdir(parents=True, exist_ok=True)

        # Write feature_cols.json but NO parquet
        (paths.feature_matrix_expanded_h5 / "feature_cols.json").write_text(
            json.dumps(["alpha_a"]), encoding="utf-8"
        )
        split_plan = pd.DataFrame(
            {
                "fold_id": [1],
                "train_start_date": ["2020-01-01"],
                "train_end_date": ["2020-01-05"],
                "test_start_date": ["2020-01-06"],
                "test_end_date": ["2020-01-07"],
            }
        )
        split_plan.to_csv(paths.wfa_reports / "baseline_h5_split_plan.csv", index=False)

        monkeypatch.setattr(
            "scripts.phase8_model_selection.feature_discovery.load_feature_selection_config",
            lambda: _tiny_cfg(),
        )

        with pytest.raises(FileNotFoundError):
            run_feature_discovery(max_folds=1, paths=paths)