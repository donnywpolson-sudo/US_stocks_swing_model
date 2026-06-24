import pandas as pd
import pytest

from quant_project_daily.causal_gating import apply_causal_gating


def _frame(rows: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "date": dates.date,
            "raw_ticker": "A.US",
            "ticker": "A",
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.0,
            "volume": 200_000,
            "openint": 0,
            "source_file": "a.us.txt",
            "year": dates.year,
            "dollar_volume": 2_000_000.0,
        }
    )


def test_first_252_bars_not_tradable() -> None:
    out = apply_causal_gating(_frame())
    assert not out.loc[:251, "tradable"].any()
    assert bool(out.loc[252, "tradable"])


def test_causal_gating_no_future_dollar_volume_lookahead() -> None:
    base = _frame()
    changed_future = base.copy()
    changed_future.loc[253:, "dollar_volume"] = 0.0
    a = apply_causal_gating(base)
    b = apply_causal_gating(changed_future)
    pd.testing.assert_series_equal(a.loc[:252, "tradable"], b.loc[:252, "tradable"], check_names=False)


def test_60d_underlying_proxy_fields_are_ticker_local_and_trailing() -> None:
    dates = pd.date_range("2020-01-01", periods=65, freq="D")
    rows = []
    for ticker, base_dv in [("A", 1_000_000.0), ("B", 10_000_000.0)]:
        for i, d in enumerate(dates):
            rows.append(
                {
                    "date": d.date(),
                    "raw_ticker": f"{ticker}.US",
                    "ticker": ticker,
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.0,
                    "volume": 0 if ticker == "B" and i in {10, 20} else 200_000,
                    "openint": 0,
                    "source_file": f"{ticker.lower()}.us.txt",
                    "year": d.year,
                    "dollar_volume": base_dv + i,
                }
            )

    out = apply_causal_gating(pd.DataFrame(rows))
    a = out[out["ticker"] == "A"].reset_index(drop=True)
    b = out[out["ticker"] == "B"].reset_index(drop=True)

    assert a.loc[:58, "median_dollar_volume_60"].isna().all()
    assert a.loc[:58, "zero_volume_count_60"].isna().all()
    assert a.loc[59, "median_dollar_volume_60"] == pytest.approx(1_000_029.5)
    assert b.loc[59, "median_dollar_volume_60"] == pytest.approx(10_000_029.5)
    assert a.loc[59, "zero_volume_count_60"] == 0
    assert b.loc[59, "zero_volume_count_60"] == 2
    assert a.loc[60, "median_dollar_volume_60"] == pytest.approx(1_000_030.5)


def test_60d_underlying_proxy_fields_do_not_use_future_rows() -> None:
    base = _frame(rows=80)
    changed_future = base.copy()
    changed_future.loc[60:, "dollar_volume"] = 0.0
    changed_future.loc[60:, "volume"] = 0

    a = apply_causal_gating(base)
    b = apply_causal_gating(changed_future)

    pd.testing.assert_series_equal(
        a.loc[:59, "median_dollar_volume_60"],
        b.loc[:59, "median_dollar_volume_60"],
        check_names=False,
    )
    pd.testing.assert_series_equal(
        a.loc[:59, "zero_volume_count_60"],
        b.loc[:59, "zero_volume_count_60"],
        check_names=False,
    )
