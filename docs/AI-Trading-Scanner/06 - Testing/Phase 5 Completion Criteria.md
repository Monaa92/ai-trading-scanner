# Phase 5 completion criteria

Status: **ORIGINAL CANDIDATE CHANGES REQUIRED; REMEDIATION CANDIDATE RE-REVIEW REQUIRED.**

Phase 5 is complete only when the exact candidate satisfies this invariant: given an immutable trade proposal, authoritative parent/allocation state, deterministic risk configuration and explicit time, it can deterministically reject or size the proposal, atomically reserve both ownership scopes, and fail closed without I/O or order submission.

| Criterion | Candidate evidence |
| --- | --- |
| Typed ownership | Stable account, agent, allocation, risk, sizing, reservation, lock and approval-binding identities |
| Exact arithmetic | Decimal-only capital/risk/quantity/equity/loss/headroom values; float/non-finite/negative rejection; self-consistent sizing equalities; downward generic-increment sizing |
| Versioned risk | Content-identified `BASELINE_RESEARCH_V1`, explicitly research-only and unvalidated; LIVE cannot be configured |
| Structured decision | Immutable `APPROVED_FOR_RESERVATION` or `REJECTED` with canonical reason codes, evaluated revisions/limits and content-identified safety/loss evidence |
| Proposal binding | Decisions bind exact Phase 4 proposal; exact final quantity cannot be silently resized |
| Approval boundary | Manual reservation requires externally supplied binding to proposal, sizing, quantity, mandate, configuration, dimensions and validity |
| Atomic reservation | Proposal guard then parent then allocation locks; current capital, authority, loss, lock and outstanding-downside state revalidated; both immutable replacement snapshots and reservation publish together or none do |
| Isolation/capacity | Agent ownership, parent aggregate capacity and proposal-wide uniqueness checked; no peer allocation borrowing, duplicate economic intent or negative capital |
| Lifecycle | ACTIVE → RELEASED/CONSUMED-before-expiry/EXPIRED; active replay revalidates and deadline equality expires; same terminal request idempotent; conflicting transition rejected |
| Conservation | Every parent/allocation snapshot preserves total = available + active reserved + committed |
| Scoped safety | Parent locks propagate; allocation/agent locks remain local; lock/reserve race cannot destroy existing reservations |
| Scope boundary | No order, broker, fill, provider, AI, portfolio P&L, external API or durable database implementation |

Original candidate verification on 2026-09-14: 371 total tests passed, comprising 303 Phase 1–4 cases and 68 focused Phase 5 cases. Independent review nevertheless returned CHANGES REQUIRED because that suite missed substantive adversarial paths. The replacement adds 27 targeted cases (95 focused Phase 5; 398 total). The exact replacement workspace passes the full suite, both test splits, Ruff lint/format, strict mypy, lock verification, package build, source and isolated installed-wheel health, credential/coupling scans, whitespace, all 32 ADR fields and all internal documentation links. Counts and automated gates do not override the still-required independent re-review.

Known limitation: `InMemoryCapitalCoordinator` is correct only within one process and coordinator instance. It is not crash-durable, does not coordinate multiple workers, and does not replace the future transactional ledger/outbox. `committed_capital` is a reservation lifecycle state, not evidence of an order, fill or position; its modeled downside remains conservatively unavailable until a future position lifecycle can close/reconcile it.

See [[01 - Architecture/Risk Engine]], [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[01 - Architecture/Portfolio Accounting/Position Sizing]] and [[06 - Testing/Phase 5 Independent Review]].
