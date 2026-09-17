# Four-agent autonomous and survival experiments

Research question: can a daytrading participant preserve fixed starting capital without discretionary human trading intervention, and does AI improve or worsen that outcome? No success is assumed. “Autonomous” removes discretionary trade approval, not risk limits, emergency supervision or audit requirements.

## Initial protocol shape — not activated

Four participant IDs link four independent agents/accounts, each initially EUR50 virtual capital, with exact amounts/FX/cost treatment frozen. Experiment 1 now defines four unvalidated strategy hypotheses in [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]]; assigning a profile to an agent does not bind it to an AI model or validate it. Numeric drawdown/survival thresholds remain unselected. Dynamic management cannot be included until its own controlled comparison qualifies; architecture support does not imply activation.

Before start, preregister participant configurations, strategy/risk/management/AI hashes, data/run mode, SIMULATION execution environment, ORDER_ENABLED submission mode, FULL_AUTO approval policy, context EXPERIMENT, experiment type AUTONOMOUS_EXPERIMENT, initial funding, exact start/end dates or stopping events, universe, common data availability/cutoffs, clock/latency/execution/cost models, random streams, candidate logging/counterfactual rules, survival endpoint definition, warning/preservation/termination thresholds, sample/uncertainty plan and administrator intervention policy. Missing required parameters block start. Bind immutable ExperimentRegistration to a manifest and participant runs; no duplicated mutable “experiment config” copy.

Equal input access means identical eligible data snapshots and publication times, not forcing equal order times after different AI computation latency. Cache/delivery fairness and outages are recorded. Each agent has its own equity/cash/reservations/day latch/orders/trades/metrics; identical candidate input may produce divergent legitimate paths. Separate common-random-number indexing aligns comparable simulated events without consuming another participant's RNG state. Shared-account capacity competition is a different, explicitly coupled experiment.

## Freeze, adaptation and termination

Activation snapshots all configs and allocates funds before any participant sees evaluation outcomes. Immutable artifacts remain retrievable. Agent services cannot write registry/configuration endpoints; supervisor compares frozen hashes on decisions/dispatch. A difference stops affected entries, records violation and follows the registered failure rule. Emergency safety restriction is always allowed, logged as intervention and possible protocol deviation; it never authorizes an opportunistic configuration edit. Resume after intervention is not silently counted as uninterrupted autonomous survival.

An adaptive strategy is permissible only if its causal update algorithm, input boundaries, initial state, update cadence, allowed parameter ranges, deterministic caps, randomness and stopping behavior were frozen before start. Log each state transition under that algorithm. Selecting a new prompt/model/threshold after seeing results is a material experiment change, not “learning.” A new configuration requires a new participant run/experiment with the old result retained; no in-place repair of unfavorable results.

Record both participant terminal outcomes and experiment orchestration state. One failed independent agent does not automatically stop surviving agents unless the registered experiment rule says so; keep the failed agent in denominators/leaderboard. System/account failure may pause or stop all affected participants with explicit scope. Planned end invokes exit/cancel/reconciliation; residual holdings are visible. EXPERIMENT_COMPLETED requires flat reconciled state; EXPERIMENT_FAILED may have outstanding exposure under mandatory recovery, never implies liquidation succeeded.

Uninterrupted-autonomy and capital-preservation endpoints are distinct: a human emergency intervention can end the autonomy endpoint while leaving capital intact. Infrastructure loss is not automatically financial ruin; record failure causes separately and avoid treating informative outages as harmless censoring. See [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]] and [[03 - Experiments/Survival Analysis]].

## Fair comparison and inference

Use common historical/prospective evaluation windows, costs and survival definitions; report all four paths, including inactive/failed participants. A four-arm winner is descriptive, not an accepted strategy. The four simultaneous agents are correlated through the same market and do not constitute four independent replicates. Pre-register comparisons/multiple-testing family and retain all prompt/strategy variants. Baseline vs filter isolates filtering; adding dynamic management also changes a factor, so C vs A does not isolate AI. Compare C vs B for the added management policy and use ablations/replications before attributing causality.

Use [[03 - Experiments/Experiment Framework]] and [[02 - Agents & Strategies/Model Benchmarking]] for chronological validation, holdout protection, clustered uncertainty and prospective AI contamination controls. Counterfactual analyses never alter actual participant funds. No fixed date/sample/risk-of-ruin probability is invented here. Gates in [[00 - Project/Roadmap]] put autonomous paper experimentation after historical validation and paper operational tests, never before them.

## Separate future 4+1 protocol

[[03 - Experiments/4+1 Historical Experiment]] is a separate future historical protocol. It preserves Experiment 1 and adds [[02 - Agents & Strategies/Autonomous Survival Agent]] as a deliberately different adaptive participant. Its world/objective/action schemas and initial policy are frozen, while causally produced policy state may evolve under the preregistered algorithm. This is the existing adaptive-strategy exception applied explicitly; it does not permit outcome-driven configuration edits.

Agent 5 and descendants share one top-level economic entity. Internal allocations are claims on existing capital rather than new experiment funding. Its active-survival epochs prevent permanent-cash and token-trade gaming without imposing a raw trade count. The 4+1 protocol remains SIMULATION-only and unimplemented.
