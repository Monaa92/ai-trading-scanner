# ADR-025 — Broker-agnostic execution boundary

- Status: ACCEPTED as architecture policy; no adapter implementation or broker connection.
- Date: 2026-09-13.

## Context

Agents must remain strategy-focused while providers differ in order, account and capability semantics.

## Decision

Agents emit provider-neutral decisions. Only the execution coordinator calls a versioned BrokerAdapter after risk, authority and safety checks; market data remains a separate normalized layer.

## Rationale

One controlled boundary prevents provider logic and credentials from entering agents and makes capability failure auditable.

## Consequences

Adapters cannot choose environment or authority. Unknown/unsupported capability fails before submission. Agent/allocation identity is mandatory for idempotency and reconciliation.

## Alternatives considered

Direct agent SDK calls; broker-specific strategies; one interface combining market data and execution.

## Conditions for revisiting

Revisit only if a verified provider constraint cannot be represented without weakening safety or isolation.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[01 - Architecture/Broker Architecture]]. Index: [[00 - Project/Decisions/ADRs]].
