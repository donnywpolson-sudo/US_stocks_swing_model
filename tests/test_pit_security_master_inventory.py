from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from scripts.project_config import ProjectPaths
from scripts.validation.pit_security_master_inventory import (
    REQUIRED_COLUMNS,
    build_pit_security_master_inventory,
    build_pit_security_master_markdown,
    write_pit_security_master_inventory,
)


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily.parquet",
        labeled_target_h5=tmp_path / "data" / "labeled" / "target_h5",
        feature_matrix_baseline_h5=tmp_path / "data" / "feature_matrices" / "baseline_h5",
        feature_matrix_expanded_h5=tmp_path / "data" / "feature_matrices" / "expanded_h5",
        frozen_features_expanded_h5_v1=tmp_path / "data" / "frozen_features" / "expanded_h5_v1",
        oos_predictions_baseline_h5=tmp_path / "data" / "oos_predictions" / "baseline_h5",
        validation_reports=tmp_path / "reports" / "validation",
        label_reports=tmp_path / "reports" / "labels",
        feature_reports=tmp_path / "reports" / "features",
        wfa_reports=tmp_path / "reports" / "wfa",
        metrics_reports=tmp_path / "reports" / "metrics",
        gates_reports=tmp_path / "reports" / "gates",
    )


def _write_master(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "data" / "reference" / "pit_security_master.csv"
    path.parent.mkdir(parents=True)
    path.write_text(text.lstrip(), encoding="utf-8")
    return path


def _valid_master_csv() -> str:
    return """
permanent_id,raw_ticker,ticker,security_type,listing_date,delisting_date,ticker_start_date,ticker_end_date,exchange,is_otc,is_common_stock,is_etf,is_etn,is_adr,source,source_asof_date
PERM-1,AAPL.US,AAPL,common_stock,1980-12-12,,1980-12-12,,NASDAQ,false,true,false,false,false,unit_fixture,2026-01-01
PERM-2,OLD.US,OLD,common_stock,1999-01-04,2018-03-01,1999-01-04,2018-03-01,NYSE,false,true,false,false,false,unit_fixture,2026-01-01
"""


def test_missing_input_writes_missing_pit_statuses(tmp_path: Path) -> None:
    result = write_pit_security_master_inventory(_paths(tmp_path))

    assert result["pit_security_metadata_status"] == "missing"
    assert result["survivorship_delisting_coverage_status"] == "missing"
    assert result["modeling_gate_decision"] == "do_not_run_new_model_work"
    assert result["blockers"] == ["missing_input_file"]
    assert (tmp_path / "reports" / "audit" / "pit_security_master_inventory.json").exists()
    assert (tmp_path / "reports" / "audit" / "pit_security_master_inventory.md").exists()


def test_valid_fixture_proves_pit_metadata_and_records_coverage(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_master(tmp_path, _valid_master_csv())
    paths.raw_txt.mkdir(parents=True)
    (paths.raw_txt / "aapl.us.txt").write_text("x", encoding="utf-8")
    (paths.raw_txt / "old.us.txt").write_text("x", encoding="utf-8")
    paths.research_ohlcv_daily.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": ["AAPL", "OLD", "MSFT"]}).to_parquet(paths.research_ohlcv_daily, index=False)

    inventory = build_pit_security_master_inventory(paths, generated_at_utc="2026-01-01T00:00:00+00:00")

    assert inventory["status_summary"]["pit_security_metadata"] == "proven"
    assert inventory["status_summary"]["survivorship_delisting_coverage"] == "proven"
    assert inventory["validation"]["row_count"] == 2
    assert inventory["validation"]["source_count"] == 1
    assert inventory["validation"]["source_asof_date_count"] == 1
    assert inventory["coverage_summary"]["metadata_raw_tickers_in_raw_count"] == 2
    assert inventory["coverage_summary"]["metadata_tickers_in_research_count"] == 2
    assert inventory["coverage_summary"]["research_symbols_missing_from_metadata_count"] == 1


def test_invalid_fixture_reports_schema_boolean_date_duplicate_and_interval_blockers(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_master(
        tmp_path,
        """
permanent_id,raw_ticker,ticker,security_type,listing_date,delisting_date,ticker_start_date,ticker_end_date,is_otc,is_common_stock,is_etf,is_etn,is_adr,source,source_asof_date
PERM-1,BAD.US,BAD,common_stock,2021-02-30,2020-01-01,2021-01-05,2021-01-04,maybe,true,false,false,false,,2026-01-01
PERM-1,BAD.US,BAD,common_stock,2021-01-01,,2021-01-05,,false,true,false,false,false,fixture,bad-date
""",
    )

    inventory = build_pit_security_master_inventory(paths, generated_at_utc="2026-01-01T00:00:00+00:00")
    blockers = set(inventory["validation"]["blockers"])

    assert inventory["status_summary"]["pit_security_metadata"] == "unverified"
    assert "missing_required_columns" in blockers
    assert "empty_required_values" in blockers
    assert "invalid_boolean_values" in blockers
    assert "invalid_date_values" in blockers
    assert "duplicate_identity_rows" in blockers
    assert "reversed_date_intervals" in blockers
    assert inventory["validation"]["missing_columns"] == ["exchange"]
    assert inventory["validation"]["boolean_invalid_counts"]["is_otc"] == 1
    assert inventory["validation"]["duplicate_identity_row_count"] == 2


def test_pit_security_master_template_header_matches_validator_columns() -> None:
    template_path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "pit_security_master_template.csv"

    with template_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows == [list(REQUIRED_COLUMNS)]
    header = rows[0]
    assert header == list(REQUIRED_COLUMNS)


def test_markdown_preserves_h5_timing_and_safety_guardrails(tmp_path: Path) -> None:
    inventory = build_pit_security_master_inventory(_paths(tmp_path), generated_at_utc="2026-01-01T00:00:00+00:00")
    report = build_pit_security_master_markdown(inventory)

    assert "research-ready and walk-forward-ready" in report
    assert "h5 / 5d" in report
    assert "next_open" in report
    assert "exit_close_5d" in report
    assert "profitability" in report
    assert "option liquidity" in report
    assert "option P&L" in report
    assert "paper readiness" in report
    assert "production readiness" in report
    assert "live-trading readiness" in report


def test_script_writes_only_scoped_audit_artifacts_in_temp_repo(tmp_path: Path) -> None:
    result = write_pit_security_master_inventory(_paths(tmp_path))

    artifact_paths = {Path(path) for path in result["artifacts"].values()}
    assert artifact_paths == {
        tmp_path / "reports" / "audit" / "pit_security_master_inventory.json",
        tmp_path / "reports" / "audit" / "pit_security_master_inventory.md",
    }
    assert all(path.exists() for path in artifact_paths)
