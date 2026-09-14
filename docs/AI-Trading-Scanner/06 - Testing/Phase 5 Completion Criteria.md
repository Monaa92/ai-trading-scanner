# Phase 5 completion criteria

Status: **IMPLEMENTED AND LOCALLY VERIFIED; INDEPENDENT RISK-CRITICAL REVIEW REQUIRED.**

Phase 5 is complete only when the exact candidate satisfies this invariant: given an immutable trade proposal, authoritative parent/allocation state, deterministic risk configuration and explicit time, it can deterministically reject or size the proposal, atomically reserve both ownership scopes, and fail closed without I/O or order submission.

| Criterion | Candidate evidence |
| --- | --- |
| Typed ownership | Stable account, agent, allocation, risk, sizing, reservation, lock and approval-binding identities |
| Exact arithmetic | Decimal-only capital/risk/quantity values; float/non-finite/negative rejection; downward generic-increment sizing |
| Versioned risk | Content-identified `BASELINE_RESEARCH_V1`, explicitly research-only and unvalidated; LIVE cannot be configured |
| Structured decision | Immutable `APPROVED_FOR_RESERVATION` or `REJECTED` with canonical reason codes and evaluated revisions/limits |
| Proposal binding | Decisions bind exact Phase 4 proposal; exact final quantity cannot be silently resized |
| Approval boundary | Manual reservation requires externally supplied binding to proposal, sizing, quantity, mandate, configuration, dimensions and validity |
| Atomic reservation | Parent then allocation locks; current state revalidated; both immutable replacement snapshots and reservation publish together or none do |
| Isolation/capacity | Agent ownership and parent aggregate capacity checked; no peer allocation borrowing or negative capital |
| Lifecycle | ACTIVE → RELEASED/CONSUMED/EXPIRED; same terminal request idempotent; conflicting transition rejected |
| Conservation | Every parent/allocation snapshot preserves total = available + active reserved + committed |
| Scoped safety | Parent locks propagate; allocation/agent locks remain local; lock/reserve race cannot destroy existing reservations |
| Scope boundary | No order, broker, fill, provider, AI, portfolio P&L, external API or durable database implementation |

Candidate verification on 2026-09-14: 371 total tests passed, comprising the preserved 303 Phase 1–4 cases and 68 focused Phase 5 cases. The focused suite includes real barrier-coordinated threads for same-agent capacity, shared-parent capacity, duplicate proposal, release/reserve and lock/reserve races. Ruff lint/format and strict mypy pass. Package build, source and isolated installed-package health, lock validation, security/scope scans, whitespace, ADR fields and documentation links also pass locally. A remote candidate/fresh-clone result is not recorded because review-branch creation was blocked before commit.

Known limitation: `InMemoryCapitalCoordinator` is correct only within one process. It is not crash-durable, does not coordinate multiple workers, and does not replace the future transactional ledger/outbox. `committed_capital` is a reservation lifecycle state, not evidence of an order, fill or position.

See [[01 - Architecture/Risk Engine]], [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[01 - Architecture/Portfolio Accounting/Position Sizing]] and [[06 - Testing/Phase 5 Independent Review]].
