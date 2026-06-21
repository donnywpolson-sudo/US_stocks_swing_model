# Quant Project Daily Agents

## Repo Rules

- Do not commit raw or generated data; `data/**` and `reports/**` stay ignored.
- Scripts must be deterministic, repo-relative, and testable.
- Do not add labels, features, WFA, models, backtests, metrics, or gates unless explicitly asked.
- Use `pytest` for validation.

## Final output

This section overrides any earlier Output Format, Tests, Validation, Manual Check, Added/Removed/Modified, or reporting sections in this file.

Final output only, using exactly these sections in this order:

## Changed
* Files changed and concise purpose, or "None."

## Notes/blockers
* Remaining risks, blockers, preserved user work, failed checks if important, or important caveats.
* Write "None." if there are no meaningful notes/blockers.

## Next
* The single most useful next action, or "None."

## Metrics
* Elapsed time: report if available from the runtime or command wrapper; otherwise write "not available to agent".
* Token usage: report final token usage if available from Codex runtime/tool output; otherwise write "not available to agent".

Do not estimate or fabricate elapsed time or token usage.
Do not include Tests, Validation, Manual Check, Why, Added, Removed, or Modified sections unless explicitly requested.