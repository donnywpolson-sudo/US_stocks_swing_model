from __future__ import annotations

import csv
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.phase1A_download.alpha_vantage_listing_status import (
    OUTPUT_COLUMNS,
    build_listing_status_url,
    parse_listing_status_csv,
    write_listing_status_csv,
)


def test_alpha_vantage_listing_status_template_header_matches_output_columns() -> None:
    template_path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "alpha_vantage_listing_status_template.csv"

    with template_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows == [list(OUTPUT_COLUMNS)]


def test_build_listing_status_url_uses_listing_status_function_state_and_date() -> None:
    url = build_listing_status_url("demo-key", state="delisted", query_date="2014-07-10")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.alphavantage.co"
    assert params["function"] == ["LISTING_STATUS"]
    assert params["state"] == ["delisted"]
    assert params["date"] == ["2014-07-10"]
    assert params["apikey"] == ["demo-key"]


def test_parse_listing_status_csv_enriches_rows_without_pit_clearance_fields() -> None:
    rows = parse_listing_status_csv(
        """
symbol,name,exchange,assetType,ipoDate,delistingDate,status
ABC,ABC Corp,NASDAQ,Stock,2012-01-03,,Active
XYZ,XYZ Fund,NYSE Arca,ETF,2011-05-02,2020-06-01,Delisted
""".lstrip(),
        query_state="delisted",
        source_asof_date="2026-06-29",
    )

    assert rows == [
        {
            "symbol": "ABC",
            "name": "ABC Corp",
            "exchange": "NASDAQ",
            "assetType": "Stock",
            "ipoDate": "2012-01-03",
            "delistingDate": "",
            "status": "Active",
            "query_state": "delisted",
            "source": "Alpha Vantage LISTING_STATUS",
            "source_asof_date": "2026-06-29",
        },
        {
            "symbol": "XYZ",
            "name": "XYZ Fund",
            "exchange": "NYSE Arca",
            "assetType": "ETF",
            "ipoDate": "2011-05-02",
            "delistingDate": "2020-06-01",
            "status": "Delisted",
            "query_state": "delisted",
            "source": "Alpha Vantage LISTING_STATUS",
            "source_asof_date": "2026-06-29",
        },
    ]
    assert "permanent_id" not in rows[0]
    assert "ticker_start_date" not in rows[0]
    assert "ticker_end_date" not in rows[0]


def test_write_listing_status_csv_writes_ignored_reference_artifact(tmp_path: Path) -> None:
    output = tmp_path / "data" / "reference" / "alpha_vantage_listing_status.csv"
    result = write_listing_status_csv(
        [
            {
                "symbol": "ABC",
                "name": "ABC Corp",
                "exchange": "NASDAQ",
                "assetType": "Stock",
                "ipoDate": "2012-01-03",
                "delistingDate": "",
                "status": "Active",
                "query_state": "active",
                "source": "Alpha Vantage LISTING_STATUS",
                "source_asof_date": "2026-06-29",
            }
        ],
        output,
    )

    assert result["row_count"] == 1
    with output.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == list(OUTPUT_COLUMNS)
    assert rows[1] == [
        "ABC",
        "ABC Corp",
        "NASDAQ",
        "Stock",
        "2012-01-03",
        "",
        "Active",
        "active",
        "Alpha Vantage LISTING_STATUS",
        "2026-06-29",
    ]
