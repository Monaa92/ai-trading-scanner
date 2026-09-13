# Multi-agent extension review

Date: 2026-09-13. Historical review of the first multi-agent documentation extension. Documentation/architecture/specification only; no trading agents were implemented. Its then-open strategy assignments were subsequently specified as four unvalidated Experiment 1 profiles in [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]]. Fixed exits remain the active baseline specification. Current readiness is in [[00 - Project/Current Status]]. Existing main branch at 5065408 and prior uncommitted documentation were inspected before changes; none was staged, committed or pushed.

## Requirement coverage and key decisions

| Request | Canonical specification and decision |
| --- | --- |
| 1. Independent trading agents | [[01 - Architecture/Agent Architecture]]: identity/config/ledger isolation, shared immutable data, per-account writer |
| 2. Execution authority | [[01 - Architecture/Execution/Execution Modes]]: later refinement separates SIGNAL_ONLY/ORDER_ENABLED submission, MANUAL_APPROVAL/FULL_AUTO policy and AUTONOMOUS_EXPERIMENT type |
| 3. Immutable approval lifecycle | [[01 - Architecture/Execution/Approval Workflow]]: exact terms, expiry, terminal reasons, fresh risk/safety and no stale consent |
| 4. Four EUR50 participants | [[03 - Experiments/Autonomous Experiments]]: independent accounts and equivalent availability; later Experiment 1 profiles remain hypotheses |
| 5. Survival research | [[03 - Experiments/Survival Analysis]]: capital/time/activity measures, failure/censoring and no artificial score |
| 6. Agent states | [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]]: scoped supervisor locks, preservation policy, terminal outcomes and administrative authority |
| 7. All decisions logged | [[07 - Operations/Logging & Observability]]: candidates/non-trades/approvals/safety/state/config as well as fills |
| 8. Rejected opportunities | [[03 - Experiments/Counterfactual Analysis]]: separate isolated hypothetical ledgers and full-path versus opportunity diagnostics |
| 9. Period statistics | [[09 - Performance/Agent Statistics]]: trade/day/ISO-week/month/lifetime, flow/unrealized bridges and recomputed ratios |
| 10. Leaderboard | [[09 - Performance/Reporting Architecture]]: descriptive comparisons, common periods, failed arms retained, no single best-agent score |
| 11. Dynamic management | [[01 - Architecture/Execution/Trade Management]]: fixed baseline, independently versioned/tested alternatives, no long-stop widening |
| 12. Normal capital/configuration | [[01 - Architecture/Portfolio Accounting/Capital Allocation]]: reusable sizing from allocated equity and validated profiles, EUR50 not hard-coded |
| 13. Compounding and flows | Same allocation specification: own gains/losses, owner transfers, no double funding and session-boundary change policy |
| 14. Configuration history | [[07 - Operations/Configuration]]: immutable composed versions, actor/request/effective time and performance segments |
| 15. Experiment vs normal | [[03 - Experiments/Autonomous Experiments]] and [[01 - Architecture/Execution/Execution Modes]]: frozen science versus deliberate controlled updates |
| 16. Final safety gate | [[01 - Architecture/Execution/Safety Gate]]: risk owns economics; safety owns authority/health/consent and fresh risk binding |
| 17. Live autonomy | [[06 - Testing/Live Readiness]] and [[07 - Operations/Security & Secrets]]: separate explicit owner live/full-auto choices, AI cannot activate |
| 18. Dashboard | [[09 - Performance/Reporting Architecture]]: complete proposal cards and deliberate privileged flows; specification only |
| 19. Data model | [[01 - Architecture/Data Model]]: extend existing registry/run/ledger/summary concepts with ownership and a few explicit entities |
| 20. Tests | [[06 - Testing/Test Strategy]]: isolation, approval races, allocation, frozen manifests, management and statistics invariants |
| 21. Governance/ADRs | [PROJECT_RULES](../../../PROJECT_RULES.md), [AGENTS](../../../../AGENTS.md), [[00 - Project/Decisions/ADRs]] 017–024 |
| 22. Roadmap | [[00 - Project/Roadmap]]: validation before autonomous paper, comparison before manual operational rollout, separate later live choices |
| 23–24. Review/report | This note and completion report: inventory, consistency, checks, questions and next milestone |

