import pandas as pd

from scripts.phase2_causal_base.research_universe import build_research_universe


def test_research_universe_keeps_warmup_and_marks_model_eligible() -> None:
    causal = pd.DataFrame(
        {
            "date": ["2008-12-31", "2009-01-01", "2009-12-31", "2010-01-01", "2010-01-02"],
            "ticker": ["A", "A", "A", "A", "B"],
            "tradable": [True, True, True, False, True],
            "close": [1, 2, 3, 4, 5],
        }
    )

    result = build_research_universe(causal)
    out = result.data

    assert list(out["date"].astype(str)) == ["2009-01-01", "2009-12-31", "2010-01-01", "2010-01-02"]
    assert out.loc[out["date"].astype(str) < "2010-01-01", "model_eligible"].sum() == 0
    assert out.loc[out["ticker"] == "A", "model_eligible"].sum() == 0
    assert out.loc[out["ticker"] == "B", "model_eligible"].sum() == 1
    assert result.summary["total_input_rows"] == 5
    assert result.summary["rows_kept"] == 4
    assert result.summary["rows_dropped_before_warmup_start_date"] == 1
    assert result.summary["model_eligible_rows"] == 1
    assert result.summary["rows_by_year"] == {"2009": 2, "2010": 2}
    assert result.summary["model_eligible_rows_by_year"] == {"2010": 1}
