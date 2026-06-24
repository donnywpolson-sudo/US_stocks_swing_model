import csv
from pathlib import Path


TEMPLATE_COLUMNS = [
    "snapshot_date",
    "snapshot_time",
    "underlying",
    "expiration",
    "dte",
    "option_type",
    "strike",
    "bid",
    "ask",
    "mid",
    "last",
    "volume",
    "open_interest",
    "implied_volatility",
    "delta",
    "gamma",
    "theta",
    "vega",
    "source",
    "source_symbol",
]


def test_stage17_manual_option_chain_template_header() -> None:
    template_path = Path("docs/examples/stage17_manual_option_chain_template.csv")
    with template_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows == [TEMPLATE_COLUMNS]


def test_stage17_manual_option_chain_mapping_guide_covers_required_cautions() -> None:
    guide = Path("docs/stage17_manual_option_chain_mapping.md").read_text(encoding="utf-8")

    required_phrases = [
        "`snapshot_time` | `snapshot_timestamp`",
        "`underlying` | `underlying_ticker`",
        "`option_type` | `call_put`",
        "`source` | `data_source`",
        "`source_symbol` | `option_symbol`",
        "Accepted values are `C`, `P`, `CALL`, or `PUT`",
        "`bid` must be less than or equal to `ask`",
        "Keep `snapshot_date` separate from Stage 16 `score_date`",
        "not prove option liquidity",
        "not an option P&L test",
    ]
    for phrase in required_phrases:
        assert phrase in guide
