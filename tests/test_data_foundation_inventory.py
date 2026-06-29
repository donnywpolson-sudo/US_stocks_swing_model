from __future__ import annotations

from pathlib import Path

from scripts.project_config import ProjectPaths
from scripts.validation.corporate_action_inventory import build_corporate_action_inventory
from scripts.validation.data_foundation_inventory import (
    ALLOWED_STATUSES,
    build_data_foundation_inventory,
    build_data_foundation_inventory_markdown,
    write_data_foundation_inventory,
)
from scripts.validation.pit_security_master_inventory import build_pit_security_master_inventory


def _paths(tmp_path: Path) -> ProjectPaths:
    return ProjectPaths(
        repo_root=tmp_path,
        raw_txt=tmp_path / "data" / "raw_txt",
        raw_manifest=tmp_path / "data" / "raw_manifest" / "raw_manifest.parquet",
        validated=tmp_path / "data" / "validated",
        normalized=tmp_path / "data" / "normalized",
        causal=tmp_path / "data" / "causal",
        research_ohlcv_daily=tmp_path / "data" / "research_ohlcv_daily",
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


def _stooq_config() -> dict:
    return {
        "limitations": {
            "metadata_missing": True,
            "metadata_notes": "No listing/delisting, name, or exchange metadata found in any archive.",
            "survivorship_bias_risk": True,
            "adjusted_uncertainty": True,
            "adjusted_notes": [
                "Stooq adjustment behavior unverified from official documentation",
                "Dividend adjustment status: UNCONFIRMED",
            ],
        }
    }


def _execution_costs() -> dict:
    return {
        "round_trip_cost_bps": 25,
        "decile_buckets": 10,
        "quintile_buckets": 5,
        "score_outlier_abs_threshold": 5.0,
    }


def _items_by_id(inventory: dict) -> dict[str, dict]:
    return {item["id"]: item for item in inventory["inventory_items"]}


def test_metadata_missing_sets_pit_security_items_to_missing_or_unverified(tmp_path: Path) -> None:
    inventory = build_data_foundation_inventory(
        _paths(tmp_path),
        generated_at_utc="2026-01-01T00:00:00+00:00",
        stooq_config=_stooq_config(),
        execution_costs=_execution_costs(),
    )
    items = _items_by_id(inventory)

    pit_ids = [
        "pit_security_type",
        "pit_listing_delisting_dates",
        "pit_permanent_id_ticker_history",
        "pit_exchange_otc_status",
        "pit_security_class_flags",
    ]
    assert {items[item_id]["status"] for item_id in pit_ids} <= {"missing", "unverified"}
    assert items["survivorship_delisting_coverage"]["status"] == "missing"
    assert all(item["status"] in ALLOWED_STATUSES for item in inventory["inventory_items"])


def test_flat_execution_config_proves_only_configured_bps(tmp_path: Path) -> None:
    inventory = build_data_foundation_inventory(
        _paths(tmp_path),
        generated_at_utc="2026-01-01T00:00:00+00:00",
        stooq_config=_stooq_config(),
        execution_costs=_execution_costs(),
    )
    items = _items_by_id(inventory)

    assert items["execution_configured_round_trip_bps"]["status"] == "proven"
    assert "round_trip_cost_bps=25" in items["execution_configured_round_trip_bps"]["evidence"]
    assert items["execution_realistic_fill_model"]["status"] == "unverified"
    assert items["execution_ranking_vs_executable_pnl"]["status"] == "accepted_limitation"


def test_split_like_gap_report_proves_detection_not_adjustment_policy(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.validation_reports.mkdir(parents=True)
    (paths.validation_reports / "raw_split_like_gaps.csv").write_text("ticker,date,gap_pct\nAAA,2020-01-02,100\n", encoding="utf-8")

    inventory = build_data_foundation_inventory(
        paths,
        generated_at_utc="2026-01-01T00:00:00+00:00",
        stooq_config=_stooq_config(),
        execution_costs=_execution_costs(),
    )
    items = _items_by_id(inventory)

    assert items["corporate_action_split_gap_detection"]["status"] == "proven"
    assert items["corporate_action_adjustment_policy"]["status"] == "unverified"
    assert "heuristic" in items["corporate_action_split_gap_detection"]["implication"]


def test_markdown_preserves_required_guardrails_and_timing(tmp_path: Path) -> None:
    inventory = build_data_foundation_inventory(
        _paths(tmp_path),
        generated_at_utc="2026-01-01T00:00:00+00:00",
        stooq_config=_stooq_config(),
        execution_costs=_execution_costs(),
    )
    report = build_data_foundation_inventory_markdown(inventory)

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


def test_data_foundation_evidence_input_guide_lists_paths_commands_and_caveats() -> None:
    guide_path = Path(__file__).resolve().parents[1] / "docs" / "data_foundation_evidence_inputs.md"
    guide = guide_path.read_text(encoding="utf-8")

    required_text = [
        "docs/examples/pit_security_master_template.csv",
        "docs/examples/corporate_actions_template.csv",
        "docs/examples/ohlcv_adjustment_policy_template.json",
        "docs/examples/alpha_vantage_listing_status_template.csv",
        "data/reference/pit_security_master.csv",
        "data/reference/corporate_actions.csv",
        "data/reference/ohlcv_adjustment_policy.json",
        "data/reference/alpha_vantage_listing_status.csv",
        "python scripts/validation/audit_pit_security_master_inventory.py",
        "python scripts/validation/audit_corporate_action_inventory.py",
        "python scripts/phase1A_download/download_alpha_vantage_listing_status.py",
        "Alpha Vantage LISTING_STATUS",
        "supplemental survivorship evidence only",
        "must not populate or clear `data/reference/pit_security_master.csv`",
        "h5 / 5d",
        "PIT means point-in-time",
        "as of the prediction date",
        "future-resolved",
        "templates are non-evidence",
        "CSV templates are header-only",
        "must not include example evidence rows",
        "production readiness",
        "live-trading readiness",
        "profitability",
        "option liquidity",
        "option P&L",
    ]

    for text in required_text:
        assert text in guide


def test_data_foundation_evidence_inputs_remain_ignored_data_paths() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    guide = (repo_root / "docs" / "data_foundation_evidence_inputs.md").read_text(encoding="utf-8")
    gitignore_rules = set((repo_root / ".gitignore").read_text(encoding="utf-8").splitlines())

    accepted_inputs = [
        "data/reference/pit_security_master.csv",
        "data/reference/corporate_actions.csv",
        "data/reference/ohlcv_adjustment_policy.json",
        "data/reference/alpha_vantage_listing_status.csv",
    ]

    for accepted_input in accepted_inputs:
        assert accepted_input in guide
        assert accepted_input.startswith("data/reference/")

    assert "data/**" in gitignore_rules
    assert "!docs/**" in gitignore_rules


def test_evidence_input_guide_matches_inventory_metadata(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    guide = (repo_root / "docs" / "data_foundation_evidence_inputs.md").read_text(encoding="utf-8")

    pit_inventory = build_pit_security_master_inventory(
        _paths(tmp_path),
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )
    corporate_inventory = build_corporate_action_inventory(
        _paths(tmp_path),
        generated_at_utc="2026-01-01T00:00:00+00:00",
    )

    advertised_inputs = [
        pit_inventory["accepted_input"],
        corporate_inventory["accepted_inputs"]["corporate_actions"],
        corporate_inventory["accepted_inputs"]["ohlcv_adjustment_policy"],
    ]

    assert advertised_inputs == [
        "data/reference/pit_security_master.csv",
        "data/reference/corporate_actions.csv",
        "data/reference/ohlcv_adjustment_policy.json",
    ]

    for advertised_input in advertised_inputs:
        assert advertised_input in guide
        assert advertised_input.startswith("data/reference/")


def test_readme_links_data_foundation_evidence_input_guide_with_caveats() -> None:
    readme_path = Path(__file__).resolve().parents[1] / "README.md"
    readme = readme_path.read_text(encoding="utf-8")

    required_text = [
        "docs/data_foundation_evidence_inputs.md",
        "h5 / 5d",
        "templates are non-evidence",
        "authoritative external sources",
        "production readiness",
        "live-trading readiness",
        "profitability",
        "option liquidity",
        "option P&L",
    ]

    for text in required_text:
        assert text in readme


def test_write_data_foundation_inventory_writes_only_scoped_audit_artifacts(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    (tmp_path / "configs" / "data_sources").mkdir(parents=True)
    (tmp_path / "configs").mkdir(exist_ok=True)
    (tmp_path / "configs" / "data_sources" / "stooq.yaml").write_text(
        """
limitations:
  metadata_missing: true
  metadata_notes: No listing/delisting, name, or exchange metadata found in any archive.
  survivorship_bias_risk: true
  adjusted_uncertainty: true
  adjusted_notes:
    - Stooq adjustment behavior unverified from official documentation
    - Dividend adjustment status: UNCONFIRMED
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "configs" / "execution_costs.yaml").write_text(
        "round_trip_cost_bps: 25\n",
        encoding="utf-8",
    )

    result = write_data_foundation_inventory(paths)

    artifact_paths = {Path(path) for path in result["artifacts"].values()}
    assert artifact_paths == {
        tmp_path / "reports" / "audit" / "data_foundation_inventory.json",
        tmp_path / "reports" / "audit" / "data_foundation_inventory.md",
    }
    assert all(path.exists() for path in artifact_paths)
    assert result["modeling_gate_decision"] == "do_not_run_new_model_work"
