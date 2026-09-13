# Architecture review and open decisions

Review date: 2026-09-13. Scope: design/documentation/governance only. No strategy is validated, no backtest exists, and no broker/AI/database is connected. [PROJECT_RULES](../../../PROJECT_RULES.md) owns governance. This review records recommendations and their evidence limits.

## Repository inspection and preservation

Initial branch `main` tracked `origin/main` at `5065408` (Initial commit). Tracked files were README and `.gitignore`; `docs/` already existed untracked. All nine existing Markdown notes were empty. Four nonempty `.obsidian` JSON settings files were read; the agent did not edit them. The expected Strategy/Trading/Research/Technical/Decisions/Operations layout existed. No unexpected production code or existing written architecture was found. `.env` was already ignored. Remote points to the requested repository; intended private visibility is user-specified, not independently verified remotely. No branch/index/commit/push/PR mutation is part of this pass.

During this task `.obsidian/workspace.json` changed outside the agent's edits: its current content shows Overview open and updated recently opened notes. This is consistent with Obsidian workspace activity. It is preserved as found, not reverted or counted as an authored change. `.gitignore`, app.json, appearance.json and core-plugins.json matched their initial SHA-256 hashes at review.

## Resolved design questions

| # | Question | Recommendation and canonical detail |
| --- | --- | --- |
| 1 | Event-driven, vectorized or hybrid? | Hybrid: pure/vectorized features, causal event-driven portfolio and execution; [[06 - Testing/Backtesting]] |
| 2 | Authoritative timestamps? | UTC intervals, market event and available/receipt times separate; decisions use available_at, fills retain actual time or explicit interval uncertainty; [[01 - Architecture/Market Data]] |
| 3 | Same-bar stop/target? | Stop-first absent ordering evidence, ambiguity counts and full scenario sensitivity; no guaranteed lower-bound claim; [[06 - Testing/Backtesting]] |
| 4 | Minimum finer data? | One-minute bars improve cross-minute ordering; ordered trades plus bid/ask/status needed for sub-minute evidence; queue/depth still a separate limitation |
| 5 | Multi-timeframe alignment? | Completed session-anchored buckets, backward as-of on available_at, no partial/future joins; [[02 - Agents & Strategies/Shared Agent Rules/Indicators]] |
| 6 | EUR50/fractional/USD sizing? | Currency cash ledger, recorded FX/conversions, decimal floor, cost/cash/risk/minimum/protection constraints; reject infeasible q; [[01 - Architecture/Portfolio Accounting/Position Sizing]] |
| 7 | Daily loss definition? | Realized plus unrealized net equity/FX/cost effects; dynamic conservative ceiling and latched lock; [[01 - Architecture/Risk Engine]] |
| 8 | Rejected/expired signals and count? | Zero until first positive entry-intent fill; reserve slots while uncertain; partial fills count once |
| 9 | What is a trade? | Flat→long→flat position episode, aggregate partial fills, residual entry cannot reopen it; [[09 - Performance/Performance Metrics]] |
| 10 | Strategy version semantics? | Patch for corrections, minor for same-family behavior changes, major for incompatible family/contracts; every behavior-changing patch still comparative; [[02 - Agents & Strategies/Strategy Versioning]] |
| 11 | Dataset identity? | Immutable canonical content/manifest SHA-256 including source/feed/vintage/actions/calendar/quality and partitions; [[01 - Architecture/Data Model]] |
| 12 | Reproducibility metadata? | Immutable full run manifest, retained artifacts and append-only linked events; commit plus dirty patch if relevant; [[07 - Operations/Configuration]] |
| 13 | Promotion evidence? | Preregistered comparable out-of-sample effect/uncertainty/risk guardrails, full artifacts and review; no arbitrary performance threshold selected now; [[03 - Experiments/Experiment Framework]] |
| 14 | Data snooping correction? | Trial/family registry, limited search, clustered paired inference, Holm for valid confirmatory p-values, fresh confirmation after exploration |
| 15 | Regime robustness? | Few causal predeclared regimes fit on development only; all cells/counts reported, insufficient coverage stays inconclusive |
| 16 | Fair AI A/B? | Same candidate information, isolated capital paths, actual AI delay/cost, stored responses and frozen prompts; historical training leakage explicitly limited; [[02 - Agents & Strategies/Model Benchmarking]] |
| 17 | Must be deterministic? | Normalization under pinned rules, features, strategy, risk, ledger, state transitions, metrics, selection and replay; [[01 - Architecture/System Architecture]] |
| 18 | May be probabilistic? | AI and explicitly seeded simulation stresses; external broker/network behavior is observed, never assumed replayable |
| 19 | Disable new orders when? | Stale/unknown data/FX/account, lockouts, unknown submissions/positions, lost durability, bad configuration/mode/auth or critical clock/capability faults; reductions remain separately controlled; [[07 - Operations/Runbooks/Incident and Failure Procedures]] |
| 20 | Persist before submit? | Signal/input/version IDs, snapshots/risk math, reservation, intent bounds/client ID/request hash, audit and outbox in one transaction; [[01 - Architecture/Execution/Order Lifecycle]] |
| 21 | Restart reconciliation? | Lock, fence writer, query overlapping orders/fills/positions/cash, resolve unknown IDs, replay deduped facts, restore protection/counters, release only resolved locks |
| 22 | Paper/backtest differences? | Captured-data paired replay; candidate timing, fill/no-fill, prices, partials, costs and equity differences classified and tested on fresh captures; [[06 - Testing/Paper Trading]] |
| 23 | What blocks live? | Missing any evidence threshold, unresolved critical bug/position/capability/security issue, insufficient net edge/robustness or no explicit owner approval; [[06 - Testing/Live Readiness]] |
| 24 | Tiny-account useful/misleading metrics? | Show EUR cents, cash utilization, net expectancy, trade count, costs and marked drawdown; win rate/annualized ratios alone mislead; [[09 - Performance/Performance Metrics]] |
| 25 | What needs real data? | Feed coverage/latency/revisions, FX availability, spreads/costs, liquidity, feasible fractions/protection, actual setup frequency and regime sample; open register below |

