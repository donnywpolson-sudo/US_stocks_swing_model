import pandas as pd
import pytest

from quant_project_daily.baseline_wfa import PREDICTION_COLUMNS, run_fold, select_folds, validate_feature_cols


def _matrix() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2020-01-01", periods=8)
    for d in dates:
        for i, ticker in enumerate(["A", "B", "C"]):
            rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "f1": float(i) if not (ticker == "C" and d == dates[1]) else None,
                    "f2": float(d.day),
                    "target_class_20d": [-1, 0, 1][i],
                    "fwd_ret_20d": [-0.1, 0.0, 0.1][i],
                    "next_open": 999.0,
                }
            )
    return pd.DataFrame(rows)


def _fold() -> dict[str, object]:
    return {
        "fold_id": 1,
        "train_start_date": "2020-01-01",
        "train_end_date": "2020-01-06",
        "test_start_date": "2020-01-07",
        "test_end_date": "2020-01-10",
    }


def test_run_fold_respects_split_dates_and_output_rows() -> None:
    result = run_fold(_matrix(), _fold(), ["f1", "f2"], {"target_column": "target_class_20d", "ridge_alpha": 1.0})
    assert len(result.predictions) == 12
    assert result.predictions["date"].min().isoformat() == "2020-01-07"
    assert result.predictions["date"].max().isoformat() == "2020-01-10"
    assert result.summary["train_row_count"] == 12
    assert result.summary["test_row_count"] == 12
    assert list(result.predictions.columns) == PREDICTION_COLUMNS


def test_prediction_ranks_are_by_test_date() -> None:
    result = run_fold(_matrix(), _fold(), ["f1", "f2"], {"target_column": "target_class_20d", "ridge_alpha": 1.0})
    for _, g in result.predictions.groupby("date"):
        assert sorted(g["pred_long_rank_20d"].tolist()) == [1, 2, 3]
        assert sorted(g["pred_short_rank_20d"].tolist()) == [1, 2, 3]
        assert g["pred_rank_pct_by_date"].between(1 / 3, 1.0).all()


def test_train_only_imputer_scaler_do_not_fit_on_test_rows() -> None:
    base = _matrix()
    test_start = pd.Timestamp(_fold()["test_start_date"])
    mask_test_a = (base["date"] == test_start) & (base["ticker"] == "A")
    base.loc[mask_test_a, "f1"] = None
    changed = base.copy()
    changed.loc[(changed["date"] >= test_start) & (changed["ticker"] != "A"), "f1"] = 1_000_000.0

    pred_base = run_fold(base, _fold(), ["f1", "f2"], {"target_column": "target_class_20d", "ridge_alpha": 1.0}).predictions
    pred_changed = run_fold(changed, _fold(), ["f1", "f2"], {"target_column": "target_class_20d", "ridge_alpha": 1.0}).predictions

    a_base = pred_base.loc[(pred_base["date"] == test_start.date()) & (pred_base["ticker"] == "A"), "pred_score_20d"].item()
    a_changed = pred_changed.loc[
        (pred_changed["date"] == test_start.date()) & (pred_changed["ticker"] == "A"), "pred_score_20d"
    ].item()
    assert a_base == a_changed


def test_leakage_columns_rejected_from_features() -> None:
    with pytest.raises(ValueError):
        validate_feature_cols(["f1", "next_open"], ["target_class_20d"], ["next_open"], ["date", "ticker"])


def test_max_folds_limits_requested_folds() -> None:
    plan = pd.DataFrame({"fold_id": [1, 2, 3]})
    assert select_folds(plan, max_folds=2)["fold_id"].tolist() == [1, 2]
    assert select_folds(plan, fold_id=3)["fold_id"].tolist() == [3]
