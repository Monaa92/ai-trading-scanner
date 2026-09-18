# Autonomous Survival Agent

Status: **DESIGNED — AGENT 5 IS NOT IMPLEMENTED OR ACTIVATED.** Agent 5 is a future adaptive participant inside deterministic SIMULATION. It is not a fifth fixed Phase 4 strategy, is not part of Experiment 1, and receives no broker, network, AI-provider, PAPER or LIVE authority.

[[00 - Project/Decisions/ADR-035 - Autonomous survival economic entity]] records the governing decision. [[01 - Architecture/Execution/Replay and Simulation Architecture]] defines the immutable economic world in which the agent may operate.

## Objective and experiment semantics

Agent 5 receives one initial virtual-capital contribution. No deposit, refill, bailout, descendant funding or resurrection is allowed after initialization. Legitimate trading P&L and posted costs change its capital. Internal allocations only partition existing economic value.

Its primary research objective is **maximize active economic survival duration through selective trading and sustainable capital growth**. This is evaluated lexicographically rather than collapsed into a tunable scalar:

1. remain within the immutable world, authority and risk constraints;
2. maximize completed active-survival epochs before ruin or protocol failure;
3. among equal survival durations, prefer greater net liquidation value and capital growth;
4. then prefer lower drawdown, lower cost drag and less inefficient turnover under the registered comparison rule.

The finite experiment horizon prevents “not yet dead” from becoming infinite success. Administrative horizon completion is right-censored survival evidence, not proof of immortality. Total return alone is insufficient, and trade count alone is never an objective.

## Active-survival requirement

Cash inactivity and meaningless tiny trades are separate gaming attacks. The run therefore freezes an `ActiveSurvivalPolicy` with evaluation epochs, a causal opportunity-reference policy, minimum economic materiality, participation measurement and terminal inactivity rule. Numeric values remain unselected until preregistration.

The opportunity reference is an engine-owned, deterministic and strategy-neutral rule evaluated from the same causal market evidence. It identifies windows in which at least one trade was economically executable after the registered costs, liquidity, capital and hard-risk constraints. Agent 5 cannot define, suppress or edit this reference after seeing outcomes.

For each finite epoch the engine records:

- eligible opportunity mass and unavailable-data coverage;
- Agent 5 evaluation coverage and every TRADE/NO_TRADE decision;
- economically meaningful participation mass;
- net capital contribution, cost drag, exposure and drawdown;
- missed eligible windows with causal reasons;
- whether the epoch satisfies the preregistered active-participation rule.

Participation mass is risk-and-time weighted rather than a raw trade count. A trade counts only when it passes ordinary proposal/risk/execution gates, reaches a materiality floor relative to causally current entity equity, and creates actual exposure. Splitting one economic action, submitting unfillable orders, immediate wash-like churn or trading below the materiality floor does not increase participation. The policy caps any one trade's contribution so a single token action cannot satisfy a long activity window.

Agent 5 retains first-class `NO_TRADE` for every individual opportunity. Epochs with no reference-qualified opportunity have no activity obligation. Epochs with qualified opportunities may still contain many justified NO_TRADE decisions, but persistent failure to achieve the frozen participation requirement ends the active-survival run as `INACTIVE_FAILURE`. This is a protocol endpoint, not fabricated financial death: the entity can remain economically ALIVE while its experiment participation is terminal.

This construction has explicit consequences:

- permanent cash holding cannot win because opportunity-bearing inactive epochs terminate active survival;
- arbitrary frequent trading cannot win because only material exposure counts and losses/costs reduce the higher-priority survival/equity objectives;
- the reference rule can bias which opportunities count, so its version and sensitivity analysis must be reported;
- thresholds selected after observing Agent 5 outcomes would invalidate the run;
- no-opportunity regimes correctly allow inactivity rather than forcing bad trades.

## One economic entity

