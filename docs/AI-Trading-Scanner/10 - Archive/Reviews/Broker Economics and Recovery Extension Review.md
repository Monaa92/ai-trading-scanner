# Broker, economics and recovery extension review

Archived historical snapshot: this note records the documentation-only repository state before executable Phases 1–3. Use [[00 - Project/Current Status]] for current readiness.

Date: 2026-09-13. Scope: final documentation consistency continuation plus broker, experiment-economics, reporting and recovery architecture. No runtime implementation was authorized or added.

## Readiness and resulting architecture

**PHASE 3 STATUS: NOT READY FOR TESTING.** [[06 - Testing/Phase 3 Completion Criteria]] maps every supplied completion criterion to repository evidence. The system remains documentation-only.

The final conceptual flow is shared data sources -> Market Data -> Market Intelligence -> immutable NormalizedMarketSnapshot -> four isolated strategy agents -> TRADE_PROPOSAL or NO_TRADE -> central Risk Engine -> approval/execution policy -> final Safety Gate -> BrokerAdapter -> planned SimulationBroker or future IBKR/Kraken. Agents cannot call provider APIs. Shared market input never shares cash, positions, risk, orders or results.

[[01 - Architecture/Execution/Execution Modes]] now separates data/run mode, SIMULATION/PAPER/LIVE environment, SIGNAL_ONLY/ORDER_ENABLED submission, MANUAL_APPROVAL/FULL_AUTO policy and NORMAL/EXPERIMENT context. AUTONOMOUS_EXPERIMENT is a frozen experiment type. PAPER + FULL_AUTO is valid; FULL_AUTO and adapter registration never imply LIVE.

Manual approval binds the exact immutable proposal hash/version. Entry envelope, entry, stop, target, quantity, instrument, direction, environment, submission/approval policy, configuration, management mandate or any execution-critical material change requires a new proposal and consent. Fresh risk/safety/capability/account checks can block every approved or auto-authorized submission.

The four Experiment 1 profiles are Momentum, Mean Reversion, Breakout and Multi-Factor. They receive equivalent normalized information, universe, timestamps, starting capital, risk, costs and execution assumptions while retaining independent ledgers and identities. Strategy and AI model remain separate dimensions. NO_TRADE is first-class and no trade quota exists.

EUR 50 is the initial per-agent virtual allocation. The sweep adds EUR 100/250/500/1,000 as configuration. Separate allocation namespaces and parent-account conservation prevent double-spending. Frozen autonomous runs allow only preregistered adaptive algorithms. Replay reuses an AI decision only when portfolio/capital state cannot alter it.

Trading economics report Gross Trading P&L, Net Trading P&L after execution costs, and Net Economic P&L after attributable AI/operating costs. AI budgets never alter portfolio cash/risk. Warning/critical/hard-stop controls have no numeric values yet; hard stop preserves deterministic exit/protection. Daily/weekly/monthly/lifetime metrics reconcile from decisions, fills, trade episodes and ledger watermarks. Actual and counterfactual records remain disjoint.

Survival reporting separates capital preservation, uninterrupted autonomy, lockouts/interventions and experiment completion/failure. Trade management retains fixed stop/fixed target as baseline; there is no engine-wide profit cap. Future strategy-specific exits are independently versioned, causally evaluated, risk-bounded and subject to immutable re-approval.

The design scales normal trading through versioned capital/risk/strategy/model/management/cost profiles and performance segments without making EUR 50 an engine constant. Shared broker accounts remain infrastructure only and cannot merge logical portfolios. LIVE appears after validation only: future IBKR PAPER -> separately authorized IBKR LIVE + MANUAL_APPROVAL -> potentially LIVE + FULL_AUTO after another deliberate decision.

## Current adapter and reporting status

