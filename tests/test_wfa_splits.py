import pandas as pd

from quant_project_daily.wfa_splits import build_wfa_plan


CFG = {
    "train_window_days": 1260,
    "test_window_days": 63,
    "step_days": 63,
    "purge_days": 20,
    "embargo_days": 0,
}


def _date_counts(n: int, rows_per_date: int = 2) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.bdate_range("2010-01-01", periods=n), "row_count": rows_per_date})


def test_wfa_train_test_separation_and_purge_window() -> None:
    result = build_wfa_plan(_date_counts(1400), CFG)
    first = result.plan.iloc[0]
    dates = pd.bdate_range("2010-01-01", periods=1400)
    assert first["train_start_date"] == str(dates[0].date())
    assert first["train_end_date"] == str(dates[1259].date())
    assert first["purge_start_date"] == str(dates[1260].date())
    assert first["purge_end_date"] == str(dates[1279].date())
    assert first["test_start_date"] == str(dates[1280].date())
    assert first["test_end_date"] == str(dates[1342].date())
    assert first["train_end_date"] < first["test_start_date"]
    assert first["purge_end_date"] < first["test_start_date"]


def test_wfa_no_train_test_overlap_and_step_advances() -> None:
    result = build_wfa_plan(_date_counts(1500), CFG)
    assert len(result.plan) >= 2
    first = result.plan.iloc[0]
    second = result.plan.iloc[1]
    assert first["test_start_date"] != second["test_start_date"]
    assert pd.bdate_range(first["test_start_date"], second["test_start_date"]).size - 1 == CFG["step_days"]
    assert first["train_end_date"] < first["test_start_date"]
    assert second["train_end_date"] < second["test_start_date"]


def test_wfa_insufficient_history_creates_no_invalid_folds() -> None:
    result = build_wfa_plan(_date_counts(1000), CFG)
    assert result.plan.empty
    assert result.summary["total_folds"] == 0
    assert "insufficient_history_for_full_fold" in result.summary["warnings"]


def test_wfa_row_counts_match_selected_dates() -> None:
    result = build_wfa_plan(_date_counts(1400, rows_per_date=3), CFG)
    first = result.plan.iloc[0]
    assert first["train_row_count"] == CFG["train_window_days"] * 3
    assert first["test_row_count"] == CFG["test_window_days"] * 3
    assert first["purged_date_count"] == 20
