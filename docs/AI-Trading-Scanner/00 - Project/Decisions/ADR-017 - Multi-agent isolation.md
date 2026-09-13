# ADR-017 — Multi-agent isolation

- Status: ACCEPTED as extension design policy; no implementation or validated trading result.
- Date: 2026-09-13.

## Context

Concurrent participants need independent results even when using the same feed.

## Decision

Isolate agent/allocation/run decisions, accounting, orders and metrics; share immutable market data only. Use a fenced writer per funding account.

## Rationale

Stops state, cash and scheduling contamination without duplicating provider integrations.

## Consequences

Parent-account integrity locks may affect all funded agents; independent account locks remain independent. Shared broker attribution requires certification.

## Alternatives considered

One global portfolio; an LLM instance as the agent identity; shared mutable strategy state.

## Conditions for revisiting

Revisit physical deployment after measured scale, retaining logical and permission isolation.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Agent Architecture]]. Index: [[00 - Project/Decisions/ADRs]].
