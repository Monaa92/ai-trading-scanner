# ADR-031 — Durable recovery by storage class

- Status: ACCEPTED as recovery policy; remote experiment storage remains unresolved.
- Date: 2026-09-13.

## Context

Source/knowledge and high-volume experiment evidence have different durability and storage needs.

## Decision

Version non-secret source, configuration and Obsidian Markdown in Git; keep local UI/cache state regenerable; back up authoritative experiment data separately with integrity and restore checks; recreate secrets securely.

## Rationale

No single local computer or generated dashboard may be the sole copy of critical state.

## Consequences

Current source, documentation, Phase 1 package, lockfile and tests are protected on `origin/main`; future authoritative telemetry remains the durability gap. No paid service is introduced. Full readiness waits for a selected experiment store and tested restore.

## Alternatives considered

Put all telemetry in Git; rely on generated charts; store secrets in vault notes; accept local-only history.

## Conditions for revisiting

Measured volume, retention and regulatory needs may select a durable backend through a later ADR.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[07 - Operations/Disaster Recovery]]. Index: [[00 - Project/Decisions/ADRs]].
