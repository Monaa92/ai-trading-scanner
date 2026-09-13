# ADR-010 — PostgreSQL as intended persistent datastore

- Status: ACCEPTED as initial architecture policy; implementation/market performance remain unvalidated.
- Date: 2026-09-13.

## Context

Atomic cash/reservation/intent writes and structured audit queries need a durable transactional store.

## Decision

Plan PostgreSQL for ledger, decisions, registry and projections; large immutable datasets may be externally stored with hashes.

## Rationale

Relational constraints and transactions suit consistency requirements without initial distributed services.

## Consequences

No database is connected and no migrations exist; Supabase hosting is optional, not selected infrastructure.

## Alternatives considered

SQLite for local-only use, document database, event store for every entity.

## Conditions for revisiting

Revisit after measured scale/operations needs; preserve transactional and evidence guarantees.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specification: [[01 - Architecture/Data Model]]. Index: [[00 - Project/Decisions/ADRs]].
