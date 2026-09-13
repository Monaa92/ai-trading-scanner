# ADR-027 — Versioned transaction costs in decisions

- Status: ACCEPTED as experiment and accounting policy; numeric fee profiles remain unset.
- Date: 2026-09-13.

## Context

Small-capital strategies can appear attractive before commissions, spread, slippage, exchange fees and FX.

## Decision

Require a versioned round-trip cost estimate before every trade proposal, reject insufficient expected net edge and preserve resolved cost assumptions with every run.

## Rationale

Net economics, not gross movement, determines whether an opportunity is executable.

## Consequences

Experiment 1 cannot start until `SIMULATED_IBKR_US_TIERED` has sourced values. Historical results never adopt a newer fee profile automatically.

## Alternatives considered

Deduct costs only after fills; hardcode fees in strategies; waive fees for EUR 50.

## Conditions for revisiting

Revise through a new cost-profile version and rerun controlled comparisons.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[04 - Costs & Economics/Transaction Costs]]. Index: [[00 - Project/Decisions/ADRs]].
