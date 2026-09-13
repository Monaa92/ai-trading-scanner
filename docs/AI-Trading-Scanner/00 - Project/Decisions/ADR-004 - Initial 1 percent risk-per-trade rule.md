# ADR-004 — Initial 1 percent risk-per-trade rule

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

The owner specifies a small initial EUR50 experiment.

## Decision

Cap modeled entry loss at 1% of current conservative account equity, also bounded by daily headroom and cash.

## Rationale

An explicit deterministic budget is auditable and cannot be overridden by opportunity scores.

## Consequences

Initially about EUR0.50; costs/minima can force no trade; actual gap losses may exceed modeled risk.

## Alternatives considered

Fixed EUR risk, optimized risk fraction, volatility-only capital allocation.

## Conditions for revisiting

Revisit only as an explicit material risk change with owner review, stress evidence and risk-history entry.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/Portfolio Accounting/Position Sizing]]. Index: [[00 - Project/Decisions/ADRs]].
