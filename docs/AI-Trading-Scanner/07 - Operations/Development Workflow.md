# Development workflow

Read [PROJECT_RULES](../../PROJECT_RULES.md), [[01 - Architecture/System Architecture]], relevant domain notes and ADRs first. Inspect complete Git status, existing user changes and current code before editing. Preserve unrelated work. Graphify is **not verified installed/configured**; when available, use its architecture/code graph as additional evidence and check it against source. Otherwise use file/import/call searches; graph tooling is not a gate to ordinary work.

Target sequence for a future authorized implementation task:

`requirement → docs → source/graph inspection → scoped branch → implementation → tests → applicable backtest/regression/comparison → docs/history/ADR updates → complete diff review → independent review where required → authorized commit → authorized push → authorized PR`

Use `codex/` branch prefix unless the owner specifies another name. Do not create branches/commits/pushes/PRs for this initial documentation pass. Later commit/push/PR steps only occur when explicitly authorized; a workflow diagram is not authorization.

Define the change class before implementation: documentation, refactor preserving behavior, material strategy, risk-critical, AI or architecture. [[06 - Testing/Test Strategy]] specifies checks. Material strategy versions/changelog and controlled comparisons are mandatory once the backtester exists. Risk and AI histories are additional, not substitutes. Architecture changes require ADRs and a contradiction check against canonical specifications.

Risk-critical scope includes data/time semantics, indicators feeding decisions, strategy timing, cash/FX/sizing, limits, fill models, order idempotency, protection, reconciliation, persistence, secrets/mode and AI authority. Require independent competent review of invariants, adversarial cases and evidence before merging. A one-line risk change is not low risk just because the diff is small.

Review the full diff including newly created/untracked files, report actual checks, failed/unrun tests and unknown assumptions, and state whether evidence supports the claimed change. Never hide a rejected experiment. Keep operation/config values out of code magic numbers; runtime activation is a separate reviewed configuration event.
