# ADR-007 — Material strategy changes require comparative validation

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Uncontrolled changes can produce unsupported improvement claims.

## Decision

Once a functioning backtester exists, compare every material change with the previous accepted version under identical conditions; before first acceptance use the registered initial baseline and disclose no accepted predecessor.

## Rationale

Paired evidence distinguishes changes from shifting data/model assumptions.

## Consequences

Version/changelog required; rerun both versions if infrastructure changes; retain rejected results.

## Alternatives considered

Informal visual comparison, only current-version results, win-rate-only acceptance.

## Conditions for revisiting

Method details may evolve through documented validation, but quantitative comparable evidence remains mandatory.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[03 - Experiments/Experiment Framework]]. Index: [[00 - Project/Decisions/ADRs]].
