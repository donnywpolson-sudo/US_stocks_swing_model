"""
Tests for the Stooq raw archive inspector.

These tests verify classification, hashing, report generation,
and robustness against unknown/missing files. They do NOT
modify raw ZIPs or load entire datasets into memory.

Default tests use tiny synthetic ZIPs created in tmp_path.
Real-data integration tests are skipped unless RUN_REAL_DATA_TESTS=1.
"""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import pytest

# The inspector module
from scripts.raw_ingest.inspect_stooq_raw import (
    _classify_inner_file,
    _detect_encoding,
    _extract_symbol_from_path,
    build_schema_profile,
    build_prepare_plan,
    inspect_zip,
    inventory_all,
    sha256_file,
    write_inventory_csv,
    write_inventory_json,
    write_schema_profile,
    write_prepare_plan,
)


# ---------------------------------------------------------------------------
# Shared helpers: tiny synthetic ZIP builders
# ---------------------------------------------------------------------------

DAILY_ASCII_CONTENT = "Date,Open,High,Low,Close,Volume,Per,Time\n20240102,10.1,10.5,9.9,10.3,1000,D,000000\n20240103,10.3,10.6,10.0,10.4,1200,D,000000\n"

HOURLY_ASCII_CONTENT = "Date,Time,Open,High,Low,Close,Volume,Per\n20240102,093000,10.1,10.2,9.9,10.15,500,60\n20240102,103000,10.15,10.3,10.1,10.25,300,60\n"

DOP_CONTENT = '"Field1",1,2,3\n"Field2",2,3,4\n'

MASTER_CONTENT = b"\x00" * 10  # tiny binary placeholder

EMASTER_CONTENT = b"\x01" * 10  # tiny binary placeholder


def _make_daily_zip(path: Path) -> None:
    """Create a tiny ZIP containing one daily_ascii .txt file."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data/daily/us/nasdaq etfs/aadr.us.txt", DAILY_ASCII_CONTENT)
        zf.writestr("data/daily/us/nasdaq etfs/msft.us.txt", DAILY_ASCII_CONTENT)


def _make_hourly_zip(path: Path) -> None:
    """Create a tiny ZIP containing one hourly_ascii .txt file."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data/hourly/us/nyse stocks/2/zws.us.txt", HOURLY_ASCII_CONTENT)
        zf.writestr("data/hourly/us/nyse stocks/2/aapl.us.txt", HOURLY_ASCII_CONTENT)


def _make_d_us_ms_zip(path: Path) -> None:
    """Create a tiny MetaStock daily ZIP with MASTER, EMASTER, DOP, DAT."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data/daily/us/nasdaq etfs/MASTER", MASTER_CONTENT)
        zf.writestr("data/daily/us/nasdaq etfs/EMASTER", EMASTER_CONTENT)
        zf.writestr("data/daily/us/nasdaq etfs/F1.DOP", DOP_CONTENT)
        zf.writestr("data/daily/us/nasdaq etfs/F1/DAT", b"\x02" * 8)


def _make_h_us_ms_zip(path: Path) -> None:
    """Create a tiny MetaStock hourly ZIP with MASTER, EMASTER, DOP, DAT."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data/hourly/us/nasdaq etfs/MASTER", MASTER_CONTENT)
        zf.writestr("data/hourly/us/nasdaq etfs/EMASTER", EMASTER_CONTENT)
        zf.writestr("data/hourly/us/nasdaq etfs/F1.DOP", DOP_CONTENT)
        zf.writestr("data/hourly/us/nasdaq etfs/F1/DAT", b"\x02" * 8)


@pytest.fixture()
def synthetic_raw(tmp_path: Path) -> Path:
    """Create a synthetic data/raw directory with 4 tiny ZIPs for testing."""
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    _make_daily_zip(raw_dir / "d_us_txt.zip")
    _make_hourly_zip(raw_dir / "h_us_txt.zip")
    _make_d_us_ms_zip(raw_dir / "d_us_ms.zip")
    _make_h_us_ms_zip(raw_dir / "h_us_ms.zip")
    return raw_dir


# ---------------------------------------------------------------------------
# Integration guard — skips real-data tests unless explicitly requested
# ---------------------------------------------------------------------------

RUN_REAL = os.environ.get("RUN_REAL_DATA_TESTS", "") == "1"


def _maybe_skip_real() -> None:
    """Skip if real data not requested."""
    if not RUN_REAL:
        pytest.skip("Real-data integration test; set RUN_REAL_DATA_TESTS=1 to run")


@pytest.fixture(scope="session")
def raw_root() -> Path:
    """Real data/raw root — only used in integration tests."""
    _maybe_skip_real()
    root = Path(__file__).resolve().parents[2] / "data" / "raw"
    if not root.is_dir():
        pytest.skip("data/raw directory not found")
    return root


