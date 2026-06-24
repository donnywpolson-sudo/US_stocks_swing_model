import json
from pathlib import Path

from quant_project_daily.gates import evaluate_baseline_gate, run_baseline_gate
from quant_project_daily.config import ProjectPaths


def _make_paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path,
        raw_manifest=tmp_path,
        validated=tmp_path,
        normalized=tmp_path,
        causal=tmp_path,
        research_ohlcv_daily=tmp_path,
        labeled_target_h5=tmp_path,
        feature_matrix_baseline_h5=tmp_path,
        feature_matrix_expanded_h5=tmp_path,
        frozen_features_expanded_h5_v1=tmp_path,
        oos_predictions_baseline_h5=tmp_path,
        validation_reports=tmp_path,
        label_reports=tmp_path,
        feature_reports=tmp_path,
        wfa_reports=tmp_path,
        metrics_reports=tmp_path / "metrics_reports",
        gates_reports=tmp_path / "gates_reports",
    )


THRESHOLDS = {
    "min_total_oos_rows": 1_000_000,
    "min_fold_count": 20,
    "min_rank_ic_t_stat": 2.0,
    "min_mean_daily_rank_ic": 0.0,
    "min_long_short_net_return": 0.0,
    "min_top_decile_net_return": 0.0,
    "warn_short_leg_net_return_lte": 0.0,
    "warn_long_short_net_return_below": 0.005,
    "warn_mean_daily_rank_ic_below": 0.05,
    "warn_abs_score_extreme_above": 5.0,
}


def _metrics(**overrides):
    base = {
        "total_oos_rows": 2_000_000,
        "fold_count": 30,
        "mean_daily_rank_ic": 0.06,
        "rank_ic_t_stat": 3.0,
        "long_short_net_return": 0.01,
        "top_decile_net_return": 0.02,
        "bottom_decile_net_short_return": 0.01,
        "score": {"min": -1, "max": 1},
        "blockers": [],
        "warnings": [],
    }
    base.update(overrides)
    return base


def test_gate_pass_when_required_criteria_pass() -> None:
    out = evaluate_baseline_gate(_metrics(), THRESHOLDS)
    assert out["status"] == "PASS"
    assert out["passed"] is True
    assert set(out) >= {"gate_name", "status", "passed", "warnings", "failures", "metrics_used", "thresholds", "recommendation", "next_stage"}


def test_gate_pass_with_warnings() -> None:
    out = evaluate_baseline_gate(_metrics(bottom_decile_net_short_return=-0.01, warnings=["fold_1_score_outlier"], score={"min": -6, "max": 1}, mean_daily_rank_ic=0.03), THRESHOLDS)
    assert out["status"] == "PASS_WITH_WARNINGS"
    assert "short_leg_net_return_non_positive" in out["warnings"]
    assert "extreme_prediction_score" in out["warnings"]
    assert "mean_daily_rank_ic_below_0_05" in out["warnings"]


def test_gate_fail_when_rank_ic_non_positive() -> None:
    out = evaluate_baseline_gate(_metrics(mean_daily_rank_ic=0.0), THRESHOLDS)
    assert out["status"] == "FAIL"
    assert "mean_daily_rank_ic_failed_positive_threshold" in out["failures"]


def test_gate_fail_when_long_short_net_non_positive() -> None:
    out = evaluate_baseline_gate(_metrics(long_short_net_return=0.0), THRESHOLDS)
    assert out["status"] == "FAIL"
    assert "long_short_net_return_failed_positive_threshold" in out["failures"]


def test_gate_fail_when_metrics_missing_or_blockers_exist() -> None:
    missing = evaluate_baseline_gate(None, THRESHOLDS, ["metrics_file_missing"])
    blocked = evaluate_baseline_gate(_metrics(blockers=["bad"]), THRESHOLDS)
    assert missing["status"] == "FAIL"
    assert "metrics_file_missing" in missing["failures"]
    assert blocked["status"] == "FAIL"
    assert "metrics_blockers_present" in blocked["failures"]


class TestRunBaselineGate:
    """File-based tests for run_baseline_gate using tmp_path."""

    _passing_metrics = {
        "total_oos_rows": 2_000_000,
        "fold_count": 30,
        "mean_daily_rank_ic": 0.06,
        "rank_ic_t_stat": 3.0,
        "long_short_net_return": 0.01,
        "top_decile_net_return": 0.02,
        "bottom_decile_net_short_return": 0.01,
        "score": {"min": -1, "max": 1},
        "blockers": [],
        "warnings": [],
    }

    def test_passing_case(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        paths.metrics_reports.mkdir(parents=True, exist_ok=True)
        (paths.metrics_reports / "baseline_h5_metrics_summary.json").write_text(
            json.dumps(self._passing_metrics), encoding="utf-8"
        )

        result = run_baseline_gate(paths=paths)

        assert (paths.gates_reports / "baseline_h5_gate.json").exists()
        assert result["status"] != "FAIL"

    def test_missing_metrics_file(self, tmp_path: Path) -> None:
        paths = _make_paths(tmp_path)
        paths.metrics_reports.mkdir(parents=True, exist_ok=True)
        # no metrics JSON written

        result = run_baseline_gate(paths=paths)

        assert result["status"] == "FAIL"
        assert "metrics_file_missing" in result["failures"]
