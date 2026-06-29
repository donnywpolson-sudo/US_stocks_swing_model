from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from scripts.project_config import ProjectPaths
from scripts.phase8_model_selection.feature_selection import (
    freeze_feature_set,
    run_feature_selection,
    select_features,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# select_features – rejection reasons
# ---------------------------------------------------------------------------

class TestSelectFeaturesRejectReasons:
    """Verify every reject-reason path in select_features."""

    def test_all_rejection_reasons(self) -> None:
        discovery = pd.DataFrame(
            [
                {
                    "feature": "strong_feat",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "leakage_fwd_ret_foo",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.50,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "excessive_null_feat",
                    "folds_scored": 2,
                    "non_null_pct": 0.3,  # < 0.50
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "non_finite_feat",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 0.5,  # < 0.99
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "near_zero_var_feat",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 0.0,  # <= min_std
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "weak_ic_feat",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.0,  # < 0.001
                    "sign_stability": 1.0,
                },
                {
                    "feature": "unstable_sign_feat",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 0.0,  # < 0.50
                },
            ]
        )

        # permissive thresholds so only the intended rejection triggers
        cfg = _cfg()
        cfg["max_selected_features"] = 10

        ranking, selected, rejected, summary = select_features(discovery, cfg, corr=None)

        reasons = dict(zip(rejected["feature"], rejected["reject_reason"]))
        assert "strong_feat" in selected["feature"].values
        assert reasons["leakage_fwd_ret_foo"] == "leakage_name"
        assert reasons["excessive_null_feat"] == "excessive_nulls"
        assert reasons["non_finite_feat"] == "non_finite"
        assert reasons["near_zero_var_feat"] == "near_zero_variance"
        assert reasons["weak_ic_feat"] == "weak_rank_ic"
        assert reasons["unstable_sign_feat"] == "unstable_sign"

    def test_correlation_pruning(self) -> None:
        """Two valid features with pair correlation above threshold;
        only the higher-ranked (by selection_score) should survive."""
        discovery = pd.DataFrame(
            [
                {
                    "feature": "alpha",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.20,
                    "sign_stability": 1.0,
                },
                {
                    "feature": "beta",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.10,
                    "sign_stability": 1.0,
                },
            ]
        )

        # correlation matrix: 0.96 > 0.95 threshold
        corr = pd.DataFrame(np.eye(2), index=["alpha", "beta"], columns=["alpha", "beta"])
        corr.loc["alpha", "beta"] = corr.loc["beta", "alpha"] = 0.96

        cfg = _cfg()
        cfg["max_selected_features"] = 10

        ranking, selected, rejected, summary = select_features(discovery, cfg, corr)

        assert selected["feature"].tolist() == ["alpha"]
        reasons = dict(zip(rejected["feature"], rejected["reject_reason"]))
        assert reasons["beta"] == "correlation_pruned"


# ---------------------------------------------------------------------------
# run_feature_selection – full integration via tmp_path
# ---------------------------------------------------------------------------

class TestRunFeatureSelection:
    """run_feature_selection(paths=temp_paths) with monkeypatched config."""

    def test_happy_path(self, tmp_path, monkeypatch) -> None:
        paths = _paths(tmp_path)

        # Write discovery CSV with one valid feature
        paths.feature_reports.mkdir(parents=True, exist_ok=True)
        discovery = pd.DataFrame(
            [
                {
                    "feature": "mom_20d",
                    "folds_scored": 2,
                    "non_null_pct": 1.0,
                    "finite_pct": 1.0,
                    "std": 1.0,
                    "abs_mean_rank_ic": 0.15,
                    "sign_stability": 0.80,
                }
            ]
        )
        discovery.to_csv(paths.feature_reports / "expanded_h5_feature_discovery.csv", index=False)

        # Write correlations CSV (empty is fine since no pruning needed)
        corr = pd.DataFrame(columns=["feature_a", "feature_b", "max_abs_corr"])
        corr.to_csv(paths.feature_reports / "expanded_h5_feature_correlations.csv", index=False)

        monkeypatch.setattr(
            "scripts.phase8_model_selection.feature_selection.load_feature_selection_config",
            lambda: _cfg(),
        )

        summary = run_feature_selection(paths)

        # Assert output files exist
        ranking_path = paths.feature_reports / "expanded_h5_feature_ranking.csv"
        selected_path = paths.feature_reports / "expanded_h5_selected_features.csv"
        rejected_path = paths.feature_reports / "expanded_h5_rejected_features.csv"
        summary_path = paths.feature_reports / "expanded_h5_selection_summary.json"

        assert ranking_path.exists(), f"missing {ranking_path}"
        assert selected_path.exists(), f"missing {selected_path}"
        assert rejected_path.exists(), f"missing {rejected_path}"
        assert summary_path.exists(), f"missing {summary_path}"

        assert summary["selected_feature_count"] >= 1

    def test_missing_discovery_raises(self, tmp_path) -> None:
        paths = _paths(tmp_path)
        with pytest.raises(FileNotFoundError, match="missing Stage21 discovery output"):
            run_feature_selection(paths)


# ---------------------------------------------------------------------------
# freeze_feature_set – integration via tmp_path
# ---------------------------------------------------------------------------

class TestFreezeFeatureSet:
    """freeze_feature_set(paths=temp_paths) after selection outputs exist."""

    def test_happy_path(self, tmp_path, monkeypatch) -> None:
        paths = _paths(tmp_path)
        paths.feature_reports.mkdir(parents=True, exist_ok=True)

        # Simulate Stage22 outputs
        selected_df = pd.DataFrame([{"feature": "mom_20d", "selected": True}])
        rejected_df = pd.DataFrame(
            [{"feature": "weak_feat", "selected": False, "reject_reason": "weak_rank_ic"}]
        )
        selected_df.to_csv(paths.feature_reports / "expanded_h5_selected_features.csv", index=False)
        rejected_df.to_csv(paths.feature_reports / "expanded_h5_rejected_features.csv", index=False)

        monkeypatch.setattr(
            "scripts.phase8_model_selection.feature_selection.load_feature_selection_config",
            lambda: _cfg(),
        )

        manifest = freeze_feature_set(paths)

        frozen_dir = paths.frozen_features_expanded_h5_v1
        assert (frozen_dir / "feature_cols.json").exists()
        assert (frozen_dir / "selected_features.csv").exists()
        assert (frozen_dir / "rejected_features.csv").exists()
        assert (frozen_dir / "manifest.json").exists()

        # manifest selected count matches selected rows
        feature_cols = json.loads((frozen_dir / "feature_cols.json").read_text())
        assert feature_cols == ["mom_20d"]
        assert manifest["selected_feature_count"] == 1