- SimulationBrokerAdapter: required current experiment component, **NOT IMPLEMENTED**.
- IBKRBrokerAdapter: future equity placeholder, **DEFERRED**, no credentials or connection.
- KrakenBrokerAdapter: future crypto placeholder, **DEFERRED**, excluded from Experiment 1.
- Performance dashboard/generator: contract only, **NOT IMPLEMENTED**; no data or charts fabricated.
- Authoritative experiment persistence/backup: conceptual boundary only, **NOT IMPLEMENTED**.

## Files created in this continuation — 27 Markdown files

- [[00 - Project/Current Status]]
- [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]]
- [[03 - Experiments/Capital Sweep]]
- [[03 - Experiments/Decision Replay]]
- [[03 - Experiments/Experiment 1]]
- [[03 - Experiments/Minimum Viable Capital]]
- [[03 - Experiments/Reporting]]
- [[04 - Costs & Economics/AI Inference Costs]]
- [[04 - Costs & Economics/API Budget Controls]]
- [[04 - Costs & Economics/Transaction Costs]]
- [[05 - Brokers/Broker Capabilities]]
- [[05 - Brokers/IBKR]]
- [[05 - Brokers/Kraken]]
- [[05 - Brokers/Simulation]]
- [[06 - Testing/Phase 3 Completion Criteria]]
- [[07 - Operations/Disaster Recovery]]
- [[09 - Performance/Dashboard]]
- [[01 - Architecture/Scanner]]
- [[00 - Project/Decisions/ADR-025 - Broker-agnostic execution boundary]]
- [[00 - Project/Decisions/ADR-026 - Future IBKR equity and Kraken crypto adapters]]
- [[00 - Project/Decisions/ADR-027 - Versioned transaction costs in decisions]]
- [[00 - Project/Decisions/ADR-028 - Strategy and model are independent experiment dimensions]]
- [[00 - Project/Decisions/ADR-029 - Capital sweep and replay equivalence]]
- [[00 - Project/Decisions/ADR-030 - Separate AI operating-cost ledger]]
- [[00 - Project/Decisions/ADR-031 - Durable recovery by storage class]]
- [[00 - Project/Decisions/ADR-032 - Strategy-specific profit management]]
- This review.

## Files modified in this continuation — 37 Markdown files

- [AGENTS.md](../../../../AGENTS.md), [README.md](../../../../README.md), [PROJECT_RULES.md](../../../PROJECT_RULES.md)
- [[00 - Project/Overview]], [[00 - Project/Roadmap]], [[01 - Architecture/System Architecture]], [[00 - Project/Decisions/ADRs]]
- [[00 - Project/Decisions/ADR-018 - Explicit execution modes]], [[00 - Project/Decisions/ADR-019 - Frozen autonomous experiment configurations]]
- [[07 - Operations/Runbooks/Incident and Failure Procedures]], [[07 - Operations/Setup]]
- [[09 - Performance/Agent Statistics]], [[03 - Experiments/Autonomous Experiments]], [[06 - Testing/Backtesting]], [[03 - Experiments/Counterfactual Analysis]], [[03 - Experiments/Experiment Framework]], [[10 - Archive/Reviews/Multi-Agent Extension Review]], [[09 - Performance/Performance Metrics]]
- [[02 - Agents & Strategies/Strategy Overview]]
- [[01 - Architecture/AI Architecture]], [[01 - Architecture/System Components]], [[01 - Architecture/Broker Architecture]], [[07 - Operations/Configuration]], [[09 - Performance/Reporting Architecture]], [[01 - Architecture/Data Model]], [[08 - Research/External References]], [[01 - Architecture/Market Data]], [[01 - Architecture/Agent Architecture]], [[07 - Operations/Logging & Observability]], [[07 - Operations/Security & Secrets]], [[06 - Testing/Test Strategy]]
- [[01 - Architecture/Execution/Approval Workflow]], [[01 - Architecture/Execution/Execution Modes]], [[06 - Testing/Live Readiness]], [[06 - Testing/Paper Trading]], [[01 - Architecture/Execution/Safety Gate]], [[01 - Architecture/Execution/Trade Management]]

