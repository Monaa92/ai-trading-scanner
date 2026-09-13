# ADR-016 — Session-reset indicator initialization

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Unspecified overnight initialization makes nominally identical indicators produce different signals.

## Decision

V1 EMA/RSI/ATR reset each RTH session with documented seeds; VWAP/extrema use complete session prefixes.

## Rationale

An explicit simple baseline is reproducible and avoids mixing split/overnight price conventions.

## Consequences

EMA50 needs 50 valid five-minute bars and sharply limits early opportunities; missing prefixes disable session aggregates.

## Alternatives considered

Continuous RTH history, extended-hours smoothing, provider-calculated indicators.

## Conditions for revisiting

Test continuous-state alternatives only as registered strategy versions with causal corporate-action handling and comparisons.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[02 - Agents & Strategies/Shared Agent Rules/Indicators]]. Index: [[00 - Project/Decisions/ADRs]].