## Unresolved choices and gates

- Four strategy profile names/mandates are now specified, while actual research parameters and any dynamic policy remain unselected; each requires registration and prior-stage evidence. No architecture option is a validated strategy.
- Survival failure floors, drawdown warning/preservation/reset thresholds, infeasibility duration, horizon, minimum activity/coverage and uncertainty plan: unset until justified and preregistered. No ruin probability from four correlated paths.
- Exact profile/risk/monetary/aggregate limits for normal capital levels: owner-defined and validated; general configurable fields do not activate looser settings.
- Actual paper-account separation/availability, shared-account netting/attribution/protection capability, FX/settlement/cost sources and tiny-quantity feasibility: require future provider/account tests. Independent simulated ledgers are the default research topology.
- Operational approval TTL, final-validation freshness lease, fan-out fairness/resource budgets and intervention stopping rules: registered/measured before execution. Do not lengthen stale proposals because a user responded late.
- Beyond-baseline trade management and AI recommendation contracts: separate strategy/management/AI versions and controlled comparisons before activation.
- Future normal intraday allocation changes or multi-account routing, broader shared-symbol execution and AUTONOMOUS_EXPERIMENT in LIVE: unsupported initial capabilities requiring additional design/evidence. Normal changes initially require flat reconciled session-boundary cutover.
- Existing live-readiness confidence/effect/PF/drawdown/duration thresholds remain unresolved; this extension supplies no trading evidence or live permission.

## Consistency resolutions

Retained the original EUR50 1%/3%/one-position/three-entry profile but scoped it per participant allocation with additional parent constraints. General r/d/monetary caps are configuration rather than capital-specific branches. Existing daily latch/reset semantics remain; agents cannot reset themselves. Distinguished risk approval from human consent, preflight from executable authority, and execution environment from submission/approval policy. Consent waiting holds no capital; final commit/dispatch checks prevent races/stale approval where locally controllable, with external in-flight uncertainty still reconciled.

Fixed management remains unchanged; dynamic amendments never activate retroactively or lower a confirmed long stop. Shared account coupling is not advertised as independent experimentation. Actual-path means the realized path of its labeled simulated/live environment; hypothetical outcomes cannot change that ledger. Survival and financial/operational failure endpoints remain distinct, with non-trade costs/FX and informative censoring visible. Previous ADR decisions/history are preserved and scoped by new ADRs; no strategy improvement is claimed.

## Next milestone

Exactly Phase 1 offline foundation in [[00 - Project/Roadmap]]: verify/select/pin runtime/dependencies, minimal package/test/health boundary and typed agent/account/allocation/data-run/environment/submission/approval/context configuration validation with LIVE disabled. No workers, approval service, allocation ledger, broker/AI integration, strategy/risk execution, database migrations or UI. This task implements none of it.

## File inventory and checks

The completion inventory and verification results below refer to this extension only; the original [[10 - Archive/Reviews/Architecture Review]] remains a historical record of the first pass.


### Created in this extension — 21 Markdown files

- [[00 - Project/Decisions/ADR-017 - Multi-agent isolation]]
- [[00 - Project/Decisions/ADR-018 - Explicit execution modes]]
- [[00 - Project/Decisions/ADR-019 - Frozen autonomous experiment configurations]]
- [[00 - Project/Decisions/ADR-020 - Immutable manual approvals]]
- [[00 - Project/Decisions/ADR-021 - Normal operation and experimental profiles]]
- [[00 - Project/Decisions/ADR-022 - Isolated capital allocation]]
- [[00 - Project/Decisions/ADR-023 - Final deterministic safety gate]]
- [[00 - Project/Decisions/ADR-024 - Versioned trade management]]
- [[09 - Performance/Agent Statistics]]
- [[03 - Experiments/Autonomous Experiments]]
- [[03 - Experiments/Counterfactual Analysis]]
- [[10 - Archive/Reviews/Multi-Agent Extension Review]]
- [[03 - Experiments/Survival Analysis]]
- [[09 - Performance/Reporting Architecture]]
- [[01 - Architecture/Agent Architecture]]
- [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]]
- [[01 - Architecture/Execution/Approval Workflow]]
- [[01 - Architecture/Portfolio Accounting/Capital Allocation]]
- [[01 - Architecture/Execution/Execution Modes]]
- [[01 - Architecture/Execution/Safety Gate]]
- [[01 - Architecture/Execution/Trade Management]]

