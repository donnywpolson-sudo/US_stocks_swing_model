import pandas as pd
import pytest

from quant_project_daily.execution import assign_score_buckets, daily_long_short_from_buckets
from quant_project_daily.metrics import build_metrics


def _preds() -> pd.DataFrame:
    rows = []
    for fold_id, date in [(1, "2020-01-02"), (1, "2020-01-03"), (2, "2020-01-06")]:
        for i in range(10):
            rows.append(
                {
                    "fold_id": fold_id,
                    "date": date,
                    "ticker": f"T{i}",
                    "raw_ticker": f"T{i}.US",
                    "target_class_5d": 0,
                    "fwd_ret_5d": (i - 4.5) / 100,
                    "pred_score_5d": float(i),
                }
            )
    return pd.DataFrame(rows)


def test_long_short_baskets_and_costs() -> None:
    df = _preds()
    df["decile"] = assign_score_buckets(df, 10)
    daily = daily_long_short_from_buckets(df, "decile", 10, 1, round_trip_cost_bps=25)
    assert daily["long_gross_return"].iloc[0] == 0.045
    assert daily["short_gross_return"].iloc[0] == 0.045
    assert daily["long_net_return"].iloc[0] == pytest.approx(0.0425)
    assert daily["short_net_return"].iloc[0] == pytest.approx(0.0425)
    assert daily["long_short_net_return"].iloc[0] == pytest.approx(0.0425)


def test_decile_quintile_assignment_is_by_date() -> None:
    df = _preds()
    df["decile"] = assign_score_buckets(df, 10)
    for _, g in df.groupby("date"):
        assert g.loc[g["ticker"] == "T9", "decile"].item() == 10
        assert g.loc[g["ticker"] == "T0", "decile"].item() == 1


def test_rank_ic_direction_and_fold_metrics() -> None:
    summary, reports = build_metrics(_preds(), {"round_trip_cost_bps": 25, "decile_buckets": 10, "quintile_buckets": 5, "score_outlier_abs_threshold": 5})
    assert summary["mean_daily_rank_ic"] == pytest.approx(1.0)
    assert summary["fold_count"] == 2
    assert len(reports["fold_metrics"]) == 2
    assert summary["long_short_gross_return"] > summary["long_short_net_return"]


def test_warnings_for_outliers_and_too_few_names() -> None:
    df = _preds().head(4).copy()
    df.loc[df.index[0], "pred_score_5d"] = 99
    summary, _ = build_metrics(df, {"round_trip_cost_bps": 25, "decile_buckets": 10, "quintile_buckets": 5, "score_outlier_abs_threshold": 5})
    assert "dates_with_too_few_names_for_deciles" in summary["warnings"]
    assert any("score_outlier" in w for w in summary["warnings"])
