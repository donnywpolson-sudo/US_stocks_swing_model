# CODEX_HANDOFF

## What changed
- Refactored the active target/model pipeline from `h20`/20-trading-day forward labels to `h5`/5-trading-day forward labels.
- Updated active target, baseline, expanded feature, WFA, metrics, gates, feature discovery, feature selection, and tests to use `h5` paths and `5d` target/model/prediction columns.
- Added repo root to pytest `pythonpath` so existing tests importing `scripts.*` collect under `pytest`.

## Files changed
- `configs/project.yaml`
- `configs/wfa.yaml`
- `configs/baseline_features.yaml`
- `configs/baseline_model.yaml`
- `configs/gates.yaml`
- `configs/expanded_features.yaml`
- `configs/feature_selection.yaml`
- `pyproject.toml`
- `src/quant_project_daily/config.py`
- `src/quant_project_daily/targets.py`
- `src/quant_project_daily/features_baseline.py`
- `src/quant_project_daily/features_expanded.py`
- `src/quant_project_daily/column_registry.py`
- `src/quant_project_daily/wfa_splits.py`
- `src/quant_project_daily/baseline_wfa.py`
- `src/quant_project_daily/execution.py`
- `src/quant_project_daily/metrics.py`
- `src/quant_project_daily/gates.py`
- `src/quant_project_daily/feature_discovery.py`
- `src/quant_project_daily/feature_selection.py`
- `tests/test_*.py`

## Commands run
- `pytest`
- `python scripts/stage09_generate_targets.py`
- `python scripts/stage11_build_baseline_features.py`
- `python scripts/stage13_build_column_registry.py`
- `python scripts/stage14_build_wfa_plan.py`

## Test results
- `pytest`: 92 passed.
- Stage 09: wrote `data/labeled/target_h5/targets.parquet` and `reports/labels/target_h5_*`.
- Stage 11: wrote `data/feature_matrices/baseline_h5/baseline_h5.parquet`, registry JSONs, and `reports/features/baseline_h5_summary.json`.
- Stage 13: registry counts were 55 features, 5 targets, 11 metadata, 4 excluded.
- Stage 14: wrote `reports/wfa/baseline_h5_split_plan.csv`; summary reported 45 folds and `purge_days: 5`.
- Targeted stale-name checks found no `h20` or forward-target `20d` names in active configs/source/tests/scripts, new `h5` reports, or new `h5` parquet schemas.

## Remaining work
- Optional next pipeline stage: run `python scripts/stage15_run_baseline_wfa.py` against the new `baseline_h5` plan.

## Next recommended step
- Run Stage 15 baseline WFA only if the user approves the heavier model run.

---

## Current run: Stage 02-14 h5 rebuild and verification

## What changed
- Rebuilt generated artifacts from Stage 02 through Stage 14 only.
- Ran conditional validation and split-gap diagnostics because both diagnostic scripts were present.
- Added `reports/validation/h5_research_ready_lineage_report.md` with current counts, lineage, active filters, stale-reference status, and OHLCV-only limitations.
- Did not modify source code, configs, tests, raw files, or Stage 15+ model artifacts.

## Files changed
- Generated data under `data/raw_manifest`, `data/validated`, `data/normalized`, `data/causal`, `data/research_ohlcv_daily`, `data/labeled/target_h5`, and `data/feature_matrices/baseline_h5`.
- Generated reports under `reports/validation`, `reports/labels`, `reports/features`, and `reports/wfa`.
- `reports/validation/h5_research_ready_lineage_report.md`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/stage02_build_raw_manifest.py`
- `python scripts/stage03_validate_raw_data.py`
- `python scripts/stage05_normalize_daily.py`
- `python scripts/stage07_causal_gating.py`
- `python scripts/stage08_build_research_universe.py`
- `python scripts/stage09_generate_targets.py`
- `python scripts/stage11_build_baseline_features.py`
- `python scripts/stage13_build_column_registry.py`
- `python scripts/stage14_build_wfa_plan.py`
- `python scripts/audit_validation_diagnostics.py`
- `python scripts/audit_gap_impact.py`
- `pytest tests/test_raw_parser.py tests/test_raw_validation.py tests/test_validation_diagnostics.py tests/test_gap_impact_diagnostics.py tests/test_research_universe.py tests/test_targets.py tests/test_features_baseline.py tests/test_column_registry.py tests/test_wfa_splits.py`

## Test results
- Targeted pytest: 22 passed.
- Raw preflight: 12,210 raw txt files; 43 zero-byte files; `data/raw` absent; 174-symbol shortfall versus the 12,384-symbol Stooq YAML reference.
- Stage 02: 12,210 files scanned; 12,167 parse-ok; 43 parse errors; 27,503,809 raw rows counted.
- Stage 03: 27,503,703 valid rows; 106 rejected rows; 20,212 zero-volume warning rows; 4,787 split-like gap warning rows.
- Stage 07: 14,892,916 tradable rows.
- Stage 08: 23,774,790 rows kept; 12,553,171 model-eligible rows; 7,677 model-eligible tickers.
- Stage 09: 12,524,133 h5 label-valid rows.
- Stage 11/13: 12,524,133 baseline_h5 rows; 55 features; 5 targets; 11 metadata; 4 excluded.
- Stage 14: 45 WFA folds; `purge_days: 5`; no blockers or warnings.
- Artifact consistency check: no mismatches between current summaries and current parquet/CSV artifacts.
- Stale-reference check: one stale README phrase remains (`20-day target generation`); active h5 schemas did not contain stale h20 target/model columns.

## Remaining work
- Optional docs cleanup: update the README stale `20-day target generation` wording to h5.
- Optional future universe change: implement `min_traded_days_pct_252d` only if explicitly requested, then rerun Stage 07-14.
- Stage 15+ remains out of scope for this run.

## Next recommended step
- Review `reports/validation/h5_research_ready_lineage_report.md`; do not proceed past Stage 14 unless explicitly requested.

---

## Current run: Stage 15 baseline_h5 WFA

## What changed
- Ran active Stage 15 baseline WFA for `baseline_h5`.
- Generated OOS prediction parquet files under `data/oos_predictions/baseline_h5`.
- Generated `reports/wfa/baseline_h5_fold_summary.csv` and `reports/wfa/baseline_h5_oos_summary.json`.
- Did not run metrics, gates, expanded features, feature discovery, feature selection, frozen feature stages, or Stage 18+.
- Did not change source code, configs, tests, raw data, or old h20 generated artifacts.

## Files changed
- `data/oos_predictions/baseline_h5/fold_001.parquet` through `fold_045.parquet`
- `reports/wfa/baseline_h5_fold_summary.csv`
- `reports/wfa/baseline_h5_oos_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/stage15_run_baseline_wfa.py`

## Test results
- Stage 15 completed successfully.
- Folds requested: 45.
- Folds completed: 45.
- Folds failed: 0.
- Total OOS prediction rows: 9,903,519.
- Prediction date range: 2015-01-13 through 2026-04-22.
- OOS output files: 45 parquet files under `data/oos_predictions/baseline_h5`.
- Prediction schema: `fold_id`, `date`, `ticker`, `raw_ticker`, `target_class_5d`, `fwd_ret_5d`, `pred_score_5d`, `pred_rank_pct_by_date`, `pred_long_rank_5d`, `pred_short_rank_5d`.
- Row total from OOS parquet files matched `reports/wfa/baseline_h5_oos_summary.json`.
- Targeted stale-name search over active Stage 15 configs/scripts and `baseline_h5` WFA reports found no `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20`.
- No pytest was run because no code or config was changed.

## Remaining work
- Optional next stage: metrics/gates remain out of scope and should only run if explicitly requested.

## Next recommended step
- Review `reports/wfa/baseline_h5_oos_summary.json` and OOS parquet outputs; do not run Stage 18+ unless explicitly requested.

---

## Current run: Stage 18 baseline_h5 metrics

## What changed
- Ran active Stage 18 metrics from the completed `baseline_h5` OOS predictions.
- Generated active h5 metrics reports under `reports/metrics`.
- Did not rerun Stage 02-15.
- Did not run Stage 19 gates, expanded features, feature discovery, feature selection, frozen feature stages, or new model training.
- Did not change source code, configs, tests, raw data, columns, paths, or old h20 generated artifacts.

## Files changed
- `reports/metrics/baseline_h5_decile_returns.csv`
- `reports/metrics/baseline_h5_quintile_returns.csv`
- `reports/metrics/baseline_h5_daily_long_short.csv`
- `reports/metrics/baseline_h5_fold_metrics.csv`
- `reports/metrics/baseline_h5_score_diagnostics.csv`
- `reports/metrics/baseline_h5_metrics_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/stage18_build_metrics.py`

## Test results
- Stage 18 completed successfully.
- No pytest was run because no code or config was changed.
- Metrics summary: 9,903,519 OOS rows, 2015-01-13 through 2026-04-22, 45 folds.
- Mean daily rank IC: 0.024544545012611444.
- Rank IC t-stat: 8.917909948635398.
- Top decile gross/net return: 0.0018753549909624036 / -0.0006246450090375968.
- Bottom decile gross/net short return: 0.0013651729938471508 / -0.0011348270061528496.
- Long-short gross/net return: 0.001620263992404777 / -0.0008797360075952234.
- Long/short basket hit rate: 0.5344973747920488 / 0.5188032999407569.
- Round-trip cost bps: 25.0.
- Warnings: none.
- Blockers: none.
- Generated h5 metrics row counts: 28,350 decile rows, 14,175 quintile rows, 2,835 daily long-short rows, 45 fold metric rows, 45 score diagnostic rows.
- Targeted stale-name search over active Stage 18 configs/scripts and `baseline_h5` metrics outputs found no `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20`.
- `reports/gates` was not updated by this run; only historical `baseline_h20_gate.json` is present there.

## Remaining work
- Optional next stage: Stage 19 gates remain out of scope and should only run if explicitly requested.

## Next recommended step
- Review `reports/metrics/baseline_h5_metrics_summary.json`; do not run Stage 19 gates unless explicitly requested.

---

## Current run: Stage 19 baseline_h5 research gate

## What changed
- Ran active Stage 19 research gate from `reports/metrics/baseline_h5_metrics_summary.json`.
- Generated active h5 gate output at `reports/gates/baseline_h5_gate.json`.
- Did not rerun Stage 02-18.
- Did not run expanded features, feature discovery, feature selection, frozen feature stages, or new model training.
- Did not change source code, configs, tests, raw data, columns, paths, or old h20 generated artifacts.

## Files changed
- `reports/gates/baseline_h5_gate.json`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/stage19_baseline_gate.py`

## Test results
- Stage 19 completed successfully.
- No pytest was run because no code or config was changed.
- Gate name: `baseline_h5_research_gate`.
- Gate status: `FAIL`.
- Passed: `false`.
- Failures: `long_short_net_return_failed_positive_threshold`, `top_decile_net_return_failed_positive_threshold`.
- Warnings: `mean_daily_rank_ic_below_0_05`, `short_leg_net_return_non_positive`.
- Metrics used: total OOS rows `9,903,519`; fold count `45`; mean daily rank IC `0.024544545012611444`; rank IC t-stat `8.917909948635398`; long-short net return `-0.0008797360075952234`; top decile net return `-0.0006246450090375968`; bottom decile net short return `-0.0011348270061528496`; score min/max `-3.971729151160467` / `4.293357211464696`.
- Recommendation: `stop_and_inspect_pipeline_model_data`.
- Next stage: `null`.
- Targeted stale-name search over active Stage 19 configs/scripts and `reports/gates/baseline_h5_gate.json` found no `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20`.
- Historical `reports/gates/baseline_h20_gate.json` remains present and was not modified.

## Remaining work
- Gate failed on net-return thresholds; inspect pipeline/model/data before any feature expansion or next-stage research.

## Next recommended step
- Review `reports/gates/baseline_h5_gate.json` and inspect the failed net-return thresholds before proceeding.

---

## Current run: baseline_h5 cost sensitivity diagnostics

## What changed
- Generated cost-sensitivity and long-only diagnostics from existing Stage 15/18 `baseline_h5` outputs.
- Reused existing OOS predictions and metrics reports; did not rerun Stage 02-19.
- Did not change configs, labels, features, model code, metrics thresholds, gates, prediction artifacts, raw data, or training outputs.
- Did not run expanded features, feature discovery, feature selection, frozen feature stages, or new model training.

## Files changed
- `reports/metrics/baseline_h5_cost_sensitivity.csv`
- `reports/metrics/baseline_h5_cost_sensitivity_by_fold.csv`
- `reports/metrics/baseline_h5_cost_sensitivity_by_year.csv`
- `reports/metrics/baseline_h5_cost_sensitivity_diagnostic.md`
- `CODEX_HANDOFF.md`

## Commands run
- Inline Python diagnostic generation from existing `reports/metrics/baseline_h5_*` files and `reports/wfa/baseline_h5_oos_summary.json`.

## Test results
- No pytest was run because no source, config, or test code was changed.
- Aggregate cost sensitivity rows: 9.
- Fold cost sensitivity rows: 405.
- Year cost sensitivity rows: 108.
- Break-even round-trip cost: top decile long-only `18.753549909623963` bps; bottom decile short-only `13.651729938471506` bps; long-short basket `16.20263992404772` bps.
- At 25 bps: top long net `-0.0006246450090376036`; short net `-0.0011348270061528494`; long-short net `-0.0008797360075952282`.
- At 10 bps: top long net `0.0008753549909623964`; short net `0.0003651729938471506`; long-short net `0.0006202639924047719`.
- Decile diagnostics: top predicted decile outperformed bottom predicted decile gross before costs; strict monotonicity `false`; non-decreasing monotonicity `false`; adjacent decile inversions `2`; decile Spearman `0.41818181818181815`.
- Fold-level long-short positive counts: 33/45 at 0 bps, 31/45 at 5 bps, 25/45 at 10 bps, 20/45 at 25 bps.
- Year-level long-short positive counts: 11/12 at 0 bps, 9/12 at 5 bps, 8/12 at 10 bps, 4/12 at 25 bps.
- Short leg is weaker than the long leg.
- Diagnostic interpretation: the 25 bps gate failure is mainly a cost-assumption issue in the mechanical sense, but also a signal-strength issue if the strategy truly must clear 25 bps execution drag.
- Targeted stale-name search over active diagnostics, h5 metrics outputs, and relevant Stage 18 metrics code/config paths found no stale target/model names.

## Remaining work
- Inspect execution-drag assumptions, turnover, tradability, and long-only stability before changing the model or loosening gates.

## Next recommended step
- Review `reports/metrics/baseline_h5_cost_sensitivity_diagnostic.md`; do not loosen the gate or tune the model before resolving the execution-drag and short-leg questions.

---

## Current run: baseline_h5 underlying signal options overlay readiness

## What changed
- Created an options-intent interpretation report for `baseline_h5` as an underlying 5-trading-day directional ranking signal.
- Created a latest historical OOS candidate diagnostic CSV from existing Stage 15 OOS predictions and existing feature/causal metadata.
- Did not rerun Stage 02-19.
- Did not change labels, features, model code, training outputs, gates, metrics thresholds, configs, source code, tests, or raw data.
- Did not run expanded features, feature discovery, feature selection, frozen feature stages, new model training, or an options backtest.

