from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scripts.project_config import ProjectPaths, project_paths


ALLOWED_STATUSES = {"proven", "missing", "unverified", "accepted_limitation", "not_applicable"}
MODELING_GATE_DECISION = "do_not_run_new_model_work"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _item(item_id: str, category: str, label: str, status: str, evidence: str, implication: str, evidence_paths: list[str]) -> dict[str, Any]:
    return {"id": item_id, "category": category, "label": label, "status": status, "evidence": evidence, "implication": implication, "evidence_paths": evidence_paths}


def build_data_foundation_inventory(
    paths: ProjectPaths | None = None,
    *,
    generated_at_utc: str | None = None,
    stooq_config: dict[str, Any] | None = None,
    execution_costs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = paths or project_paths()
    root = p.repo_root
    stooq_cfg = stooq_config if stooq_config is not None else _read_yaml(root / "configs" / "data_sources" / "stooq.yaml")
    execution_cfg = execution_costs if execution_costs is not None else _read_yaml(root / "configs" / "execution_costs.yaml")
    limitations = stooq_cfg.get("limitations", {})
    metadata_missing = bool(limitations.get("metadata_missing"))
    metadata_note = limitations.get("metadata_notes", "No repo-local PIT security master evidence found.")
    pit_status = "missing" if metadata_missing else "unverified"
    items = [
        _item("pit_security_type", "PIT security metadata", "Security type", pit_status, metadata_note, "Common-stock-only and security-class filters are not proven.", ["configs/data_sources/stooq.yaml"]),
        _item("pit_listing_delisting_dates", "PIT security metadata", "Listing and delisting dates", pit_status, metadata_note, "Point-in-time listing eligibility and delisted-name coverage are not proven.", ["configs/data_sources/stooq.yaml"]),
        _item("pit_permanent_id_ticker_history", "PIT security metadata", "Ticker history or permanent ID", pit_status, metadata_note, "Ticker changes and identity continuity remain unresolved.", ["configs/data_sources/stooq.yaml"]),
        _item("pit_exchange_otc_status", "PIT security metadata", "Exchange and OTC status", pit_status, metadata_note, "Exchange filters and OTC exclusion are not proven.", ["configs/data_sources/stooq.yaml"]),
        _item("pit_security_class_flags", "PIT security metadata", "ADR, ETF, ETN, and common-stock flags", pit_status, metadata_note, "Security-class-specific claims must remain limitations.", ["configs/data_sources/stooq.yaml"]),
        _item("survivorship_delisting_coverage", "Survivorship/delisting coverage", "Delisted-name representation", "missing" if limitations.get("survivorship_bias_risk") or metadata_missing else "unverified", "Stooq source config records missing listing/delisting metadata and survivorship bias risk.", "Universe coverage cannot be treated as fully point-in-time or survivorship-clean.", ["configs/data_sources/stooq.yaml"]),
        _item("corporate_action_adjustment_policy", "Corporate-action proof", "Adjusted/unadjusted OHLCV status", "unverified", "Adjustment policy is not independently documented in repo-local evidence.", "Split, dividend, and distribution treatment is not proven for performance interpretation.", ["configs/data_sources/stooq.yaml"]),
        _item("corporate_action_split_gap_detection", "Corporate-action proof", "Split-like gap detection", "proven" if (p.validation_reports / "raw_split_like_gaps.csv").exists() else "missing", "Raw validation emits split-like gap inventory for h5 target-window invalidation.", "This is heuristic split-like gap evidence, not independent corporate-action adjustment proof.", ["reports/validation/raw_split_like_gaps.csv"]),
        _item("corporate_action_dividend_distribution_policy", "Corporate-action proof", "Dividend and distribution treatment", "unverified", "Dividend/distribution adjustment status is unverified.", "Dividend/distribution effects remain limitations for return interpretation.", ["configs/data_sources/stooq.yaml"]),
        _item("execution_configured_round_trip_bps", "Execution-cost assumptions", "Configured flat round-trip bps", "proven" if "round_trip_cost_bps" in execution_cfg else "missing", f"Configured round_trip_cost_bps={execution_cfg.get('round_trip_cost_bps')}.", "This proves only the configured flat diagnostic cost, not executable fills.", ["configs/execution_costs.yaml"]),
        _item("execution_realistic_fill_model", "Execution-cost assumptions", "Spread, slippage, commission, borrow, financing, capacity, and fill model", "unverified", "Repo-local execution config contains flat bps inputs only.", "Net returns remain flat-drag ranking diagnostics unless separate execution evidence is added.", ["configs/execution_costs.yaml"]),
        _item("execution_ranking_vs_executable_pnl", "Execution-cost assumptions", "Ranking diagnostics separated from executable PnL", "accepted_limitation", "Current artifacts are research-ready and walk-forward-ready ranking diagnostics only.", "Do not treat metrics as profitability, paper-readiness, production-readiness, or live-trading evidence.", ["configs/execution_costs.yaml"]),
    ]
    return {
        "generated_at_utc": generated_at_utc or _utc_now(),
        "modeling_gate_decision": MODELING_GATE_DECISION,
        "active_h5_timing": {"horizon": "h5 / 5 trading days", "prediction_as_of": "after the completed daily bar", "entry": "next_open", "exit": "exit_close_5d"},
        "inventory_items": items,
        "accepted_limitations": [item["id"] for item in items if item["status"] in {"missing", "unverified", "accepted_limitation"}],
        "stop_conditions": ["Do not run WFA, retrain, change labels, change gates, build feature variants, or regenerate official pipeline artifacts from this evidence pass.", "Do not claim profitability, investment advice, option liquidity, option P&L, paper readiness, production readiness, or live-trading readiness."],
        "future_acceptance_gates": ["Resolve PIT security metadata or explicitly accept it as a limitation before future model work.", "Resolve survivorship/delisting coverage or explicitly accept it as a limitation before future model work."],
    }


def build_data_foundation_inventory_markdown(inventory: dict[str, Any]) -> str:
    lines = [
        "# Data-Foundation Inventory",
        "",
        "This is a research-ready and walk-forward-ready evidence inventory for the active h5 / 5d daily OHLCV pipeline. It is not investment advice and does not imply profitability, option liquidity, option P&L, paper readiness, production readiness, or live-trading readiness.",
        "",
        "- Preserve active h5 / 5d timing: prediction after the completed daily bar, entry at `next_open`, and exit at `exit_close_5d`.",
        "",
    ]
    for item in inventory["inventory_items"]:
        lines.append(f"- `{item['id']}`: `{item['status']}` - {item['implication']}")
    return "\n".join(lines) + "\n"


def write_data_foundation_inventory(paths: ProjectPaths | None = None) -> dict[str, Any]:
    p = paths or project_paths()
    inventory = build_data_foundation_inventory(p)
    audit_dir = p.repo_root / "reports" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / "data_foundation_inventory.json"
    md_path = audit_dir / "data_foundation_inventory.md"
    json_path.write_text(json.dumps(inventory, indent=2, default=str), encoding="utf-8")
    md_path.write_text(build_data_foundation_inventory_markdown(inventory), encoding="utf-8")
    return {"artifacts": {"json": str(json_path), "markdown": str(md_path)}, "modeling_gate_decision": MODELING_GATE_DECISION, "inventory_item_count": len(inventory["inventory_items"])}
