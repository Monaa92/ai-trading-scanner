# Gated roadmap

Phases 1, 2 and 3 are complete. Phase 3 deterministic indicators were independently reviewed, approved and merged into `main` through PR #2. A roadmap authorizes no implementation, account connection or trading beyond an explicitly scoped task.

| Phase | Deliverable | Exit criterion |
| --- | --- | --- |
| 0 | Governance/architecture and multi-agent specifications | Coherent rules, ADRs, isolation/approval/safety/capital contracts, open assumptions |
| 1 | Offline Python/FastAPI foundation | Verified/pinned runtime, package/lock/test layout, typed config/identity/data-run/environment/submission/approval validation and minimal health boundary; LIVE disabled and no execution |
| 2 | Historical data/calendar/quality — IMPLEMENTED | Immutable canonical records, provenance, available-at semantics, XNYS sessions, quality findings, deterministic dataset identity and audited synthetic fixtures. Provider ingestion, persisted revisions and real datasets remain later work. |
| 3 | Deterministic indicators — COMPLETE | Exact formulas, seeds/session/gaps, warning lineage, prefix invariance and batch/incremental fixtures pass; independently reviewed, approved and merged in PR #2 (`0cf0497`) |
| 4 | Strategy and proposal contracts | Registered unoptimized baseline parameters, four independent strategy profiles, first-class NO_TRADE, model/profile independence and agent-scoped pure evaluations/dedup; no order submission |
| 5 | Risk/allocation/safety | Decimal sizing, parent+agent atomic reservations, scoped locks and ownership/approval contract tests independently reviewed |
| 6 | Backtesting/simulation | Causal SimulationBroker lifecycle, isolated participants, versioned round-trip costs, fixed management, decision/approval replay where valid, audit and core metrics pass |
| 7 | Historical validation | Registered comparable evidence, rejection/counterfactual separation and failed experiments retained |
| 7a | Optional management hypotheses | Separately specified/versioned dynamic policy and fixed-baseline comparison before any use |
| 8 | Broker paper integration | Verified fractional protection, attribution, idempotency/reconciliation and kill switch; live unavailable |
| 9 | Independent EUR50 paper qualification | Agent cash/counters/locks and parent-scope behavior verified; equivalent data delivery |
| 9a | Multi-agent autonomous paper experiments | Frozen registered participants, independent funding, survival endpoints and stopping/intervention rules; no unvalidated strategy assignments |
| 10 | Performance comparison/analytics | Capital sweeps/MVC and day/week/month/lifetime, lifecycle, survival, execution/AI cost and complete cohort/uncertainty reports; reproducible Obsidian summaries |
| 11 | Read-only agent dashboard | Freshness, modes, actual/counterfactual separation and descriptive leaderboard verified; no accidental activation controls |
| 12 | Optional AI abstraction | Scoped OFF/FILTER contracts and strict structured outputs, no administrative permissions |
| 13 | AI filter/ranking | Frozen model/prompt, failure/deadline policies and standalone validation |
| 14 | AI versus baseline/four-agent comparison | Prospective frozen comparisons after required AI/management prerequisites; strategy profiles exist but exact parameters/model assignments remain unregistered |
| 14a | Manual-approval operational mode (paper first) | Complete immutable cards, APPROVE/REJECT, final revalidation, expiry/race/restart tests and controlled normal config changes |
| 15 | Extended paper/shadow operational validation | Adequate independent days/regimes, approved profile/management/mode, recovery drills and discrepancy evidence |
| 16 | Live-readiness review | Complete agent/profile/capital-specific dossier, unresolved critical issues block |
| 17 | Consider separately authorized small live operation | Only after all gates, explicit owner decision; manual approval first, never guaranteed |
| 17a | Consider FULL_AUTO live | Additional deliberate owner configuration and autonomous-profile evidence after live review; not implied by Phase 17 or paper autonomy |

Autonomous paper experiments are controlled research after historical/paper validation. They do not advance operational live autonomy. The four profile names are hypotheses, not permission to invent missing parameters or activate unvalidated management. A deterministic-only program can skip AI phases, documenting that choice, then validate manual operation. Core accounting/audit/statistics begin before research, not postponed to Phase 10.

Exact next action: **Phase 4 strategy and proposal contracts**: registered baseline parameters, pure agent-scoped evaluation, first-class `NO_TRADE`, and no order submission. It requires a separately authorized implementation task.
