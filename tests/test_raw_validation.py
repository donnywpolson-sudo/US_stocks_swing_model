from pathlib import Path

from quant_project_daily.raw_validation import validate_raw_files


HEADER = "<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>\n"


def _write(tmp_path: Path, name: str, rows: list[str]) -> Path:
    p = tmp_path / name
    p.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    return p


def test_validation_rejects_bad_rows_and_counts_reasons(tmp_path: Path) -> None:
    p = _write(
        tmp_path,
        "bad.us.txt",
        [
            "A.US,D,20240102,000000,10,11,9,10,100,0",
            "A.US,D,20240102,000000,10,11,9,10,100,0",
            "B.US,D,20240103,000000,10,9,8,10,100,0",
            "C.US,X,20240103,000000,10,11,9,10,100,0",
            "D.US,D,20240103,123000,10,11,9,10,100,0",
            "E.US,D,20240103,000000,10,11,9,10,-1,0",
        ],
    )
    result = validate_raw_files([p])
    assert len(result.valid) == 0
    assert result.reason_counts["duplicate_ticker_date"] == 2
    assert result.reason_counts["bad_ohlc_consistency"] == 1
    assert result.reason_counts["bad_per"] == 1
    assert result.reason_counts["bad_time"] == 1
    assert result.reason_counts["bad_volume_negative"] == 1


def test_zero_volume_is_warning_not_reject(tmp_path: Path) -> None:
    p = _write(tmp_path, "zero.us.txt", ["A.US,D,20240102,0,10,11,9,10,0,0"])
    result = validate_raw_files([p])
    assert len(result.valid) == 1
    assert result.warning_counts["zero_volume_bar"] == 1


def test_bad_openint_is_rejected_not_silently_coerced(tmp_path: Path) -> None:
    """Malformed openint must be reported as bad_numeric_openint, not coerced to zero."""
    p = _write(tmp_path, "openint.us.txt", ["A.US,D,20240102,000000,10,11,9,10,100,abc"])
    result = validate_raw_files([p])
    assert len(result.valid) == 0
    assert result.reason_counts["bad_numeric_openint"] == 1


def test_summary_has_unique_rejected_and_reason_event_count(tmp_path: Path) -> None:
    """Summary must report unique_rejected_rows and rejection_reason_event_count."""
    p = _write(tmp_path, "dup.us.txt", ["A.US,D,20240102,000000,10,11,9,10,100,0", "A.US,D,20240102,000000,10,11,9,10,100,0"])
    result = validate_raw_files([p])
    assert "unique_rejected_rows" in result.summary
    assert "rejection_reason_event_count" in result.summary
    assert isinstance(result.summary["unique_rejected_rows"], int)
    assert isinstance(result.summary["rejection_reason_event_count"], int)
    assert result.summary["rejection_reason_event_count"] >= result.summary["unique_rejected_rows"]
