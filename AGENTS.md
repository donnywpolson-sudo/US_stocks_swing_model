# Quant Project Daily Agents

## Repo Rules

- Do not commit raw or generated data; `data/**` and `reports/**` stay ignored.
- Scripts must be deterministic, repo-relative, and testable.
- Do not add labels, features, WFA, models, backtests, metrics, or gates unless explicitly asked.
- Use `pytest` for validation.

## Final output

This section overrides any earlier Output Format, Tests, Validation, Manual Check, Added/Removed/Modified, or reporting sections in this file.

Final output only, using exactly these sections in this order:

### Done

* One very simple bullet point stating what was done, or `None`.

### Problems

List only unresolved problems. Do not list completed work, confirmations, or normal caveats unless they affect the next step.

Low

* Minor follow-up only.
* No correctness, safety, validation, data, or goal impact.
* Work can continue.
* If none, write `None`.

Medium

* Real caveat, incomplete verification, or non-blocking risk.
* Result is usable, but should be verified before merge, cleanup, promotion, or broader execution.
* If none, write `None`.

Severe

* Blocking issue.
* Result is unsafe, invalid, misleading, incomplete, or not ready.
* Requires a fix, rerun, rollback, or user decision before continuing.
* If none, write `None`.

Rules:

* Do not include generic notes.
* Do not list completed work here.
* Do not call something Severe unless it prevents safe continuation.
* Use concrete evidence where applicable: command output, failed test name, file path, metric, row count, or report path.
* End with exactly one proceed line: `Proceed status: yes / yes with medium problems / no`.

### Next Step(s)

The `Next Step(s)` section must contain a copy-paste-ready Codex prompt for the next run.

Rules:

* Make it usable in a fresh Codex thread.
* Include exact scope, files, commands, stop conditions, and forbidden actions.
* Prefer one row, one approved batch, or one explicit user decision.
* If any Severe problem exists, the prompt must focus only on clearing that problem.
* If no Severe problems exist but Medium problems exist, the prompt must focus on verification, caveat approval, or risk reduction.
* If no Medium or Severe problems exist, the prompt must name the next forward-progress task.
* Do not include optional polish unless explicitly requested.
* Do not write vague items like "continue improving," "investigate further," or "clean things up."
* If no next work exists, write `None`.

Preferred prompt format:

```text
Continue from CODEX_HANDOFF.md.

Next selected scope: <one row, one approved batch, or one decision>.

Rules:
- <forbidden actions>
- <scope limits>
- <validation requirements>

Task:
- <exact action 1>
- <exact action 2>
- <exact action 3>

Stop when:
- <clear acceptance condition>
```

### Metrics

Elapsed time: <duration>
Token usage: <tokens>

Do not estimate or fabricate elapsed time or token usage.
If metrics are unavailable, write `not available to agent`.

## Final output restrictions

* Do not include a `Changed` section.
* Do not write `Notes/blockers`; write only `Problems`.
* Do not include a `Tests` section unless explicitly requested.
* Do not include any top-level section except `Done`, `Problems`, `Next Step(s)`, and `Metrics`.
* Project/local `AGENTS.md` files may add task-specific rules, but final responses must still include only `Done`, `Problems`, `Next Step(s)`, and `Metrics`.
