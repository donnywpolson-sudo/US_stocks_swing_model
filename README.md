quant_project_daily
Daily US equities OHLCV research pipeline scaffold.
Generated outputs under data/** and reports/** are ignored and should not be committed.
Implemented pipeline stages
Project/config scaffold
Raw manifest: scripts/stage02_build_raw_manifest.py
Raw validation: scripts/stage03_validate_raw_data.py
Daily normalization: scripts/stage05_normalize_daily.py
Causal gating: scripts/stage07_causal_gating.py
Research universe: scripts/stage08_build_research_universe.py
h5 / 5-trading-day target generation: scripts/stage09_generate_targets.py
Baseline feature matrix: scripts/stage11_build_baseline_features.py
Column registry: scripts/stage13_build_column_registry.py
WFA split plan: scripts/stage14_build_wfa_plan.py
Daily underlying signal review export: scripts/stage16_build_daily_underlying_signals.py
Baseline WFA: scripts/stage15_run_baseline_wfa.py
Metrics: scripts/stage18_build_metrics.py
Baseline gate: scripts/stage19_baseline_gate.py
Expanded features: scripts/stage20_build_expanded_features.py
Feature discovery: scripts/stage21_discover_features.py
Feature selection: scripts/stage22_select_features.py
Frozen feature set: scripts/stage23_freeze_feature_set.py
Stage numbers are intentionally non-contiguous because they follow the existing script filenames.
Raw input format
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
Run
pytest

python scripts/stage02_build_raw_manifest.py --limit 25
python scripts/stage03_validate_raw_data.py --limit 25
python scripts/stage05_normalize_daily.py
python scripts/stage07_causal_gating.py
python scripts/stage08_build_research_universe.py
python scripts/stage09_generate_targets.py
python scripts/stage11_build_baseline_features.py
python scripts/stage13_build_column_registry.py
python scripts/stage14_build_wfa_plan.py
python scripts/stage16_build_daily_underlying_signals.py
python scripts/stage15_run_baseline_wfa.py
python scripts/stage18_build_metrics.py
python scripts/stage19_baseline_gate.py
python scripts/stage20_build_expanded_features.py
python scripts/stage21_discover_features.py
python scripts/stage22_select_features.py
python scripts/stage23_freeze_feature_set.py
