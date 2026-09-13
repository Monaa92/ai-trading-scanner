# ADR-009 — Deterministic calculations are authoritative over AI

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Indicators, accounting and risk require reproducible numeric semantics.

## Decision

Compute authoritative features, ledger, risk and metrics deterministically; AI can only consume their snapshots.

## Rationale

Prevents hallucinated numbers from changing financial state.

## Consequences

Indicator implementation versions and input lineage are required; AI explanations cannot replace calculations.

## Alternatives considered

LLM-calculated indicators or AI corrections to account balances.

## Conditions for revisiting

Implementation algorithms may change with versioned fixtures/comparisons; authoritative deterministic boundary remains.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[02 - Agents & Strategies/Shared Agent Rules/Indicators]]. Index: [[00 - Project/Decisions/ADRs]].
