# Phase 6 completion criteria

Status: **IN PROGRESS — CONTRACT FOUNDATION AND IN-MEMORY SCHEDULER IMPLEMENTED; END-TO-END REPLAY NOT IMPLEMENTED.**

Phase 6 is complete only when one deterministic offline pipeline consumes canonical Phase 2 data and causally drives accepted Phase 3 indicators, Phase 4 decisions, Phase 5 risk/reservation state, simulated execution, portfolio accounting and structured retained results. Passing the foundation model tests does not satisfy this completion invariant.

## Implemented foundation evidence

| Area | Implemented contract evidence | Remaining behavioral evidence |
| --- | --- | --- |
| Run identity | Immutable manifest binds dataset, participant ownership, strategy/model dimensions, indicator/risk/management/configuration, execution/cost models, starting capital and SIMULATION replay dimensions | Runner must resolve and retain the exact manifest and reject absent/mismatched artifacts |
| Causal clocks | Market references separate interval/event/availability; orders separate decision/submission/eligibility/expiry; fills separate simulated execution from causal recording; scheduler exposes envelopes only in canonical order | Orchestration must prove no future bar/indicator/quality/portfolio/fill payload state enters a decision |
| Event order | Versioned phase ranks and stable dependency-aware tie-break keys; equal-time position changes/realized trades/checkpoints and order-insensitive artifact registries derive from the canonical trace; content-identified schedule consumes each envelope once with deterministic exhaustion | Discrete orchestration loop must create and process payload effects in the specified sequence independent of worker order |
| Simulation execution | MARKET-only full-fill contract; strict later eligibility; next eligible same-XNYS-session bar open; calendar-bounded expiry; typed unique terminal fill/unfilled/no-data/rejected resolution linkage; stop-first ambiguity; no randomness | Scheduler must emit terminal outcomes; order status/cancel behavior, liquidity gates, fixed stop/target and reservation lifecycle must execute |
| Costs | Content-identified exact minimum/per-share/spread/slippage/other-fee components | Sourced `SIMULATED_IBKR_US_TIERED`, round-trip reconciliation, rounding/regulatory/FX behavior remain |
| Portfolio | Cash partitions plus canonical-event-ordered in-memory COMPLETE reconciliation derive fill notional, costs, cash, open positions/cost basis, realized/unrealized/gross/net P&L, trades and equity; supplied snapshots/trades must match exactly | Transactional/idempotent posting service, durable ledger/restart, external marks, broader lifecycle and injected publication-failure recovery remain |
| Results | Content-identified result linkage, typed terminal resolution references, deterministic UTF-8 NDJSON trace bytes/hash and schedule/run/prefix-bound in-memory checkpoints | Durable checkpoint/artifact store, crash restart, indexing, retention and dashboard inputs remain |
| Isolation/authority | Run/order/fill/position/result identities carry account, allocation and agent; SIMULATION + replay only; package has no broker/provider/network/AI imports | Multi-participant orchestration and adversarial cross-agent execution/storage tests remain |

## Completion gates

Phase 6 must not be marked COMPLETE until all of these pass:

1. A deterministic scheduler replays canonical Phase 2 records strictly by `available_at`, not only event time.
2. Accepted Phase 3 indicators update from causal prefixes and retain visible quality lineage.
3. Phase 4 strategies evaluate only after those inputs are available; NO_TRADE remains a persisted normal outcome.
4. Phase 5 risk and reservation receive the exact causally current participant/parent state.
5. Simulation order state, expiry, rejection, cancellation, fill and fixed protection/exit behavior are deterministic and fail closed.
6. A completed-bar decision cannot fill from the same bar; V1 fills use the next eligible same-session bar open and are published only when its source becomes available.
7. Reservation, cash, position, costs, realized/unrealized P&L and equity transition atomically and conserve value under duplicate/failure/replay cases.
8. Gross and net trading P&L reproduce exactly; every commission/spread/slippage/fee is attributable and debited once.
9. Same immutable dataset/configuration/state produces byte-identical ordered events, decisions, orders, fills, portfolios, result identities and P&L.
10. Adding or changing future data cannot alter any earlier decision, risk result, order or fill.
11. Missing intervals, gaps, halts, stale inputs, unavailable liquidity, end-of-data and ambiguous stop/target paths produce the configured conservative result rather than fabricated fills.
12. Structured run artifacts survive a process restart with checksum/integrity verification, or Phase 6 is explicitly limited to non-restartable diagnostic runs and cannot feed promotion evidence.
13. Multiple isolated participant fixtures can consume equivalent shared data without sharing cash, reservations, positions, risk, costs, orders or results.
14. Full regression, focused unit/property/integration/replay/injected-failure tests, static checks, documentation consistency and independent competent human review pass.
15. No broker SDK, network/provider call, paid AI, PAPER, LIVE or external order authority exists.

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

## Explicitly out of scope

Phase 6 does not include external market-data ingestion, empirical strategy validation, Phase 7 historical research, capital-sweep/MVC experiments, the four-agent experiment runner, AI inference, broker adapters, IBKR, Kraken, PAPER, LIVE, frontend/3D office, production deployment or claims of profitability. Dynamic management remains separately versioned and unvalidated; fixed protection/exit behavior is the first simulation target.

See [[06 - Testing/Backtesting]], [[05 - Brokers/Simulation]], [[01 - Architecture/Portfolio Accounting/Portfolio Accounting]], [[04 - Costs & Economics/Transaction Costs]] and [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]].
