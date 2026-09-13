# ADR-006 — Alpaca as initial market-data and paper-trading provider

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

The requested initial provider offers documented data and paper interfaces.

## Decision

Plan Alpaca adapters first, behind provider-neutral contracts; do not integrate in this pass.

## Rationale

Matches the proposed stack while preserving replacement options.

## Consequences

Account entitlements, fractional protection, costs and feed quality remain unverified; official docs are not successful contract tests.

## Alternatives considered

Other brokers/providers or simulator-only development.

## Conditions for revisiting

Revisit if coverage, eligibility, protection, economics or reliability fail requirements.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[08 - Research/External References]]. Index: [[00 - Project/Decisions/ADRs]].