## Unvalidated assumptions and decision register

| Topic | Status / required evidence | Blocks |
| --- | --- | --- |
| Trend-pullback premise and indicator usefulness | HYPOTHESIS; registered historical/prospective tests, no profitable premise assumed | Strategy acceptance |
| Pullback/lookback/ATR/stop-buffer values and optional RSI/RVOL/context filters | Required research values unset; preregister limited ranges/justification before tests | Executable strategy configuration |
| Session-reset EMA50 late-session opportunity loss | PROVISIONAL explicit baseline; compare continuous-state variant under new version | Broad claims, not documenting baseline |
| RTH/cutoff/flatten policies | RTH fixed V1; cutoff/flatten lead parameters need granularity/latency and early-close tests | Runnable execution profile |
| Broker/account eligibility and settlement restrictions | OPEN QUESTION, verify actual account/current rules and costs later | Broker paper and any live consideration |
| Fractional minima, increments, protection/brackets/OCO and residual liquidation | REQUIRES VALIDATION on exact order/account combinations; provider docs have ambiguity | Paper automation |
| FX source, rate sides, staleness, conversion and tiny-notional costs | OPEN QUESTION; observed historical/prospective availability, fee policy and ledger tests | Evidential sizing/backtests/paper |
| Market-data feed/subscription/history/point-in-time actions/universe | OPEN QUESTION; coverage audit and immutable dataset, no silent IEX/SIP mixing | Comparable broad historical inference |
| Publication grace, stale thresholds, clock budget, routing/cancel latency | PROVISIONAL required config; measure streams and fault tests | Paper entry and calibrated simulation |
| Spread/slippage/fees/impact/participation/ambiguity assumptions | REQUIRES VALIDATION; capture data, sensitivity and finer-resolution evidence | Strong execution/performance claims |
| Dates/splits/embargo/regimes/effect size/power/testing family | OPEN QUESTION pending usable data and research plan | Confirmatory evaluation |
| Live gate thresholds beyond 300 trades | Required but unset; independent-day duration, precision, economic/PF/drawdown/concentration and discrepancy limits preregistered | Any live recommendation |
| AI value/model/prompt reproducibility and historical knowledge | No provider chosen; prospective frozen A/B required | AI acceptance |
| Python/Node/dependencies/hosting/database/Graphify | Unverified per [[07 - Operations/Setup]]; no setup invented | Relevant implementation/integration |
| Backup/retention/storage sizing and future multi-user/productization | Operational decisions deferred to measured volumes and requirements | Readiness/production operations, not Phase 1 skeleton |

Initial risk numbers are owner constraints, not validated optimal allocations. Conservative simulation policies are engineering choices with known bias/precision limits, not measured market facts. Exact setup profitability, live execution quality, future regimes and AI value cannot be established by documentation.

## Consistency decisions and highest-risk implementation areas

Resolve these tensions explicitly: core metrics arrive in Phase 6/7 even though richer analytics is Phase 10; paper sandbox balance never overrides the EUR50 overlay; strategy approval is distinct from order/fill/position state; daily entry counters count first fills rather than signals; protective exits survive new-entry lockouts; AI failure vetoes FILTER entries rather than silently changing the A/B arm; holdout bug reruns do not restore unseen status; runtime data-flow cycles do not imply domain import cycles.

Highest risks, in priority order: temporal availability/revisions and intrabar leakage; currency/cash/fee sizing at tiny notional; atomic reservation and ambiguous submission; partial-fill protection/cancel races and restart reconciliation; biased datasets/multiple-testing/holdout misuse; simulation-to-paper mismatch; AI version/latency/contamination and control isolation. These require adversarial fixtures and stronger review, not only happy-path tests.

## Next milestone and review scope

