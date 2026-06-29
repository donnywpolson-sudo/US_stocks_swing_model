# CODEX_HANDOFF

## Current status
- Generated UTC: 2026-06-29.
- Repository hygiene is current through origin/main.
- Recent pushed hygiene commits:
  - 6ef00c9 Align raw parquet exporter with flat layout
  - 1e8c49f Document flat raw parquet layout policy
  - 14f31f7 Restructure pipeline into phase script packages
  - eba896d Update repo agent operating instructions
  - 938a2df Remove stale VS Code settings backup
- reports/validation/raw_parquet_export_summary.json remains ignored/stale by design; do not refresh it unless explicitly scoped.

## Research checkpoint
- Active target horizon remains h5 / 5 trading days.
- Baseline_h5 WFA completed previously: 45/45 folds, 0 failed, 9,903,519 OOS rows.
- Current baseline_h5 gate remains FAIL.
- Gate failures remain long_short_net_return_failed_positive_threshold and top_decile_net_return_failed_positive_threshold.
- Configured execution-cost diagnostic remains round_trip_cost_bps: 25.
- Treat the 25 bps setting as a flat research-drag assumption, not realistic executable cost evidence.
- Daily signals and later-stage execution remain blocked unless separately approved after a new research decision.

## Guardrails
- Do not mutate data/raw_txt or data/raw_parquet.
- Do not stage generated data/** or reports/** artifacts.
- Do not refresh stale ignored reports unless explicitly scoped.
- Do not run WFA, model, target, feature, gate, exporter, or broader pipeline stages without explicit approval.
- Preserve h5 / 5d naming and label semantics.
- Do not claim production readiness, live-trading readiness, profitability, or investment advice.

## Latest handoff refresh
- Condensed CODEX_HANDOFF.md from accumulated historical run logs into this current-state checkpoint.
- No raw files, generated data, generated reports, configs, scripts, tests, or model artifacts should be changed by this handoff refresh.

## Next recommended step
- No executable pipeline step is currently approved.
- Next git hygiene decision: push the CODEX_HANDOFF.md refresh commit or leave it local for review.
- Future research work requires explicit approval to reopen feature/model research from the failed baseline_h5 gate checkpoint.