Agent 5 and all descendants share one stable `economic_entity_id`, one top-level account/allocation and one authoritative ledger. A descendant has a `sub_agent_id`, role/policy identity and an internal allocation envelope, but never owns newly created capital.

At every committed checkpoint:

```text
entity available capital
+ descendant available allocations
+ descendant reservations
+ committed capital
+ posted position cost/economic value adjustments
= reconciled Agent 5 economic capital
```

Internal budgets are exclusive claims against the parent's existing allocatable balance. Creating a child atomically decreases unallocated entity capacity or transfers capacity from another child; it cannot change total entity equity or broker buying power. Reservations remain owned by the economic entity and attributed to exactly one descendant. One order/fill cannot be copied across descendants. Leverage, borrowing, shorting and negative allocations are unavailable unless a later experiment profile explicitly adds and bounds them.

Only the deterministic `Agent5EntityCoordinator` may create, transfer, revoke or retire internal allocations. It validates parent/child ownership, revisions, outstanding reservations, open positions and conservation in the same transaction. Retiring a child with exposure or unresolved orders is forbidden; it first enters draining state and loses new-exposure authority.

## Self-organization

Self-organization means changing versioned policy state, roles and internal allocations. It never means editing source code or loading arbitrary executable code.

Agent 5 may propose:

- create a sub-agent with a declarative role and registered capability set;
- drain and retire a sub-agent;
- replace a role/policy with a new immutable version;
- transfer an internal allocation within entity limits;
- select or combine registered strategy/evaluation primitives;
- change decision cadence or internal routing within frozen bounds;
- promote or retire an internal policy using causal evidence.

Roles are open-ended labels plus a constrained declarative policy specification. The architecture does not hard-code scanner, momentum, regime or critic as the only roles. An invented role becomes executable only when its requested capabilities map to registered validators and deterministic services. Text alone grants no capability.

There is no architecture-defined fixed role list or required child count. Agent 5 may create any finite organization that fits the preregistered compute, inference and concurrency quotas. Those operational quotas prevent denial-of-service and child-spam gaming; they do not create trading capital. Usage/cost remains in the separate AI/operating ledger, and Net Economic P&L may report it without debiting portfolio cash.

Each accepted mutation emits immutable `PolicyTransitionEvidence` containing old/new policy identities, parent transition, requested action, reason, exact causal evidence set, scheduler position/time, proposer identity, validation result, affected sub-agent identities, internal allocations, configuration and resulting organization hash. Rejected proposals are retained. Organization history is reconstructable from the initial state plus ordered transitions.

The organization is an acyclic ownership tree rooted at the economic entity. Stable identities are never reused. A policy revision creates a new identity and predecessor link; it does not rewrite historical decisions. Concurrent changes use expected revision and deterministic ordering, so one wins and the others re-evaluate current state.

## Frozen adaptation envelope

Agent 5 complies with the project's frozen autonomous-experiment rule by preregistering:

- initial organization and policy identity;
- policy-update algorithm/provider interface and update cadence;
- allowed proposal/action schemas and capability bounds;
- role-definition schema and registered executable primitives;
- risk, execution, cost, FX, survival, activity and death rules;
- internal-allocation limits and conservation rules;
- model/prompt policy if a future model is used;
- randomness and retry/failure treatment;
- experiment horizon and termination rules.

The resulting policy state may evolve causally. The envelope itself may not. Expanding capabilities, replacing the update algorithm, changing the objective or relaxing a boundary starts a new versioned run.

## Immutable world boundary

Neither Agent 5 nor a descendant may modify or bypass:

- application source, registered executable primitives or dependency set;
- scheduler, event ordering, causal visibility or market/FX history;
- execution, ambiguity, liquidity, cost or accounting rules;
- risk/safety limits, lockouts, approval policy or operating authority;
- entity ledger, capital reconciliation or identity/provenance validation;
- survival/activity objective, ruin condition, horizon or experiment manifest;
- durable event evidence, checkpoints, prior policy versions or results;
- credentials, network endpoints, broker adapters or environment switches.

