# ADR-015 — Durable intents and capability-gated protection

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Ambiguous broker responses and fractional partial fills can create duplicate or unprotected exposure.

## Decision

Commit risk/reservation/intent/audit/outbox before entry submission; reconcile unknown outcomes; block paper entries without verified fractional protection/liquidation.

## Rationale

Keeps recoverable authorization and avoids inferring safety from generic provider support.

## Consequences

Stable client IDs are necessary but not magic exactly-once execution; no blind retry or automatic synthetic-stop fallback.

## Alternatives considered

Submit-then-log, optimistic retry, client-side stop by default.

## Conditions for revisiting

Revisit protective mechanism only through separate reviewed capability tests/ADR; durability and no-duplicate principles remain.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/Execution/Order Lifecycle]]. Index: [[00 - Project/Decisions/ADRs]].
