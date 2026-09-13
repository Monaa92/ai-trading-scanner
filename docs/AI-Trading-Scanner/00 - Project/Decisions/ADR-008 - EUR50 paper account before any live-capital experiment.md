# ADR-008 — EUR50 paper account before any live-capital experiment

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

The owner wants a small-capital feasibility test before risking real funds.

## Decision

Use a EUR50-equivalent internally cash-constrained simulation and paper phase before any live consideration.

## Rationale

Exposes fractional/minimum/cost/FX constraints and operational defects before capital risk.

## Consequences

Paper balance cannot enlarge the overlay; paper success alone does not authorize live; 300 trades alone insufficient.

## Alternatives considered

Start live immediately, use unrestricted large paper buying power.

## Conditions for revisiting

Revisit initial paper allocation only through recorded risk/research review; live always requires separate gate and authorization.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[06 - Testing/Paper Trading]]. Index: [[00 - Project/Decisions/ADRs]].