The policy runtime receives a read-only, allowlisted causal view and emits typed proposals. File-system, process, network, database mutation, reflection into coordinator internals and administrative APIs are outside its capability set. World-boundary violations are retained as rejected actions and can terminate the experiment under the frozen protocol.

## Future AI/model boundary

A future provider-independent `ReasoningAdapter` may produce analysis, policy proposals, sub-agent definitions, allocation requests, trade proposals and retirement requests. It is not an authority.

Every response is captured in an immutable `ModelDecisionEnvelope` with model/provider/version when known, prompt/policy/schema identities, exact allowlisted causal input identity, generation parameters/seed if available, raw response hash, parsed output identity, parent policy, requested action, timestamps/token/cost evidence and deterministic validation result. Secrets are excluded.

Economic replay never calls the remote model to reproduce history. It replays the captured envelope through the deterministic validator. A new inference is a new evidence event or counterfactual run. Thus the market clock, order/fill/accounting engine and application of validated actions remain deterministic even if model reasoning is nondeterministic.

Model timeouts, malformed output, unknown model revision or budget exhaustion yield a typed failure/NO_ACTION according to the frozen policy. AI/API spend posts only to the separate operating-cost ledger and cannot reduce or increase trading cash. A model cannot allocate capital, create a child, place an order or change a policy without engine validation and atomic commit.

## Survival state and death

Agent 5 uses three economic states plus a separate experiment endpoint:

- `ALIVE`: causally marked net liquidation value and execution viability are above registered warning/ruin conditions;
- `AT_RISK`: warning condition met, data/FX marks degraded, or viability is approaching the registered floor; hard risk may restrict new exposure;
- `DEAD`: the objective deterministic ruin predicate has latched;
- `INACTIVE_FAILURE`: an experiment terminal reason, not an economic state.

At each authoritative checkpoint the engine computes conservative net liquidation value from cash in every currency, current causally available FX, positions marked under the registered liquidation policy, accrued execution/FX costs and liabilities. The ruin predicate and `minimum_economically_executable_capital` methodology are immutable configuration. The latter is derived from the registered universe, quantity increments, costs and risk limits; it is not a convenient fixed amount chosen after results.

Missing/stale marks do not prove death or safety. They put the entity AT_RISK, block new exposure and invoke the data-failure policy. `DEAD` latches when the registered value/solvency predicate is conclusively met at an authoritative checkpoint. It is irreversible even if later prices would have recovered.

On the death transition, every descendant immediately loses proposal and new-exposure authority; pending entries are cancelled; no internal policy mutation can restore authority. Open positions become an engine-owned estate. The deterministic liquidation policy tries to resolve them through later causal execution evidence. `EstateResolutionStatus` records flat, residual exposure, unavailable data and final conservative value separately. The entity remains DEAD throughout; liquidation proceeds cannot resurrect it. End-of-data without a fill retains residual exposure and an incomplete estate rather than fabricating value.

## Audit and outputs

Agent 5 results include ordinary run/accounting metrics plus active-survival epochs, opportunity/reference coverage, meaningful participation, inactivity endpoint, economic-state history, ruin/death evidence, estate resolution, capital trajectory, child creation/retirement, policy revisions, allocation transfers, organization snapshots, rejected mutations, world-boundary violations and causal reasons for major changes. Results distinguish capital survival, active autonomous operation, lockouts/interventions and experiment completion/failure.

Agent 5 is compared with Agents A–D under [[03 - Experiments/4+1 Historical Experiment]]. Its flexibility is intentional, but it receives no privileged market evidence, other-agent state or future outcomes.

See [[01 - Architecture/Agent Architecture]], [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[03 - Experiments/Survival Analysis]], [[03 - Experiments/Autonomous Experiments]] and [[04 - Costs & Economics/AI Inference Costs]].
