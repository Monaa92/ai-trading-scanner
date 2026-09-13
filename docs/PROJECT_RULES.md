# Project rules

Effective: 2026-09-13. Authoritative governance for AI Trading Scanner, repository `Monaa92/ai-trading-scanner`, intended to remain private. This pass specifies a future system; it does not implement or authorize trading.

## Purpose and decision classes

Investigate whether a systematic intraday scanner works under realistic constraints. Negative results are valid and must be retained. Profitability is not an assumption. Trading correctness and research validity take precedence over productization.

Every rule/parameter must declare its class:

| Class | Meaning |
| --- | --- |
| FIXED ENGINEERING RULE | Causality, isolation, accounting, idempotency or safety invariant; changes require ADR/review |
| RISK CONSTRAINT | Owner-specified or more restrictive approved exposure limit; not optimized for returns |
| HYPOTHESIS | Strategy premise or rule awaiting evidence |
| PROVISIONAL / REQUIRES VALIDATION | Selected design or simulation assumption awaiting measurement |
| OPEN QUESTION | Unresolved; affected capability remains unavailable when safety depends on it |
| VALIDATED FINDING | Evidence-linked, limited to named versions, datasets and conditions; never universal proof |

No validated strategy findings exist as of this date. An accepted architecture ADR is not a validated trading finding.

## Canonical baseline and precedence

Canonical V1 benchmark profile (not universal engine constants): US equities/ETFs, long-only intraday trend pullback, completed 5-minute regular-session bars, no leverage/options/CFDs/shorts, one position and at most three new filled entry intents per exchange session. No pyramiding or re-entry under the same intent. Simulated initial capital is EUR 50 with explicit currency ledgers and time-stamped FX. Risk per trade is at most 1% of current conservative equity. The daily loss lock uses realized plus unrealized net equity change and a 3% ceiling as precisely defined in [Risk Management](AI-Trading-Scanner/01%20-%20Architecture/Risk%20Engine.md). Intended net modeled reward/risk is at least 2.0. These limits do not guarantee realized losses will stay inside them. Experiment 1 applies the same hard scope/risk/cost/information constraints to the four strategy profiles in [Experiment 1 Strategy Profiles](AI-Trading-Scanner/02%20-%20Agents%20&%20Strategies/Experiment%201%20Strategy%20Profiles.md); it does not pretend the trend-pullback rules define all four strategies.

Precedence: this governance document → accepted ADRs → canonical domain specifications → derived summaries → implementation. Contradictions must be resolved and documented, never exploited. The canonical definitions are [Risk Management](AI-Trading-Scanner/01%20-%20Architecture/Risk%20Engine.md), [Position Sizing](AI-Trading-Scanner/01%20-%20Architecture/Portfolio%20Accounting/Position%20Sizing.md), [Backtesting Methodology](AI-Trading-Scanner/06%20-%20Testing/Backtesting.md), [Market Data](AI-Trading-Scanner/01%20-%20Architecture/Market%20Data.md), and [AI Architecture](AI-Trading-Scanner/01%20-%20Architecture/AI%20Architecture.md). Risk always overrides signals, AI, ranking and UI suggestions.

## Change control for every agent and contributor

All rules in [AGENTS.md](../AGENTS.md) are mandatory. Read affected notes first; document exact behavior/configuration changes with tests in the same proposed change. Do not silently change any threshold, strategy rule, risk rule, execution/cost assumption or AI behavior. Preserve user work and inspect Git state before editing. Use Obsidian links inside the vault. Important decisions require ADRs.

Every material strategy change creates a new version and a [Strategy Changelog](AI-Trading-Scanner/00%20-%20Project/Decisions/Strategy%20Changelog.md) entry. Material risk and AI changes additionally update [Risk History](AI-Trading-Scanner/00%20-%20Project/Decisions/Risk%20History.md) and [AI History](AI-Trading-Scanner/00%20-%20Project/Decisions/AI%20History.md). Changed indicator semantics that affect decisions are strategy changes too. Rejected experiments remain available.

Once the backtester functions, every material strategy modification must be evaluated against the previous accepted version on the same immutable data, costs, execution model, risk profile and evaluation period. Report trade count, win rate, average winner/loser, expectancy, profit factor, maximum drawdown, net result after modeled costs and evaluation period. Before the first accepted version, compare with the registered initial baseline and cash/no-trade control; state that no accepted predecessor exists. If infrastructure assumptions change, rerun both versions; do not compare unmatched runs as evidence of improvement. The phrase “the strategy improved” requires quantitative evidence, uncertainty and scope.

Never tune repeatedly on the final holdout, hide failed experiments, cherry-pick symbols/periods, or describe insufficient evidence as profitability. Separate code from immutable experiment configuration. Missing mandatory configuration means a run cannot start; no invisible defaults. Acceptance means a recorded research decision, not live permission.

## Risk-critical changes and merge requirements

Risk-critical includes time/availability semantics, data quality affecting decisions, indicator inputs, sizing/FX/rounding, equity/cash ledger, reservations, daily limits, execution/fill assumptions, order state/idempotency, reconciliation, stop protection, mode/credential isolation, persistence of decisions and AI control boundaries.

Before merging such code, require relevant unit, property, integration, deterministic replay/regression and injected-failure checks; comparative evaluation where behavior changes; complete audit evidence; and independent competent human review of failure paths and invariants. An agent's self-review alone is insufficient. Record reviewer and approval in the future change record. No unresolved critical findings, unexplained regression changes or missing checks may pass. Documentation-only changes require link, consistency, scope and secret checks, not fabricated execution tests. Report exact checks and limitations.

## Security and authorization

