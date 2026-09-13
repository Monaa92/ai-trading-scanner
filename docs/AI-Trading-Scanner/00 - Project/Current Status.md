# Current Project Status

Last updated: 2026-09-13. Working-tree state: Phase 2 historical-data foundation implemented and locally verified, with independent risk-critical merge review pending; no trading functionality, external data, or experiment data exists.

**Current phase:** Phase 2 historical data, calendar and quality foundation, **IMPLEMENTED LOCALLY; MERGE REVIEW PENDING**. Python 3.13.15 and exact dependencies are locked. The offline package now validates immutable OHLCV records and provenance, resolves versioned XNYS regular sessions, emits structured data-quality findings, computes deterministic dataset identities, and exposes causal `available_at`-bounded slices. This status does not authorize or implement trading.

| Phase | Actual status | Evidence |
| --- | --- | --- |
| Phase 1 | IMPLEMENTED | Typed package/configuration, independent execution dimensions, fail-closed startup, CLI/FastAPI health, 111 regression tests. |
| Phase 2 | IMPLEMENTED LOCALLY; REVIEW PENDING | `market_data` models/calendar/quality/dataset/fixtures modules and 60 added behavior cases; complete suite, lint, format and strict typing pass locally. Independent competent human review is not yet recorded. |
| Phase 3 deterministic indicators | NOT IMPLEMENTED | No indicator calculations, seeds, warm-up, gap propagation or prefix-invariance implementation. |
| Phase 3 technical completion gate | NOT READY FOR TESTING | The later end-to-end experiment gate in [[06 - Testing/Phase 3 Completion Criteria]] remains separate and mostly unimplemented. |

IMPLEMENTED: version-controlled architecture/governance; Phase 1 identities, execution/configuration safety and health; `InstrumentId`/`DatasetId`; 1/5/15/60-minute half-open UTC bars; actual/modeled availability metadata; local XNYS holidays, DST and early closes through pinned `exchange-calendars==4.13.2`; provenance and adjustment state; canonical SHA-256 identity; structured fatal/warning validation; deterministic synthetic fixtures; and immutable causal data slices. Health validates a known local session and fixture without credentials or network calls.

PARTIAL: the market-data layer is a validated offline foundation. It has no provider ingestion, persistence, revision store, corporate-action processor, resampler, full normalized market-intelligence snapshot, or replay scheduler. The causal reader prevents bars from appearing before `available_at`, but later strategy APIs must preserve that boundary.

PLANNED/DEFERRED: deterministic indicators; scanner; agents and strategies; risk and portfolio accounting; execution coordinator and broker adapters; full replay/simulation; experiments and authoritative persistence; metrics/dashboards; PAPER/LIVE; IBKR/Kraken; AI inference; crypto. Future large historical and experiment data requires separately selected durable backup.

Current blockers: none for offline Phase 2 use. Independent competent human review remains required by [PROJECT_RULES](../../PROJECT_RULES.md) before treating risk-critical time/availability behavior as merge-approved or using it downstream.

Review material: [[06 - Testing/Phase 2 Independent Review]].

Next recommended action: **Phase 3 deterministic indicators only**—implement causal, session-aware indicator calculations and prefix-invariance fixtures over the Phase 2 slices without adding strategies, brokers, AI, or trading execution.
