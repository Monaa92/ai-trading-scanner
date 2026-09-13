# ADR-011 — Provider abstractions for market data broker and AI

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

The strategy must survive provider replacement and offline tests.

## Decision

Define inward-facing ports with adapter implementations, typed errors and capability snapshots.

## Rationale

Removes SDK/network dependencies from deterministic core.

## Consequences

Raw provider evidence is retained; unsupported capabilities fail closed instead of leaking provider quirks into strategy.

## Alternatives considered

Direct SDK calls from strategy/risk, provider-specific shared domain objects.

## Conditions for revisiting

Revisit interface granularity when concrete integration reveals gaps, retaining dependency direction.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/System Components]]. Index: [[00 - Project/Decisions/ADRs]].
