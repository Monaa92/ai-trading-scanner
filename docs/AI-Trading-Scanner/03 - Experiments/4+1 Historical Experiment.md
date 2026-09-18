# 4+1 historical experiment

Status: **DESIGNED — NOT REGISTERED OR RUN.** This is a future Phase 6 readiness/Phase 7 research protocol. It does not change the existing four-agent Experiment 1 or select final historical dates, instruments, costs, FX observations or thresholds.

## Research shape

Five top-level participants consume equivalent causal market and FX evidence:

| Participant | Architecture | Mutable policy during run |
| --- | --- | --- |
| Agent A | Momentum / Trend Following `BASELINE_RESEARCH_V1` | No |
| Agent B | Mean Reversion `BASELINE_RESEARCH_V1` | No |
| Agent C | Breakout / Volatility `BASELINE_RESEARCH_V1` | No |
| Agent D | Multi-Factor / Opportunistic `BASELINE_RESEARCH_V1` | No |
| Agent 5 | [[02 - Agents & Strategies/Autonomous Survival Agent]] | Yes, only inside the frozen adaptation envelope |

The first four remain unvalidated deterministic research policies. Agent 5 is a different adaptive architecture, so this experiment compares participant systems rather than isolating strategy profile alone. Any strategy-only or model-only causal claim requires a separate controlled experiment. No profitability or superiority claim follows from one 4+1 run.

## Frozen registration

Before any participant sees outcomes, one experiment registration binds:

- point-in-time US-equity universe and membership provenance;
- historical period, train/development/holdout role and holdout-access history;
- canonical dataset, calendar and market/FX availability methodology;
- identical starting capital amount and EUR base currency per top-level participant;
- execution, liquidity, ambiguity, end-of-run, cost and FX profiles;
- risk limits and fixed stop/target management baseline;
- strategy configurations for A–D;
- Agent 5 initial policy, adaptation envelope, activity/survival/death policies;
- evaluation schedule, horizon, stopping, failure and incomplete-run rules;
- reporting metrics, comparison family and uncertainty limitations;
- software revision, schema versions and durable-storage target.

Numeric values that are currently open block registration. Existing EUR50 examples remain experiment configurations, not engine assumptions or recommendations.

## Equivalent information and independent economics

One canonical evidence fan-out records a content identity for each released batch. All five participant schedules reference the same market/FX records, `available_at` cutoffs, calendar, universe and information availability. A participant may process or decide differently, but cannot see a record before the others are eligible to see it.

Each top-level participant owns a distinct account, allocation, coordinator namespace, journal, orders, fills, positions, reservations, costs, P&L, survival state and result. No participant can read another participant's private decisions, organization, portfolio or outcome. Shared caches contain immutable input/feature artifacts keyed by complete version and data identities; they contain no mutable account state.

Agent 5 descendants remain inside Agent 5's single economic entity and do not become extra experimental arms or receive extra capital. Infrastructure contention, processing delay and missing delivery are measured per participant. If shared-resource effects differ, equivalence is marked limited rather than assumed.

## Fairness boundaries

Agent 5 is intentionally more adaptive than A–D. Its permitted advantage is causal self-organization within frozen rules. It may not receive future records, hidden benchmark results, other-agent state, future test performance or execution facts unavailable at its decision time.

The activity opportunity reference is engine-owned and computed from the same evidence. It is used to detect inactivity gaming, not supplied with future profitability labels. Agent 5's policy cannot inspect which reference opportunities later won.

Randomness remains disabled initially. If a future model produces nondeterministic reasoning, the captured output is immutable input to deterministic validation and replay. Model comparison requires separate registrations so strategy and model dimensions remain separable.

## Run and result structure

The experiment coordinator advances one canonical evidence position and obtains an isolated committed transition from every nonterminal participant. A deterministic participant-order rule prevents worker scheduling from changing outcomes. One participant failure does not mutate another; experiment-level infrastructure failure records the affected scope and follows the registered stop/recovery policy.

Every completed result retains ending equity, return, gross/net realized and unrealized P&L, every cost category, drawdown, turnover, trade/NO_TRADE counts, exposure, decision/data coverage, survival duration and endpoint. Agent 5 additionally retains policy/organization evolution, internal allocations, activity epochs, economic-state history, death/estate evidence and world-boundary violations.

Comparison requires matching dataset/evidence, horizon, cost/FX/execution/risk profiles and completeness. Results with different causal inputs, missing marks, unresolved positions or failed durable recovery are not labeled equivalent. Failed, inactive, dead, aborted and incomplete participants remain in the result set.

## READY FOR FIRST SERIOUS 4+1 HISTORICAL TEST

The project reaches this state only when all conditions below are implemented, independently reviewed and verified from a fresh process:

1. Phase 2 causal data and provenance cover the registered period/universe with explicit quality limitations.
2. The accepted scheduler/orchestrator plus complete order, resolution, fill and fixed position lifecycle produce no same-bar/future leakage.
3. Sourced versioned transaction-cost and causal EUR/USD FX profiles reconcile expected and realized economics.
4. Atomic reservation, cash, cost, FX, position, trade and equity posting conserves every participant's capital under duplicates, concurrency and injected failures.
5. End-of-run policy and all terminal orders/positions reconcile or classify the run incomplete.
6. Durable journal/checkpoint recovery proves monotonic resume, anti-rollback and byte-identical replay/result evidence.
7. Five isolated top-level accounts consume equivalent evidence without state/capital contamination.
8. Agent 5 entity conservation, active-survival, death, policy mutation and sub-agent lifecycle withstand the adversarial tests in [[06 - Testing/Test Strategy]].
9. Immutable result artifacts reproduce all reported metrics and retain negative/failed outcomes.
10. Exact experiment inputs, comparison plan and open limitations are preregistered; the final holdout has not been repeatedly inspected.
11. Full regressions, static/documentation checks and independent competent review pass.

This label means the architecture can produce trustworthy historical research evidence. It does not mean any strategy is profitable or ready for external execution.

## NOT YET PAPER READY

Historical-test readiness does not provide broker-hosted PAPER authority. Paper readiness still requires the broker adapter, capability validation, account reconciliation, external-order idempotency, protection behavior, outage/restart handling, credentials/secrets operations, kill switches and independent paper-specific review in [[06 - Testing/Paper Trading]]. Agent 5 would require an additional explicit paper experiment registration and cannot inherit simulation authority.

## NOT YET LIVE READY

Neither this design nor a successful historical/Agent 5 result grants LIVE authority. LIVE requires the later roadmap evidence, deliberate owner configuration, external safety/reconciliation operations and independent live-readiness decision. FULL_AUTO never implies LIVE. Agent 5 and future model runtimes can never enable it themselves.

## Open registration decisions

- historical dates, point-in-time universe and dataset licensing/provenance;
- sourced numeric cost and FX profiles, freshness and rounding;
- liquidity participation and partial-fill policy;
- terminal-liquidation timing;
- opportunity-reference, materiality, epoch and active-participation thresholds;
- ruin floor and minimum economically executable capital methodology;
- first durable storage/backup deployment and restore target;
- initial deterministic Agent 5 policy provider and whether any later model experiment is separate;
- sample size, repeated-run structure and uncertainty method.

See [[03 - Experiments/Experiment Framework]], [[03 - Experiments/Autonomous Experiments]], [[03 - Experiments/Survival Analysis]], [[01 - Architecture/Execution/Replay and Simulation Architecture]] and [[06 - Testing/Phase 6 Completion Criteria]].
