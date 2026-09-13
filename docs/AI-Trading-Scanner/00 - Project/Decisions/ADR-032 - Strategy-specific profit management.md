# ADR-032 — Strategy-specific profit management

- Status: ACCEPTED as architecture policy; dynamic management remains unimplemented and unvalidated.
- Date: 2026-09-13.

## Context

A universal profit cap can truncate momentum/breakout gains, while unconstrained downside changes can violate safety.

## Decision

Do not impose a reusable-engine profit cap. Keep fixed stop/fixed target as the baseline; version and validate future strategy-specific exits separately under central hard downside controls and immutable amendment approval.

## Rationale

Upside management belongs to the strategy hypothesis; the Risk Engine owns the mandatory safety envelope.

## Consequences

Agents may propose only registered actions and cannot weaken protection. Material entry/stop/target/quantity/mandate changes invalidate manual approval. Lifecycle metrics include MFE, MAE and profit giveback.

## Alternatives considered

Universal take-profit percentage; agent-controlled risk weakening; activate dynamic exits without baseline comparison.

## Conditions for revisiting

Only comparative causal evidence, capability/failure tests and applicable approval may activate a management policy.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Execution/Trade Management]]. Index: [[00 - Project/Decisions/ADRs]].
