# ADR-014 — Daily loss includes unrealized equity changes

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Realized-only limits ignore current open losses; a fixed EUR limit can exceed 3% of reduced equity.

## Decision

Use realized plus unrealized flow-adjusted equity loss from session start with ceiling 3% times min(start,current equity), remaining headroom and a session latch.

## Rationale

Conservatively satisfies current-equity intent and prevents profits enlarging the ceiling.

## Consequences

Exact crossing from EUR50 is slightly below EUR1.50; FX/fees matter; reset only at verified session boundary.

## Alternatives considered

Realized-only, fixed start-equity 3%, trailing peak equity drawdown.

## Conditions for revisiting

Any change needs owner risk review, formulas, stress comparisons and Risk History; no return-driven silent tuning.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/Risk Engine]]. Index: [[00 - Project/Decisions/ADRs]].
