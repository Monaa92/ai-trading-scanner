# ADR-019 — Frozen autonomous experiment configurations

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Unrecorded agent changes invalidate fair survival and AI comparisons.

## Decision

Freeze participant starting allocations and strategy/risk/AI/management/execution manifests. Only preregistered bounded adaptation may evolve state.

## Rationale

Preserves interpretable comparable paths and negative results.

## Consequences

Emergency interventions are retained/protocol-assessed; new configs require new runs. The four Experiment 1 strategy profiles remain unvalidated and their exact parameters/model assignments require registration.

## Alternatives considered

Agents optimize themselves without a fixed protocol; reset losing runs.

## Conditions for revisiting

Revisit adaptive protocols prospectively with validation, never rewrite observed conditions.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[03 - Experiments/Autonomous Experiments]]. Index: [[00 - Project/Decisions/ADRs]].
