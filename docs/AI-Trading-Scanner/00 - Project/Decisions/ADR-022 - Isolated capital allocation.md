# ADR-022 — Isolated capital allocation

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Several agents cannot each spend the same broker balance.

## Decision

Maintain attributed allocation ledgers and unallocated capital; atomically validate agent and parent constraints and balanced transfers.

## Rationale

Prevents double allocation and hidden cross-subsidy.

## Consequences

Separate virtual EUR50 accounts are experimental replicates; real shared funding must partition actual capacity. No ambiguous same-symbol netting initially.

## Alternatives considered

Give each agent full broker buying power; silently lend idle peer cash.

## Conditions for revisiting

Shared-account capabilities may expand only after attribution, protection and concurrency review.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Portfolio Accounting/Capital Allocation]]. Index: [[00 - Project/Decisions/ADRs]].
