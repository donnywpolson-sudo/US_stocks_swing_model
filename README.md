us_stocks_swing_model
Daily US equities OHLCV research pipeline scaffold.
Generated outputs under data/** and reports/** are ignored and should not be committed.
Data-foundation evidence inputs
For h5 / 5d data-foundation evidence intake, use docs/data_foundation_evidence_inputs.md to map templates to ignored accepted input paths and validator commands. The templates are non-evidence; accepted inputs must come from authoritative external sources. Schema validation does not imply production readiness, live-trading readiness, profitability, option liquidity, option P&L, or investment advice.
Implemented phase folders
Project/config scaffold
Raw manifest: scripts/phase1C_validate/build_raw_manifest.py
Raw validation: scripts/phase1C_validate/validate_raw_data.py
Daily normalization: scripts/phase2_causal_base/run_normalize_daily.py
Causal gating: scripts/phase2_causal_base/run_causal_gating.py
Research universe: scripts/phase2_causal_base/build_research_universe.py
h5 / 5-trading-day target generation: scripts/phase3_labels/generate_targets.py
Baseline feature matrix: scripts/phase4_features/build_baseline_features.py
Column registry: scripts/phase4_features/build_column_registry.py
WFA split plan: scripts/phase5_wfa/build_wfa_plan.py
Daily underlying signal review export: scripts/phase8_model_selection/build_daily_underlying_signals.py
Baseline WFA: scripts/phase7_wfa/run_baseline_wfa.py
Metrics: scripts/phase8_model_selection/build_metrics.py
Baseline gate: scripts/phase8_model_selection/baseline_gate.py
Expanded features: scripts/phase4_features/build_expanded_features.py
Feature discovery: scripts/phase8_model_selection/discover_features.py
Feature selection: scripts/phase8_model_selection/select_features.py
Frozen feature set: scripts/phase8_model_selection/freeze_feature_set.py
Phase folders follow the same direct `scripts/phase...` format used by the futures intraday project.
Raw input format
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
Run
pytest

python scripts/phase1C_validate/build_raw_manifest.py --limit 25
python scripts/phase1C_validate/validate_raw_data.py --limit 25
python scripts/phase2_causal_base/run_normalize_daily.py
python scripts/phase2_causal_base/run_causal_gating.py
python scripts/phase2_causal_base/build_research_universe.py
python scripts/phase3_labels/generate_targets.py
python scripts/phase4_features/build_baseline_features.py
python scripts/phase4_features/build_column_registry.py
python scripts/phase5_wfa/build_wfa_plan.py
python scripts/phase8_model_selection/build_daily_underlying_signals.py
python scripts/phase7_wfa/run_baseline_wfa.py
python scripts/phase8_model_selection/build_metrics.py
python scripts/phase8_model_selection/baseline_gate.py
python scripts/phase4_features/build_expanded_features.py
python scripts/phase8_model_selection/discover_features.py
python scripts/phase8_model_selection/select_features.py
python scripts/phase8_model_selection/freeze_feature_set.py
