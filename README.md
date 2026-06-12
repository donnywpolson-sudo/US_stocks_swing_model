# quant_project_daily

Daily US equities OHLCV research pipeline scaffold.

Implemented pipeline stages:

1. Project/config scaffold
2. Raw manifest (raw TXT inventory)
3. Raw validation (per-row reject/warn accounting)
4. Validated parquet (raw validated bars)
5. Daily normalization
6. Normalized parquet bars
7. Causal gating
8. Causal parquet bars
9. Daily normalization
10. Research universe
11. 20-day targets
12. Baseline features
13. WFA split plan
14. Baseline WFA (walk-forward analysis)
15. Metrics
16. Baseline gate

Generated `data/` and `reports/` directories are ignored in git.

Raw input format:

```text
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
```

Run:

```bash
pytest
python scripts/stage02_build_raw_manifest.py --limit 25
python scripts/stage03_validate_raw_data.py --limit 25
python scripts/stage05_normalize_daily.py
python scripts/stage07_causal_gating.py
python scripts/stage08_build_research_universe.py
python scripts/stage09_generate_targets.py
python scripts/stage11_build_baseline_features.py
python scripts/stage14_build_wfa_plan.py
python scripts/stage15_run_baseline_wfa.py
python scripts/stage18_build_metrics.py
python scripts/stage19_baseline_gate.py