The count above treats current-task authoring separately from the in-place vault rename. The rename moved 79 existing files with identical relative paths/content hashes and no duplicate. Git sees the whole documentation tree as untracked because it was never committed.

## Verification results

- Git state and complete tracked/untracked inventory reviewed; HEAD and `origin/main` both remain `5065408fb795cc0d60231bfd9447d519c6bfa828`; index empty.
- Vault rename verified source absent/target present and 79 pre-rename files identical by SHA-256/size. Five `.obsidian` JSON files parse successfully; ignore file unchanged.
- Link validator: 104 Markdown files (101 in vault), 567 Obsidian wiki links and 91 Markdown links checked; zero unresolved links.
- ADR validator: ADR-001–032 sequential and required fields present; ADR-001–016 content untouched by this continuation.
- Markdown whitespace/fence/empty-file validator: 104 files checked; zero trailing-whitespace, missing-final-newline, empty-file or unbalanced-fence findings. Tracked `git diff --check` passed.
- Credential/private-key scan: 109 text/JSON files checked; zero credential-like findings. No credentials were requested.
- Terminology/invariant matrix checked 21 required documentation invariants covering isolation, execution dimensions, all four named semantics, FULL_AUTO/LIVE, AI privilege denials, immutable/material approval, final revalidation, four-agent input/state boundaries, configurable EUR50, allocation conservation, frozen experiments, counterfactual/statistics/survival separation, versioned management, idempotency identity, roadmap ordering and ADR ranges; 21/21 passed.
- File-type inventory contains Markdown, Obsidian JSON, README/AGENTS and `.gitignore` only. No production source, manifests, migrations, tests, binary artifacts or generated charts were added.
- Graphify `graphifyy` v0.9.56 and CLI help were verified outside the restricted sandbox. No project Graphify config/generated output or old vault-path reference exists; path-specific integration is therefore NOT CONFIGURED and no graph-resolution claim is made.

## Open questions and exact next milestone

Open: sourced numeric `SIMULATED_IBKR_US_TIERED` assumptions; strategy parameters/model assignment; experiment period/universe/data manifest; risk/survival/API-budget thresholds; replay-dependency declaration schema; SimulationBroker fill/capability details; authoritative experiment storage and backup target; and future account-specific IBKR capability certification. None can be represented as completed evidence now.

The exact next technical milestone is **Phase 1 offline foundation only**: pin the runtime/dependencies; create a minimal package/test/health boundary; implement typed validation for identities and all execution dimensions with LIVE disabled; and prove that SIMULATION needs no credentials, adapter registration cannot enable LIVE/CRYPTO, and strategy/model identifiers remain independent. Do not build broker connections or trading execution in that milestone.

The vault reorganization was later explicitly approved and completed with a recorded 84-file source/destination map. Before link repair, the 106-file size/SHA-256 multiset matched exactly; all sources were absent, destinations present and zero links unresolved afterward. The numbered hierarchy uses `10 - Archive` because `09 - Performance` is required for generated reporting.

Post-reorganization checks covered 104 Markdown files, 567 Obsidian wikilinks, 91 Markdown links, 32 ADRs, five Obsidian JSON files and 21 architecture invariants. All passed. Workspace JSON contained 25 distinct Markdown references and all resolved after path repair. Git classification selected 101 vault notes, four stable vault settings, `AGENTS.md` and `docs/PROJECT_RULES.md`; machine-specific `.obsidian/workspace.json` remains ignored.

## Explicit completion facts

NO production implementation was added. The later explicitly authorized recovery follow-up stages, commits and pushes only the reviewed architecture/documentation foundation. NO secrets were added. No broker account was connected, no credentials were required, no orders were placed, no PAPER/LIVE was enabled and no crypto was added to Experiment 1.
