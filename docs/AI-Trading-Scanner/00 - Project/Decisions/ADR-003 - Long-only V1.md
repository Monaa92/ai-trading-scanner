# ADR-003 — Long-only V1

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Short execution introduces separate borrow, margin and risk assumptions.

## Decision

Allow only long cash-funded entries; prohibit shorts, options, CFDs, leverage and pyramiding in V1.

## Rationale

Concentrates validation on one position direction and explicit capital limits.

## Consequences

Reject excess sells and unsupported instruments; adverse long gaps still exist.

## Alternatives considered

Long/short symmetry or leveraged instruments.

## Conditions for revisiting

Revisit only with separate risk architecture, account capability evidence and owner-approved scope.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/Risk Engine]]. Index: [[00 - Project/Decisions/ADRs]].
