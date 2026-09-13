# ADR-013 — Causal hybrid backtesting and conservative ambiguity

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Vectorization alone cannot enforce account and execution chronology; OHLC does not reveal intrabar order.

## Decision

Use vectorized causal features and event-driven portfolio execution; eligible opens strictly follow submission plus latency; stop-first when ordering unknown.

## Rationale

Makes look-ahead and optimistic fill assumptions explicit and testable.

## Consequences

Discretization delays and unresolved paths must be reported; 1-minute/tick upgrades need versioned model comparisons.

## Alternatives considered

Same-close fills, unconstrained vectorized returns, optimistic target-first paths.

## Conditions for revisiting

Revisit with measured higher-resolution data and a new execution-model version, rerunning comparators.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[06 - Testing/Backtesting]]. Index: [[00 - Project/Decisions/ADRs]].
