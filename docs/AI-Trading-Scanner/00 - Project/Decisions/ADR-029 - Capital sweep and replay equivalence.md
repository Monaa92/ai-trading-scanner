# ADR-029 — Capital sweep and replay equivalence

- Status: ACCEPTED as experiment-design policy; sweep and replay are not implemented.
- Date: 2026-09-13.

## Context

Capital efficiency needs comparable EUR 50–1,000 arms, but repeated AI calls waste budget when capital cannot affect a decision.

## Decision

Treat capital as immutable experiment configuration; replay a decision artifact only under a versioned proof that portfolio/capital state cannot affect the decision. Otherwise require separate inference/run.

## Rationale

This preserves validity while enabling cost-efficient experimentation.

## Consequences

Every arm owns a separate ledger. MVC stores underlying metrics and uses no universal threshold. Coincidentally equal outputs do not prove equivalence.

## Alternatives considered

Always re-call AI; always reuse decisions; choose the largest or first profitable capital arm.

## Conditions for revisiting

Replay rules change only with new causal-dependency evidence, schema version and adversarial tests.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specifications: [[03 - Experiments/Capital Sweep]], [[03 - Experiments/Decision Replay]]. Index: [[00 - Project/Decisions/ADRs]].
