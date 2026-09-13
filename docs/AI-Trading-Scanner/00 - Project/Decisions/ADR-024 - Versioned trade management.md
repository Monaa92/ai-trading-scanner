# ADR-024 — Versioned trade management

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Dynamic exits change strategy outcomes and can create unprotected or excessive sell exposure.

## Decision

Keep fixed stop/target baseline; separately version/test/compare dynamic management and route amendments through risk/safety/mandate validation.

## Rationale

Allows controlled research without silently changing the baseline or giving AI risk authority.

## Consequences

No long stop widening; acknowledgement and cancellation races modeled; management hypothesis not activated by design.

## Alternatives considered

Unlogged stop adjustments; AI-direct exits; treat partial profit as authority for extra risk.

## Conditions for revisiting

Activate only after independent historical/capability/failure validation and applicable approval.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Execution/Trade Management]]. Index: [[00 - Project/Decisions/ADRs]].
