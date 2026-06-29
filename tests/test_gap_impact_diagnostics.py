import pandas as pd

from scripts.validation.gap_impact_diagnostics import build_gap_impact


def test_gap_impact_joins_by_ticker_date_and_counts_model_status() -> None:
    gaps = pd.DataFrame(
        [
            {"ticker": "A", "date": "2009-12-31", "prev_close": 10.0, "open": 4.0, "close": 4.0, "gap_pct": -60.0},
            {"ticker": "A", "date": "2010-01-04", "prev_close": 4.0, "open": 8.0, "close": 8.0, "gap_pct": 100.0},
            {"ticker": "B", "date": "2010-01-04", "prev_close": 5.0, "open": 2.0, "close": 2.0, "gap_pct": -60.0},
            {"ticker": "Z", "date": "2010-01-04", "prev_close": 1.0, "open": 3.0, "close": 3.0, "gap_pct": 200.0},
        ]
    )
    research = pd.DataFrame(
        [
            {"ticker": "A", "date": pd.Timestamp("2009-12-31").date(), "model_eligible": False, "tradable": True, "year": 2009},
            {"ticker": "A", "date": pd.Timestamp("2010-01-04").date(), "model_eligible": True, "tradable": True, "year": 2010},
            {"ticker": "B", "date": pd.Timestamp("2010-01-04").date(), "model_eligible": False, "tradable": False, "year": 2010},
        ]
    )
    research_summary = {"research_start_date": "2010-01-01", "model_eligible_rows_by_year": {"2010": 1}}

    summary, reports = build_gap_impact(gaps, research, research_summary)

    assert summary["total_split_like_gaps_input"] == 4
    assert summary["split_like_gaps_inside_research_dataset"] == 3
    assert summary["split_like_gaps_before_research_start_date"] == 1
    assert summary["split_like_gaps_model_eligible_true"] == 1
    assert summary["split_like_gaps_model_eligible_false"] == 2
    assert summary["pct_research_window_split_like_gaps_not_model_eligible"] == 2 / 3
    assert reports["with_status"].loc[reports["with_status"]["ticker"] == "Z", "in_research_dataset"].item() is False
    assert reports["by_year"].loc[reports["by_year"]["year"] == 2010, "research_model_eligible_rows"].item() == 1
    assert reports["largest_abs"].iloc[0]["ticker"] == "Z"
