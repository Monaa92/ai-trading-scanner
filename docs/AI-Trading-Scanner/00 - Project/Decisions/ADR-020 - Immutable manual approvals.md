# ADR-020 — Immutable manual approvals

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

A user decision must not authorize a different or stale trade.

## Decision

Bind consent to immutable proposal/version/hash and exact mandate; changed material terms require fresh consent. Revalidate risk/safety before intent and dispatch.

## Rationale

Makes APPROVE/REJECT sufficient while preserving deterministic safety.

## Consequences

Pending consent holds no capital; final reservation can fail. No manual-to-auto fallback; emergency/protective exits retain bounded mandate.

## Alternatives considered

Approval of an instrument alone; pre-reserved indefinite proposals; trusting UI approval flags.

## Conditions for revisiting

Revisit consent envelope only through explicit versioned semantics and race/expiry tests.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Execution/Approval Workflow]]. Index: [[00 - Project/Decisions/ADRs]].