Recommend exactly Phase 1 offline Python/FastAPI foundation in [[00 - Project/Roadmap]], after a new scoped instruction. Select verified runtimes, package/lock/test layout, strict configuration/mode boundaries and minimal health endpoint; no trading logic, integrations, migrations or deployment. Nothing from that milestone is implemented here.

Documentation acceptance checks include full tracked/untracked diff inspection, link resolution, ADR field/governance consistency, scope/secret review and preservation of existing settings. Actual check results are recorded in the completion report; proposed behavioral tests in [[06 - Testing/Test Strategy]] are specifications, not executed tests.

## Authored file inventory

46 new Markdown files:

| Location | Created files |
| --- | --- |
| Repository root | [AGENTS.md](../../../../AGENTS.md) |
| Strategy (4) | [[02 - Agents & Strategies/Shared Agent Rules/Indicators]], [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]], [[02 - Agents & Strategies/Strategy Versioning]], [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]] |
| Trading (5) | [[06 - Testing/Live Readiness]], [[01 - Architecture/Execution/Order Lifecycle]], [[06 - Testing/Paper Trading]], [[01 - Architecture/Portfolio Accounting/Position Sizing]], [[00 - Project/Decisions/Risk History]] |
| Research (8) | [[00 - Project/Decisions/AI History]], [[02 - Agents & Strategies/Model Benchmarking]], [[10 - Archive/Reviews/Architecture Review]], [[06 - Testing/Backtesting]], [[08 - Research/Research Integrity]], [[03 - Experiments/Experiment Framework]], [[03 - Experiments/Results/Failed Experiments]], [[09 - Performance/Performance Metrics]] |
| Technical (10) | [[01 - Architecture/AI Architecture]], [[01 - Architecture/System Components]], [[01 - Architecture/Broker Architecture]], [[07 - Operations/Configuration]], [[01 - Architecture/Data Model]], [[08 - Research/External References]], [[01 - Architecture/Market Data]], [[07 - Operations/Logging & Observability]], [[07 - Operations/Security & Secrets]], [[06 - Testing/Test Strategy]] |
| Operations (2) | [[07 - Operations/Development Workflow]], [[07 - Operations/Runbooks/Incident and Failure Procedures]] |
| Decisions (16) | Individual ADR-001 through ADR-016, fully enumerated in [[00 - Project/Decisions/ADRs]] |

10 existing Markdown files populated/modified: [README.md](../../../../README.md), [PROJECT_RULES.md](../../../PROJECT_RULES.md), [[00 - Project/Overview]], [[00 - Project/Roadmap]], [[01 - Architecture/System Architecture]], [[00 - Project/Decisions/ADRs]], [[07 - Operations/Setup]], [[00 - Project/Decisions/Strategy Changelog]], [[02 - Agents & Strategies/Strategy Overview]], [[01 - Architecture/Risk Engine]]. Existing untracked documents remain untracked; no staging was performed.

Review fixes: aligned signal expiry with first possible causal execution boundary; specified boundary halt events cannot erase earlier fills; explicitly labeled simulated immediate linked protection as an unverified model assumption; prevented a proposed stop at/above current bid; removed extra ADR end-of-file blank lines found by whitespace checks. These are initial specification corrections, not tested strategy improvements.

## Documentation verification record

- 56 Markdown files checked; no empty notes or unmatched fenced blocks.
- 228 Obsidian links and 44 relative Markdown links resolved to existing files; no broken targets.
- 16 ADRs contain all eight required fields/sections and the 2026-09-13 date.
- Reviewed complete 56-file authored diff: tracked README diff plus no-index diffs for untracked Markdown. New-file whitespace checks and tracked `git diff --check` pass under the repository's normal line-ending settings after ADR blank-line cleanup.
- Credential/private-key pattern scan returned zero findings; authored content contains no secrets. `.env` ignore behavior verified.
- File inventory/hash comparison found only Markdown additions/agent edits; no original files removed. External Obsidian workspace activity is noted above. Git HEAD remains `5065408fb795cc0d60231bfd9447d519c6bfa828`; index remains unstaged.
- Cross-reviewed governance, all ADRs, architecture, roadmap, strategy, risk, execution, AI and live gate; initial contradictions corrected as listed above. All 25 design questions are mapped here.
- No Python/frontend/runtime tests, backtests, broker tests or profitability evaluation ran: no implementation exists. All such cases are future specifications.

No production trading code, migrations, integrations, deployment, commit, push or pull request was created in this pass.

## Subsequent multi-agent specification extension

The preceding file inventory and verification counts describe the original pass, not the current extended repository. [[10 - Archive/Reviews/Multi-Agent Extension Review]] records the later extension and current checks. Initial single-account risk/mode assumptions are refined by ADR-017 onward into explicit agent/allocation scopes and environment/context/execution fields. Initial EUR50 strategy/risk values and fixed exits remain unvalidated profile settings; generalized normal profiles are not active. No production implementation or experiments were added.
