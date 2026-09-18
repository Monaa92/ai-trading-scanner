# Phase 6 completion criteria

Status: **IN PROGRESS — FOUNDATION/SCHEDULER/ORCHESTRATION ACCEPTED; MILESTONE 6.1 REMEDIATION IMPLEMENTED AND AWAITING INDEPENDENT RE-REVIEW.**

Phase 6 is complete only when one deterministic offline pipeline consumes canonical Phase 2 data and causally drives accepted Phase 3 indicators, Phase 4 decisions, Phase 5 risk/reservation state, simulated execution, portfolio accounting and structured retained results. Passing the foundation model tests does not satisfy this completion invariant.

## Implemented foundation evidence

| Area | Implemented contract evidence | Remaining behavioral evidence |
| --- | --- | --- |
| Run identity | Immutable V1 manifest binds the accepted foundation fields. V2 adds the complete `SimulationLiquidityConfiguration`; changing its version/participation/policy changes run identity, while accepted V1 identities remain stable and cannot initialize the 6.1 resolver. | Runner must resolve and retain the exact manifest and reject absent/mismatched artifacts |
| Causal clocks | Market references separate interval/event/availability; executable scheduling requires the fully validated typed artifact; one-event orchestration intersects the Phase 2 as-of view with the actually consumed market-event prefix. The 6.1 candidate resolves only an atomic released-prefix view and keeps unreleased/equal-time future records invisible. | Fill, portfolio and protection events must preserve this boundary |
| Event order | Versioned phase ranks and stable dependency-aware tie-break keys; equal-time position changes/realized trades/checkpoints and order-insensitive artifact registries derive from the canonical trace; one process-local cursor consumes each envelope once. The orchestration step advances only through `next_event()` and never mutates schedule history. | The later execution loop must create and process order/fill/portfolio effects in the specified sequence independent of worker order |
| Strategy/risk orchestration | All four registered strategy configurations run through the existing Phase 3 calculators and Phase 4 evaluator with identical normalized market evidence in equivalent runs. Reconstruction derives the exact causal slice and independently recomputes indicators and the decision. NO_TRADE produces immutable evidence and no risk mutation. Proposals go through the existing Phase 5 risk engine and atomic coordinator; immutable process-local transition evidence binds the exact attempt, reservation and pre/post capital state. Candidate `b76891f7a1d787c2c07d26c0f4dd6a42df55aada` passed final targeted review. | Multi-participant historical runner, durable evidence store and integration with execution/accounting remain |
| Simulation execution | MARKET-only full-fill contract plus unreviewed 6.1 remediation: authoritative cursor-bound idempotent creation, atomic versioned projection, strict later same-session candidates, V2 manifest-bound full-fill liquidity, engine-stamped cancellation, resolver-authoritative provenance and non-future-dated terminal evidence | Independent 6.1 re-review; then fill creation, cost/FX, reservation lifecycle, accounting and fixed stop/target remain |
| Costs | Content-identified exact minimum/per-share/spread/slippage/other-fee components | Sourced `SIMULATED_IBKR_US_TIERED`, round-trip reconciliation, rounding/regulatory/FX behavior remain |
| Portfolio | Cash partitions plus canonical-event-ordered in-memory COMPLETE reconciliation derive fill notional, costs, cash, open positions/cost basis, realized/unrealized/gross/net P&L, trades and equity; supplied snapshots/trades must match exactly | Transactional/idempotent posting service, durable ledger/restart, external marks, broader lifecycle and injected publication-failure recovery remain |
| Results | Content-identified result linkage, typed terminal resolution references, deterministic UTF-8 NDJSON trace bytes/hash and scheduler-issued current-state in-memory checkpoints; content identity is not authentication | Durable monotonic checkpoint/artifact store, cross-process anti-rollback, crash restart, indexing, retention and dashboard inputs remain |
| Isolation/authority | Run/order/fill/position/result identities carry account, allocation and agent; orchestration rejects foreign capital scope and binds proposal/risk/reservation ownership. Equivalent per-agent runs share immutable market evidence while coordinators remain separate. SIMULATION + replay only; package has no broker/provider/network/AI imports. | Final multi-participant runner plus adversarial cross-agent execution/storage tests remain |

## Completion gates

Phase 6 must not be marked COMPLETE until all of these pass:

