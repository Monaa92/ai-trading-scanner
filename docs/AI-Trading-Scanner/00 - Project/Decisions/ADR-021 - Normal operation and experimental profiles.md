# ADR-021 — Normal operation and experimental profiles

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

EUR50 trials should test a reusable engine, not define all future account sizes.

## Decision

Treat EUR50/initial risk limits as an experiment profile; normal operation uses validated configurable capital/currency/risk/strategy/mode and auditable effective segments.

## Rationale

Shares core correctness while distinguishing frozen science from deliberate operational changes.

## Consequences

Initial limits/fixed exits stay unchanged. No general profile is activated; increases are owner-controlled, not agent actions.

## Alternatives considered

Capital-specific code; all modes permanently frozen; mutable unversioned normal settings.

## Conditions for revisiting

Revisit supported profile scope after tests and readiness at the proposed scale.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Portfolio Accounting/Capital Allocation]]. Index: [[00 - Project/Decisions/ADRs]].