### Modified in this extension — 31 Markdown files

- [AGENTS.md](../../../../AGENTS.md)
- [README.md](../../../../README.md)
- [PROJECT_RULES.md](../../../PROJECT_RULES.md)
- [[00 - Project/Overview]]
- [[00 - Project/Roadmap]]
- [[01 - Architecture/System Architecture]]
- [[00 - Project/Decisions/ADRs]]
- [[07 - Operations/Runbooks/Incident and Failure Procedures]]
- [[00 - Project/Decisions/AI History]]
- [[02 - Agents & Strategies/Model Benchmarking]]
- [[10 - Archive/Reviews/Architecture Review]]
- [[06 - Testing/Backtesting]]
- [[03 - Experiments/Experiment Framework]]
- [[09 - Performance/Performance Metrics]]
- [[00 - Project/Decisions/Strategy Changelog]]
- [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]]
- [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]]
- [[01 - Architecture/AI Architecture]]
- [[01 - Architecture/System Components]]
- [[01 - Architecture/Broker Architecture]]
- [[07 - Operations/Configuration]]
- [[01 - Architecture/Data Model]]
- [[07 - Operations/Logging & Observability]]
- [[07 - Operations/Security & Secrets]]
- [[06 - Testing/Test Strategy]]
- [[06 - Testing/Live Readiness]]
- [[01 - Architecture/Execution/Order Lifecycle]]
- [[06 - Testing/Paper Trading]]
- [[01 - Architecture/Portfolio Accounting/Position Sizing]]
- [[00 - Project/Decisions/Risk History]]
- [[01 - Architecture/Risk Engine]]

No pre-existing files were removed. Existing ADR-001–016, trading predicates, indicator specifications and Obsidian settings remain unchanged in this extension. The V1 signal deduplication key now includes agent/allocation/participant scope; its single-agent strategy rules remain unchanged. Prior uncommitted work is preserved.

### Verification results — 2026-09-13

- Re-read existing governance, architecture, risk, execution/backtesting, research, AI, data, audit, paper/live and relevant ADR specifications before integration.
- Captured/reviewed the complete working-tree Markdown diff (77 file sections, including untracked files); compared pre-extension SHA-256 inventory to isolate 21 additions and 31 modifications. No deleted or non-Markdown changed files; ADR-001–016 and Obsidian settings retain their baseline hashes.
- All 77 Markdown files are nonempty; fenced blocks balanced. All 426 Obsidian links and 65 relative Markdown links resolve. All 24 ADRs have required fields/date; new sequence is 017–024.
- Tracked git diff --check and no-index checks for untracked Markdown pass. Credential/private-key pattern scan reports zero matches; authored content contains no secrets; .env ignore behavior verified.
- Reviewed isolation, profile-versus-engine limits, mode/environment separation, immutable consent, full-auto safety parity, AI privileges, frozen adaptation, allocation conservation, counterfactual provenance, lifecycle authority, dynamic exits and roadmap ordering. Corrected agent-scoped V1 deduplication, self-reservation double-count ambiguity, signal-only preflight versus submission authority, and blanket dynamic consent in manual mode.
- Proposed unit/property/integration/backtest/fault tests are specifications only. No runtime tests, backtests, broker operations, survival estimates or profitability evaluation were executed.
- HEAD remains 5065408fb795cc0d60231bfd9447d519c6bfa828 on main; index unchanged. No production code, migrations, deployment, commit, push or pull request added.
