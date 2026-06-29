from pathlib import Path

from scripts.phase1C_validate.raw_validation import clean_ticker, normalize_time_value, read_raw_txt


def test_angle_headers_ticker_and_time_values(tmp_path: Path) -> None:
    p = tmp_path / "a.us.txt"
    p.write_text("<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\nA.US,D,20240102,000000,1,2,1,2,100,0\n", encoding="utf-8")
    df = read_raw_txt(p)
    assert list(df.columns) == ["ticker", "per", "date", "time", "open", "high", "low", "close", "vol", "openint"]
    assert clean_ticker(df["ticker"].iloc[0]) == "A"
    assert normalize_time_value("000000") == "000000"
    assert normalize_time_value(0) == "000000"
