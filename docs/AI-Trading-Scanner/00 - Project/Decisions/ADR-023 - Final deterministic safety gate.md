# ADR-023 — Final deterministic safety gate

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Risk arithmetic alone does not authorize an order or guarantee current operational health.

## Decision

Require explicit safety preflight, approval policy and fresh risk/safety authority at transaction and dispatch for all modes.

## Rationale

Separates economic risk ownership from identity, environment, consent and health checks.

## Consequences

Safety references risk results instead of competing formulas; permission epochs constrain revocation races. In-flight ambiguity still requires reconciliation.

## Alternatives considered

UI-only checks; skip checks after approval; unrestricted automatic adapter access.

## Conditions for revisiting

Revisit interfaces with tests; safety and authority precedence remain mandatory.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Execution/Safety Gate]]. Index: [[00 - Project/Decisions/ADRs]].
