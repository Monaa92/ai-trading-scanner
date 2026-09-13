# ADR-018 — Explicit execution dimensions

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Automation, simulation/live environment and experimental intent are different permissions.

## Decision

Separate data/run mode, SIMULATION/PAPER/LIVE execution environment, SIGNAL_ONLY/ORDER_ENABLED submission mode, MANUAL_APPROVAL/FULL_AUTO approval policy and NORMAL/EXPERIMENT context. AUTONOMOUS_EXPERIMENT is an experiment type with its own frozen manifest.

## Rationale

Prevents auto mode from implying live access or bypassing risk.

## Consequences

SIGNAL_ONLY cannot dispatch; FULL_AUTO only omits human trade approval. LIVE remains disabled; live autonomy needs distinct owner authorization. Existing records using the earlier combined labels require an explicit migration mapping and are never interpreted by string similarity.

## Alternatives considered

A single paper/live/auto enum; implicit automatic fallback.

## Conditions for revisiting

New combinations require scoped capability/readiness evidence and owner-approved ADR.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Execution/Execution Modes]]. Index: [[00 - Project/Decisions/ADRs]].
