# Raw Parquet Layout Policy

This repo treats the Stooq raw parquet layout as one flat parquet file per ticker directly under `data/raw_parquet`.

The durable source of truth for this policy is the exporter implementation in `scripts/phase1B_convert/raw_parquet_export.py` and the targeted coverage in `tests/test_raw_parquet_export.py`. The exporter writes ticker files such as `AAPL.parquet` directly under the configured raw parquet output directory.

The reports under `reports/validation`, including `raw_parquet_export_summary.json` and `raw_parquet_layout_reconciliation.json`, are ignored generated or local diagnostic artifacts. They are useful for local evidence, but they are not durable policy artifacts and should not override the tracked exporter code and tests.

`reports/validation/raw_parquet_export_summary.json` may remain stale until a separately approved report-only refresh. Do not infer the active raw parquet layout from that report when it disagrees with the tracked exporter policy.

This is research-ready and walk-forward-ready repository hygiene for the h5 / 5d research pipeline. It is not production-ready or live-trading-ready guidance, and it is not investment advice.
