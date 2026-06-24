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