## Files changed
- `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md`
- `reports/signals/baseline_h5_latest_underlying_candidates.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inline Python report/export generation from existing `data/oos_predictions/baseline_h5`, `data/feature_matrices/baseline_h5/baseline_h5.parquet`, `data/causal/stooq_daily_causal.parquet`, and existing Stage 18/19 reports.
- Targeted stale-name search across the new report/export and active h5 configs/scripts/source paths.

## Test results
- No pytest was run because no source, config, or test code was changed.
- Report exists: `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md`.
- Candidate export exists: `reports/signals/baseline_h5_latest_underlying_candidates.csv`.
- Latest historical OOS date: `2026-04-22`.
- Candidate rows: `1,027`.
- Candidate counts: bullish `513`, bearish `514`.
- Proxy pass counts: bullish 25m `206`, bullish 50m `155`, bearish 25m `217`, bearish 50m `148`.
- Exact 60-day liquidity proxy fields were not available in existing artifacts; the export uses closest existing fields `median_dollar_volume_20`, `zero_volume_count_20`, and `history_bars`.
- Targeted stale-name search over active checked paths found no `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20` matches.

## Remaining work
- Add contract-level option-chain data before evaluating option liquidity, option execution, or option P&L.
- Add exact 60-day underlying liquidity proxy fields in a future signal-export stage if required.

## Next recommended step
- Review `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md` and `reports/signals/baseline_h5_latest_underlying_candidates.csv`; do not claim option profitability or option liquidity until contract-level options data is added.

---

## Current run: Stage 07-14 exact 60d underlying proxy refresh

## What changed
- Added exact Stooq-only 60-row underlying proxy fields in causal gating: `median_dollar_volume_60` and `zero_volume_count_60`.
- Preserved existing 20d tradability behavior using `median_dollar_volume_20`, `zero_volume_count_20`, `min_history_bars`, and `price_min`.
- Refreshed dependency artifacts only through Stage 14.
- Updated the options-overlay readiness report wording to state that refreshed Stage 07-14 causal/research artifacts now contain exact 60d proxy fields, while the existing historical OOS candidate CSV still uses prior 20d proxy fields.
- Did not modify raw data.
- Did not run Stage 15, Stage 18, Stage 19, expanded features, feature discovery, feature selection, frozen feature stages, daily scoring/export, final Ridge training, model artifact saving, or options backtests.

## Files changed
- `src/quant_project_daily/causal_gating.py`
- `tests/test_no_lookahead.py`
- `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md`
- Generated Stage 07-14 artifacts under `data/**` and `reports/**`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_no_lookahead.py`
- `python scripts/stage07_causal_gating.py`
- `python scripts/stage08_build_research_universe.py`
- `python scripts/stage09_generate_targets.py`
- `python scripts/stage11_build_baseline_features.py`
- `python scripts/stage13_build_column_registry.py`
- `python scripts/stage14_build_wfa_plan.py`
- Targeted artifact verification for causal/research 60d proxy columns and Stage 07-14 row counts.
- Targeted stale-name searches across active configs/scripts/src/tests/README and Stage 07-14 reports.

## Test results
- `pytest tests/test_no_lookahead.py`: 4 passed.
- Stage 07: rows `27,503,703`; tradable rows `14,892,916`; new underlying proxy fields reported as `median_dollar_volume_60`, `zero_volume_count_60`, `history_bars`.
- Stage 08: rows kept `23,774,790`; model-eligible rows `12,553,171`; tickers kept `12,167`; model-eligible tickers `7,677`.
- Stage 09: total rows `23,774,790`; h5 label-valid rows `12,524,133`; class counts `-1: 2,503,184`, `0: 7,517,765`, `1: 2,503,184`.
- Stage 11: baseline_h5 rows `12,524,133`; features `55`; targets `5`; metadata `11`; output dates `2010-01-04` through `2026-05-21`.
- Stage 13: features `55`; targets `5`; metadata `11`; excluded `4`.
- Stage 14: WFA folds `45`; purge days `5`; total test rows `9,903,519`; blockers `[]`; warnings `[]`.
- Causal artifact verification: `median_dollar_volume_60`, `zero_volume_count_60`, and `history_bars` present; non-null 60d proxy rows `26,808,451`.
- Research artifact verification: `median_dollar_volume_60`, `zero_volume_count_60`, and `history_bars` present.
- Stage 08-14 core counts matched the prior handoff values; adding 60d proxy fields did not change universe eligibility.
- Targeted stale-name search found no active `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20` references in active checked paths. Broad `20d` matches were legitimate rolling feature/proxy names.

## Remaining work
- Future Run C remains separate: design and implement daily underlying-signal scoring/export only after this 60d proxy schema refresh is accepted.
- Regenerate historical candidate diagnostics in a future reporting run if exact 60d proxy columns are required in `reports/signals/baseline_h5_latest_underlying_candidates.csv`.
- Contract-level option-chain data is still required before validating options liquidity, execution, IV, Greeks, DTE, strike/expiration selection, or option P&L.

## Next recommended step
- Review the refreshed Stage 07-14 artifacts and the updated options-overlay readiness report; keep daily scoring/export and options-chain work out of scope until a separate Run C is explicitly started.

---

## Current run: refresh historical OOS candidates with exact 60d proxies

## What changed
- Regenerated `reports/signals/baseline_h5_latest_underlying_candidates.csv` from existing Stage 15 OOS predictions plus refreshed research-universe proxy fields.
- Replaced prior 20d liquidity proxy fields in the candidate CSV with exact 60d fields: `median_dollar_volume_60`, `zero_volume_count_60`, and `history_bars`.
- Added/kept `options_liquidity_verified=false`, `exact_60d_liquidity_proxy_available=true`, and `candidate_export_type=historical_oos_underlying_signal_diagnostic`.
- Updated `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md` so it states the historical OOS candidate export now uses exact 60d proxy fields.
- Did not modify raw data.
- Did not rerun Stage 02-19.
- Did not run Stage 15, Stage 18, Stage 19, expanded features, feature discovery, feature selection, frozen feature stages, daily live scoring/export, new model training, gate loosening, new labels, final model artifact saving, or options backtests.

## Files changed
- `reports/signals/baseline_h5_latest_underlying_candidates.csv`
- `reports/metrics/baseline_h5_underlying_signal_options_overlay_readiness.md`
- `CODEX_HANDOFF.md`

## Commands run
- Read/inspected existing OOS predictions under `data/oos_predictions/baseline_h5`.
- Read/inspected refreshed research artifacts under `data/research_ohlcv_daily`.
- Inline Python diagnostic regeneration for `reports/signals/baseline_h5_latest_underlying_candidates.csv`.
- Targeted CSV/report verification commands.
- Targeted stale-name search across active configs/scripts and active h5 reports.

## Test results
- No pytest was run because no source, config, or test code was changed in this run.
- First inline regeneration attempt failed before writing because `quant_project_daily` was not on `PYTHONPATH`; reran with local bucket assignment logic and completed successfully.
- Latest OOS date: `2026-04-22`.
- Latest OOS rows: `5,134`.
- Candidate rows: `1,027`.
- Missing proxy counts: `median_dollar_volume_60=0`, `zero_volume_count_60=0`, `history_bars=0`.
- Raw ticker mismatch count: `0`.
- Exact 60d proxy available rows: `1,027`.
- `options_liquidity_verified=true` rows: `0`.
- Candidate export type values: `historical_oos_underlying_signal_diagnostic`.
- Bearish candidates: `514`; pass 25m proxy `220`; pass 50m proxy `165`.
- Bullish candidates: `513`; pass 25m proxy `209`; pass 50m proxy `158`.
- Targeted stale-name search found no active stale target/model names in configs/scripts or active h5 report/export paths. The only checked hit was `h20` in `reports/validation/h5_research_ready_lineage_report.md`, where it documents that active h5 schemas did not contain stale h20 target/model columns.

## Remaining work
- Daily underlying-signal scoring/export remains a separate future Run C.
- Contract-level option-chain data is still required before validating options liquidity, execution, IV, Greeks, DTE, strike/expiration selection, or option P&L.

## Next recommended step
- Review the refreshed historical OOS candidate CSV and readiness report; do not treat the candidates as live trade recommendations or options liquidity proof.

---

## Current run: Stage 16 daily underlying signal review export

## What changed
- Added a separate `baseline_h5` scoring feature matrix path for latest model-eligible rows: `data/feature_matrices/baseline_h5_scoring`.
- Added Stage 16 daily underlying signal review export at `scripts/stage16_build_daily_underlying_signals.py`.
- Added final in-memory Ridge scoring from existing label-valid `baseline_h5` features to the latest model-eligible scoring rows.
- Added review-only daily candidate output at `reports/signals/baseline_h5_daily_underlying_candidates.csv`.
- Added reproducibility summary at `reports/signals/baseline_h5_daily_underlying_signal_summary.json`.
- Updated README to list Stage 16 after Stage 14 and before Stage 15.
- Did not persist a model artifact and did not create a `models/` directory.
- Did not modify raw data.
- Did not rerun Stage 02-15, Stage 18, Stage 19, expanded features, feature discovery, feature selection, frozen feature stages, gates, metrics, or options backtests.

## Files changed
- `configs/project.yaml`
- `src/quant_project_daily/config.py`
- `src/quant_project_daily/features_baseline.py`
- `src/quant_project_daily/daily_underlying_signals.py`
- `scripts/stage16_build_daily_underlying_signals.py`
- `tests/test_features_baseline.py`
- `tests/test_daily_underlying_signals.py`
- `README.md`
- Generated scoring matrix under `data/feature_matrices/baseline_h5_scoring`
- Generated signal reports under `reports/signals`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_features_baseline.py tests/test_daily_underlying_signals.py tests/test_baseline_wfa.py`
- `python scripts/stage16_build_daily_underlying_signals.py`
- Targeted output verification for candidate schema, proxy fields, pass/fail rules, model persistence status, and stale active h20 target/model names.
- Optional score-date scoring feature sanity check for `2026-05-29` with `PYTHONPATH=src`.

## Test results
- Focused pytest: 17 passed.
- Stage 16 completed successfully.
- Scoring feature matrix summary: input rows `23,774,790`; output rows `5,200`; score date `2026-05-29`; feature count `55`; target column count `0`; no nulls in active feature columns.
- Final in-memory Ridge training rows: `12,524,133`.
- Training date range: `2010-01-04` through `2026-05-21`.
- Score rows: `5,200` for `2026-05-29`.
- Daily candidate rows: `1,040`.
- Bearish candidates: `520`; pass 25m proxy `214`; pass 50m proxy `166`.
- Bullish candidates: `520`; pass 25m proxy `225`; pass 50m proxy `151`.
- Candidate CSV columns exclude `fwd_ret_5d`, `target_class_5d`, `label_valid_5d`, `next_open`, and `exit_close_5d`.
- Candidate CSV contains exact 60d proxy fields with zero missing values: `median_dollar_volume_60`, `zero_volume_count_60`, and `history_bars`.
- Candidate CSV has only signal deciles `1` and `10`.
- `options_liquidity_verified` is `false` for every row.
- Candidate export type is `future_daily_underlying_signal_review`.
- Proxy pass/fail flags exactly match the requested Stooq-only rules.
- No `models/` directory is present.
- Targeted stale-name search across active configs/scripts/src/README and active h5 signal reports found no `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20` matches.
- Optional score-date scoring feature sanity check returned score date `2026-05-29` and `5,200` rows.

## Remaining work
- Treat Stage 16 output as underlying review candidates only, not trade recommendations.
- Contract-level option-chain data is still required before validating options liquidity, execution, IV, Greeks, DTE, strike/expiration selection, or option P&L.
- Future work can decide whether model persistence is useful after the CSV workflow is reviewed.

## Next recommended step
- Review `reports/signals/baseline_h5_daily_underlying_candidates.csv` and `reports/signals/baseline_h5_daily_underlying_signal_summary.json`; do not use them as options recommendations or options liquidity proof.

---

## Current run: Stage 16 daily underlying signal review runbook

## What changed
- Created `reports/signals/baseline_h5_daily_underlying_signal_review_runbook.md`.
- Documented how to interpret Stage 16 daily underlying candidates as research review input for future options workflows.
- Added manual review checklist covering top-ranked candidate review, 50m/25m proxy preference, manual option-chain checks, bid/ask spread, volume/open interest, expiration/DTE, strike availability, IV/IV rank, and illiquid-contract avoidance.
- Added future automation section for daily data refresh, daily Stage 16 scoring, option-chain snapshot logging, option liquidity filters after chain data exists, and later option P&L research only after historical/logged chain data exists.
- Included latest known Stage 16 summary values: score date `2026-05-29`, rows scored `5,200`, candidates exported `1,040`, 25m proxy pass count `439`, 50m proxy pass count `317`, and validation status with empty summary blockers/warnings.
- Did not modify raw data.
- Did not rerun Stage 02-19 or Stage 16.
- Did not retrain models, save model artifacts, change labels/features/gates/metrics/prediction logic, run expanded features/discovery/selection/frozen stages, or build options backtests.

## Files changed
- `reports/signals/baseline_h5_daily_underlying_signal_review_runbook.md`
- `CODEX_HANDOFF.md`

## Commands run
- Read/inspected `reports/signals/baseline_h5_daily_underlying_signal_summary.json`.
- Read/inspected `reports/signals/baseline_h5_daily_underlying_candidates.csv`.
- Verified required runbook wording and checklist coverage.
- Targeted stale-name search across active Stage 16 runbook/report text.

## Test results
- No pytest was run because no source, config, or test code was changed in this run.
- Runbook exists and frames Stage 16 output as underlying review-only candidates.
- Runbook explicitly states it is not a trade recommendation, not an options liquidity screen, and not an options P&L backtest.
- Targeted stale-name search found no `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, or `target_h20` references in active checked runbook/report text.

## Remaining work
- Contract-level option-chain data is still required before validating option liquidity, execution, IV, Greeks, DTE, strike/expiration selection, or option P&L.

## Next recommended step
- Review `reports/signals/baseline_h5_daily_underlying_signal_review_runbook.md` alongside the Stage 16 candidate CSV before designing any option-chain logging or options research workflow.

---

## Current run: Stage 17 manual option-chain snapshot import

## What changed
- Added a vendor-neutral manual option-chain CSV import path for future Stage 16 candidate review.
- Added strict core contract/quote requirements: `snapshot_date`, `underlying_ticker`, `option_symbol`, `expiration`, `strike`, `call_put`, `bid`, `ask`, and `data_source`.
- Preserved the vendor-neutral schema with nullable optional fields, automatic `mid` calculation from bid/ask, and automatic `DTE` calculation from `snapshot_date` and `expiration`.
- Added candidate linkage by `underlying_ticker` while preserving both Stage 16 `score_date` and option-chain `snapshot_date`.
- Added reporting for candidate tickers without option rows and option-chain tickers outside the candidate file.
- Added tiny manual fixture coverage for missing optional fields.
- Did not call external APIs, use broker credentials, build an options backtest, calculate options P&L, retrain models, rerun Stage 02-19, or rerun Stage 16.

## Files changed
- `configs/project.yaml`
- `src/quant_project_daily/config.py`
- `src/quant_project_daily/option_chain_snapshots.py`
- `scripts/stage17_import_option_chain_snapshots.py`
- `tests/fixtures/manual_option_chain_snapshot.csv`
- `tests/fixtures/stage16_candidates_tiny.csv`
- `tests/test_option_chain_snapshots.py`
- Generated option artifacts under `data/options/raw_snapshots`, `data/options/normalized`, `data/options/candidate_linked`, and `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_option_chain_snapshots.py -q`
- `python scripts/stage17_import_option_chain_snapshots.py tests\fixtures\manual_option_chain_snapshot.csv --candidates-path tests\fixtures\stage16_candidates_tiny.csv`
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active configs/scripts/src/tests/README and new option outputs.

## Test results
- Focused pytest: 5 passed.
- Manual fixture import completed successfully.
- Raw snapshot output: `data/options/raw_snapshots/manual_option_chain_snapshot.csv`.
- Normalized output: `data/options/normalized/manual_option_chain_snapshot_normalized.csv`.
- Candidate-linked output: `data/options/candidate_linked/manual_option_chain_snapshot_candidate_linked.csv`.
- Import summary output: `reports/options/manual_option_chain_snapshot_import_summary.json`.
- Input rows: 3.
- Normalized rows: 3.
- Candidate-linked rows: 3.
- Snapshot date: `2026-06-01`.
- Stage 16 fixture score date: `2026-05-29`.
- `snapshot_date_equals_score_date`: `false`.
- Missing optional field counts include `data_delay_status=3`, `snapshot_timestamp=3`, `last=1`, `volume=1`, `open_interest=1`, `implied_volatility=1`, `delta=1`, `gamma=1`, `theta=1`, `vega=1`, and `quote_timestamp=1`.
- Linkage summary: candidate tickers `2`; option-chain tickers `2`; linked rows `2`; unlinked option rows `1`; candidate without option rows `BBB`; option-chain ticker outside candidates `ZZZ`.
- Targeted stale-name search found no active stale h20/20d target/model names in the checked paths.

## Remaining work
- Choose a real option-chain data source later: broker API, paid market-data API, delayed snapshots, manual CSV process, or historical options dataset.
- Add post-import option liquidity filters only after real contract-level fields are available.
- Continue treating Stage 16 and Stage 17 outputs as review inputs only, not trade recommendations or option-liquidity proof.
- Do not build options P&L or an options backtest until reliable historical/logged option-chain data exists.

## Next recommended step
- Review `reports/options/manual_option_chain_snapshot_import_summary.json` and the fixture outputs, then decide on a real option-chain source before adding any vendor-specific connector.

---

## Current run: Stage 17 manual option-chain template prep

## What changed
- Added a canonical manual option-chain CSV template for preparing broker/vendor exports before Stage 17 import.
- Added a short mapping guide from user-facing manual-export columns to the current Stage 17 internal schema.
- Added a docs ignore exception so the CSV template is visible as a docs artifact.
- Documented required core fields, nullable optional fields, accepted call/put values, bid/ask validation, and `snapshot_date` versus Stage 16 `score_date`.
- Added focused docs/template tests.
- Did not import real option-chain data.
- Did not call external APIs, add broker/API clients, add credentials, build option P&L, score option liquidity, make trade recommendations, or touch raw/model/gate/WFA/metrics/Stage 02-16 outputs.

## Files changed
- `docs/examples/stage17_manual_option_chain_template.csv`
- `docs/stage17_manual_option_chain_mapping.md`
- `tests/test_stage17_manual_option_chain_docs.py`
- `.gitignore`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_option_chain_snapshots.py tests/test_stage17_manual_option_chain_docs.py -q`
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across `docs`, `configs`, `scripts`, `src`, `tests`, and `README.md`.

## Test results
- Focused pytest: 7 passed.
- Stale-name search found no active stale h20/20d target/model names in the checked paths.
- No real Stage 17 import was attempted because no real manual option-chain CSV path was provided.

## Remaining work
- Obtain or choose a real manual option-chain export source and confirm it contains required core fields before attempting an import.
- If the export uses vendor-specific headers, add a narrow mapping fixture or converter in a later run without adding credentials or API clients unless explicitly requested.

## Next recommended step
- Review `docs/stage17_manual_option_chain_mapping.md`, then provide a real manually exported option-chain CSV path when ready for a separate import-validation run.

---

## Current run: Stage 17 real AMD Power E*TRADE option-chain import

## What changed
- Imported the real manually captured Power E*TRADE AMD option-chain CSV through Stage 17.
- Extended Stage 17 normalization to accept the documented manual-template columns directly and map them into the existing internal option-chain schema.
- Added validation coverage for template-column input, nonnegative `volume`/`open_interest`, and expiration after `snapshot_date`.
- Did not modify raw stock data.
- Did not add broker/API clients, add credentials, call external APIs, build option P&L, claim option liquidity/profitability/trade readiness, or run Stage 02-16/18-19.

## Files changed
- `src/quant_project_daily/option_chain_snapshots.py`
- `tests/test_option_chain_snapshots.py`
- Generated option artifacts under `data/options/raw_snapshots`, `data/options/normalized`, `data/options/candidate_linked`, and `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- Read/inspected `manual_option_snapshots/AMD_2026-06-24_etrade_option_chain.csv`.
- `pytest tests/test_option_chain_snapshots.py tests/test_stage17_manual_option_chain_docs.py -q`
- `python scripts/stage17_import_option_chain_snapshots.py manual_option_snapshots\AMD_2026-06-24_etrade_option_chain.csv`
- Targeted artifact validation for summary counts, output existence, required fields, bid/ask, nonnegative volume/open interest, expiration dates, call/put values, and `snapshot_date` versus `score_date`.
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and option outputs.

## Test results
- Focused pytest: 10 passed.
- Real input path: `manual_option_snapshots/AMD_2026-06-24_etrade_option_chain.csv`.
- Input header matched `docs/examples/stage17_manual_option_chain_template.csv`.
- Input rows: 20.
- Normalized rows: 20.
- Invalid/quarantined rows: 0.
- Candidate-linked rows: 20.
- Linked rows to Stage 16 `baseline_h5` daily candidates: 20.
- Candidate tickers without option-chain rows: 1,039.
- Option-chain tickers outside candidates: 0.
- Unlinked option rows: 0.
- Raw snapshot output: `data/options/raw_snapshots/AMD_2026-06-24_etrade_option_chain.csv`.
- Normalized output: `data/options/normalized/AMD_2026-06-24_etrade_option_chain_normalized.csv`.
- Candidate-linked output: `data/options/candidate_linked/AMD_2026-06-24_etrade_option_chain_candidate_linked.csv`.
- Import summary output: `reports/options/AMD_2026-06-24_etrade_option_chain_import_summary.json`.
- Snapshot date: `2026-06-24`.
- Stage 16 score date: `2026-05-29`.
- `snapshot_date_equals_score_date`: `false`.
- `snapshot_matches_score_date_rows`: 0.
- Required core field missing-value counts: none.
- Bid greater than ask rows: 0.
- Negative bid/ask rows: 0.
- Negative volume rows: 0.
- Negative open interest rows: 0.
- Expiration not after snapshot date rows: 0.
- Invalid call/put rows: 0.
- Underlying tickers: `AMD`.
- Call/put values: `C`, `P`.
- Missing optional field counts: `snapshot_timestamp=20`, `underlying_price=20`, `DTE=0`, `mid=0`, `last=0`, `volume=0`, `open_interest=0`, `implied_volatility=0`, `delta=0`, `gamma=0`, `theta=0`, `vega=0`, `quote_timestamp=20`, `data_delay_status=20`.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.

## Remaining work
- Treat the AMD option-chain import as data collection and candidate review support only.
- Do not infer option liquidity, execution quality, profitability, or trade readiness from successful import.
- Future work may add a vendor-specific mapper or logger only if explicitly requested and after source/credential handling is approved.

## Next recommended step
- Review `reports/options/AMD_2026-06-24_etrade_option_chain_import_summary.json` and the normalized/candidate-linked AMD outputs before deciding whether to import more manual snapshots.

---

## Current run: Stage 17 manual snapshot batch manifest workflow

## What changed
- Added Stage 17 batch manifest import while preserving the existing single-file Stage 17 CSV import path.
- Added manifest validation for exact columns, duplicate file paths, missing files, and manifest-vs-snapshot checks for underlying, snapshot date, optional snapshot time, and source.
- Added batch reports under `reports/options`: batch summary JSON, candidate coverage CSV, and batch failures CSV.
- Candidate coverage is one row per Stage 16 `baseline_h5` daily candidate and keeps `options_liquidity_verified=false`.
- Added a docs manifest template and updated the Stage 17 mapping guide with storage, manifest, batch report, and review-only language.
- Added fixture coverage for two valid manual snapshots plus one invalid bid/ask snapshot.
- Did not modify raw stock data, add broker/API clients, add credentials, call external APIs, build option P&L, claim option liquidity/profitability/trade readiness, or rerun Stage 02-19.

## Files changed
- `src/quant_project_daily/option_chain_snapshots.py`
- `scripts/stage17_import_option_chain_snapshots.py`
- `docs/stage17_manual_option_chain_mapping.md`
- `docs/examples/stage17_manual_snapshot_manifest_template.csv`
- `tests/test_option_chain_snapshots.py`
- `tests/test_stage17_manual_option_chain_docs.py`
- `tests/fixtures/manual_option_chain_snapshot_aaa_template.csv`
- `tests/fixtures/manual_option_chain_snapshot_zzz_template.csv`
- `tests/fixtures/manual_option_chain_snapshot_invalid_bid_ask.csv`
- `tests/fixtures/stage17_manual_snapshot_manifest.csv`
- Generated fixture batch outputs under `data/options/**` and `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_option_chain_snapshots.py tests/test_stage17_manual_option_chain_docs.py -q`
- `python scripts/stage17_import_option_chain_snapshots.py --manifest tests\fixtures\stage17_manual_snapshot_manifest.csv --candidates-path tests\fixtures\stage16_candidates_tiny.csv`
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and option outputs.

## Test results
- Focused pytest: 12 passed.
- Fixture batch manifest rows: 3.
- Succeeded files: 2.
- Failed files: 1.
- Total successful input rows: 3.
- Total normalized rows: 3.
- Total candidate-linked rows: 3.
- Invalid/quarantined rows: 0; row-level quarantine is not implemented in v1.
- Batch failure: `tests/fixtures/manual_option_chain_snapshot_invalid_bid_ask.csv` failed with `ask must be greater than or equal to bid`.
- Candidate coverage rows: 2.
- Candidate tickers covered: 1 (`AAA`).
- Candidate tickers without chain rows: 1 (`BBB`).
- Option-chain tickers outside candidates: 1 (`ZZZ`).
- Linked rows: 2.
- Unlinked option rows: 1.
- Snapshot-score date matching rows: 0.
- Missing optional field counts: `snapshot_timestamp=1`, `underlying_price=3`, `DTE=0`, `mid=0`, `last=0`, `volume=0`, `open_interest=0`, `implied_volatility=0`, `delta=0`, `gamma=0`, `theta=0`, `vega=0`, `quote_timestamp=3`, `data_delay_status=3`.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.

## Remaining work
- Create a real `manual_option_snapshots/stage17_manual_snapshot_manifest.csv` only when more real manual snapshots are ready for batch import.
- Keep manual option snapshots as candidate review data only.
- Do not infer option liquidity, execution quality, profitability, or trade readiness from successful imports.
- Add broker/API automation only if explicitly requested later with approved credential handling.

## Next recommended step
- Review `reports/options/stage17_manual_snapshot_batch_summary.json` and `reports/options/stage17_manual_snapshot_candidate_coverage.csv`, then prepare a real manual snapshot manifest when multiple real captures are available.

---

## Current run: Stage 17 real six-file Power E*TRADE batch import

## What changed
- Batch imported six real manually captured Power E*TRADE option-chain CSV snapshots through Stage 17 using `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.
- Verified manifest columns, duplicate paths, file existence, and exact Stage 17 manual-template headers before importing.
- Generated per-file raw snapshot, normalized option-chain, candidate-linked option-chain, and import summary outputs for AMD, MU, ORCL, PLTR, QCOM, and XOM.
- Generated real batch summary, candidate coverage, and failures reports under `reports/options`.
- Did not modify raw stock data, add broker/API clients, add credentials, call external APIs, build option P&L, claim option liquidity/profitability/trade readiness, or rerun Stage 02-16/18-19.

## Files changed
- Generated real option artifacts under `data/options/raw_snapshots`, `data/options/normalized`, `data/options/candidate_linked`, and `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- Read/inspected `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.
- Preflight validation for manifest columns, duplicate file paths, file existence, and CSV headers.
- `python scripts/stage17_import_option_chain_snapshots.py --manifest manual_option_snapshots\stage17_manual_snapshot_manifest.csv`
- Artifact validation for per-file outputs, batch outputs, required fields, bid/ask, nonnegative bid/ask/volume/open interest, expiration dates, call/put values, score/snapshot date separation, and `options_liquidity_verified`.
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and option outputs.

## Test results
- No pytest was run because no import code changed in this run.
- Manifest columns matched exactly: `file_path`, `underlying`, `snapshot_date`, `snapshot_time`, `source`, `notes`.
- Manifest rows: 6.
- Duplicate manifest file paths: 0.
- All six listed CSV files existed.
- All six CSV headers matched `docs/examples/stage17_manual_option_chain_template.csv`.
- Succeeded files: 6.
- Failed files: 0.
- Total input rows: 120.
- Total normalized rows: 120.
- Total candidate-linked rows: 120.
- Invalid/quarantined rows: 0.
- Candidate coverage rows: 1,040.
- Covered candidate tickers: 6 (`AMD`, `MU`, `ORCL`, `PLTR`, `QCOM`, `XOM`).
- Uncovered candidate tickers: 1,034.
- Chain tickers outside candidates: 0.
- Linked rows: 120.
- Unlinked option rows: 0.
- Snapshot date: `2026-06-24`.
- Stage 16 score date: `2026-05-29`.
- Snapshot-score date matching rows: 0.
- Snapshot-score date mismatch linked rows: 120.
- Required core field missing-value counts: none.
- Bid greater than ask rows: 0.
- Negative bid/ask rows: 0.
- Negative volume rows: 0.
- Negative open interest rows: 0.
- Expiration not after snapshot date rows: 0.
- Invalid call/put rows: 0.
- `options_liquidity_verified=true` rows: 0.
- Missing optional field counts: `snapshot_timestamp=120`, `underlying_price=120`, `DTE=0`, `mid=0`, `last=0`, `volume=0`, `open_interest=0`, `implied_volatility=0`, `delta=0`, `gamma=0`, `theta=0`, `vega=0`, `quote_timestamp=120`, `data_delay_status=120`.
- Output reports exist: `reports/options/stage17_manual_snapshot_batch_summary.json`, `reports/options/stage17_manual_snapshot_candidate_coverage.csv`, and `reports/options/stage17_manual_snapshot_batch_failures.csv`.
- Per-file raw, normalized, candidate-linked, and summary outputs exist for AMD, MU, ORCL, PLTR, QCOM, and XOM.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.

## Remaining work
- Manual option snapshots remain candidate review data only.
- Do not infer option liquidity, execution quality, profitability, or trade readiness from successful imports.
- Snapshot date `2026-06-24` differs from Stage 16 score date `2026-05-29`; do not imply the chains existed on the signal score date.
- Add broker/API automation only if explicitly requested later with approved credential handling.

## Next recommended step
- Review `reports/options/stage17_manual_snapshot_batch_summary.json` and `reports/options/stage17_manual_snapshot_candidate_coverage.csv`; collect more manual snapshots only when additional candidate review coverage is needed.

---

## Current run: Stage 17 manual snapshot quality diagnostics

## What changed
- Generated review-only Stage 17 manual snapshot quality diagnostics from existing real batch outputs.
- Created `reports/options/stage17_manual_snapshot_quality_diagnostic.md`.
- Created `reports/options/stage17_manual_snapshot_contract_quality.csv`.
- Created `reports/options/stage17_manual_snapshot_ticker_quality.csv`.
- Summarized snapshot quality, manual review coverage, candidate-linked option-chain rows, covered/uncovered candidate tickers, and score-date/snapshot-date mismatch.
- Did not modify source, config, tests, raw stock data, model code, labels, features, gates, WFA, metrics, or Stage 02-19 outputs.
- Did not add broker/API clients, credentials, external API calls, option P&L, option liquidity verification, profitability claims, or trade-readiness claims.

## Files changed
- Generated reports under `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- Read/inspected `reports/options/stage17_manual_snapshot_batch_summary.json`.
- Read/inspected `reports/options/stage17_manual_snapshot_candidate_coverage.csv`.
- Read/inspected normalized and candidate-linked Stage 17 option-chain outputs under `data/options`.
- Inline Python diagnostic generation for contract quality, ticker quality, and markdown report.
- Output validation for report existence, row counts, covered tickers, date mismatch, and review-only wording.
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and option outputs.

## Test results
- No pytest was run because no source/config/test code changed in this run.
- Required input outputs existed: batch summary, candidate coverage, normalized option-chain files, and candidate-linked option-chain files.
- Contract quality rows: 120.
- Ticker quality rows: 6.
- Covered candidate tickers: `AMD`, `MU`, `ORCL`, `PLTR`, `QCOM`, `XOM`.
- Uncovered candidate tickers count: 1,034.
- Chain tickers outside candidates: 0.
- Candidate-linked option-chain rows analyzed: 120.
- Snapshot date: `2026-06-24`.
- Stage 16 score date: `2026-05-29`.
- Snapshot-score date mismatch rows: 120.
- The report states the option chains were captured after the signal score date and are not historical option chains for that signal date.
- Ticker-level rows all include contracts captured, call/put counts, median/max spread percent, median/total volume, median/total open interest, rows with volume/open interest above zero, rows with bid <= ask, missing optional-field counts, and IV/Greek completeness flags.
- Contract-level rows include bid, ask, mid, bid-ask spread, spread percent of mid, volume, open interest, implied volatility, Greeks, option type, strike, expiration, DTE, ticker, snapshot date, score date, and snapshot-score-date match flag.
- The report uses the required review-only framing: snapshot quality, manual review coverage, and candidate-linked option-chain rows.
- The report keeps `options_liquidity_verified=false` and does not claim option liquidity, execution quality, option P&L, profitability, or trade readiness.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.

## Remaining work
- Manual snapshots remain review data only.
- Do not infer option liquidity, execution quality, profitability, or trade readiness from these diagnostics.
- Do not use the 2026-06-24 option snapshots as historical option chains for the 2026-05-29 Stage 16 score date.
- Future work can define explicit option liquidity criteria only if requested; option P&L/backtesting remains out of scope until reliable historical option data exists.

## Next recommended step
- Review `reports/options/stage17_manual_snapshot_quality_diagnostic.md` with the two diagnostic CSVs before deciding whether to collect additional manual snapshots or define explicit review filters.

---

## Current run: Stage 17 observed-chain review rubric

## What changed
- Added review-only contract rubric fields to `reports/options/stage17_manual_snapshot_contract_quality.csv`: `iv_present`, `greeks_present`, `spread_pct_bucket`, `volume_bucket`, `open_interest_bucket`, and `observed_snapshot_quality`.
- Added review-only ticker rubric fields to `reports/options/stage17_manual_snapshot_ticker_quality.csv`, including contract label counts, spread buckets, rows with full Greeks, rows with IV, and `observed_ticker_review_summary`.
- Created candidate-linked observed-chain review output at `reports/options/stage17_manual_snapshot_candidate_review.csv`.
- Updated `reports/options/stage17_manual_snapshot_quality_diagnostic.md` with a `Review Rubric` section.
- Did not modify source, config, tests, raw stock data, model code, labels, features, gates, WFA, metrics, broker/API code, credentials, or Stage 02-19 outputs.
- Did not add option P&L simulation, profitability claims, verified liquidity claims, execution-quality claims, or trade-readiness wording.

## Files changed
- `reports/options/stage17_manual_snapshot_contract_quality.csv`
- `reports/options/stage17_manual_snapshot_ticker_quality.csv`
- `reports/options/stage17_manual_snapshot_candidate_review.csv`
- `reports/options/stage17_manual_snapshot_quality_diagnostic.md`
- `CODEX_HANDOFF.md`

## Commands run
- Inline Python rubric generation from existing Stage 17 diagnostics.
- Inline Python validation for row counts, required columns, rubric section presence, and `options_liquidity_verified=false`.
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and `reports/options`.

## Test results
- No pytest was run because no source/config/test code changed.
- Contract rows: 120.
- Ticker rows: 6.
- Candidate review rows: 1,040.
- Covered candidate tickers: 6.
- Uncovered candidate tickers: 1,034.
- Snapshot-score date mismatch contract rows: 120.
- `options_liquidity_verified=true` rows: 0.
- Contract review label counts: `complete_fields=110`, `wide_spread=8`, `sparse_activity=2`, `incomplete_fields=0`.
- Ticker review summary counts: `complete_fields=3`, `wide_spread=3`, `sparse_activity=0`, `incomplete_fields=0`.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.

## Remaining work
- Manual snapshots remain review data only.
- The 2026-06-24 option snapshots are not historical option chains for the 2026-05-29 Stage 16 score date.
- Review labels are observed snapshot heuristics only and should not be used as trade selection, verified option liquidity, execution quality, option P&L, profitability, or trade readiness.

## Next recommended step
- Review the candidate-linked output `reports/options/stage17_manual_snapshot_candidate_review.csv` before deciding whether to collect more manual snapshots or define additional review filters.

---

## Current run: Stage 17 next manual snapshot targets

## What changed
- Created `reports/options/stage17_next_manual_snapshot_targets.csv` from the current Stage 16 h5 daily candidates and Stage 17 candidate review coverage.
- Created `reports/options/stage17_next_manual_snapshot_targets.md` with uncovered 25m/50m proxy counts and top 10 bullish/bearish manual capture targets.
- Excluded existing manual snapshot tickers: `AMD`, `MU`, `ORCL`, `PLTR`, `QCOM`, and `XOM`.
- Kept the report framed as a manual snapshot data-collection priority list only.
- Did not modify source, config, tests, raw stock data, model code, labels, features, gates, WFA, metrics, broker/API code, credentials, or Stage 02-19 outputs.
- Did not add option P&L simulation, profitability claims, verified liquidity claims, execution-quality claims, or trade-readiness wording.

## Files changed
- `reports/options/stage17_next_manual_snapshot_targets.csv`
- `reports/options/stage17_next_manual_snapshot_targets.md`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected `reports/options/stage17_manual_snapshot_candidate_review.csv`.
- Inspected `reports/signals/baseline_h5_daily_underlying_candidates.csv`.
- Inline Python generation for `stage17_next_manual_snapshot_targets.csv` and `stage17_next_manual_snapshot_targets.md`.
- Inline Python validation for output existence, exact columns, row counts, covered ticker exclusion, top/bottom signal deciles, proxy counts, and data-collection wording.

## Test results
- No pytest was run because no source/config/test code changed.
- Stage 16 candidate rows: 1,040.
- Output target rows: 1,034.
- Covered tickers excluded: `AMD`, `MU`, `ORCL`, `PLTR`, `QCOM`, `XOM`.
- Uncovered targets passing 50m Stooq-only underlying proxy: 311.
- Uncovered targets passing 25m Stooq-only underlying proxy: 433.
- Output contains only top/bottom signal-decile rows.
- Output contains no `already_has_manual_snapshot=true` rows.
- Top 10 bullish capture targets: `LBRT`, `AROC`, `NE`, `CNX`, `MLI`, `SU`, `GLNG`, `PBR`, `PBR-A`, `VTR`.
- Top 10 bearish capture targets: `MULL`, `IONX`, `ORCX`, `MUU`, `CAR`, `RKLX`, `SOXL`, `UMAC`, `TECL`, `PLTU`.

## Remaining work
- Manual option snapshots remain review data only.
- The target list is not a trade recommendation list.
- Option liquidity, execution quality, option P&L, profitability, and trade readiness remain unvalidated.

## Next recommended step
- Use `reports/options/stage17_next_manual_snapshot_targets.md` to pick the next manual option-chain snapshots to capture, then import those snapshots through the existing Stage 17 manual workflow.

---

## Current run: Manual option snapshot file copy

## What changed
- Copied the 10 provided Power E*TRADE option-chain CSVs from `C:\Users\donny\Downloads` into `manual_option_snapshots`.
- Confirmed `manual_option_snapshots/stage17_manual_snapshot_manifest.csv` references 16 snapshot files.
- Did not run Stage 17 import in this step.
- Did not modify source, config, tests, raw stock data, model code, labels, features, gates, WFA, metrics, broker/API code, or credentials.

## Files changed
- `manual_option_snapshots/LBRT_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/AROC_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/NE_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/CNX_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/MLI_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/MULL_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/IONX_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/ORCX_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/MUU_2026-06-24_etrade_option_chain.csv`
- `manual_option_snapshots/CAR_2026-06-24_etrade_option_chain.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Verified the 10 provided CSV files existed under `C:\Users\donny\Downloads`.
- Copied the 10 CSV files into `manual_option_snapshots`.
- Validated the Stage 17 manual snapshot manifest against the filesystem.

## Test results
- Manifest rows: 16.
- Present files: 16.
- Missing files: 0.
- Manifest tickers present: `AMD`, `MU`, `ORCL`, `PLTR`, `QCOM`, `XOM`, `LBRT`, `AROC`, `NE`, `CNX`, `MLI`, `MULL`, `IONX`, `ORCX`, `MUU`, `CAR`.

## Remaining work
- Run the Stage 17 manual batch import when ready.
- Manual option snapshots remain review data only and do not validate option liquidity, execution quality, option P&L, profitability, or trade readiness.

## Next recommended step
- Run the existing Stage 17 batch import against `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.

---

## Current run: Stage 17 expanded real manual snapshot batch import

## What changed
- Ran the real Stage 17 manual snapshot batch import using `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.
- Refreshed per-file raw snapshot outputs, normalized option-chain outputs, candidate-linked option-chain outputs, and per-file import summaries for 16 Power E*TRADE manual snapshot CSVs.
- Refreshed `reports/options/stage17_manual_snapshot_batch_summary.json`.
- Refreshed `reports/options/stage17_manual_snapshot_candidate_coverage.csv`.
- Refreshed `reports/options/stage17_manual_snapshot_batch_failures.csv`.
- Refreshed review-only diagnostics: `reports/options/stage17_manual_snapshot_quality_diagnostic.md`, `reports/options/stage17_manual_snapshot_contract_quality.csv`, `reports/options/stage17_manual_snapshot_ticker_quality.csv`, and `reports/options/stage17_manual_snapshot_candidate_review.csv`.
- Did not modify source, config, tests, raw stock data, model code, labels, features, gates, WFA, metrics, broker/API code, or credentials.
- Did not rerun Stage 02-16 or Stage 18-19.
- Did not add option P&L simulation, profitability claims, verified liquidity claims, execution-quality claims, or trade-readiness wording.

## Files changed
- Generated Stage 17 outputs under `data/options/raw_snapshots`
- Generated Stage 17 outputs under `data/options/normalized`
- Generated Stage 17 outputs under `data/options/candidate_linked`
- Generated Stage 17 reports under `reports/options`
- `CODEX_HANDOFF.md`

## Commands run
- Read the goal objective file from `C:\Users\donny\.codex\attachments\1b686c41-66d1-4203-a3dd-69cd25452619\goal-objective.md`.
- Inspected `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.
- Inspected Stage 17 import code and CLI help.
- Inline Python preflight validated manifest columns, expected tickers, duplicate paths, file existence, and all 16 CSV headers against the Stage 17 manual template schema.
- Ran `python scripts/stage17_import_option_chain_snapshots.py --manifest manual_option_snapshots/stage17_manual_snapshot_manifest.csv`.
- Inline Python refreshed review-only contract, ticker, candidate review, and markdown diagnostics.
- Inline Python validation checked per-file outputs, batch counts, coverage counts, core fields, bid/ask ordering, nonnegative numeric fields, expiration after snapshot date, valid call/put values, separate `score_date` and `snapshot_date`, diagnostics row counts, and review-only wording.

## Test results
- No pytest was run because no source/config/test code changed in this run.
- Manifest rows: 16.
- Successful files: 16.
- Failed files: 0.
- Total input rows: 318.
- Total normalized rows: 318.
- Total linked rows: 318.
- Invalid/quarantined rows: 0.
- Covered candidate tickers: 16.
- Uncovered candidate tickers: 1,024.
- Chain tickers outside candidates: 0.
- Snapshot-score date mismatch linked rows: 318.
- `options_liquidity_verified=true` rows: 0.
- Review diagnostic contract rows: 318.
- Review diagnostic ticker rows: 16.
- Review diagnostic candidate rows: 1,040.
- Missing optional field counts: `snapshot_timestamp=318`, `underlying_price=318`, `DTE=0`, `mid=0`, `last=0`, `volume=0`, `open_interest=0`, `implied_volatility=0`, `delta=0`, `gamma=0`, `theta=0`, `vega=0`, `quote_timestamp=318`, `data_delay_status=318`.
- Contract review label counts: `complete_fields=120`, `wide_spread=181`, `sparse_activity=17`, `incomplete_fields=0`.
- Ticker review summary counts: `complete_fields=3`, `wide_spread=13`, `sparse_activity=0`, `incomplete_fields=0`.
- Batch failures report exists with header only and no data rows.
- The refreshed quality diagnostic states that 2026-06-24 option snapshots are not historical option chains for the 2026-05-29 Stage 16 score date.

## Remaining work
- Manual option snapshots remain review data only.
- The refreshed diagnostics do not validate option liquidity, execution quality, option P&L, profitability, or trade readiness.
- Any future option liquidity criteria or option P&L/backtesting work should be requested explicitly and should use appropriate option-chain history.

## Next recommended step
- Review `reports/options/stage17_manual_snapshot_quality_diagnostic.md` and `reports/options/stage17_manual_snapshot_candidate_review.csv` before deciding whether to collect more snapshots or define explicit review filters.

---

## Current run: h5 / Stage 16 / Stage 17 checkpoint audit

## Current project state
- Active naming remains h5 / 5d.
- Stage 16 daily underlying candidate export exists at `reports/signals/baseline_h5_daily_underlying_candidates.csv`.
- Stage 16 candidate rows: 1,040.
- Stage 16 score date represented: `2026-05-29`.
- Stage 17 expanded manual Power E*TRADE snapshot batch import is refreshed.
- Stage 17 manifest rows: 16.
- Stage 17 successful files: 16.
- Stage 17 failed files: 0.
- Stage 17 total input rows: 318.
- Stage 17 total normalized rows: 318.
- Stage 17 total linked rows: 318.
- Stage 17 covered candidate tickers: 16.
- Stage 17 uncovered candidate tickers: 1,024.
- Stage 17 chain tickers outside candidates: 0.
- Stage 17 snapshot-score date mismatch linked rows: 318.
- `options_liquidity_verified=true` rows: 0.
- Review diagnostic contract rows: 318.
- Review diagnostic ticker rows: 16.
- Review diagnostic candidate rows: 1,040.

## Dirty worktree classification
- Commit-eligible source/script/doc/test changes:
  - `docs/stage17_manual_option_chain_mapping.md`
  - `scripts/stage17_import_option_chain_snapshots.py`
  - `src/quant_project_daily/option_chain_snapshots.py`
  - `tests/test_option_chain_snapshots.py`
  - `tests/test_stage17_manual_option_chain_docs.py`
  - `docs/examples/stage17_manual_snapshot_manifest_template.csv`
  - `tests/fixtures/manual_option_chain_snapshot_aaa_template.csv`
  - `tests/fixtures/manual_option_chain_snapshot_invalid_bid_ask.csv`
  - `tests/fixtures/manual_option_chain_snapshot_zzz_template.csv`
  - `tests/fixtures/stage17_manual_snapshot_manifest.csv`
- Handoff/local checkpoint file:
  - `CODEX_HANDOFF.md`
- Generated or local ignored artifacts:
  - `data/**`
  - `reports/**`
  - `manual_option_snapshots/*.csv`
  - `manual_option_snapshots/stage17_manual_snapshot_manifest.csv`

## .gitignore verification
- `.gitignore` ignores `data/**`.
- `.gitignore` ignores `reports/**`.
- `.gitignore` ignores `*.csv`, which protects manual option snapshot CSVs and the manual snapshot manifest unless a path is explicitly unignored.
- `git check-ignore -v` confirmed ignore protection for representative Stage 17 data outputs, report outputs, manual snapshot CSVs, the manual snapshot manifest, and the Stage 16 daily candidate report.

## Commands run
- `git status --short --untracked-files=all`
- `git diff --name-only`
- `git ls-files --others --exclude-standard`
- `git diff --stat`
- `git check-ignore -v data/options/normalized/LBRT_2026-06-24_etrade_option_chain_normalized.csv reports/options/stage17_manual_snapshot_batch_summary.json reports/options/stage17_manual_snapshot_candidate_review.csv manual_option_snapshots/LBRT_2026-06-24_etrade_option_chain.csv manual_option_snapshots/stage17_manual_snapshot_manifest.csv reports/signals/baseline_h5_daily_underlying_candidates.csv`
- Inline Python artifact/count validation for Stage 16 candidate export and Stage 17 batch/coverage/review outputs.
- `pytest tests/test_option_chain_snapshots.py tests/test_stage17_manual_option_chain_docs.py -q`
- Targeted stale-name search for `h20`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` across active docs/configs/scripts/src/tests/README and `reports/options`.

## Test and check results
- Focused pytest result: 12 passed.
- Targeted stale-name search found no active stale h20/20d target/model names in checked paths.
- Required Stage 16 and Stage 17 output files exist and are non-empty.
- Stage 17 review-only wording remains present in `reports/options/stage17_manual_snapshot_quality_diagnostic.md`.
- Stage 17 diagnostic wording states that the `2026-06-24` option snapshots are not historical option chains for the `2026-05-29` Stage 16 score date.

## Remaining blockers and caveats
- Manual option snapshots remain review data only.
- The current workflow does not validate option liquidity, execution quality, option P&L, profitability, or trade readiness.
- The dirty worktree is intentionally not committed in this run.

## Next recommended scope
- If requested, prepare a commit containing only the commit-eligible Stage 17 source/script/doc/test/template changes and exclude generated/local artifacts.
- Do not add broker/API automation, option P&L, model tuning, expanded features, feature discovery, feature selection, or frozen feature stages without a new explicit scope.

---

## Current run: baseline h5 signal viability diagnostic

## What changed
- Generated a read-only baseline h5 signal viability diagnostic from existing outputs only.
- Confirmed the active gate failure is driven by small positive gross edge being below the configured 25 bps round-trip cost assumption.
- Confirmed mean daily rank IC is positive, while top-decile net and long-short net diagnostics remain negative at 25 bps.
- Tested OHLCV-only candidate filters using existing OOS predictions joined to existing `data/research_ohlcv_daily` proxy fields.
- No retraining, WFA rerun, tuning, feature changes, gate changes, option P&L, broker/API work, or Stage 17 option evidence was used.

## Files changed
- `reports/metrics/baseline_h5_signal_viability_diagnostic.md`
- `reports/metrics/baseline_h5_signal_viability_by_year.csv`
- `reports/metrics/baseline_h5_signal_viability_by_fold.csv`
- `reports/metrics/baseline_h5_candidate_filter_diagnostic.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected existing gate, metrics, cost sensitivity, WFA/OOS, feature, signal, and research OHLCV proxy artifacts.
- Inline Python diagnostic generation from `data/oos_predictions/baseline_h5`, `reports/metrics/baseline_h5_*`, `reports/gates/baseline_h5_gate.json`, and `data/research_ohlcv_daily`.
- Inline Python validation confirmed generated CSV row counts, official metric alignment, and filter diagnostics.
- Targeted wording search on the new markdown report for prohibited claims: `trade-ready`, `validated liquidity`, `profitable`, `approved`, `execute`, and `option P&L`.
- Targeted stale-name search on the new h5 diagnostic outputs for active stale h20/20d target/model names.
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- OOS rows processed: 9,903,519.
- Historical top/bottom decile rows processed for filter diagnostics: 1,980,712.
- Daily rank IC observations: 2,835.
- By-year diagnostic rows: 12.
- By-fold diagnostic rows: 45.
- Candidate-filter diagnostic rows: 8.
- Break-even bps: top-decile long 18.7535, bottom-decile short 13.6517, long-short 16.2026.
- `all_top_bottom_deciles` in the candidate-filter diagnostic matches the official active metrics summary for top gross, short gross, and long-short gross returns.
- Best tested 25 bps long-short net filter: `close_ge_10` at -0.0003745700318334.
- Stooq-only 25m proxy long-short net at 25 bps: -0.0011640809348667.
- Stooq-only 50m proxy long-short net at 25 bps: -0.0011268258781205.
- Prohibited wording search found only allowed guardrail statements saying no option P&L was used.
- Stale-name search found no active h20/20d target/model names in the new diagnostic outputs.

## Remaining blockers and caveats
- Baseline h5 gate remains `FAIL`.
- Current evidence supports continued research, not trade recommendations or readiness claims.
- OHLCV-only filters do not prove security type, option liquidity, execution quality, or option P&L.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Run a read-only long-only versus short-side diagnostic using existing OOS rows to decide whether the short side should stay in the baseline gate.
- Review cost assumptions before changing gates because observed break-even bps are below the current 25 bps assumption.
- Defer expanded features until the baseline failure mode is isolated by side, cost, and OHLCV-only filter segment.

---

## Current run: baseline h5 long-only viability diagnostic

## What changed
- Generated a read-only long-only h5 diagnostic from existing OOS predictions.
- Separated long-only top-score bands from short-side and long-short diagnostics.
- Evaluated top 20%, top 10%, top 5%, top 2%, top 1%, fixed top 25, fixed top 50, and fixed top 100 long-only bands.
- Evaluated OHLCV-only filters using existing `data/research_ohlcv_daily` fields: close, `median_dollar_volume_60`, `zero_volume_count_60`, and `history_bars`.
- No retraining, tuning, WFA rerun, feature changes, gate changes, API/broker work, Stage 17 option evidence, or option P&L was used.

## Files changed
- `reports/metrics/baseline_h5_long_only_viability.md`
- `reports/metrics/baseline_h5_long_only_by_year.csv`
- `reports/metrics/baseline_h5_long_only_by_fold.csv`
- `reports/metrics/baseline_h5_long_only_filter_grid.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected existing `data/oos_predictions/baseline_h5`, `reports/metrics/baseline_h5_metrics_summary.json`, `reports/gates/baseline_h5_gate.json`, prior viability diagnostics, and `data/research_ohlcv_daily` schema.
- Inline Python generated long-only band, cost, year/fold, volatility/drawdown proxy, and OHLCV-only filter-grid diagnostics.
- Inline Python validation confirmed output row counts and official top-decile long metric alignment.
- Targeted wording search on the new markdown report for prohibited claims: `trade-ready`, `validated liquidity`, `approved`, `profitable`, `execute`, and `option P&L`.
- Targeted stale-name search on the new h5 diagnostic outputs for active stale h20/20d target/model names.
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- OOS parquet files read: 45.
- Top-20% candidate rows used as the long-only selection superset: 1,979,575.
- Band/filter rows evaluated: 4,252,908.
- Long-only bands: 8.
- Filter definitions: 9.
- By-year diagnostic rows: 96.
- By-fold diagnostic rows: 360.
- Filter-grid rows: 72.
- `top_10_pct` + `all_long_band` matches official active top-decile long gross and 25 bps net metrics exactly.
- Tested 25 bps survivors: 9 band/filter combinations.
- Best tested 25 bps profile: `fixed_top_25` + `median_dollar_volume_60_ge_25m`, net 25 bps 0.0002986454818788, break-even 27.986454818788275 bps, average candidates/day 9.866573.
- Active top-decile long remains negative at 25 bps: -0.0006246450090375, break-even 18.753549909624034 bps.
- Prohibited wording search found only allowed guardrail statements saying no option P&L was used.
- Stale-name search found no active h20/20d target/model names in the new diagnostic outputs.

## Remaining blockers and caveats
- Baseline h5 gate remains `FAIL`.
- Positive long-only narrow/filter diagnostics are research leads only, not readiness or profitability claims.
- Volatility and drawdown values are proxies over overlapping h5 forward-return observations.
- OHLCV-only filters do not prove security type, option liquidity, execution quality, or option P&L.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Design a read-only long-only gate candidate diagnostic using existing OOS rows.
- Focus on fixed top-N and dollar-volume-filtered long-only profiles before expanded features.
- Do not change gates until the cost assumption and long-only scope are explicitly approved.

---

## Current run: baseline h5 long-only gate candidate diagnostic

## What changed
- Generated a read-only diagnostic for a possible separate long-only h5 gate candidate.
- Focus profile inspected: `fixed_top_25` + `median_dollar_volume_60_ge_25m`.
- Compared nearby long-only profiles across fixed top 10/25/50/100 and top 1%/2%/5%/10%/20%.
- Compared non-option filters: no added filter, `close >= 5`, `close >= 10`, `median_dollar_volume_60 >= 25m`, and `median_dollar_volume_60 >= 50m`.
- Official gates were not changed.
- No retraining, tuning, expanded features, feature selection, API/broker work, Stage 17 option evidence, or option P&L was used.

## Files changed
- `reports/metrics/baseline_h5_long_only_gate_candidate_diagnostic.md`
- `reports/metrics/baseline_h5_long_only_gate_candidate_grid.csv`
- `reports/metrics/baseline_h5_long_only_gate_candidate_by_year.csv`
- `reports/metrics/baseline_h5_long_only_gate_candidate_by_fold.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected existing long-only reports under `reports/metrics`.
- Inspected `configs/gates.yaml` read-only.
- Inline Python generated the candidate profile grid and year/fold robustness reports from existing `data/oos_predictions/baseline_h5` and `data/research_ohlcv_daily`.
- Inline Python validation checked row counts and official top-decile long metric alignment.
- Searched new report text for prohibited claims: `trade-ready`, `validated liquidity`, `approved`, `profitable`, `execute`, and `option P&L`.
- Targeted stale-name search on new outputs for active h20/20d target/model names.
- `git diff -- configs/gates.yaml`
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- Candidate grid rows: 45.
- Candidate by-year rows: 540.
- Candidate by-fold rows: 2,025.
- Bands evaluated: 9.
- Filters evaluated: 5.
- `top_10_pct` + `all_long_band` matches official top-decile long gross and 25 bps net metrics.
- Focus profile `fixed_top_25` + `median_dollar_volume_60_ge_25m`: net 25 bps 0.0002986454818788, break-even 27.986454818788275 bps, positive years 4/12, positive folds 22/45.
- Best nearby profile by 25 bps net is the same focus profile.
- `configs/gates.yaml` has no diff.
- Prohibited wording search found only guardrail/negative statements.
- Stale-name search found no active h20/20d target/model names in the new outputs.

## Remaining blockers and caveats
- The focus profile is strong enough to document as a research gate candidate, but not robust enough for official gate replacement yet.
- Main caveats: narrow average candidate count, mixed year/fold stability, overlapping h5 return dependence, cost assumption uncertainty, and OHLCV-only limitations.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Draft a read-only proposed long-only gate specification and validation checklist.
- Include minimum year/fold stability requirements and cost-sensitivity requirements before any official gate change is considered.
- Do not change official gates unless a future prompt explicitly scopes that change.

---

## Current run: baseline h5 proposed long-only gate spec/checklist

## What changed
- Drafted a read-only proposed long-only h5 gate spec.
- Drafted a checklist for future validation before any official gate replacement.
- Kept the focus profile as a research-only candidate: `pred_long_rank_5d <= 25` and `median_dollar_volume_60 >= 25,000,000`.
- Explicitly documented that the official gate remains unchanged and still fails.
- No retraining, tuning, WFA rerun, expanded features, feature selection, API/broker work, official gate change, Stage 17 option evidence, or option P&L was used.

## Files changed
- `reports/metrics/baseline_h5_long_only_gate_proposed_spec.md`
- `reports/metrics/baseline_h5_long_only_gate_checklist.md`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected gate-candidate diagnostics under `reports/metrics`.
- Inspected `reports/gates/baseline_h5_gate.json`.
- Inspected `configs/gates.yaml` read-only.
- Wrote the proposed spec and checklist.
- Searched new files for prohibited claims: `trade-ready`, `validated liquidity`, `approved`, `profitable`, `execute`, and `option P&L`.
- Targeted stale-name search on new files for active h20/20d target/model names.
- `git diff -- configs/gates.yaml`
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- Proposed spec written: `reports/metrics/baseline_h5_long_only_gate_proposed_spec.md`.
- Checklist written: `reports/metrics/baseline_h5_long_only_gate_checklist.md`.
- Official gate config has no diff.
- Stale-name search found no active h20/20d target/model names in the new files.
- Prohibited wording search found only `option P&L` in explicit out-of-scope statements.
- Focus profile remains research-only: net 25 bps 0.000299, break-even 27.99 bps, positive years 4/12, positive folds 22/45.

## Remaining blockers and caveats
- The focus profile does not meet the proposed stability checklist for official replacement.
- Proposed review floors include break-even at least 30 bps, at least 7/12 positive years, at least 27/45 positive folds, and at least 10 average candidates/day.
- The current focus profile is below those proposed review floors.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Run a turnover and cost-sensitivity diagnostic for the proposed long-only gate candidate.
- Keep official gates unchanged until a future prompt explicitly scopes a gate change and the checklist passes.

---

## Current run: baseline h5 long-only turnover/cost diagnostic

## What changed
- Generated a read-only turnover and cost-sensitivity diagnostic for the proposed research-only long h5 gate candidate.
- Focus profile: `pred_long_rank_5d <= 25` plus `median_dollar_volume_60 >= 25,000,000`.
- Compared nearby fixed top-N profiles: fixed top 10, 25, and 50.
- Compared filters: no added OHLCV proxy filter, `median_dollar_volume_60 >= 25m`, `median_dollar_volume_60 >= 50m`, and `close >= 10`.
- Official gates were not changed.
- No retraining, tuning, WFA rerun, expanded features, feature selection, API/broker work, Stage 17 option evidence, or option P&L was used.

## Files changed
- `reports/metrics/baseline_h5_long_only_turnover_cost_diagnostic.md`
- `reports/metrics/baseline_h5_long_only_turnover_cost_grid.csv`
- `reports/metrics/baseline_h5_long_only_turnover_by_year.csv`
- `reports/metrics/baseline_h5_long_only_turnover_by_fold.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected current long-only gate candidate reports under `reports/metrics`.
- Inspected OOS prediction and research OHLCV proxy schemas.
- Inspected `configs/gates.yaml` read-only.
- Inline Python generated turnover/cost grid, by-year, by-fold, and markdown diagnostics from existing `data/oos_predictions/baseline_h5` and `data/research_ohlcv_daily`.
- Inline Python validation checked row counts, cost columns, focus-profile consistency, and reported turnover fields.
- Searched new outputs for prohibited claims: `trade-ready`, `validated liquidity`, `approved`, `profitable`, `execute`, and `option P&L`.
- Targeted stale-name search on new outputs for active h20/20d target/model names.
- `git diff -- configs/gates.yaml`
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- Turnover/cost grid rows: 12.
- By-year rows: 144.
- By-fold rows: 540.
- Bands evaluated: 3.
- Filters evaluated: 4.
- Cost levels included: 0, 5, 10, 15, 20, 25, 30, 40, and 50 bps.
- Focus profile net 25 bps: 0.0002986454818788.
- Focus profile break-even: 27.986454818788275 bps.
- Focus profile average candidates/day: 9.86657253794564.
- Focus profile average day-to-day overlap: 0.3195558244569196.
- Focus profile average entries per transition: 6.626059322033898.
- Focus profile average exits per transition: 6.623587570621469.
- Focus profile estimated one-way turnover/day: 0.6800445587268666.
- Focus profile estimated h5 round-trip turnover proxy: 6.800445587268666.
- Focus profile positive years: 4/12.
- Focus profile positive folds: 22/45.
- Profiles positive at 25 bps: 5/12.
- Official gate config has no diff.
- Prohibited wording search found only `option P&L` in explicit out-of-scope guardrail statements.
- Stale-name search found no active h20/20d target/model names in the new outputs.

## Remaining blockers and caveats
- The positive 25 bps result is not primarily a low-turnover result; selection churn is high.
- The positive result appears driven mostly by stronger gross returns from a narrow, dollar-volume-filtered selection.
- Break-even remains below the proposed 30 bps floor.
- The profile still fails proposed checklist floors for positive years, positive folds, and average candidates/day.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Keep the profile as a research lead, not an official replacement.
- Investigate whether feature improvements or a more stable long-only definition can improve year/fold stability before any official gate change.

---

## Current run: baseline h5 persistence/turnover diagnostic

## What changed
- Generated a read-only turnover-reduction and signal-persistence diagnostic for the long-only h5 research lead.
- Focus profile remains `pred_long_rank_5d <= 25` plus `median_dollar_volume_60 >= 25,000,000`.
- Tested fixed top 10, 25, and 50 rank variants.
- Tested no persistence plus 2-day and 3-day persistence against top 25, 50, and 100 rank thresholds.
- Tested filters: no added OHLCV proxy filter, `median_dollar_volume_60 >= 25m`, `median_dollar_volume_60 >= 50m`, and `close >= 10`.
- Official gates were not changed.
- No retraining, tuning, WFA rerun, expanded features, feature selection, API/broker work, Stage 17 option evidence, or option P&L was used.

## Files changed
- `reports/metrics/baseline_h5_long_only_persistence_turnover_diagnostic.md`
- `reports/metrics/baseline_h5_long_only_persistence_turnover_grid.csv`
- `reports/metrics/baseline_h5_long_only_persistence_by_year.csv`
- `reports/metrics/baseline_h5_long_only_persistence_by_fold.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected current turnover/cost reports and OOS/research schemas.
- Inline Python generated persistence turnover/cost diagnostics from existing `data/oos_predictions/baseline_h5` and `data/research_ohlcv_daily`.
- Inline Python validation checked output files, row counts, cost columns, focus-profile consistency, best persistence profile, official gate diff, stale active h20 names, and wording guardrails.
- `git diff -- configs/gates.yaml`
- `git status --short --untracked-files=all`

## Test and check results
- No pytest was run because no source/config/test code changed.
- Initial generation shell command timed out after printing a completion summary; follow-up validation confirmed all output files are present and internally consistent.
- Persistence grid rows: 84.
- By-year rows: 1,008.
- By-fold rows: 3,780.
- Rank variants: 3.
- Persistence variants: 7.
- Filter variants: 4.
- Focus profile net 25 bps: 0.0002986454818788.
- Focus profile break-even: 27.986454818788275 bps.
- Focus profile average candidates/day: 9.86657253794564.
- Focus profile estimated one-way turnover/day: 0.6800445587268666.
- Best net persistence profile: `fixed_top_10` + `top_50_3d_persist` + `median_dollar_volume_60_ge_50m`, net 25 bps 0.0010267379068174, one-way turnover 0.5450028364534321, average candidates/day 1.6624649859943978.
- Profiles positive at 25 bps: 12/84 overall and 7/72 persistence variants.
- Official gate config has no diff.
- Prohibited wording search found only `option P&L` in explicit out-of-scope guardrail statements.
- Stale-name search found no active h20/20d target/model names in the new outputs.

## Remaining blockers and caveats
- Persistence reduces selection churn in some variants but generally makes the candidate set very narrow.
- The best persistence profile improves 25 bps net but averages only about 1.66 candidates/day.
- Persistence does not solve year/fold stability enough for official gate replacement.
- Evidence points to regime instability and limited edge margin more than pure turnover.
- Generated reports are ignored and were not staged or committed.

## Next recommended scope
- Do not change official gates.
- Treat persistence as a secondary diagnostic, not the main fix.
- Prioritize feature improvement or a more stable long-only definition, plus cost assumption review.

---

## Current run: experimental long_only_h5_phase1 feature path

## What changed
- Added an experimental Phase 1 h5 feature set named `long_only_h5_phase1`.
- Added separate experimental feature and OOS prediction paths; official `baseline_h5` feature, OOS, WFA, and gate paths were not replaced.
- Added eight OHLCV-only experimental features: risk-adjusted 20d/60d momentum, 20d positive-return fraction, 5d-vs-60d pullback/overextension, 5d/20d and 20d/60d volatility ratios, ATR-to-volatility ratio, and 20d/60d dollar-volume ratio.
- Added a fixture-tested experimental WFA wrapper, but did not run the full experimental WFA comparison.
- Built the experimental feature matrix only.

## Files changed
- `configs/project.yaml`
- `configs/long_only_h5_phase1_features.yaml`
- `src/quant_project_daily/config.py`
- `src/quant_project_daily/features_long_only_phase1.py`
- `scripts/experimental_build_long_only_h5_phase1_features.py`
- `scripts/experimental_run_long_only_h5_phase1_wfa.py`
- `tests/test_features_long_only_phase1.py`
- Generated ignored artifacts under `data/feature_matrices/long_only_h5_phase1`
- Generated ignored report `reports/features/long_only_h5_phase1_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_no_lookahead.py tests/test_features_baseline.py tests/test_features_long_only_phase1.py -q`
- `python scripts/experimental_build_long_only_h5_phase1_features.py`
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 reports\wfa\baseline_h5_oos_summary.json`
- `rg -n -S "target_class_20d|fwd_ret_20d|pred_score_20d|baseline_h20|target_h20" configs scripts src tests README.md reports\features`

## Test and check results
- Targeted pytest: 14 passed.
- Experimental feature build completed with 12,524,133 rows and 63 features.
- Experimental output path: `data/feature_matrices/long_only_h5_phase1`.
- Experimental summary: `reports/features/long_only_h5_phase1_summary.json`.
- Official baseline output paths were not replaced: no diff in `configs/gates.yaml`, `data/feature_matrices/baseline_h5`, or `reports/wfa/baseline_h5_oos_summary.json`.
- Targeted stale active 20d target/model search returned no matches.

## Remaining work
- Full experimental WFA/comparison has not been run.
- Before running it, use:
  `python scripts/experimental_run_long_only_h5_phase1_wfa.py`
- Expected WFA outputs:
  `data/oos_predictions/long_only_h5_phase1/fold_*.parquet`,
  `reports/wfa/long_only_h5_phase1_fold_summary.csv`, and
  `reports/wfa/long_only_h5_phase1_oos_summary.json`.

## Next recommended scope
- Run the experimental WFA only if approved as the next heavier comparison step.
- After WFA, generate read-only comparison diagnostics versus current `baseline_h5`; do not change official gates unless a later prompt explicitly scopes that work.

---

## Current run: attempted long_only_h5_phase1 experimental WFA

## What changed
- Updated the experimental WFA loop to stop iterating after the first caught fold failure.
- Ran only the approved experimental WFA command.
- Did not run comparison diagnostics.
- Did not change official gates, official `baseline_h5` predictions, official `baseline_h5` WFA summaries, or official metrics.

## Files changed
- `src/quant_project_daily/features_long_only_phase1.py`
- Partial generated ignored outputs under `data/oos_predictions/long_only_h5_phase1`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/experimental_run_long_only_h5_phase1_wfa.py`

## Test and check results
- First command attempt was aborted before completion and left partial folds.
- Second command attempt restarted from scratch and completed folds 001 through 031.
- The command exited with code 1 before printing a handled `fold_failed` line and before writing `reports/wfa/long_only_h5_phase1_fold_summary.csv` or `reports/wfa/long_only_h5_phase1_oos_summary.json`.
- No Python WFA process remained running after the failure.
- Present partial experimental OOS files: `fold_001.parquet` through `fold_031.parquet`.

## Remaining work
- Do not run comparison diagnostics until a complete experimental WFA summary exists.
- Next debugging step, if approved, should isolate fold 032 or add safer per-fold flushing/checkpointing to the experimental wrapper before rerunning.

---

## Current run: long_only_h5_phase1 WFA fold 032 isolation

## What changed
- Isolated the incomplete experimental WFA failure after fold 031 without deleting partial fold outputs.
- Confirmed fold 032 data is valid and fold 032 succeeds when run alone through the same fold fitting path.
- Identified the likely failure cause as experimental wrapper memory/state behavior from accumulating all fold prediction DataFrames in memory and writing summaries only after the full loop.
- Added experimental-only resume/range controls and per-fold summary flushing to the Phase 1 WFA wrapper.
- Did not rerun full WFA and did not run comparison diagnostics.
- Did not touch official `baseline_h5` gates, predictions, reports, configs, or summaries.

## Files changed
- `src/quant_project_daily/features_long_only_phase1.py`
- `scripts/experimental_run_long_only_h5_phase1_wfa.py`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected `scripts/experimental_run_long_only_h5_phase1_wfa.py`.
- Inspected `src/quant_project_daily/features_long_only_phase1.py`.
- Validated partial `data/oos_predictions/long_only_h5_phase1/fold_*.parquet` files.
- Inspected fold 032 feature slice from `data/feature_matrices/long_only_h5_phase1/long_only_h5_phase1.parquet`.
- Ran no-write fold 032 reproduction through `_read_matrix_for_fold()` and `run_fold()`.
- `pytest tests/test_features_long_only_phase1.py -q`
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json`

## Test and check results
- Partial experimental folds present: 31 files, `fold_001.parquet` through `fold_031.parquet`.
- Partial experimental OOS row count: 6,085,533.
- Partial fold schemas are consistent and required prediction/target columns have zero null rows.
- Fold 032 split plan: train `2017-10-05` through `2022-10-06`; test `2022-10-14` through `2023-01-13`; expected train rows `4,271,688`; expected test rows `248,038`.
- Fold 032 feature slice: 4,538,998 rows; 63 feature columns; no missing required columns; zero feature nulls; zero feature infinite values; zero target nulls.
- Fold 032 no-write reproduction succeeded: 248,038 prediction rows; train rows `4,271,688`; test rows `248,038`; prediction score min/max `-1.0556644929962153` / `0.20563177926948356`.
- The fold 032 matrix slice used about 2,337 MB in pandas before fitting.
- Focused tests: 3 passed.
- Official baseline artifact diff check was empty.

## Remaining work
- To continue WFA without deleting existing partial outputs, use:
  `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --start-fold 32`
- Expected behavior: skip/preserve existing folds 001-031 only if included, run folds 032-045, flush `reports/wfa/long_only_h5_phase1_fold_summary.csv` and `reports/wfa/long_only_h5_phase1_oos_summary.json` as folds complete.
- Do not run comparison diagnostics until a complete experimental WFA summary exists.

---

## Current run: long_only_h5_phase1 resumed WFA from fold 032

## What changed
- Ran only the approved resume command:
  `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --start-fold 32`
- Preserved existing experimental folds 001-031.
- Completed and wrote experimental folds 032-044.
- Did not run comparison diagnostics.
- Did not stage or commit generated data/reports.
- Did not touch official `baseline_h5` gates, predictions, configs, reports, or summaries.

## Files changed
- Generated ignored outputs under `data/oos_predictions/long_only_h5_phase1`
- Generated ignored checkpoint summaries:
  - `reports/wfa/long_only_h5_phase1_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1_oos_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --start-fold 32`
- Verified experimental fold files and row counts.
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv`

## Test and check results
- Resume command exited with code 1 after starting fold 045.
- Folds completed in this resumed run: 032 through 044.
- Fold 045 did not complete and `data/oos_predictions/long_only_h5_phase1/fold_045.parquet` is absent.
- Existing experimental fold files now present: 44 files, `fold_001.parquet` through `fold_044.parquet`.
- Total rows across existing experimental OOS fold files: 9,579,411.
- Checkpoint summary files exist, but represent the resumed requested range and are not a complete 45-fold WFA summary.
- Official baseline artifact diff check was empty.

## Remaining work
- Do not run comparison diagnostics yet.
- Next safe command, if approved, is:
  `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --fold-id 45`
- Expected result: run only fold 045, write `fold_045.parquet`, and update checkpoint summaries for that requested fold.
- After fold 045 completes, build or refresh a complete all-fold experimental summary before any comparison diagnostics.

---

## Current run: long_only_h5_phase1 fold 045 completion

## What changed
- Ran only the approved command:
  `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --fold-id 45`
- Preserved existing experimental folds 001-044.
- Wrote `data/oos_predictions/long_only_h5_phase1/fold_045.parquet`.
- Did not run comparison diagnostics.
- Did not refresh a complete all-fold WFA summary.
- Did not stage or commit generated data/reports.
- Did not touch official `baseline_h5` gates, predictions, configs, reports, or summaries.

## Files changed
- Generated ignored output:
  - `data/oos_predictions/long_only_h5_phase1/fold_045.parquet`
- Generated ignored checkpoint summaries for the requested fold-only run:
  - `reports/wfa/long_only_h5_phase1_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1_oos_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- `python scripts/experimental_run_long_only_h5_phase1_wfa.py --resume --fold-id 45`
- Verified experimental fold file count, row counts, and schema consistency.
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv`

## Test and check results
- Fold 045 completed successfully.
- Fold 045 rows written: 324,108.
- Experimental fold files now present: 45 files, `fold_001.parquet` through `fold_045.parquet`.
- Total rows across experimental OOS fold files: 9,903,519.
- Experimental fold schemas are consistent across all 45 files.
- Current `reports/wfa/long_only_h5_phase1_*` summaries reflect the last requested single-fold run only, not a complete all-fold summary.
- Official baseline artifact diff check was empty.

## Remaining work
- Next safe step is to refresh a complete experimental all-fold WFA summary from the existing 45 fold files without rerunning folds.
- Do not run comparison diagnostics until that complete summary is refreshed and verified.

---

## Current run: long_only_h5_phase1 complete WFA summary refresh

## What changed
- Refreshed complete experimental all-fold WFA summaries from existing fold parquet files only.
- Did not rerun WFA folds.
- Did not retrain.
- Did not run comparison diagnostics.
- Did not delete or overwrite `fold_001.parquet` through `fold_045.parquet`.
- Did not stage or commit generated data/reports.
- Did not touch official `baseline_h5` gates, predictions, configs, reports, or summaries.

## Files changed
- Generated ignored summaries:
  - `reports/wfa/long_only_h5_phase1_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1_oos_summary.json`
- `CODEX_HANDOFF.md`

## Commands run
- Inline summary-only Python reading `data/oos_predictions/long_only_h5_phase1/fold_*.parquet`.
- Verified refreshed JSON/CSV summary counts.
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv configs\baseline_model.yaml configs\baseline_features.yaml`

## Test and check results
- Experimental fold parquet files present: 45.
- Refreshed `long_only_h5_phase1_fold_summary.csv` rows: 45.
- Fold IDs covered: 1 through 45.
- Refreshed summary `folds_completed`: 45.
- Refreshed summary `folds_failed`: 0.
- Refreshed summary total OOS rows: 9,903,519.
- Refreshed summary prediction date range: 2015-01-13 through 2026-04-22.
- Feature count: 63.
- Official baseline artifact diff check was empty.

## Remaining work
- Next safe step is read-only Phase 1 versus official baseline comparison diagnostics, if explicitly approved.
- Do not change official gates unless a later prompt explicitly scopes that work.

---

## Current run: long_only_h5_phase1 vs baseline_h5 read-only comparison

## What changed
- Generated read-only comparison diagnostics from existing completed OOS parquet files only.
- Compared official `baseline_h5` against experimental `long_only_h5_phase1`.
- Did not rerun WFA.
- Did not retrain.
- Did not run expanded feature discovery/selection.
- Did not run option P&L or broker/API work.
- Did not change official gates.
- Did not stage or commit generated data/reports.

## Files changed
- Generated ignored comparison reports:
  - `reports/metrics/long_only_h5_phase1_vs_baseline_diagnostic.md`
  - `reports/metrics/long_only_h5_phase1_vs_baseline_summary.csv`
  - `reports/metrics/long_only_h5_phase1_vs_baseline_profile_grid.csv`
  - `reports/metrics/long_only_h5_phase1_vs_baseline_by_year.csv`
  - `reports/metrics/long_only_h5_phase1_vs_baseline_by_fold.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inline read-only comparison Python reading:
  - `data/oos_predictions/baseline_h5/fold_*.parquet`
  - `data/oos_predictions/long_only_h5_phase1/fold_*.parquet`
  - `data/research_ohlcv_daily`
- Verified generated report row counts.
- Searched new comparison outputs for prohibited claim wording.
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv configs\baseline_model.yaml configs\baseline_features.yaml reports\gates`

## Test and check results
- Both OOS sets: 45 folds and 9,903,519 rows.
- Comparison summary rows: 2.
- Profile grid rows: 12.
- By-year rows: 144.
- By-fold rows: 540.
- Baseline mean daily rank IC: 0.024544545012611444.
- Phase 1 mean daily rank IC: 0.02470595386591374.
- Rank IC delta: +0.00016140885330229518.
- Baseline focus profile `fixed_top_25 + median_dollar_volume_60 >= 25m` net at 25 bps: 0.00029864548187882737.
- Phase 1 focus profile net at 25 bps: 0.0003359905564698528.
- Focus profile net 25 bps delta: +0.00003734507459102546.
- Phase 1 focus profile positive years/folds at 25 bps: 5/12 years and 21/45 folds.
- Baseline focus profile positive years/folds at 25 bps: 4/12 years and 22/45 folds.
- Diagnostic status: `needs_more_diagnostics`.
- Wording search found only an explicit guardrail statement that no option P&L was created.
- Official baseline artifact diff check was empty.

## Remaining work
- Phase 1 remains experimental and should not replace official gates from this diagnostic.
- Next safe scope is deeper read-only robustness diagnostics, feature ablation, or revising the Phase 1 feature set; do not change official gates unless explicitly scoped.

---

## Current run: long_only_h5_phase1 feature-family robustness diagnostic

## What changed
- Generated read-only robustness and ablation-style diagnostics for experimental `long_only_h5_phase1`.
- Used existing artifacts only: completed Phase 1 OOS predictions, official baseline OOS predictions, Phase 1 feature matrix/registry, and prior Phase 1-vs-baseline comparison reports.
- Did not retrain, rerun WFA, tune model parameters, run feature selection, change official gates, replace official baseline outputs, add option P&L, or add API/broker work.
- Did not stage or commit generated reports.

## Files changed
- Generated ignored reports:
  - `reports/metrics/long_only_h5_phase1_feature_family_diagnostic.md`
  - `reports/metrics/long_only_h5_phase1_feature_family_summary.csv`
  - `reports/metrics/long_only_h5_phase1_feature_diagnostic.csv`
  - `reports/metrics/long_only_h5_phase1_vs_baseline_by_regime.csv`
- `CODEX_HANDOFF.md`

## Commands run
- Inspected Phase 1 feature config/registry and prior comparison reports.
- Inline diagnostic Python scanned OOS-aligned rows from:
  - `data/feature_matrices/long_only_h5_phase1/long_only_h5_phase1.parquet`
  - `data/oos_predictions/long_only_h5_phase1/fold_*.parquet`
  - prior `reports/metrics/long_only_h5_phase1_vs_baseline_*` outputs
- Verified generated report row counts.
- Searched new outputs for prohibited claim wording.
- `git diff -- configs\gates.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv configs\baseline_model.yaml configs\baseline_features.yaml reports\gates`

## Test and check results
- OOS-aligned diagnostic row count: 9,903,519.
- Feature diagnostic rows: 63.
- Feature-family summary rows: 5.
- Regime diagnostic rows: 228.
- Phase 1 focus profile beat baseline in 7/12 years and 25/45 folds.
- Most promising review families: `volatility_risk` and `volume_liquidity`.
- Noisy/unstable family: `momentum_trend`.
- Redundant family: `reversal_pullback`, driven by `pullback_5d_vs_60d` correlation with baseline `ret_60d`.
- Specific feature notes:
  - `vol_ratio_20d_60d`: strongest Phase 1 added feature by fold mean rank IC, positive in 34/45 folds.
  - `vol_ratio_5d_20d`: positive in 28/45 folds.
  - `dollar_volume_ratio_20d_60d`: weak but positive in 26/45 folds.
  - `mom_20d_vol_adj`, `mom_60d_vol_adj`, and `trend_pos_ret_frac_20d`: unstable/negative fold mean IC.
  - `atr14_to_vol20`: unstable.
  - `pullback_5d_vs_60d`: highly redundant with `ret_60d`.
- No fold-level model coefficients were found; true ablation requires a separately scoped experimental retraining/WFA run.
- Wording search found only the explicit allowed guardrail statement that no option P&L was created.
- Official baseline artifact diff check was empty.

## Remaining work
- Phase 1 should remain experimental.
- Safest next scope is a separately scoped experimental ablation run that keeps official `baseline_h5` untouched, such as variants without momentum/trend additions, without volatility/risk additions, and without volume/liquidity addition.

---

## Current run: long_only_h5_phase1 primary ablation variants

## What changed
- Implemented the first two experimental ablation variants only:
  - `long_only_h5_phase1_no_momentum_trend`
  - `long_only_h5_phase1_vol_liq_only`
- Generalized the experimental Phase 1 feature/WFA helper so variant configs can reuse the same h5 target, WFA split plan, and baseline Ridge settings while writing only to variant-specific experimental paths.
- Built both variant feature matrices, ran 45-fold experimental WFA for both variants, and generated read-only comparison diagnostics against official `baseline_h5` and full `long_only_h5_phase1`.
- Did not run the optional `long_only_h5_phase1_no_reversal_pullback` variant because the first two variants produced effectively identical results and did not improve enough to justify another WFA run.
- Did not change official gates, official `baseline_h5` predictions, official reports, raw data, option workflows, or Stage 02-19 artifacts.
- Did not stage or commit generated data/reports.

## Files changed
- Source/test/config/script files:
  - `src/quant_project_daily/features_long_only_phase1.py`
  - `tests/test_features_long_only_phase1.py`
  - `configs/long_only_h5_phase1_no_momentum_trend_features.yaml`
  - `configs/long_only_h5_phase1_vol_liq_only_features.yaml`
  - `scripts/experimental_build_long_only_h5_phase1_no_momentum_trend_features.py`
  - `scripts/experimental_build_long_only_h5_phase1_vol_liq_only_features.py`
  - `scripts/experimental_run_long_only_h5_phase1_no_momentum_trend_wfa.py`
  - `scripts/experimental_run_long_only_h5_phase1_vol_liq_only_wfa.py`
  - `scripts/experimental_compare_long_only_h5_ablation.py`
- Generated experimental data/reports:
  - `data/feature_matrices/long_only_h5_phase1_no_momentum_trend/`
  - `data/feature_matrices/long_only_h5_phase1_vol_liq_only/`
  - `data/oos_predictions/long_only_h5_phase1_no_momentum_trend/`
  - `data/oos_predictions/long_only_h5_phase1_vol_liq_only/`
  - `reports/features/long_only_h5_phase1_no_momentum_trend_summary.json`
  - `reports/features/long_only_h5_phase1_vol_liq_only_summary.json`
  - `reports/wfa/long_only_h5_phase1_no_momentum_trend_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1_no_momentum_trend_oos_summary.json`
  - `reports/wfa/long_only_h5_phase1_vol_liq_only_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1_vol_liq_only_oos_summary.json`
  - `reports/metrics/long_only_h5_phase1_no_momentum_trend_vs_baseline_phase1_*`
  - `reports/metrics/long_only_h5_phase1_vol_liq_only_vs_baseline_phase1_*`
- `CODEX_HANDOFF.md`

## Commands run
- `pytest tests/test_no_lookahead.py tests/test_features_long_only_phase1.py -q`
- `python scripts/experimental_build_long_only_h5_phase1_no_momentum_trend_features.py`
- `python scripts/experimental_build_long_only_h5_phase1_vol_liq_only_features.py`
- Inline feature inclusion/exclusion verification for both variants.
- `python scripts/experimental_run_long_only_h5_phase1_no_momentum_trend_wfa.py`
- `python scripts/experimental_run_long_only_h5_phase1_vol_liq_only_wfa.py`
- `python scripts/experimental_compare_long_only_h5_ablation.py --variant long_only_h5_phase1_no_momentum_trend`
- `python scripts/experimental_compare_long_only_h5_ablation.py --variant long_only_h5_phase1_vol_liq_only`
- Inline validation of fold counts, row counts, WFA summaries, and comparison summaries.
- Wording search across generated ablation reports for prohibited claim wording.
- Official baseline diff checks against gates, baseline feature/prediction paths, baseline WFA reports, baseline configs, and gate reports.

## Test and check results
- Focused tests: 10 passed.
- Feature matrices:
  - `long_only_h5_phase1_no_momentum_trend`: 12,524,133 rows, 60 features.
  - `long_only_h5_phase1_vol_liq_only`: 12,524,133 rows, 59 features.
- WFA outputs:
  - Both variants completed 45 folds.
  - Both variants produced 9,903,519 OOS rows.
  - Both variants wrote only to variant-specific experimental prediction and WFA report paths.
- Focus profile: `fixed_top_25 + median_dollar_volume_60 >= 25m`.
- Baseline reference:
  - Rank IC: 0.0245445450.
  - Net at 25 bps: 0.0002986455.
  - Positive years/folds: 4/12 years and 22/45 folds.
  - Avg candidates/day: 9.866573.
- Full `long_only_h5_phase1` reference:
  - Rank IC: 0.0247059539.
  - Net at 25 bps: 0.0003359906.
  - Positive years/folds: 5/12 years and 21/45 folds.
  - Avg candidates/day: 10.025406.
- `long_only_h5_phase1_no_momentum_trend`:
  - Rank IC: 0.0243646874.
  - Net at 25 bps: 0.0002925551.
  - Positive years/folds: 4/12 years and 27/45 folds.
  - Avg candidates/day: 9.663842.
- `long_only_h5_phase1_vol_liq_only`:
  - Rank IC: 0.0243646894.
  - Net at 25 bps: 0.0002925551.
  - Positive years/folds: 4/12 years and 27/45 folds.
  - Avg candidates/day: 9.663842.
- Interpretation:
  - Both variants improved positive-fold count versus full Phase 1 but reduced rank IC and focus-profile 25 bps net versus full Phase 1 and slightly underperformed the official baseline focus net.
  - Positive-year count did not improve beyond baseline and fell below full Phase 1.
  - Avg candidates/day fell below the approximate 10/day floor.
  - Neither variant is strong enough to propose as an official gate replacement.
- Wording search found only explicit negated readiness language.
- Official baseline artifact diff checks were empty.

## Remaining work
- Keep official `baseline_h5` gate unchanged.
- Do not run `long_only_h5_phase1_no_reversal_pullback` unless a later prompt explicitly asks for it; the first two variants already suggest the pullback feature is not the decisive issue.
- If continuing Phase 1 research, the safest next experiment is a separately scoped, narrow feature redesign or single-feature variant around the strongest prior signal such as `vol_ratio_20d_60d`, with the same experimental-only path discipline.

---

## Current checkpoint: Phase 1 experimental ablation audit

## Current experimental state
- Official `baseline_h5` gate remains unchanged and FAIL.
- Full `long_only_h5_phase1` remains experimental.
- Primary ablation variants completed:
  - `long_only_h5_phase1_no_momentum_trend`
  - `long_only_h5_phase1_vol_liq_only`
- Both ablation variants were mixed:
  - improved positive-fold count versus full Phase 1,
  - reduced rank IC and focus-profile 25 bps net versus full Phase 1,
  - did not improve positive-year count enough,
  - fell below the approximate 10 candidates/day focus-profile breadth floor.
- No official gate replacement is supported by the current evidence.
- Optional `long_only_h5_phase1_no_reversal_pullback` was not run and should remain deferred unless explicitly rescoped.

## Worktree classification
- Commit-eligible source/config/test/checkpoint files:
  - `CODEX_HANDOFF.md`
  - `configs/project.yaml`
  - `configs/long_only_h5_phase1_features.yaml`
  - `configs/long_only_h5_phase1_no_momentum_trend_features.yaml`
  - `configs/long_only_h5_phase1_vol_liq_only_features.yaml`
  - `scripts/experimental_build_long_only_h5_phase1_features.py`
  - `scripts/experimental_build_long_only_h5_phase1_no_momentum_trend_features.py`
  - `scripts/experimental_build_long_only_h5_phase1_vol_liq_only_features.py`
  - `scripts/experimental_compare_long_only_h5_ablation.py`
  - `scripts/experimental_run_long_only_h5_phase1_wfa.py`
  - `scripts/experimental_run_long_only_h5_phase1_no_momentum_trend_wfa.py`
  - `scripts/experimental_run_long_only_h5_phase1_vol_liq_only_wfa.py`
  - `src/quant_project_daily/config.py`
  - `src/quant_project_daily/features_long_only_phase1.py`
  - `tests/test_features_long_only_phase1.py`
- Generated artifacts that must remain unstaged/uncommitted:
  - `data/feature_matrices/long_only_h5_phase1/`
  - `data/feature_matrices/long_only_h5_phase1_no_momentum_trend/`
  - `data/feature_matrices/long_only_h5_phase1_vol_liq_only/`
  - `data/oos_predictions/long_only_h5_phase1/`
  - `data/oos_predictions/long_only_h5_phase1_no_momentum_trend/`
  - `data/oos_predictions/long_only_h5_phase1_vol_liq_only/`
  - `reports/features/long_only_h5_phase1*_summary.json`
  - `reports/wfa/long_only_h5_phase1*_fold_summary.csv`
  - `reports/wfa/long_only_h5_phase1*_oos_summary.json`
  - `reports/metrics/long_only_h5_phase1*_diagnostic.md`
  - `reports/metrics/long_only_h5_phase1*_summary.csv`
  - `reports/metrics/long_only_h5_phase1*_by_year.csv`
  - `reports/metrics/long_only_h5_phase1*_by_fold.csv`
- Local-only files that should remain unstaged:
  - `manual_option_snapshots/`
  - `data/options/`
  - existing ignored `data/**`, `reports/**`, cache, and virtualenv paths not explicitly scoped for source control.

## Commands run
- `git status --short`
- `git status --ignored --short`
- `git diff --name-only`
- `git ls-files --others --exclude-standard`
- `git diff -- configs\gates.yaml configs\baseline_model.yaml configs\baseline_features.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv reports\gates`
- `pytest tests/test_no_lookahead.py tests/test_features_long_only_phase1.py -q`
- `git diff -- configs\project.yaml src\quant_project_daily\config.py`

## Test and check results
- Targeted tests: 10 passed.
- Official baseline gate/config/report diff check was empty.
- `configs/project.yaml` and `src/quant_project_daily/config.py` changes are limited to experimental `long_only_h5_phase1` paths.
- Generated artifacts remain ignored/untracked and were not staged.

## Blockers and caveats
- True causal attribution still requires separately scoped experimental retraining/WFA variants; the completed variants are evidence but not sufficient for gate replacement.
- Phase 1 and both primary ablations remain research diagnostics only, not profitable/trade-ready results.
- Official `baseline_h5` remains FAIL and unchanged.

## Next recommended scope
- Plan a narrow `vol_ratio_20d_60d` redesign or single-feature experimental variant, using the same experimental-only path discipline.
- Do not run more WFA, optional ablations, or gate replacement work without explicit scope.

---

## Current run: long_only_h5_vol20_60_only feature-build checkpoint

## What changed
- Added the first narrow volatility-regime experimental variant only:
  - `long_only_h5_vol20_60_only`
- Variant definition:
  - includes all 55 baseline features,
  - includes only one Phase 1 added feature: `vol_ratio_20d_60d`,
  - excludes `vol_ratio_5d_20d`, `atr14_to_vol20`, `dollar_volume_ratio_20d_60d`, `pullback_5d_vs_60d`, `mom_20d_vol_adj`, `mom_60d_vol_adj`, and `trend_pos_ret_frac_20d`.
- Built the feature matrix only.
- Did not run WFA, comparison diagnostics, model tuning, feature search, feature selection, option/API work, option P&L, or gate replacement.

## Files changed
- `configs/long_only_h5_vol20_60_only_features.yaml`
- `scripts/experimental_build_long_only_h5_vol20_60_only_features.py`
- `scripts/experimental_run_long_only_h5_vol20_60_only_wfa.py`
- `tests/test_features_long_only_phase1.py`
- Generated local/ignored feature artifact:
  - `data/feature_matrices/long_only_h5_vol20_60_only/`

## Commands run
- `pytest tests/test_no_lookahead.py tests/test_features_long_only_phase1.py -q`
- `python scripts/experimental_build_long_only_h5_vol20_60_only_features.py`
- Inline verification of feature columns, excluded columns, feature matrix existence, and absence of WFA/OOS outputs.
- `git diff -- configs\gates.yaml configs\baseline_model.yaml configs\baseline_features.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv reports\gates`
- `git status --ignored --short`

## Test and check results
- Focused tests passed after the feature build: 11 passed.
- Feature build summary:
  - input rows: 23,774,790
  - output rows: 12,524,133
  - feature count: 56
  - target columns: 5
  - metadata columns: 11
  - tickers: 7,661
  - date range: 2010-01-04 through 2026-05-21
  - `official_baseline_replaced`: false
- Feature-column verification:
  - `vol_ratio_20d_60d` present.
  - excluded Phase 1 columns absent.
  - target/future/next-open/exit columns absent from feature list.
- WFA/OOS verification:
  - `reports/wfa/long_only_h5_vol20_60_only_oos_summary.json` does not exist.
  - `data/oos_predictions/long_only_h5_vol20_60_only/` does not exist.
- Official baseline guard diff was empty.

## Remaining work
- WFA has not run for `long_only_h5_vol20_60_only`.
- If approved, the exact next command is:
  - `python scripts/experimental_run_long_only_h5_vol20_60_only_wfa.py`
- After WFA completes, comparison diagnostics should be separately scoped and should not change official gates.

---

## Current run: long_only_h5_vol20_60_only comparison diagnostic

## What changed
- Generated read-only comparison diagnostics for `long_only_h5_vol20_60_only`.
- Compared against:
  - official `baseline_h5`,
  - full `long_only_h5_phase1`,
  - `long_only_h5_phase1_no_momentum_trend`,
  - `long_only_h5_phase1_vol_liq_only`.
- Used existing completed OOS prediction files only for model outputs.
- Attached existing `median_dollar_volume_60` from `data/research_ohlcv_daily` only because the requested focus profile requires it and OOS prediction files do not carry that proxy column.
- Did not rerun WFA, retrain, tune, implement additional variants, change official gates, add option/API work, or stage/commit generated reports.

## Files changed
- Generated ignored reports:
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_summary.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_summary.json`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_by_year.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_by_fold.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_diagnostic.md`
- `CODEX_HANDOFF.md`

## Commands run
- Preflight check for `data/oos_predictions/long_only_h5_vol20_60_only/fold_001.parquet` through `fold_045.parquet`.
- Preflight check for:
  - `reports/wfa/long_only_h5_vol20_60_only_fold_summary.csv`
  - `reports/wfa/long_only_h5_vol20_60_only_oos_summary.json`
- `git diff -- configs\gates.yaml configs\baseline_model.yaml configs\baseline_features.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv reports\gates`
- Inline read-only comparison diagnostic over existing OOS prediction files.
- Generated report existence/size checks.
- `git diff --cached --name-only`
- Wording search for prohibited claims in the new markdown diagnostic.
- `git status --short`

## Test and check results
- Preflight:
  - `long_only_h5_vol20_60_only` fold files present: 45/45.
  - WFA summaries present.
  - WFA summary reported 45 folds completed, 0 failed folds, and 9,903,519 OOS rows.
- Official baseline guard diff was empty before and after diagnostics.
- No files were staged.
- Wording guard search found no prohibited claim terms in the new diagnostic.
- Focus profile: `fixed_top_25 + median_dollar_volume_60 >= 25m`.
- Summary metrics:
  - `baseline_h5`: rank IC 0.024545, IC t-stat 8.918, net 25 bps 0.000299, break-even 27.986 bps, positive years/folds 4/12 and 22/45, avg candidates/day 9.867, turnover proxy 0.680.
  - `long_only_h5_phase1`: rank IC 0.024706, IC t-stat 9.148, net 25 bps 0.000336, break-even 28.360 bps, positive years/folds 5/12 and 21/45, avg candidates/day 10.025, turnover proxy 0.663.
  - `long_only_h5_phase1_no_momentum_trend`: rank IC 0.024365, IC t-stat 9.003, net 25 bps 0.000293, break-even 27.926 bps, positive years/folds 4/12 and 27/45, avg candidates/day 9.664, turnover proxy 0.684.
  - `long_only_h5_phase1_vol_liq_only`: rank IC 0.024365, IC t-stat 9.003, net 25 bps 0.000293, break-even 27.926 bps, positive years/folds 4/12 and 27/45, avg candidates/day 9.664, turnover proxy 0.684.
  - `long_only_h5_vol20_60_only`: rank IC 0.024404, IC t-stat 8.879, net 25 bps 0.000430, break-even 29.302 bps, positive years/folds 4/12 and 26/45, avg candidates/day 9.861, turnover proxy 0.678.
- Best/worst:
  - All compared profiles had best year 2020 and worst year 2018.
  - `long_only_h5_vol20_60_only` best fold was 22 and worst fold was 35.
- Diagnostic status: `reject_or_pause`.

## Remaining work
- Do not change official gates from this comparison.
- `long_only_h5_vol20_60_only` has better focus-profile 25 bps net but does not improve positive-year count and remains below the approximate 10 candidates/day breadth floor.
- Recommended next step is to pause or review diagnostics manually before deciding whether any further narrow experiment is worth running.

---

## Current checkpoint: long_only_h5_vol20_60_only audit

## Current experiment state
- `long_only_h5_vol20_60_only` WFA completed 45/45 folds with 0 failed folds and 9,903,519 OOS rows.
- Read-only comparison diagnostics completed under `reports/metrics`.
- Diagnostic status remains `reject_or_pause`.
- Result summary:
  - focus-profile 25 bps net improved versus official baseline, full Phase 1, and both primary ablations,
  - positive-year count stayed weak at 4/12,
  - average candidates/day remained below the approximate 10/day breadth floor,
  - no official gate replacement is supported.
- Do not run `long_only_h5_vol_ratio_pair`, optional volume-confirmation variants, or gate replacement work without new explicit scope.

## Worktree classification
- Commit-eligible source/config/test/checkpoint files:
  - `CODEX_HANDOFF.md`
  - `configs/long_only_h5_vol20_60_only_features.yaml`
  - `scripts/experimental_build_long_only_h5_vol20_60_only_features.py`
  - `scripts/experimental_run_long_only_h5_vol20_60_only_wfa.py`
  - `tests/test_features_long_only_phase1.py`
- Generated ignored artifacts that must remain unstaged:
  - `data/feature_matrices/long_only_h5_vol20_60_only/`
  - `data/oos_predictions/long_only_h5_vol20_60_only/`
  - `reports/features/long_only_h5_vol20_60_only_summary.json`
  - `reports/wfa/long_only_h5_vol20_60_only_fold_summary.csv`
  - `reports/wfa/long_only_h5_vol20_60_only_oos_summary.json`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_summary.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_summary.json`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_by_year.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_by_fold.csv`
  - `reports/metrics/long_only_h5_vol20_60_only_vs_baseline_phase1_ablation_diagnostic.md`
- Local-only files that should remain unstaged:
  - `manual_option_snapshots/`
  - `data/options/`
  - existing ignored `data/**`, `reports/**`, cache, and virtualenv paths not explicitly scoped for source control.

## Commands run
- `git status --short`
- `git status --ignored --short`
- `git diff --name-only`
- `git ls-files --others --exclude-standard`
- `git diff --cached --name-only`
- `git diff -- configs\gates.yaml configs\baseline_model.yaml configs\baseline_features.yaml data\feature_matrices\baseline_h5 data\oos_predictions\baseline_h5 reports\wfa\baseline_h5_oos_summary.json reports\wfa\baseline_h5_fold_summary.csv reports\gates`
- `pytest tests/test_no_lookahead.py tests/test_features_long_only_phase1.py -q`
- Generated report existence checks under `reports/metrics`.
- WFA summary existence/count check for `long_only_h5_vol20_60_only`.

## Test and check results
- Targeted tests: 11 passed.
- Official baseline gate/config/prediction/report diff check was empty.
- Staged diff was empty.
- Generated comparison reports are present.
- WFA summary confirms 45 completed folds, 0 failed folds, and 9,903,519 OOS rows.

## Blockers and caveats
- The variant remains experimental and does not justify a gate change.
- Better focus-profile net does not solve year/fold stability or breadth concerns.
- No profitability, readiness, option, API, or live-trading claim is supported by this work.

## Next recommended scope
- Pause experiments and review the completed diagnostics.
- If continuing later, plan a different feature redesign explicitly; do not run additional variants or WFA from the current checkpoint without a new scope.