Secrets never belong in Git/GitHub, Obsidian, logs, screenshots or documentation. `.env` remains local and ignored; create a credentials-free `.env.example` only in a later foundation task. Separate read-only data, paper and future live credentials. Development must not load live credentials. No commit, push or PR without explicit user instruction. The 2026-09-13 recovery task explicitly authorizes one reviewed architecture/documentation foundation commit and push to `origin/main`; it does not authorize a pull request or implementation.

Live remains disabled regardless of implementation maturity. [Live Readiness](AI-Trading-Scanner/06%20-%20Testing/Live%20Readiness.md) is a blocking evidence gate plus a separate explicit owner decision; Phase 17 is conditional and may never happen.

## Documentation maintenance

Canonical documents own formulas and transitions; summaries link to them. Version risk, strategy, configuration, datasets, execution, indicators and AI independently and bind them in each run manifest. Do not change accepted historic artifacts in place. Corrections append superseding records with reasons. Architectural governance changes require owner review and an ADR; they cannot be smuggled into a strategy parameter update.

## Multi-agent extension — 2026-09-13

A trading agent is an isolated configurable participant, not an LLM. [Multi-Agent Architecture](AI-Trading-Scanner/01%20-%20Architecture/Agent%20Architecture.md), [Execution Modes](AI-Trading-Scanner/01%20-%20Architecture/Execution/Execution%20Modes.md), [Approval Workflow](AI-Trading-Scanner/01%20-%20Architecture/Execution/Approval%20Workflow.md), [Safety Gate](AI-Trading-Scanner/01%20-%20Architecture/Execution/Safety%20Gate.md) and [Capital Allocation](AI-Trading-Scanner/01%20-%20Architecture/Portfolio%20Accounting/Capital%20Allocation.md) extend the canonical specifications. ADR-017 onward clarify initial single-account/profile scope; earlier limits remain in the EUR50 profile, not silently loosened.

Isolate agent/run/allocation state and authority; share only immutable inputs; enforce both agent and parent-account constraints. No double allocation, implicit borrowing or cross-agent risk resets. EUR50 is configuration. Normal profiles may deliberately vary capital, currency, risk fraction, monetary risk cap, daily limits, position/trade counts, instruments, strategy/management, submission mode and approval policy only through validated owner-controlled versions. No agent self-granted increases. V1 long-only/unlevered scope remains. Multiple-position/shared-broker execution needs stronger tests/capability review before activation.

Separate data/run mode HISTORICAL_REPLAY/LIVE_FEED/CAPTURED_REPLAY, execution environment SIMULATION/PAPER/LIVE, submission mode SIGNAL_ONLY/ORDER_ENABLED, approval policy MANUAL_APPROVAL/FULL_AUTO, and context NORMAL/EXPERIMENT. `AUTONOMOUS_EXPERIMENT` is a frozen experiment type, not an environment or approval policy. All submissions retain strategy, risk, safety, broker-capability and durability gates. SIGNAL_ONLY cannot submit. Manual approval binds immutable terms; material changes invalidate consent. Final revalidation can block submission. FULL_AUTO never implies LIVE, and no rejection/expiry can fall back to automatic execution.

Frozen autonomous experiments bind participant/risk/strategy/AI/management versions and initial funding. No top-ups, hidden changes or replacement of losing participants. Only a preregistered adaptive algorithm may evolve state within fixed limits. Emergency restriction remains possible and is logged as intervention/protocol deviation. [Agent Lifecycle](AI-Trading-Scanner/02%20-%20Agents%20&%20Strategies/Shared%20Agent%20Rules/Agent%20Lifecycle.md) forbids self-clearing locks.

Actual-path and [Counterfactual Analysis](AI-Trading-Scanner/03%20-%20Experiments/Counterfactual%20Analysis.md) ledgers/metrics stay separate. Persist non-trades, approvals, safety blocks, state/config transitions and failed participants. Normal changes create attributed effective-time performance segments. Dynamic management is separately versioned/compared; fixed exits remain baseline and stops cannot widen beyond authorized rules.

Trading agents never call brokers/exchanges or market-data providers. They consume equivalent normalized snapshots and emit TRADE_PROPOSAL or first-class NO_TRADE; the execution coordinator alone invokes the broker-agnostic adapter after risk, authority and safety. Simulation is the current planned environment. IBKR is a future equities adapter and Kraken a future crypto-experiment adapter; neither implementation exists or enables LIVE/CRYPTO. Experiment 1 remains US equities.

Version round-trip execution costs before proposal and preserve them with results. Keep Gross Trading P&L, Net Trading P&L and Net Economic P&L distinct. Trading capital and AI/API budgets are separate resources: no API debit/top-up changes portfolio cash, sizing or risk. Capital sweeps use EUR50/100/250/500/1000 profiles; decision reuse requires proof that capital/portfolio state cannot affect the decision.

The reusable engine has no universal profit cap. The current fixed stop/fixed target remains the baseline; strategy-specific management is separately versioned and validated under central hard downside controls and immutable re-approval for material amendments.

Live stays disabled by default. Owner-controlled credential/environment activation, readiness review and a separate deliberate FULL_AUTO choice are required for future live autonomy. AI/trading-agent runtimes lack these privileges. Leaderboards are descriptive, not promotion evidence. Risk-critical review includes allocation/isolation, approval races, safety/permission epochs, experiment freezing, management and statistics provenance.

Critical non-secret source and project knowledge belongs in durable version control. High-volume authoritative experiment data requires separately backed-up structured storage with integrity/restore evidence; generated Obsidian dashboards are rebuildable views. Secrets remain excluded from Git, Obsidian and reports.
