from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from scripts.phase1B_convert.raw_parquet_export import (
    export_alpha_vantage_listing_status_to_parquet,
    export_stooq_raw_txt_to_parquet,
    raw_txt_to_parquet_frame,
)


def test_raw_txt_to_parquet_frame_adds_market_year_and_sorts_rows(tmp_path: Path) -> None:
    raw_path = tmp_path / "b.us.txt"
    raw_path.write_text(
        """
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
B.US,D,20200103,000000,11,12,10,11.5,100,0
B.US,D,20191231,000000,10,11,9,10.5,200,0
""".lstrip(),
        encoding="utf-8",
    )

    frame = raw_txt_to_parquet_frame(raw_path)

    assert list(frame["date"].astype(str)) == ["2019-12-31", "2020-01-03"]
    assert list(frame["market_year"]) == ["US-2019", "US-2020"]
    assert set(["raw_ticker", "ticker", "market", "market_year", "year", "source_file"]) <= set(frame.columns)
    assert frame["raw_ticker"].unique().tolist() == ["B.US"]
    assert frame["ticker"].unique().tolist() == ["B"]
    assert frame["market"].unique().tolist() == ["US"]


def test_export_stooq_raw_txt_to_parquet_writes_one_flat_file_per_stock(tmp_path: Path) -> None:
    input_dir = tmp_path / "raw_txt"
    output_dir = tmp_path / "raw_parquet"
    input_dir.mkdir()
    (input_dir / "a.us.txt").write_text(
        """
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
A.US,D,20200102,000000,1,2,1,2,100,0
""".lstrip(),
        encoding="utf-8",
    )
    (input_dir / "b.us.txt").write_text(
        """
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
B.US,D,20200102,000000,1,2,1,2,100,0
""".lstrip(),
        encoding="utf-8",
    )

    summary = export_stooq_raw_txt_to_parquet(input_dir=input_dir, output_dir=output_dir, progress_every=None)

    assert summary["files_scanned"] == 2
    assert summary["files_written"] == 2
    assert summary["rows_written"] == 2
    assert (output_dir / "A.parquet").exists()
    assert (output_dir / "B.parquet").exists()


def test_export_alpha_vantage_listing_status_to_parquet_sorts_and_adds_years(tmp_path: Path) -> None:
    input_csv = tmp_path / "alpha_vantage_listing_status.csv"
    output_path = tmp_path / "alpha_vantage_listing_status.parquet"
    with input_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "name", "exchange", "assetType", "ipoDate", "delistingDate", "status", "query_state", "source", "source_asof_date"])
        writer.writerow(["ZZZ", "ZZZ Corp", "NYSE", "Stock", "2020-01-02", "", "Active", "active", "Alpha Vantage LISTING_STATUS", "2026-06-29"])
        writer.writerow(["AAA", "AAA Corp", "NASDAQ", "Stock", "2019-01-02", "2021-03-04", "Delisted", "delisted", "Alpha Vantage LISTING_STATUS", "2026-06-29"])

    summary = export_alpha_vantage_listing_status_to_parquet(input_csv=input_csv, output_path=output_path)
    out = pd.read_parquet(output_path)

    assert summary["rows_written"] == 2
    assert list(out["query_state"]) == ["active", "delisted"]
    assert "ipoDate_year" in out.columns
    assert "delistingDate_year" in out.columns
    assert "source_asof_date_year" in out.columns
