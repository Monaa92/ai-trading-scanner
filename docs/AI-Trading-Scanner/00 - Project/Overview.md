# AI Trading Scanner

Architecture baseline: 2026-09-13. Purpose: test whether the strategy works, not prove that it works. No production system, accepted strategy or performance evidence exists yet.

Read [PROJECT_RULES](../../PROJECT_RULES.md) first. This folder is the Obsidian vault. Notes use the numbered project hierarchy; valid local Obsidian settings are preserved.

## Navigation

- Start with [[00 - Project/Current Status]], then [[00 - Project/Roadmap]], [[01 - Architecture/System Architecture]] and [[00 - Project/Decisions/ADRs]].
- Strategy: [[02 - Agents & Strategies/Strategy Overview]], [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]], [[02 - Agents & Strategies/Shared Agent Rules/Indicators]], [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]], [[02 - Agents & Strategies/Strategy Versioning]].
- Trading: [[01 - Architecture/Risk Engine]], [[01 - Architecture/Portfolio Accounting/Position Sizing]], [[01 - Architecture/Execution/Order Lifecycle]], [[06 - Testing/Paper Trading]], [[06 - Testing/Live Readiness]], [[00 - Project/Decisions/Risk History]].
- Research: [[06 - Testing/Backtesting]], [[08 - Research/Research Integrity]], [[03 - Experiments/Experiment Framework]], [[09 - Performance/Performance Metrics]], [[00 - Project/Decisions/Strategy Changelog]], [[03 - Experiments/Results/Failed Experiments]], [[02 - Agents & Strategies/Model Benchmarking]], [[00 - Project/Decisions/AI History]], [[10 - Archive/Reviews/Architecture Review]].
- Technical: [[01 - Architecture/System Components]], [[01 - Architecture/Market Data]], [[01 - Architecture/Data Model]], [[01 - Architecture/Broker Architecture]], [[01 - Architecture/AI Architecture]], [[07 - Operations/Configuration]], [[07 - Operations/Logging & Observability]], [[06 - Testing/Test Strategy]], [[07 - Operations/Security & Secrets]], [[08 - Research/External References]].
- Operations: [[07 - Operations/Setup]], [[07 - Operations/Development Workflow]], [[07 - Operations/Runbooks/Incident and Failure Procedures]].
- Current extensions: [[01 - Architecture/Broker Architecture]], [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]], [[03 - Experiments/Experiment 1]], [[03 - Experiments/Capital Sweep]], [[03 - Experiments/Minimum Viable Capital]], [[03 - Experiments/Decision Replay]], [[04 - Costs & Economics/Transaction Costs]], [[04 - Costs & Economics/AI Inference Costs]], [[04 - Costs & Economics/API Budget Controls]].
- Readiness/reporting/recovery: [[06 - Testing/Phase 3 Completion Criteria]], [[09 - Performance/Dashboard]], [[07 - Operations/Disaster Recovery]].

The initial development universe is not a historical point-in-time universe. All trading thresholds are hypotheses or explicit risk constraints. AI is optional and never authoritative over calculations or risk. Every research result must identify its data and simulation limitations.

## Multi-agent extension

- [[01 - Architecture/Agent Architecture]] and [[01 - Architecture/Portfolio Accounting/Capital Allocation]]: participant identity, concurrent isolation, shared-account boundaries and configurable capital.
- [[01 - Architecture/Execution/Execution Modes]], [[01 - Architecture/Execution/Approval Workflow]], [[01 - Architecture/Execution/Safety Gate]]: distinct environments/policies, immutable consent and final validation.
- [[03 - Experiments/Autonomous Experiments]], [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]], [[03 - Experiments/Survival Analysis]]: frozen four-agent protocol, scoped locks and preservation endpoints.
- [[03 - Experiments/Counterfactual Analysis]], [[09 - Performance/Agent Statistics]], [[09 - Performance/Reporting Architecture]]: non-trade evidence, separate shadow results and descriptive comparisons.
- [[01 - Architecture/Execution/Trade Management]]: fixed baseline and separately tested future dynamic exits.
- [[10 - Archive/Reviews/Multi-Agent Extension Review]]: requirement mapping, inventory, checks and unresolved decisions.
- [[10 - Archive/Reviews/Broker Economics and Recovery Extension Review]]: current extension inventory, readiness, checks and open questions.

The vault folder was renamed in place to `AI-Trading-Scanner`; all 79 pre-rename files were hash-verified after the rename. The controlled numbered-folder migration then moved 84 notes with an unchanged 106-file content-hash multiset before link repair. All internal links were repaired and validated. Important non-secret Markdown and stable vault settings are included in the architecture/documentation foundation commit; machine-specific workspace state remains local. See [[07 - Operations/Disaster Recovery]].
