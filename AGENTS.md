# US Stocks Swing Model Agents

## Project Identity

- This repo is a daily US equities OHLCV swing-model research pipeline.
- The active target horizon is h5 / 5 trading days.
- Use `research-ready` and `walk-forward-ready`; do not describe this project as `production-ready` or `live-trading-ready`.

## Repo Rules

- Scripts must be deterministic, repo-relative, and testable.
- Preserve behavior and APIs unless the task requires changing them.
- Reuse existing patterns.
- Avoid rewrites, new dependencies, unrelated changes, and speculative future work.
- Do not modify secrets, credentials, lockfiles, migrations, generated artifacts, or user work unless required or explicitly requested.
- Ask before destructive operations.
- Do not commit changes unless explicitly asked.

## Data Rules

- Never modify raw files under `data/raw_txt`.
- Do not commit raw or generated data.
- `data/**` and `reports/**` are generated/ignored unless a task explicitly says to inspect or regenerate them.
- Raw input schema: `<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>`.
- Daily bars must use `PER=D` and `TIME=000000`.

## Active H5 Naming Rules

- Active target/model/report paths should use h5 / 5d names.
- Do not introduce stale h20 / 20d names into active code, configs, or reports.
- Treat `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` as stale unless clearly historical or archived.

## Pipeline Stage Boundaries

- Stage 02: raw manifest.
- Stage 03: raw validation.
- Stage 05: daily normalization.
- Stage 07: causal gating.
- Stage 08: research universe.
- Stage 09: h5 target generation.
- Stage 11: h5 baseline features.
- Stage 13: column registry.
- Stage 14: h5 WFA split plan.
- Stage 15+: model training/evaluation work; do not run unless explicitly requested.

## Causal And Leakage Rules

- Do not use future information in eligibility, labels, features, scaling, imputation, feature discovery, or WFA.
- Feature engineering must be ticker-local or date-cross-sectional only where intended.
- Train/test transformations must be fit on train only.
- Preserve purge logic for the active h5 target horizon.
- Metadata, target, label, forward-return, next-open, and exit columns must not enter feature columns.

## Universe And Data-Quality Rules

- Current OHLCV-only data can support price, volume, dollar-volume, history, zero-volume, and traded-days filters.
- Do not implement or claim filters that require unavailable metadata: common-stock-only, ETF/ETN exclusion, warrants/units/rights/preferreds exclusion, exchange filter, OTC exclusion, ADR exclusion, delisted-name coverage, permanent security IDs, borrow/shortability, or corporate-action adjustment status.
- Report those as limitations unless current files/configs prove them.

## Validation Rules

- Use `pytest` for validation.
- Run `pytest` after source, config, or test changes.
- Run the narrowest relevant check only when warranted.
- Prefer targeted tests while working.
- Ask the user to run full or expensive test suites when appropriate.
- Stop on failed commands and report command, error summary, and affected artifact.
- Do not silently continue after validation failure.

## Scope-Control Rules

- Minimize tokens, reads, edits, commands, and output. Make the smallest safe change.
- Implement directly when the task is clear.
- Plan only for broad or risky work, and keep the plan under 120 words.
- Ask only to avoid wrong, unsafe, or destructive changes.
- Read targeted files directly by path instead of asking the user to paste large files, reports, logs, or full test output.
- Search before opening many files.
- Skip generated, vendor, cache, build, data, log, and binary files unless relevant.
- Use short summaries instead of long copied output.
- Ask for full logs only when a short summary is not enough.
- Do not add labels, features, WFA, models, backtests, metrics, gates, expanded features, feature discovery, feature selection, or frozen feature stages unless explicitly asked.
- Do not rename columns, paths, configs, or reports unless the task explicitly asks for a refactor or stale-name fix.
- Do not commit unless explicitly asked.

## Multi-Step Work

- For work that may take multiple prompts, use a repo-local `CODEX_HANDOFF.md`.
- Read `CODEX_HANDOFF.md` first if it exists.
- Update `CODEX_HANDOFF.md` at the end of each multi-step run with:
  - what changed
  - files changed
  - commands run
  - test results
  - remaining work
  - next recommended step
- Do not create or update `CODEX_HANDOFF.md` for simple one-shot tasks.

## Follow-Up Prompt Handoffs

- For every non-trivial repo/research final response, include a `### Next Codex Prompt` section with one single copy-pastable fenced `text` prompt that the user can paste into another Codex thread to continue.
- Keep the prompt concise and include only the context needed for the next diagnostic or implementation run: current status, key metrics, relevant artifacts, explicit guardrails, requested task, stop conditions, and final response format if useful.
- Remove boilerplate that is not needed for the next run, such as generic blockers, full dirty-tree inventories, or generated-artifact lists, unless the next prompt is specifically about checkpointing or git hygiene.
- Preserve active h5 / 5d terminology, research-ready wording, and caveats against profitability, option liquidity, option P&L, production readiness, or live-trading readiness claims.
- If the next step is unclear, make the pasted prompt ask Codex to recommend the next step in plan mode before implementation.
- For simple one-shot tasks where no follow-up is useful, still include `### Next Codex Prompt` and write `No follow-up prompt needed.`.

## Output Style

- Be concise.
- Do not include long reasoning, tutorials, full diffs, repeated code dumps, praise, or chain-of-thought unless asked.
- Final responses must use only the sections listed below.

## Final Response Format

Use only:

### Blockers

Low

* <minor unresolved items only, or None>

Medium

* <real caveats/incomplete verification only, or None>

Severe

* <blocking issues only, or None>

Proceed status: yes / yes with medium blockers / no

### Next

1. <action> -> <expected result> -> <stop condition>

### Next Codex Prompt

```text
<single copy-pastable Codex prompt for the next diagnostic or implementation run, or "No follow-up prompt needed.">
```

### Metrics

Elapsed time: <duration or not available to agent>
Token usage: <tokens or not available to agent>

Do not estimate or fabricate elapsed time or token usage.
If metrics are unavailable, write `not available to agent`.
