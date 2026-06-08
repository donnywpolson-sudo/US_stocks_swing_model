# quant_project_daily

Daily US equities OHLCV research pipeline scaffold.

Implemented scope:

1. Project/config scaffold
2. Raw TXT manifest
3. Raw validation
4. Validated Parquet bars
5. Daily normalization
6. Normalized Parquet bars
7. Causal tradability gating
8. Causal Parquet bars

Not implemented: labels, features, WFA, models, backtests, metrics, or research gates.

Raw input format:

```text
<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>
```

Run:

```powershell
pytest
python scripts/stage02_build_raw_manifest.py --limit 25
python scripts/stage03_validate_raw_data.py --limit 25
python scripts/stage05_normalize_daily.py
python scripts/stage07_causal_gating.py
```
