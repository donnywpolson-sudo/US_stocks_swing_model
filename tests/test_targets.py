import pandas as pd

from quant_project_daily.targets import generate_targets


def _research_frame(tickers: list[str], rows: int = 25) -> pd.DataFrame:
    dates = pd.date_range("2009-12-28", periods=rows, freq="B")
    frames = []
    for j, ticker in enumerate(tickers):
        base = 10.0 + j
        frames.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": base,
                    "high": base + 1,
                    "low": base - 1,
                    "close": base + 0.5,
                    "volume": 1000,
                    "dollar_volume": (base + 0.5) * 1000,
                    "model_eligible": dates >= pd.Timestamp("2010-01-01"),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def test_next_open_entry_and_close_t5_exit() -> None:
    df = _research_frame(["A"], 25)
    df.loc[df["ticker"] == "A", "open"] = range(100, 125)
    df.loc[df["ticker"] == "A", "close"] = range(200, 225)
    result = generate_targets(df, pd.DataFrame(columns=["ticker", "date"]))
    row = result.data.loc[result.data["date"].astype(str) == "2010-01-01"].iloc[0]
    assert row["next_open"] == 105
    assert row["exit_close_5d"] == 209
    assert str(row["exit_date_5d"]) == "2010-01-08"
    assert row["fwd_ret_5d"] == (209 / 105) - 1


def test_validity_rules_pre2010_non_model_excluded_split_and_final_rows() -> None:
    df = _research_frame(["A", "ZVZZT"], 25)
    df.loc[(df["ticker"] == "A") & (df["date"] == pd.Timestamp("2010-01-05")), "model_eligible"] = False
    gaps = pd.DataFrame([{"ticker": "A", "date": "2010-01-08"}])
    result = generate_targets(df, gaps, excluded_tickers=["ZVZZT"])
    out = result.data

    assert not out.loc[(out["ticker"] == "A") & (out["date"].astype(str) == "2009-12-31"), "label_valid_5d"].item()
    assert not out.loc[(out["ticker"] == "A") & (out["date"].astype(str) == "2010-01-05"), "label_valid_5d"].item()
    assert not out.loc[(out["ticker"] == "ZVZZT") & (out["date"].astype(str) == "2010-01-01"), "label_valid_5d"].item()
    assert not out.loc[(out["ticker"] == "A") & (out["date"].astype(str) == "2010-01-01"), "label_valid_5d"].item()
    assert out.loc[(out["ticker"] == "A") & (out["date"].astype(str) == "2010-01-01"), "has_split_like_gap_in_target_window_5d"].item()
    assert not out.loc[(out["ticker"] == "A") & (out["date"].astype(str) == "2010-01-29"), "label_valid_5d"].item()
    assert result.summary["excluded_ticker_rows"] == 25
    assert result.summary["invalid_reason_counts_are_overlapping"] is True
    assert (
        result.summary["mutually_exclusive_invalid_reason_counts"]["split_like_gap_in_target_window_5d"]
        == result.summary["otherwise_valid_rows_invalidated_by_split_like_target_window_gaps"]
    )
    assert (
        result.summary["invalid_reason_counts"]["split_like_gap_in_target_window_5d"]
        >= result.summary["otherwise_valid_rows_invalidated_by_split_like_target_window_gaps"]
    )
    assert (
        sum(result.summary["mutually_exclusive_invalid_reason_counts"].values()) + result.summary["label_valid_rows"]
        == result.summary["total_rows"]
    )


def test_per_date_top_bottom_20pct_class_assignment() -> None:
    rows = []
    date = pd.Timestamp("2010-01-04")
    for i, ret in enumerate([-0.5, -0.1, 0.0, 0.2, 0.8]):
        ticker = f"T{i}"
        dates = pd.bdate_range(date, periods=6)
        for k, d in enumerate(dates):
            rows.append(
                {
                    "date": d,
                    "ticker": ticker,
                    "raw_ticker": f"{ticker}.US",
                    "open": 10.0,
                    "high": 11.0,
                    "low": 9.0,
                    "close": 10.0,
                    "volume": 1000,
                    "dollar_volume": 10_000.0,
                    "model_eligible": True,
                }
            )
        rows[-1]["close"] = 10.0 * (1.0 + ret)
    df = pd.DataFrame(rows)

    out = generate_targets(df, pd.DataFrame(columns=["ticker", "date"])).data
    first_date = out.loc[out["date"].astype(str) == "2010-01-04", ["ticker", "target_class_5d"]]
    got = dict(zip(first_date["ticker"], first_date["target_class_5d"]))
    assert got["T0"] == -1
    assert got["T4"] == 1
    assert got["T1"] == 0
    assert got["T2"] == 0
    assert got["T3"] == 0
