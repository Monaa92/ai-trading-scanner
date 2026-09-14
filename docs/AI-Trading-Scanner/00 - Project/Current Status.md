# Current Project Status

Last updated: 2026-09-14. Phases 1–3 are complete on `main`. The Phase 4 strategy/proposal foundation is implemented on `review/phase-4-strategy-proposals` and awaits independent competent human review. No order submission, external data, or experiment data exists.

**Current phase:** Phase 4 strategy and proposal contracts, **IMPLEMENTED ON REVIEW BRANCH; REVIEW PENDING**. The candidate adds registered experimental baselines for Momentum, Mean Reversion, Breakout and Multi-Factor; a pure causal evaluation boundary; explicit `NO_TRADE`; and immutable proposal/management identities. It does not authorize or implement trading.

| Phase | Actual status | Evidence |
| --- | --- | --- |
| Phase 1 | IMPLEMENTED | Typed package/configuration, independent execution dimensions, fail-closed startup, CLI/FastAPI health, 111 regression tests. |
| Phase 2 | COMPLETE | `market_data` models/calendar/quality/dataset/fixtures modules and 60 added behavior cases; independently reviewed by `Dekkerszz`, approved, and merged through PR #1 at `8987f2e`. |
| Phase 3 deterministic indicators | COMPLETE | Immutable configurations and results, four incremental/batch calculators, 48 focused behavior cases, prefix invariance and preserved visible quality warnings. Independently reviewed and approved by Dekkerszz in PR #2; merged as `0cf0497`. |
| Phase 4 strategy/proposal contracts | IMPLEMENTED ON REVIEW BRANCH; REVIEW PENDING | Four versioned research baselines, agent/config/data/indicator attribution, pure evaluations, explicit non-trades, cost-estimate boundary, immutable proposal and management fingerprints, strategy-level prefix invariance and 84 focused behavior cases. The full candidate suite passes 303 tests, including 219 Phase 1–3 regressions. |
| Phase 3 technical completion gate | NOT READY FOR TESTING | The later end-to-end experiment gate in [[06 - Testing/Phase 3 Completion Criteria]] remains separate and mostly unimplemented. |

IMPLEMENTED IN THE REVIEW CANDIDATE: all Phase 1–3 capabilities plus typed strategy/proposal/decision/management identities; `BASELINE_RESEARCH_V1` configurations; a common six-series indicator snapshot; pure long-only five-minute evaluators; structured evidence and `NO_TRADE` reasons; externally supplied round-trip cost estimates; and deterministic approval-sensitive proposal content identities. Health remains offline and checks only contract registration.

PARTIAL: the market-data layer is a validated offline foundation. It has no provider ingestion, persistence, revision store, corporate-action processor, resampler, full normalized market-intelligence snapshot, or replay scheduler. The causal reader prevents bars from appearing before `available_at`, but later strategy APIs must preserve that boundary.

PLANNED/DEFERRED: empirical strategy calibration/validation; continuous-across-session indicator variants; scanner/universe ranking; central risk and portfolio accounting; execution coordinator and broker adapters; full replay/simulation; experiments and authoritative persistence; metrics/dashboards; PAPER/LIVE; IBKR/Kraken; AI inference; crypto. Future large historical and experiment data requires separately selected durable backup.

Current blocker: Phase 4 strategy decisions, stop/invalidation intent and proposal identity are risk-critical under [PROJECT_RULES](../../PROJECT_RULES.md). Independent competent human review is required before merge. See [[06 - Testing/Phase 4 Independent Review]].

Review evidence: [[06 - Testing/Phase 2 Independent Review]] and [[06 - Testing/Phase 3 Independent Review]].

Next recommended action: independently review the exact Phase 4 candidate. After approval and merge, the next milestone is **Phase 5 risk, allocation and safety contracts**.
