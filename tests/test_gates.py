from quant_project_daily.gates import evaluate_baseline_gate


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