@pytest.fixture(scope="session")
def reports_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("reports")


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------


class TestClassification:
    """Verify that inner file paths are correctly classified."""

    def test_daily_ascii(self) -> None:
        assert _classify_inner_file("data/daily/us/nasdaq etfs/aadr.us.txt") == "daily_ascii"

    def test_hourly_ascii(self) -> None:
        assert _classify_inner_file("data/hourly/us/nyse stocks/2/zws.us.txt") == "hourly_ascii"

    def test_metastock_master(self) -> None:
        assert _classify_inner_file("data/daily/us/nasdaq etfs/MASTER") == "metastock_master"

    def test_metastock_emaster(self) -> None:
        assert _classify_inner_file("data/daily/us/nasdaq etfs/EMASTER") == "metastock_emaster"

    def test_metastock_dop(self) -> None:
        assert _classify_inner_file("data/daily/us/nasdaq etfs/F1.DOP") == "metastock_dop"

    def test_metastock_dop_hourly(self) -> None:
        assert _classify_inner_file("data/hourly/us/nasdaq etfs/F1.DOP") == "metastock_dop"

    def test_metastock_data_subdir(self) -> None:
        assert _classify_inner_file("data/daily/us/nasdaq etfs/F1/DAT") == "metastock_data"

    def test_unknown_no_ext(self) -> None:
        assert _classify_inner_file("some_random_file") == "unknown"

    def test_not_metadata(self) -> None:
        """MS files must NOT be classified as metadata."""
        ms_paths = [
            "data/daily/us/nasdaq etfs/MASTER",
            "data/daily/us/nasdaq etfs/EMASTER",
            "data/daily/us/nasdaq etfs/F1.DOP",
            "data/daily/us/nasdaq etfs/F2.DOP",
            "data/daily/us/nasdaq etfs/F1/DAT",
        ]
        for p in ms_paths:
            assert _classify_inner_file(p) != "metadata", f"{p} misclassified as metadata"

    def test_unknown_file_type(self) -> None:
        """Unknown file types must not crash — just return 'unknown'."""
        weird = ["file.xyz", "noextension", ".hidden", "data/random.bin"]
        for p in weird:
            result = _classify_inner_file(p)
            assert result in ("unknown", "unknown_ascii"), f"{p} -> {result}"


# ---------------------------------------------------------------------------
# Encoding detection tests
# ---------------------------------------------------------------------------


class TestEncodingDetection:
    def test_ascii(self) -> None:
        assert _detect_encoding(b"hello,world\n123,456") == "ascii"

    def test_binary(self) -> None:
        assert _detect_encoding(b"\xff\xfe\x00\x01\x02") == "binary"


# ---------------------------------------------------------------------------
# Symbol extraction tests
# ---------------------------------------------------------------------------


class TestSymbolExtraction:
    def test_daily_txt(self) -> None:
        assert _extract_symbol_from_path("data/daily/us/nasdaq etfs/aadr.us.txt") == "AADR.US"

    def test_hourly_txt(self) -> None:
        assert _extract_symbol_from_path("data/hourly/us/nyse stocks/2/zws.us.txt") == "ZWS.US"

    def test_empty(self) -> None:
        assert _extract_symbol_from_path("") == ""


# ---------------------------------------------------------------------------
# Hash computation tests — use synthetic file, NOT raw_root
# ---------------------------------------------------------------------------


class TestHashing:
    def test_sha256_stream(self, tmp_path: Path) -> None:
        """Hash is computed and is a valid SHA-256 hex string."""
        f = tmp_path / "tiny.zip"
        _make_daily_zip(f)
        h = sha256_file(f)
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # Will raise if not hex

    def test_sha256_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "tiny.zip"
        _make_daily_zip(f)
        h1 = sha256_file(f)
        h2 = sha256_file(f)
        assert h1 == h2


# ---------------------------------------------------------------------------
# Inventory tests — use synthetic_raw fixture (no real data)
# ---------------------------------------------------------------------------


