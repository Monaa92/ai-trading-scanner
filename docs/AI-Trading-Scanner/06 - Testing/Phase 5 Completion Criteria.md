# Phase 5 completion criteria

Status: **TWO CANDIDATES RECEIVED CHANGES REQUIRED; SECOND REMEDIATION RE-REVIEW REQUIRED.**

Phase 5 is complete only when the exact candidate satisfies this invariant: given an immutable trade proposal, authoritative parent/allocation state, deterministic risk configuration and explicit time, it can deterministically reject or size the proposal, atomically reserve both ownership scopes, and fail closed without I/O or order submission.

| Criterion | Candidate evidence |
| --- | --- |
| Typed ownership | Stable account, agent, allocation, risk, sizing, reservation, lock and approval-binding identities |
| Exact arithmetic and provenance | Decimal-only capital/risk/quantity/equity/loss/headroom values; float/non-finite/negative rejection; self-consistent sizing equalities; sizing embeds and validates the immutable proposal/risk configuration; downward generic-increment sizing |
| Versioned risk | Content-identified `BASELINE_RESEARCH_V1`, explicitly research-only and unvalidated; LIVE cannot be configured |
| Structured decision | Immutable `APPROVED_FOR_RESERVATION` or `REJECTED` with canonical reason codes, evaluated revisions/limits and content-identified safety/loss evidence |
| Proposal binding | Decisions bind exact Phase 4 proposal; exact final quantity cannot be silently resized |
| Approval boundary | Manual reservation requires externally supplied binding to proposal, sizing, quantity, mandate, configuration, dimensions and validity |
| Atomic reservation | Proposal guard then parent then allocation locks; current capital, authority, scoped/fresh loss evidence, lock and outstanding-downside state revalidated; both immutable replacement snapshots and reservation publish together or none do |
| Isolation/capacity | One registered allocation per agent/coordinator context, parent aggregate capacity and proposal-wide uniqueness checked; no fragmented agent limits, peer allocation borrowing, duplicate economic intent or negative capital |
| Lifecycle | ACTIVE → RELEASED/CONSUMED-before-expiry/EXPIRED; active replay revalidates and deadline equality expires; same terminal request idempotent; conflicting transition rejected |
| Conservation | Every parent/allocation snapshot preserves total = available + active reserved + committed |
| Scoped safety | Parent locks propagate; allocation/agent locks remain local; lock/reserve race cannot destroy existing reservations |
| Scope boundary | No order, broker, fill, provider, AI, portfolio P&L, external API or durable database implementation |

Original candidate verification on 2026-09-14: 371 total tests passed, comprising 303 Phase 1–4 cases and 68 focused Phase 5 cases. Independent review nevertheless returned CHANGES REQUIRED because that suite missed substantive adversarial paths. The replacement adds 27 targeted cases (95 focused Phase 5; 398 total). The exact replacement workspace passes the full suite, both test splits, Ruff lint/format, strict mypy, lock verification, package build, source and isolated installed-wheel health, credential/coupling scans, whitespace, all 32 ADR fields and all internal documentation links. Counts and automated gates do not override the still-required independent re-review.

Independent re-review of replacement `7ea3dc007e212d9f391bb6cc4e9b36139d005322` also returned CHANGES REQUIRED: same-agent limits fragmented across multiple allocations; sizing evidence could be coherently reidentified while retaining false proposal/configuration attribution; and loss evidence lacked scope/session/time attribution. The second remediation enforces one registered allocation per agent/coordinator context, embeds self-validating source proposal/configuration objects in sizing evidence, derives allowed risk from those immutable inputs, and versions loss/safety evidence with explicit scope, session, observation/effective/validity time and monotonic revision. It adds 21 focused cases for sequential/concurrent registration, limit-fragmentation prevention, lifecycle persistence, coherent forgery, JSON reconstruction, scope misuse, previous/future/stale sessions, causal timestamp/revision regression and final freshness revalidation.

Final second-remediation verification on 2026-09-14: 419 total tests passed, comprising 303 Phase 1–4 regression cases and 116 focused Phase 5 cases. Ruff lint and format, strict mypy, lock verification, offline source build, source health, fresh isolated offline wheel installation and installed-package health all passed. A separate 100-iteration same-agent concurrent-registration stress probe passed. The non-ignored repository secret scan found zero high-confidence credential/private-key patterns; forbidden coupling tests, whitespace validation, all 32 ADR required fields, 608 Obsidian wikilinks and 92 relative Markdown links passed with zero unresolved links. Automated evidence does not replace independent competent re-review of the exact new commit.

Known limitation: `InMemoryCapitalCoordinator` is correct only within one process and coordinator instance. It is not crash-durable, does not coordinate multiple workers, and does not replace the future transactional ledger/outbox. `committed_capital` is a reservation lifecycle state, not evidence of an order, fill or position; its modeled downside remains conservatively unavailable until a future position lifecycle can close/reconcile it.

See [[01 - Architecture/Risk Engine]], [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[01 - Architecture/Portfolio Accounting/Position Sizing]] and [[06 - Testing/Phase 5 Independent Review]].