1. A deterministic scheduler replays canonical Phase 2 records strictly by `available_at`, not only event time.
2. Accepted Phase 3 indicators update from causal prefixes and retain visible quality lineage. **Implemented and accepted with authoritative reconstruction in causal-orchestration remediation `b76891f7a1d787c2c07d26c0f4dd6a42df55aada`.**
3. Phase 4 strategies evaluate only after those inputs are available; NO_TRADE remains a persisted normal outcome. **Implemented with authoritative decision recomputation; durable persistence remains pending.**
4. Phase 5 risk and reservation receive the exact causally current participant/parent state. **Implemented and accepted with immutable process-local pre/post transaction evidence for the one-event orchestration step; execution lifecycle integration remains pending.**
5. Simulation order state, expiry, rejection, cancellation, fill and fixed protection/exit behavior are deterministic and fail closed.
6. A completed-bar decision cannot fill from the same bar; V1 fills use the next eligible same-session bar open and are published only when its source becomes available.
7. Reservation, cash, position, costs, realized/unrealized P&L and equity transition atomically and conserve value under duplicate/failure/replay cases.
8. Gross and net trading P&L reproduce exactly; every commission/spread/slippage/fee is attributable and debited once.
9. Same immutable dataset/configuration/state produces byte-identical ordered events, decisions, orders, fills, portfolios, result identities and P&L.
10. Adding or changing future data cannot alter any earlier decision, risk result, order or fill. **Decision/risk prefix isolation is covered; order/fill coverage remains pending.**
11. Missing intervals, gaps, halts, stale inputs, unavailable liquidity, end-of-data and ambiguous stop/target paths produce the configured conservative result rather than fabricated fills.
12. Structured run artifacts survive a process restart with checksum/integrity verification, or Phase 6 is explicitly limited to non-restartable diagnostic runs and cannot feed promotion evidence.
13. Multiple isolated participant fixtures can consume equivalent shared data without sharing cash, reservations, positions, risk, costs, orders or results.
14. Full regression, focused unit/property/integration/replay/injected-failure tests, static checks, documentation consistency and independent competent human review pass.
15. No broker SDK, network/provider call, paid AI, PAPER, LIVE or external order authority exists.
16. Causal EUR/USD observations, conversion legs and reporting marks reconcile every multi-currency checkpoint; stale/missing FX blocks unsupported valuation or exposure without future leakage.
17. The durable journal, monotonic cursor/checkpoint and hash-linked evidence recover after process failure without rollback, duplicate effects or mutable-history trust.
18. Agent 5's top-level entity and every descendant conserve one initial capital contribution under creation, transfer, reservation, fill, retirement, concurrency and retry; no internal action can change the frozen world/objective or administrative authority.
19. Active-survival epochs distinguish justified NO_TRADE, no-opportunity inactivity, permanent-cash gaming, meaningless token trades, economic death and protocol inactivity failure under a preregistered policy.
20. A deterministic 4+1 fixture proves equivalent causal evidence, isolated top-level economics, reconstructable Agent 5 policy/organization state and immutable comparable result artifacts. The serious historical run itself remains Phase 7 research.

## Required adversarial fixtures

- A bar available at 10:05:02 can influence a 10:05:02-or-later decision but cannot produce a 10:05 open fill; the first 5-minute candidate is 10:10.
- Fill and portfolio update at a boundary precede newly available data and the next decision; stable tie-break keys make symbol arrival order irrelevant.
- No eligible next bar before expiry records an unfilled terminal outcome without releasing/consuming capital twice.
- Gap-open, missing interval, halted interval and same-bar stop+target paths follow registered policies and surface ambiguity/coverage state.
- Duplicate/out-of-order events and fills do not duplicate cash, quantity, costs, realized trade episodes or counters.
- Injected failure at every reservation→order→fill→portfolio→artifact publication boundary restores or recovers one consistent state.
- A future-data perturbation leaves the earlier trace prefix byte-identical.
- Two agent runs sharing a dataset hash retain distinct account/allocation/agent identities and independent accounting.
- Cost profile/version change produces new run/result identities while old artifacts retain their original components.
- Float, NaN/infinity, negative values, currency mismatch, stale lineage, unsupported order/partial/randomness assumptions and invalid time order fail closed.
- Causal FX perturbation cannot alter an earlier conversion/valuation; a missing or stale required FX observation blocks rather than borrowing a later rate.
- Crash before/after each cursor, order, fill, ledger, checkpoint and artifact-publication boundary resumes to exactly one committed transition or none.
- Creating, nesting or concurrently funding many Agent 5 descendants cannot increase entity equity, buying power, reservation headroom or exposure.
- Forged role/policy/allocation/death evidence, stale policy revisions, cyclic organization and source/world mutation requests fail closed and remain audited.
- Permanent cash inactivity in opportunity-bearing epochs and economically meaningless tiny/churn trades cannot qualify as active survival; legitimate causal NO_TRADE remains valid.

## Explicitly out of scope

Phase 6 does not include external market-data ingestion, empirical strategy validation, the actual Phase 7 historical study, capital-sweep/MVC research, AI provider inference, broker adapters, IBKR, Kraken, PAPER, LIVE, frontend/3D office, production deployment or claims of profitability. It must provide the isolated deterministic runner and Agent 5/4+1 harness needed to make later historical evidence trustworthy. A future AI adapter is independently authorized and is not required for a deterministic registered Agent 5 policy. Dynamic management remains separately versioned and unvalidated; fixed protection/exit behavior is the first simulation target.

See [[06 - Testing/Backtesting]], [[05 - Brokers/Simulation]], [[01 - Architecture/Execution/Replay and Simulation Architecture]], [[02 - Agents & Strategies/Autonomous Survival Agent]], [[03 - Experiments/4+1 Historical Experiment]], [[01 - Architecture/Portfolio Accounting/Portfolio Accounting]], [[04 - Costs & Economics/Transaction Costs]], [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]], [[00 - Project/Decisions/ADR-034 - Atomic deterministic simulation execution]] and [[00 - Project/Decisions/ADR-035 - Autonomous survival economic entity]].
