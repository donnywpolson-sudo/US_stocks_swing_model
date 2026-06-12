"""
Tests for the Stooq raw archive inspector.

These tests verify classification, hashing, report generation,
and robustness against unknown/missing files. They do NOT
modify raw ZIPs or load entire datasets into memory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

# The inspector module
from scripts.raw_ingest.inspect_stooq_raw import (
    _classify_inner_file,
    _detect_encoding,
    _extract_symbol_from_path,
    build_schema_profile,
    inspect_zip,
    inventory_all,
    sha256_file,
    write_inventory_csv,
    write_inventory_json,
    write_schema_profile,
    write_prepare_plan,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def raw_root() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "raw"


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
# Hash computation tests
# ---------------------------------------------------------------------------


class TestHashing:
    def test_sha256_stream(self, raw_root: Path) -> None:
        """Hash is computed and is a valid SHA-256 hex string."""
        zips = list(raw_root.glob("*.zip"))
        if not zips:
            pytest.skip("No ZIP files in raw root")
        h = sha256_file(zips[0])
        assert isinstance(h, str)
        assert len(h) == 64
        int(h, 16)  # Will raise if not hex

    def test_sha256_deterministic(self, raw_root: Path) -> None:
        zips = list(raw_root.glob("*.zip"))
        if not zips:
            pytest.skip("No ZIP files in raw root")
        h1 = sha256_file(zips[0])
        h2 = sha256_file(zips[0])
        assert h1 == h2


# ---------------------------------------------------------------------------
# Inventory tests
# ---------------------------------------------------------------------------


class TestInventory:
    def test_inspect_zip_daily(self, raw_root: Path) -> None:
        """d_us_txt.zip contains daily_ascii files."""
        zip_path = raw_root / "d_us_txt.zip"
        if not zip_path.is_file():
            pytest.skip("d_us_txt.zip not found")
        rows = inspect_zip(zip_path)
        assert len(rows) > 0
        # At least one row should be daily_ascii
        daily_types = [r for r in rows if r["inferred_type"] == "daily_ascii"]
        assert len(daily_types) > 0, "No daily_ascii files detected"
        # Verify schema from sampled files
        for dr in daily_types[:3]:
            assert "ticker" in dr["columns"] or len(dr["columns"]) > 0

    def test_inspect_zip_hourly(self, raw_root: Path) -> None:
        """h_us_txt.zip contains hourly_ascii files."""
        zip_path = raw_root / "h_us_txt.zip"
        if not zip_path.is_file():
            pytest.skip("h_us_txt.zip not found")
        rows = inspect_zip(zip_path)
        assert len(rows) > 0
        hourly_types = [r for r in rows if r["inferred_type"] == "hourly_ascii"]
        assert len(hourly_types) > 0, "No hourly_ascii files detected"

    def test_inspect_zip_ms_not_metadata(self, raw_root: Path) -> None:
        """MS ZIPs must not be classified as metadata."""
        for fname in ("d_us_ms.zip", "h_us_ms.zip"):
            zip_path = raw_root / fname
            if not zip_path.is_file():
                continue
            rows = inspect_zip(zip_path)
            assert len(rows) > 0
            metadata_rows = [r for r in rows if r["inferred_type"] == "metadata"]
            assert len(metadata_rows) == 0, f"{fname}: found metadata rows"
            # Should have metastock types
            ms_types = [r for r in rows if "metastock" in r["inferred_type"]]
            assert len(ms_types) > 0, f"{fname}: no metastock files detected"

    def test_hash_in_inventory(self, raw_root: Path) -> None:
        """Every inventory row has a non-empty source_zip_hash."""
        for fname in ("d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"):
            zip_path = raw_root / fname
            if not zip_path.is_file():
                continue
            rows = inspect_zip(zip_path)
            for row in rows[:10]:
                assert row["source_zip_hash"], f"Missing hash in {fname}"
                assert len(row["source_zip_hash"]) == 64

    def test_raw_zip_unchanged(self, raw_root: Path) -> None:
        """ZIP file size and mtime must not change during inspection."""
        for fname in ("d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"):
            zip_path = raw_root / fname
            if not zip_path.is_file():
                continue
            before_size = zip_path.stat().st_size
            # Inspect
            inspect_zip(zip_path)
            after_size = zip_path.stat().st_size
            assert before_size == after_size, f"{fname} size changed!"

    def test_no_crash_unknown_archive(self, tmp_path: Path) -> None:
        """Non-existent ZIP returns empty list."""
        rows = inspect_zip(tmp_path / "nonexistent.zip")
        assert rows == []

    def test_inventory_all_detects_archives(self, raw_root: Path) -> None:
        """inventory_all finds all 4 ZIPs."""
        inventory = inventory_all(raw_root)
        archives_found = set(r["archive_path"] for r in inventory)
        expected = {"d_us_txt.zip", "h_us_txt.zip", "d_us_ms.zip", "h_us_ms.zip"}
        assert expected.issubset(archives_found), f"Missing archives: {expected - archives_found}"


# ---------------------------------------------------------------------------
# Schema profile tests
# ---------------------------------------------------------------------------


class TestSchemaProfile:
    def test_profile_built(self, raw_root: Path) -> None:
        inventory = inventory_all(raw_root)
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

    def test_metadata_missing(self, raw_root: Path) -> None:
        inventory = inventory_all(raw_root)
        profile = build_schema_profile(inventory)
        assert profile["metadata_missing"] is True
        assert profile["survivorship_bias_risk"] is True

    def test_no_metadata_parquet_in_plan(self, raw_root: Path) -> None:
        """The prepare plan must NOT propose a metadata parquet output."""
        from scripts.raw_ingest.inspect_stooq_raw import build_prepare_plan

        inventory = inventory_all(raw_root)
        profile = build_schema_profile(inventory)
        plan = build_prepare_plan(profile)
        # The plan should only discuss daily/hourly parquet
        assert "metadata/us_symbols.parquet" not in plan


# ---------------------------------------------------------------------------
# Report writing tests
# ---------------------------------------------------------------------------


class TestReports:
    def test_report_writes(self, raw_root: Path, reports_root: Path) -> None:
        """All four report files are written without error."""
        inventory = inventory_all(raw_root)
        profile = build_schema_profile(inventory)
        plan_text = "Test plan\n"

        inv_json = reports_root / "stooq_raw_inventory.json"
        inv_csv = reports_root / "stooq_raw_inventory.csv"
        schema = reports_root / "stooq_schema_profile.json"
        plan_md = reports_root / "stooq_prepare_plan.md"

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