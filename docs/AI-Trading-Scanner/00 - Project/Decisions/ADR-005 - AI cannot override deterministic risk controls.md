# ADR-005 — AI cannot override deterministic risk controls

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Optional AI output is not a reliable source of safety authorization.

## Decision

AI may rank or veto; every selected candidate still passes fresh deterministic risk controls.

## Rationale

Keeps authorization inspectable and independent of provider behavior.

## Consequences

No AI quantity/equity/stop/limit commands; malformed/late treatment responses veto new entry.

## Alternatives considered

LLM agents with broker tools or AI-defined safety thresholds.

## Conditions for revisiting

Safety precedence is invariant; revisiting interface details requires ADR/tests, not waiver of risk authority.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/AI Architecture]]. Index: [[00 - Project/Decisions/ADRs]].
