# US Stocks Swing Model Agents

## Project Identity

- This repo is a daily US equities OHLCV swing-model research pipeline.
- The active target horizon is h5 / 5 trading days.
- Use `research-ready` and `walk-forward-ready`; do not describe this project as `production-ready` or `live-trading-ready`.
- Outputs are research artifacts, not investment advice, profitability claims, or instructions to trade.

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
- Some generated artifacts may already be tracked from prior repo history. Treat those as existing user work: do not refresh or edit them unless the task explicitly requires it. If validation incidentally changes already-tracked generated artifacts, report the paths and do not stage them without explicit approval.
- Raw input schema: `<TICKER>,<PER>,<DATE>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>,<VOL>,<OPENINT>`.
- Daily bars must use `PER=D` and `TIME=000000`.

## Active H5 Naming Rules

- Active target/model/report paths should use h5 / 5d names.
- Do not introduce stale h20 / 20d names into active code, configs, or reports.
- Treat `h20`, `20d`, `target_class_20d`, `fwd_ret_20d`, `pred_score_20d`, `baseline_h20`, and `target_h20` as stale unless clearly historical or archived.

## H5 Timing And Label Rules

- Prediction as-of time is after the current daily bar is fully known.
- Daily bars must use `PER=D` and `TIME=000000`.
- Features and eligibility may use only information available as of that current completed bar.
- Active h5 labels enter at the next trading day's open (`next_open`) and exit at the close 5 trading days ahead (`exit_close_5d`); `fwd_ret_5d = exit_close_5d / next_open - 1`.
- Do not change close-to-close, next-open, exit, horizon, or label-window semantics unless explicitly requested.
- Before changing target labels, inspect Stage 09 target-generation code and preserve existing conventions unless the task explicitly requires a label refactor.

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
- Train/test transformations, imputation, scaling, feature selection/discovery, thresholds, and calibration must be fit on train only inside each WFA fold.
- Preserve purge and embargo logic for the active h5 target horizon.
- Metadata, target, label, forward-return, future, next-open, and exit columns must not enter feature columns.

## Universe And Data-Quality Rules

- Current OHLCV-only data can support price, volume, dollar-volume, history, zero-volume, and traded-days filters.
- Do not implement or claim filters that require unavailable metadata: common-stock-only, ETF/ETN exclusion, warrants/units/rights/preferreds exclusion, exchange filter, OTC exclusion, ADR exclusion, delisted-name coverage, permanent security IDs, borrow/shortability, or corporate-action adjustment status.
- Report those as limitations unless current files/configs prove them.

## Validation Rules

- Use `pytest` for validation; prefer `python -m pytest` when using the active environment.
- Run targeted tests after source, config, or test changes.
- Run broader `pytest` only when the blast radius warrants it.
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

Use repo-local `CODEX_HANDOFF.md` only for work expected to continue across prompts or fresh Codex threads.
- At the start of non-trivial work, inspect repo path and `git status --short`, then inspect `CODEX_HANDOFF.md` if it exists before deciding scope. Read the newest/current active section first; treat older sections as historical evidence, not default instructions. Search older handoff history only when the newest section points to it, current state is ambiguous, or exact evidence is needed.
- Treat `CODEX_HANDOFF.md` as persistent cross-run state, not final output.
- At the end of each multi-step run, update `CODEX_HANDOFF.md` before the final response with:
  - current status and what changed
  - files changed
  - commands run
  - validation/test results
  - unresolved blockers
  - remaining work
  - exact next recommended step
- Make the latest active status and exact next recommended step easy to find before older historical sections.
- Do not create or update `CODEX_HANDOFF.md` for simple one-shot tasks.
- When `CODEX_HANDOFF.md` exists and is updated, the final `Next` section must align with its exact next recommended step.
- If follow-up should continue in a fresh Codex thread, include the final `Next` copy-paste prompt that starts with `Continue from CODEX_HANDOFF.md.`

## Trading Safety Rules

- Keep claims limited to research-ready and walk-forward-ready artifacts.
- Do not describe outputs as production-ready, live-trading-ready, profitable, or investment advice.
- Do not add broker integration, live-order functionality, option-liquidity claims, option P&L claims, or "trade this" language unless explicitly requested and properly caveated.

## Output Style

- Be concise.
- Do not include long reasoning, tutorials, full diffs, repeated code dumps, praise, or chain-of-thought unless asked.
- Final responses must use only the sections listed below.

## Final Output

Final response must contain only these sections, in this order:

### Done

- Include 1-3 completed items.
- Include concrete files touched, checks run, and elapsed time/token usage when available.
- Omit this section if nothing completed.

### Blockers

