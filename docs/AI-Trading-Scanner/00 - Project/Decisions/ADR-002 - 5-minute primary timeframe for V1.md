# ADR-002 — 5-minute primary timeframe for V1

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

The trend-pullback hypothesis needs one authoritative decision interval.

## Decision

Use completed 5-minute RTH bars; higher-timeframe context is optional and causal.

## Rationale

A fixed interval simplifies deterministic fixtures while keeping intraday structure.

## Consequences

Five-minute OHLC cannot resolve many fill paths; execution may use finer data without changing the decision interval.

## Alternatives considered

One-minute decisions, tick strategies, hourly or daily primary signals.

## Conditions for revisiting

Revisit after data/latency and robustness studies; new strategy version required.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[06 - Testing/Backtesting]]. Index: [[00 - Project/Decisions/ADRs]].
