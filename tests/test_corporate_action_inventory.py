from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from scripts.project_config import ProjectPaths
from scripts.validation.corporate_action_inventory import (
    OPTIONAL_EVENT_COLUMNS,
    POLICY_REQUIRED_FIELDS,
    REQUIRED_EVENT_COLUMNS,
    build_corporate_action_inventory,
    build_corporate_action_markdown,
    write_corporate_action_inventory,
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


def _write_events(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "data" / "reference" / "corporate_actions.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip(), encoding="utf-8")
    return path


def _write_policy(tmp_path: Path, payload: dict) -> Path:
    path = tmp_path / "data" / "reference" / "ohlcv_adjustment_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _valid_events_csv() -> str:
    return """
raw_ticker,ticker,event_date,action_type,source,source_asof_date,ex_date,record_date,pay_date,split_ratio,cash_amount,currency,distribution_type,adjustment_factor
AAPL.US,AAPL,2020-08-31,split,unit_fixture,2026-01-01,2020-08-31,,,4:1,,,,0.25
OLD.US,OLD,2018-03-01,cash_dividend,unit_fixture,2026-01-01,2018-02-27,2018-02-28,2018-03-15,,0.12,USD,regular,
"""


def _valid_policy() -> dict:
    return {
        "source": "unit_fixture",
        "source_asof_date": "2026-01-01",
        "ohlcv_source": "stooq",
        "price_adjustment_policy": "documented by fixture",
        "volume_adjustment_policy": "documented by fixture",
        "split_adjustment_status": "documented by fixture",
        "dividend_adjustment_status": "documented by fixture",
        "distribution_adjustment_status": "documented by fixture",
        "official_documentation_reference": "fixture-reference",
    }


def test_missing_inputs_keep_corporate_action_statuses_missing_or_limited(tmp_path: Path) -> None:
    result = write_corporate_action_inventory(_paths(tmp_path))

    assert result["corporate_action_events_status"] == "missing"
    assert result["ohlcv_adjustment_policy_status"] == "missing"
    assert result["corporate_action_adjustment_proof_status"] == "accepted_limitation"
    assert result["event_blockers"] == ["missing_input_file"]
    assert result["policy_blockers"] == ["missing_policy_file"]
    assert (tmp_path / "reports" / "audit" / "corporate_action_inventory.json").exists()
    assert (tmp_path / "reports" / "audit" / "corporate_action_inventory.md").exists()


def test_valid_events_and_policy_prove_event_and_policy_statuses(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_events(tmp_path, _valid_events_csv())
    _write_policy(tmp_path, _valid_policy())
    paths.raw_txt.mkdir(parents=True)
    (paths.raw_txt / "aapl.us.txt").write_text("x", encoding="utf-8")
    (paths.raw_txt / "old.us.txt").write_text("x", encoding="utf-8")
    paths.research_ohlcv_daily.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": ["AAPL", "OLD", "MSFT"]}).to_parquet(paths.research_ohlcv_daily, index=False)

    inventory = build_corporate_action_inventory(paths, generated_at_utc="2026-01-01T00:00:00+00:00")

    assert inventory["status_summary"]["corporate_action_events"] == "proven"
    assert inventory["status_summary"]["ohlcv_adjustment_policy"] == "proven"
    assert inventory["status_summary"]["corporate_action_adjustment_proof"] == "proven"
    assert inventory["validation"]["corporate_actions"]["row_count"] == 2
    assert inventory["validation"]["corporate_actions"]["source_count"] == 1
    assert inventory["coverage_summary"]["event_raw_tickers_in_raw_count"] == 2
    assert inventory["coverage_summary"]["event_tickers_in_research_count"] == 2
    assert inventory["coverage_summary"]["research_symbols_missing_from_events_count"] == 1


def test_invalid_events_report_schema_date_numeric_provenance_and_action_blockers(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    _write_events(
        tmp_path,
        """
raw_ticker,event_date,action_type,source,source_asof_date,split_ratio,adjustment_factor
BAD.US,bad-date,mystery,,2026-99-99,0,-1
""",
    )
    _write_policy(tmp_path, {"source": "fixture", "source_asof_date": "bad-date"})

    inventory = build_corporate_action_inventory(paths, generated_at_utc="2026-01-01T00:00:00+00:00")
    event_blockers = set(inventory["validation"]["corporate_actions"]["blockers"])
    policy_blockers = set(inventory["validation"]["ohlcv_adjustment_policy"]["blockers"])

    assert inventory["status_summary"]["corporate_action_events"] == "unverified"
    assert "missing_required_columns" in event_blockers
    assert "empty_required_values" in event_blockers
    assert "invalid_date_values" in event_blockers
    assert "invalid_numeric_values" in event_blockers
    assert "unsupported_action_types" in event_blockers
    assert inventory["validation"]["corporate_actions"]["missing_columns"] == ["ticker"]
    assert inventory["validation"]["corporate_actions"]["numeric_invalid_counts"]["split_ratio"] == 1
    assert inventory["validation"]["corporate_actions"]["numeric_invalid_counts"]["adjustment_factor"] == 1
    assert "missing_policy_fields" in policy_blockers
    assert "invalid_policy_date_values" in policy_blockers


def test_policy_template_documents_schema_but_is_not_evidence(tmp_path: Path) -> None:
    template_path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "ohlcv_adjustment_policy_template.json"
    template = json.loads(template_path.read_text(encoding="utf-8"))

    assert list(template) == list(POLICY_REQUIRED_FIELDS)
    assert all(value == "" for value in template.values())

    _write_policy(tmp_path, template)
    inventory = build_corporate_action_inventory(_paths(tmp_path), generated_at_utc="2026-01-01T00:00:00+00:00")
    policy_validation = inventory["validation"]["ohlcv_adjustment_policy"]

    assert inventory["status_summary"]["ohlcv_adjustment_policy"] == "unverified"
    assert "empty_policy_fields" in policy_validation["blockers"]
    assert policy_validation["empty_fields"] == list(POLICY_REQUIRED_FIELDS)


def test_corporate_actions_template_header_matches_validator_columns() -> None:
    template_path = Path(__file__).resolve().parents[1] / "docs" / "examples" / "corporate_actions_template.csv"

    with template_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows == [list(REQUIRED_EVENT_COLUMNS + OPTIONAL_EVENT_COLUMNS)]
    header = rows[0]
    assert header == list(REQUIRED_EVENT_COLUMNS + OPTIONAL_EVENT_COLUMNS)


def test_split_like_and_h5_invalidation_remain_mechanics_only(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.validation_reports.mkdir(parents=True)
    paths.label_reports.mkdir(parents=True)
    (paths.validation_reports / "raw_split_like_gaps.csv").write_text("ticker,date\nAAA,2020-01-02\n", encoding="utf-8")
    (paths.validation_reports / "raw_validation_summary.json").write_text(
        json.dumps({"warning_reasons": {"split_like_gap": 3}}),
        encoding="utf-8",
    )
    (paths.label_reports / "target_h5_summary.json").write_text(
        json.dumps(
            {
                "invalid_reason_counts": {"split_like_gap_in_target_window_5d": 5},
                "mutually_exclusive_invalid_reason_counts": {"split_like_gap_in_target_window_5d": 2},
            }
        ),
        encoding="utf-8",
    )

    inventory = build_corporate_action_inventory(paths, generated_at_utc="2026-01-01T00:00:00+00:00")
    items = {item["id"]: item for item in inventory["inventory_items"]}

    assert inventory["status_summary"]["split_like_gap_detection"] == "proven"
    assert inventory["status_summary"]["h5_target_window_invalidation"] == "proven"
    assert "mechanics only" in items["h5_target_window_invalidation_mechanics"]["implication"]
    assert items["corporate_action_adjustment_proof_sufficiency"]["status"] == "accepted_limitation"


def test_markdown_preserves_h5_timing_and_safety_guardrails(tmp_path: Path) -> None:
    inventory = build_corporate_action_inventory(_paths(tmp_path), generated_at_utc="2026-01-01T00:00:00+00:00")
    report = build_corporate_action_markdown(inventory)

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


def test_write_corporate_action_inventory_writes_only_scoped_audit_artifacts(tmp_path: Path) -> None:
    result = write_corporate_action_inventory(_paths(tmp_path))

    artifact_paths = {Path(path) for path in result["artifacts"].values()}
    assert artifact_paths == {
        tmp_path / "reports" / "audit" / "corporate_action_inventory.json",
        tmp_path / "reports" / "audit" / "corporate_action_inventory.md",
    }
    assert all(path.exists() for path in artifact_paths)
    assert result["modeling_gate_decision"] == "do_not_run_new_model_work"