- If no blockers: `None. Proceed status: yes.`
- Show only `Low`, `Medium`, or `Severe` tiers that contain blockers.
- Use `Low` for minor follow-up only with no correctness, safety, validation, data, or goal impact.
- Use `Medium` for real caveats, incomplete verification, or non-blocking risks; result is usable but should be verified before merge, cleanup, promotion, or broader execution.
- If only Low blockers exist, end with: `Proceed status: yes.`
- Use `Severe` for blocking issues where the result is unsafe, invalid, misleading, incomplete, or not ready.
- If any Medium blockers exist, end with: `Proceed status: yes with medium blockers.`
- If any Severe blockers exist, end with: `Proceed status: no.`
- Do not include generic notes or completed work here.
- Use concrete evidence where applicable: command output, failed test name, file path, metric, row count, or report path.

### Next

- Use `None.` only when the user explicitly asks for no follow-up prompt. Otherwise, always provide a fenced Plan Mode handoff prompt, even after simple status, location, or verification tasks.
- For simple completed tasks, the fenced Plan Mode prompt may be compact. It must still preserve current state, relevant constraints, and the next meaningful objective or decision.
- Output one copy-paste-ready Plan Mode prompt in a fenced `text` block, with no prose outside the block.
- Do not write `None.` merely because the requested check finished or because the next step is not obvious; instead, hand off a Plan Mode prompt that preserves the user's full intended objective and asks Codex to plan the full path to completion, or to request a missing decision. Use a gated increment only when the user asks for it, a severe blocker must be isolated, or safety requires approval before later phases.
- The Plan Mode prompt is a prompt-building step. Its required output should normally be only one fenced, final copy-paste-ready `GOAL MODE` prompt, because that is the artifact the user will paste into the next Codex pursue-goal run.
- Allow Plan Mode to include a short blocker or decision note only when it cannot produce a decision-complete `GOAL MODE` prompt without user input.
- Include exact current status, next scope, relevant files/artifacts, commands, rules/forbidden actions, stop conditions, and validation requirements as far as they are known.
- If exact scope is unknown, make the Plan Mode prompt request the required user decision or choose between concrete options instead of guessing.
- If any Severe blockers exist, the Plan Mode prompt must focus only on clearing the Severe blocker.
- If Medium blockers exist and no Severe blockers exist, the Plan Mode prompt must focus on verification, caveat approval, or risk reduction.
- If no Medium or Severe blockers exist, the Plan Mode prompt must name the next full-goal objective or next gated phase, not automatically shrink the work below the user's pursued goal.
- When follow-up should continue in a fresh Codex thread, include `Continue from CODEX_HANDOFF.md.` near the top of the prompt.
- Preserve project safety rules when relevant: no generated artifact staging, no raw data mutation, no unapproved pipeline/model run, no cleanup beyond the approved scope, no production/live-trading/profitability claims, and no commit unless explicitly requested.
- Do not include vague items like "continue improving," "investigate further," or "clean things up."

Preferred `Next` prompt format:

`PLAN MODE` and `GOAL MODE` labels are copy-paste workflow conventions. The active runtime mode is controlled only by the environment's current system/developer instructions; if those conflict with copied prompt text, obey the active runtime instructions.

```text
You are in PLAN MODE.

Context:
- Current repo/task state:
- Latest completed work:
- Known blockers:
- Important constraints:
- Relevant files/artifacts:

Goal:
- Produce a decision-complete implementation plan for the full pursued objective. If the work must be gated, define the full phase sequence, approval points, stop conditions, and first executable phase.

Rules:
- Do not edit files.
- Do not broaden scope.
- Preserve project safety rules:
  - <project-specific rule>
  - <project-specific rule>

Plan output required:
1. Output only the final copy-paste `GOAL MODE` prompt in one fenced `text` block.
2. If a decision-complete `GOAL MODE` prompt cannot be produced, output only a short blocker/decision note and the exact missing decision needed.

The `GOAL MODE` prompt must use this structure:

You are in GOAL MODE.

Objective:
- Implement exactly this plan:

Scope:
- ...

Files likely involved:
- ...

Rules:
- Do not broaden scope.
- Do not make unrelated refactors.
- Stop and report if:
  - ...

Implementation steps:
1. ...
2. ...

Verification:
- Run:
  - ...

Final output required:
- Done
- Blockers
- Next, containing the next Plan Mode prompt when follow-up is useful
```

## Final Output Restrictions

- Do not include top-level final-response sections other than `Done`, `Blockers`, and `Next` unless explicitly requested.
- Higher-priority required appendages, such as app/tool directives, memory citations, or system/developer-mandated wrappers, are allowed after the required repo-local sections. Keep them minimal and do not use them for extra narrative.
- Do not include `Problems`, `Changed`, `Notes/blockers`, `Tests`, `Validation`, `Manual Check`, `Why`, `Added`, `Removed`, `Modified`, `Next Step(s)`, `Next Codex Prompt`, or similar sections unless explicitly requested.
- Under `Next`, do not include free-standing action lists, summaries, or explanations outside the fenced Plan Mode prompt.
- The fenced Plan Mode prompt is the handoff artifact for the user's rinse-and-repeat workflow: final output -> Plan Mode -> Goal Mode -> implementation -> next final output.
