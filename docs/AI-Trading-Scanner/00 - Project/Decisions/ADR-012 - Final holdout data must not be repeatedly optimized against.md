# ADR-012 — Final holdout data must not be repeatedly optimized against

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Repeated inspection converts holdout data into development data.

## Decision

Seal final holdout; evaluate a frozen specification once for confirmation, log access, use fresh future data for subsequent confirmatory tuning.

## Rationale

Preserves the meaning of unseen evaluation.

## Consequences

Bug-diagnostic reruns remain disclosed, not fresh holdouts; all prompt/strategy trials retained.

## Alternatives considered

Repeated random splits or relabeling inspected data as untouched.

## Conditions for revisiting

Revisit split/embargo design prospectively only; never reset knowledge of inspected outcomes.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[08 - Research/Research Integrity]]. Index: [[00 - Project/Decisions/ADRs]].