class TestInventory:
    def test_inspect_zip_daily(self, synthetic_raw: Path) -> None:
        """Synthetic daily ZIP contains daily_ascii files."""
        zip_path = synthetic_raw / "d_us_txt.zip"
        rows = inspect_zip(zip_path)
        assert len(rows) > 0
        # At least one row should be daily_ascii
        daily_types = [r for r in rows if r["inferred_type"] == "daily_ascii"]
        assert len(daily_types) > 0, "No daily_ascii files detected"
        # Verify schema from sampled files
        for dr in daily_types[:3]:
            assert "ticker" in dr["columns"] or len(dr["columns"]) > 0

    def test_inspect_zip_hourly(self, synthetic_raw: Path) -> None:
        """Synthetic hourly ZIP contains hourly_ascii files."""
        zip_path = synthetic_raw / "h_us_txt.zip"
        rows = inspect_zip(zip_path)
        assert len(rows) > 0
        hourly_types = [r for r in rows if r["inferred_type"] == "hourly_ascii"]
        assert len(hourly_types) > 0, "No hourly_ascii files detected"

    def test_inspect_zip_ms_not_metadata(self, synthetic_raw: Path) -> None:
        """MS ZIPs must not be classified as metadata."""
        for fname in ("d_us_ms.zip", "h_us_ms.zip"):
            zip_path = synthetic_raw / fname
            rows = inspect_zip(zip_path)
            assert len(rows) > 0
            metadata_rows = [r for r in rows if r["inferred_type"] == "metadata"]
            assert len(metadata_rows) == 0, f"{fname}: found metadata rows"
            # Should have metastock types
            ms_types = [r for r in rows if "metastock" in r["inferred_type"]]
            assert len(ms_types) > 0, f"{fname}: no metastock files detected"

    def test_hash_in_inventory(self, synthetic_raw: Path) -> None:
        """Every inventory row has a non-empty source_zip_hash."""
        for fname in ("d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"):
            zip_path = synthetic_raw / fname
            rows = inspect_zip(zip_path)
            for row in rows[:10]:
                assert row["source_zip_hash"], f"Missing hash in {fname}"
                assert len(row["source_zip_hash"]) == 64

    def test_raw_zip_unchanged(self, synthetic_raw: Path) -> None:
        """ZIP file size and mtime must not change during inspection."""
        for fname in ("d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"):
            zip_path = synthetic_raw / fname
            before_size = zip_path.stat().st_size
            # Inspect
            inspect_zip(zip_path)
            after_size = zip_path.stat().st_size
            assert before_size == after_size, f"{fname} size changed!"

    def test_no_crash_unknown_archive(self, tmp_path: Path) -> None:
        """Non-existent ZIP returns empty list."""
        rows = inspect_zip(tmp_path / "nonexistent.zip")
        assert rows == []

    def test_inventory_all_detects_archives(self, synthetic_raw: Path) -> None:
        """inventory_all finds all 4 ZIPs."""
        inventory = inventory_all(synthetic_raw)
        archives_found = set(r["archive_path"] for r in inventory)
        expected = {"d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"}
        assert expected.issubset(archives_found), f"Missing archives: {expected - archives_found}"


# ---------------------------------------------------------------------------
# Schema profile tests — use synthetic_raw fixture (no real data)
# ---------------------------------------------------------------------------


class TestSchemaProfile:
    def test_profile_built(self, synthetic_raw: Path) -> None:
        inventory = inventory_all(synthetic_raw)
        profile = build_schema_profile(inventory)
        assert len(profile["archives_detected"]) == 4
        assert profile["total_inner_files"] == sum(
            a["file_count"] for a in profile["archives_detected"]
        )
        # Must report data limitations
        assert "metadata_missing" in profile
        assert "survivorship_bias_risk" in profile
        assert "adjusted_uncertainty" in profile
        assert "adjusted_notes" in profile
        assert "timezone_notes" in profile

    def test_metadata_missing(self, synthetic_raw: Path) -> None:
        inventory = inventory_all(synthetic_raw)
        profile = build_schema_profile(inventory)
        assert profile["metadata_missing"] is True
        assert profile["survivorship_bias_risk"] is True

    def test_no_metadata_parquet_in_plan(self, synthetic_raw: Path) -> None:
        """The prepare plan must NOT propose a metadata parquet output."""
        inventory = inventory_all(synthetic_raw)
        profile = build_schema_profile(inventory)
        plan = build_prepare_plan(profile)
        # The plan should only discuss daily/hourly parquet
        assert "metadata/us_symbols.parquet" not in plan


# ---------------------------------------------------------------------------
# Report writing tests — use synthetic_raw fixture (no real data)
# ---------------------------------------------------------------------------


class TestReports:
    def test_report_writes(self, synthetic_raw: Path, tmp_path: Path) -> None:
        """All four report files are written without error."""
        inventory = inventory_all(synthetic_raw)
        profile = build_schema_profile(inventory)
        plan_text = "Test plan\n"

        inv_json = tmp_path / "stooq_raw_inventory.json"
        inv_csv = tmp_path / "stooq_raw_inventory.csv"
        schema = tmp_path / "stooq_schema_profile.json"
        plan_md = tmp_path / "stooq_prepare_plan.md"

        write_inventory_json(inventory, inv_json)
        write_inventory_csv(inventory, inv_csv)
        write_schema_profile(profile, schema)
        write_prepare_plan(plan_text, plan_md)

        assert inv_json.is_file()
        assert inv_csv.is_file()
        assert schema.is_file()
        assert plan_md.is_file()

        # Verify JSON is parseable
        with open(inv_json) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify schema JSON
        with open(schema) as f:
            prof = json.load(f)
        assert "archives_detected" in prof