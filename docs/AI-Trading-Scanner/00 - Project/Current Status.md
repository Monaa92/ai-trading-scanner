# Current Project Status

Last updated: 2026-09-14. Phases 1–4 are complete on `main`. The Phase 5 risk/allocation/safety candidate is implemented and locally verified; independent competent human review remains required. No order submission, external data, or experiment data exists.

**Current phase:** Phase 5 risk, allocation and safety contracts, **IMPLEMENTED LOCALLY; REVIEW REQUIRED**. It adds immutable risk/sizing decisions, parent/agent capital snapshots, exact Decimal sizing, atomic local reservations, scoped locks and optional approval-binding validation. It cannot create an order or connect to a broker.

| Phase | Actual status | Evidence |
| --- | --- | --- |
| Phase 1 | IMPLEMENTED | Typed package/configuration, independent execution dimensions, fail-closed startup, CLI/FastAPI health, 111 regression tests. |
| Phase 2 | COMPLETE | `market_data` models/calendar/quality/dataset/fixtures modules and 60 added behavior cases; independently reviewed by `Dekkerszz`, approved, and merged through PR #1 at `8987f2e`. |
| Phase 3 deterministic indicators | COMPLETE | Immutable configurations and results, four incremental/batch calculators, 48 focused behavior cases, prefix invariance and preserved visible quality warnings. Independently reviewed and approved by Dekkerszz in PR #2; merged as `0cf0497`. |
| Phase 4 strategy/proposal contracts | COMPLETE | Four versioned research baselines, agent/config/data/indicator attribution, pure evaluations, explicit non-trades, cost-estimate boundary, immutable proposal and management fingerprints, strategy-level prefix invariance and 84 focused behavior cases. Independently reviewed by `Dekkerszz` (APPROVED/PASS) and merged through PR #3 at `60d83842f6bb686f2a407db82781d28ff534b355`. |
| Phase 5 risk/allocation/safety | IMPLEMENTED LOCALLY; REVIEW REQUIRED | Typed ownership and identities, versioned research-only risk policy, deterministic bounded sizing, parent+allocation atomic reservations, conservation, idempotent lifecycle, scoped locks, approval/fingerprint binding and 68 focused cases. Full local suite: 371 passed. |
| Phase 3 technical completion gate | NOT READY FOR TESTING | The later end-to-end experiment gate in [[06 - Testing/Phase 3 Completion Criteria]] remains separate and mostly unimplemented. |

IMPLEMENTED THROUGH THE PHASE 5 CANDIDATE: all Phase 1–4 capabilities plus typed risk/configuration/sizing/reservation/lock/approval-binding identities; immutable parent and allocation snapshots; explicit external drawdown/safety state; pure proposal risk evaluation; exact downward quantity sizing; and a concurrency-safe in-memory coordinator. Health remains offline and validates only compact contract fixtures.

PARTIAL: the market-data layer is a validated offline foundation. It has no provider ingestion, persistence, revision store, corporate-action processor, resampler, full normalized market-intelligence snapshot, or replay scheduler. The causal reader prevents bars from appearing before `available_at`, but later strategy APIs must preserve that boundary.

PLANNED/DEFERRED: empirical strategy calibration/validation; continuous-across-session indicator variants; scanner/universe ranking; full portfolio/P&L accounting; durable transactional reservations; execution coordinator and broker adapters; full replay/simulation; experiments and authoritative persistence; metrics/dashboards; PAPER/LIVE; IBKR/Kraken; AI inference; crypto. Future large historical and experiment data requires separately selected durable backup.

Current blocker: Phase 5 is risk-critical and requires independent competent human review before merge. Its in-memory transaction boundary is not crash-durable or multi-process safe and grants no execution capability. See [[06 - Testing/Phase 5 Independent Review]].

Review evidence: [[06 - Testing/Phase 2 Independent Review]], [[06 - Testing/Phase 3 Independent Review]] and [[06 - Testing/Phase 4 Independent Review]].

Next recommended action: independently review the exact Phase 5 candidate. Only after approval and merge does the roadmap advance to **Phase 6 backtesting/simulation**.
