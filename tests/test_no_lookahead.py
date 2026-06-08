import pandas as pd

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
