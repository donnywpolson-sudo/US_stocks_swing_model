import pandas as pd
import pytest

from quant_project_daily.column_registry import build_column_registry, load_baseline_feature_config
from quant_project_daily.features_baseline import build_baseline_features


def _labeled(tickers=("A", "B"), rows=300) -> pd.DataFrame:
    frames = []
    dates = pd.bdate_range("2010-01-01", periods=rows)
    for j, ticker in enumerate(tickers):
        base = 10 + j * 1000
        close = pd.Series(range(base, base + rows), dtype=float)
        open_ = close - 0.5
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": open_,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1000 + j * 100 + pd.Series(range(rows)),
                    "dollar_volume": close * (1000 + j * 100 + pd.Series(range(rows))),
                    "model_eligible": True,
                    "next_open": open_.shift(-1),
                    "exit_close_20d": close.shift(-20),
                    "exit_date_20d": dates.to_series().shift(-20).to_numpy(),
                    "fwd_ret_20d": close.shift(-20) / open_.shift(-1) - 1,
                    "has_split_like_gap_in_target_window_20d": False,
                    "label_valid_20d": True,
                    "target_class_20d": 0,
                    "target_long_top20_20d": False,
                    "target_short_bottom20_20d": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_baseline_features_are_ticker_local_and_returns_are_correct() -> None:
    result = build_baseline_features(_labeled(rows=80))
    out = result.data.sort_values(["ticker", "date"]).reset_index(drop=True)
    a = out[out["ticker"] == "A"].reset_index(drop=True)
    b = out[out["ticker"] == "B"].reset_index(drop=True)
    assert a.loc[1, "ret_1d"] == a.loc[1, "close"] / a.loc[0, "close"] - 1
    assert pd.isna(b.loc[0, "ret_1d"])


def test_rolling_high_low_features_are_causal() -> None:
    df = _labeled(tickers=("A",), rows=300)
    base = build_baseline_features(df).data
    changed_future = df.copy()
    changed_future.loc[changed_future.index[-1], "high"] = 1_000_000
    changed = build_baseline_features(changed_future).data
    early = base["date"].astype(str) < "2010-06-01"
    pd.testing.assert_series_equal(
        base.loc[early, "dist_to_60d_high"].reset_index(drop=True),
        changed.loc[early, "dist_to_60d_high"].reset_index(drop=True),
        check_names=False,
    )


def test_rsi_and_volume_features_do_not_use_future_rows() -> None:
    df = _labeled(tickers=("A",), rows=120)
    base = build_baseline_features(df).data
    changed_future = df.copy()
    changed_future.loc[changed_future.index[-1], ["close", "volume", "dollar_volume"]] = [9999.0, 999999, 9999999.0]
    changed = build_baseline_features(changed_future).data
    early = base["date"].astype(str) < "2010-03-01"
    pd.testing.assert_series_equal(base.loc[early, "rsi_14"].reset_index(drop=True), changed.loc[early, "rsi_14"].reset_index(drop=True), check_names=False)
    pd.testing.assert_series_equal(base.loc[early, "volume_z_20d"].reset_index(drop=True), changed.loc[early, "volume_z_20d"].reset_index(drop=True), check_names=False)


def test_output_only_label_valid_and_no_leakage_in_feature_cols() -> None:
    df = _labeled(tickers=("A",), rows=80)
    df.loc[df.index[:5], "label_valid_20d"] = False
    result = build_baseline_features(df)
    assert len(result.data) == len(df) - 5
    forbidden = {"next_open", "exit_close_20d", "fwd_ret_20d", "target_class_20d", "label_valid_20d"}
    assert not (set(result.registry["feature_cols"]) & forbidden)
    assert set(result.registry["feature_cols"]) == set(load_baseline_feature_config()["feature_columns"])


def test_missing_configured_features_raises_value_error() -> None:
    """build_column_registry must fail when configured columns are missing from actual."""
    cfg = {
        "feature_columns": ["f1", "f2", "missing_feat"],
        "target_columns": ["target_class_20d", "missing_target"],
        "metadata_columns": ["date", "ticker", "missing_meta"],
        "excluded_columns": ["fwd_ret_20d"],
    }
    actual_columns = ["f1", "f2", "date", "ticker", "target_class_20d", "fwd_ret_20d"]
    with pytest.raises(ValueError, match="configured columns missing"):
        build_column_registry(actual_columns, cfg)
