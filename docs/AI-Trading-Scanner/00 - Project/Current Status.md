# Current Project Status

Last updated: 2026-09-13. Working-tree state: Phase 3 deterministic indicator candidate implemented and locally verified on `review/phase-3-indicators`; independent risk-critical review is required before merge. No trading functionality, external data, or experiment data exists.

**Current phase:** Phase 3 deterministic indicator foundation, **IMPLEMENTED ON REVIEW BRANCH; REVIEW PENDING**. The candidate adds exact-Decimal EMA, Wilder RSI, Wilder ATR and session VWAP over canonical causal slices, with explicit warm-up, session reset, gap and output-lineage semantics. This status does not authorize or implement trading.

| Phase | Actual status | Evidence |
| --- | --- | --- |
| Phase 1 | IMPLEMENTED | Typed package/configuration, independent execution dimensions, fail-closed startup, CLI/FastAPI health, 111 regression tests. |
| Phase 2 | COMPLETE | `market_data` models/calendar/quality/dataset/fixtures modules and 60 added behavior cases; independently reviewed by `Dekkerszz`, approved, and merged through PR #1 at `8987f2e`. |
| Phase 3 deterministic indicators | IMPLEMENTED ON REVIEW BRANCH; REVIEW PENDING | Immutable configurations and results, four incremental/batch calculators, 48 focused behavior cases, prefix invariance and preserved visible quality warnings. Independent competent human review is not yet recorded. |
| Phase 3 technical completion gate | NOT READY FOR TESTING | The later end-to-end experiment gate in [[06 - Testing/Phase 3 Completion Criteria]] remains separate and mostly unimplemented. |

IMPLEMENTED IN THE REVIEW CANDIDATE: all Phase 1–2 capabilities plus `IndicatorConfigurationId`; strict immutable EMA/RSI/ATR/VWAP configuration; 34-digit `Decimal`/half-even arithmetic isolated from process context; typed ready/unavailable results; causal input validation; V1 per-session state reset; gap-aware warm-up/restart; complete-prefix session VWAP; batch/incremental equivalence; and an offline indicator health fixture.

PARTIAL: the market-data layer is a validated offline foundation. It has no provider ingestion, persistence, revision store, corporate-action processor, resampler, full normalized market-intelligence snapshot, or replay scheduler. The causal reader prevents bars from appearing before `available_at`, but later strategy APIs must preserve that boundary.

PLANNED/DEFERRED: continuous-across-session indicator variants; scanner; agents and strategies; risk and portfolio accounting; execution coordinator and broker adapters; full replay/simulation; experiments and authoritative persistence; metrics/dashboards; PAPER/LIVE; IBKR/Kraken; AI inference; crypto. Future large historical and experiment data requires separately selected durable backup.

Current blocker: indicator semantics are risk-critical under [PROJECT_RULES](../../PROJECT_RULES.md). The candidate must receive independent competent human review before merge. See [[06 - Testing/Phase 3 Independent Review]].

Review evidence: [[06 - Testing/Phase 2 Independent Review]].

Next recommended action: independently review the Phase 3 candidate’s formulas, initialization, session/gap handling, causality, warning propagation and numeric determinism. After approval and merge, the next implementation milestone is **Phase 4 strategy and proposal contracts**.
