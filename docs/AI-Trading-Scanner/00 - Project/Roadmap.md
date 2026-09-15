# Gated roadmap

Phases 1–5 are complete on `main`. Phase 6 is **IN PROGRESS** on its feature branch with architecture and immutable contract foundations only. A roadmap authorizes no implementation, account connection or trading beyond an explicitly scoped task.

| Phase | Deliverable | Exit criterion |
| --- | --- | --- |
| 0 | Governance/architecture and multi-agent specifications | Coherent rules, ADRs, isolation/approval/safety/capital contracts, open assumptions |
| 1 | Offline Python/FastAPI foundation | Verified/pinned runtime, package/lock/test layout, typed config/identity/data-run/environment/submission/approval validation and minimal health boundary; LIVE disabled and no execution |
| 2 | Historical data/calendar/quality — IMPLEMENTED | Immutable canonical records, provenance, available-at semantics, XNYS sessions, quality findings, deterministic dataset identity and audited synthetic fixtures. Provider ingestion, persisted revisions and real datasets remain later work. |
| 3 | Deterministic indicators — COMPLETE | Exact formulas, seeds/session/gaps, warning lineage, prefix invariance and batch/incremental fixtures pass; independently reviewed, approved and merged in PR #2 (`0cf0497`) |
| 4 | Strategy and proposal contracts — COMPLETE | Registered unoptimized `BASELINE_RESEARCH_V1` parameters, four independent profiles, first-class NO_TRADE, model/profile independence, agent-scoped pure evaluations and deterministic proposal/management identities; no order submission. Independently reviewed and merged through PR #3 (`60d83842f6bb686f2a407db82781d28ff534b355`). |
| 5 | Risk/allocation/safety — COMPLETE | Decimal sizing against scoped/fresh current loss/headroom; sizing bound to proposal, configuration and evaluated state; exclusive parent allocation ownership; atomic public scope registration; one registered allocation per agent/coordinator context; exception-atomic parent+agent in-memory reservation/lifecycle publication; proposal-wide uniqueness; expiry-safe replay/lifecycle; relational risk evidence; partitioned scoped locks; conservation and approval-binding behavior implemented. PR #4 was independently approved by `Dekkerszz` and merged as `d08faa7ca3fdd3f35a053838f736d4d709d503d9`. |
| 6 | Causal backtesting and simulation — IN PROGRESS | Foundation: content-identified causal events/run/execution/cost/order/fill/portfolio/result contracts, unique terminal resolution linkage, same-session XNYS selection, exact reservation-economics binding, pure COMPLETE accounting reconciliation and deterministic serialization. Remaining: scheduler, Phase 2–5 orchestration, transactional lifecycle posting, external marks, durable artifacts, end-to-end/failure evidence and independent review. |
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

Exact next action: **independent competent final re-review of the third-remediated Phase 6 foundation**. If approved, continue Phase 6 with the causal scheduler and Phase 2→3 replay increment under a separately bounded task. Phase 7, external order submission, broker integration, PAPER and LIVE remain unauthorized.
