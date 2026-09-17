# Replay and simulation architecture

Status: **DESIGNED — NOT IMPLEMENTED BEYOND THE ACCEPTED PHASE 6 FOUNDATION, SCHEDULER AND CAUSAL ORCHESTRATION.** This note defines the target deterministic SIMULATION architecture. It grants no broker, network, PAPER or LIVE authority.

The accepted contracts in `ai_trading_scanner.simulation`, the Phase 2 causal data model, Phase 3 indicator semantics, Phase 4 decisions and proposals, and Phase 5 risk/reservation coordinator remain authoritative. [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]] defines event ordering, next-eligible-bar execution and V1 accounting assumptions. [[00 - Project/Decisions/ADR-034 - Atomic deterministic simulation execution]] records the extension designed here.

## Boundary and dependency direction

The simulator is the immutable economic world. Strategy or policy code proposes actions; it cannot mutate the clock, market history, execution rules, ledgers or artifacts.

```text
Frozen run manifest + canonical dataset + registered profiles
  -> authoritative replay artifact and schedule
  -> one leased scheduler transition
  -> causal market/FX prefix
  -> deterministic indicator and strategy/policy evaluation
  -> proposal or NO_TRADE
  -> risk/solvency validation and reservation
  -> simulated order command
  -> deterministic execution resolution
  -> fill or terminal no-fill evidence
  -> one atomic economic posting
  -> reservation/cash/cost/FX/position/trade/checkpoint events
  -> reconciliation and immutable result evidence
  -> next scheduler event
```

The scheduler authorizes event consumption but performs no domain mutation. The application execution coordinator invokes the future offline `SimulationBrokerAdapter`, which composes a pure resolver over a validated order, execution profile and causally released evidence; it has no credentials or network capability. The economic transaction service is the only writer for reservations, cash, positions, costs and realized trades. The artifact writer persists committed facts; reporting reads those facts and never posts accounting state.

Agents never call a broker-shaped interface. The execution coordinator is the only caller of `SimulationBrokerAdapter` and, in later phases, other `BrokerAdapter` implementations. Simulation orders are internal evidence and never imply an external submission. Future PAPER or LIVE execution must remain behind [[01 - Architecture/Broker Architecture]], separate environment configuration and later readiness gates.

## Frozen run inputs

Every executable run resolves one immutable manifest before the first event. In addition to the fields already implemented, the completed architecture binds:

- artifact, schedule and canonical dataset identities;
- agent, account, allocation, participant and economic-entity identities;
- strategy or adaptive-policy identity and initial state;
- indicator, risk, management-mandate and authority configuration identities;
- execution, order-lifecycle, liquidity, ambiguity and end-of-run policy versions;
- transaction-cost methodology and source evidence;
- base/trading currencies and FX methodology/source identities;
- XNYS calendar and market-data provenance;
- initial capital and no-external-flow policy;
- deterministic seed only for a future profile that explicitly permits randomness;
- storage schema, event-log and checkpoint versions;
- experiment horizon and terminal-resolution policy.

An absent, unknown, stale or incompatible required input blocks the run. Current V1 keeps randomness and partial fills disabled.

## Order evidence and lifecycle

`SimulatedOrder` is extended through versioned contracts rather than replaced. Every order binds the exact proposal, approval or automatic mandate, final risk decision, reservation, agent/account/allocation/economic entity, instrument, side, quantity, order type, creation event, eligibility time, expiry, execution profile and idempotency key. Recomputed identities cannot replace authoritative proposal, risk or reservation evidence.

The initial executable lifecycle is:

```text
CREATED -> ELIGIBLE -> FILLED
                    -> NO_ELIGIBLE_DATA
                    -> EXPIRED
                    -> REJECTED
          -> CANCEL_REQUESTED -> CANCELLED or FILLED
```

Only one terminal execution resolution may exist per order. Cancellation is a causally scheduled command, not retroactive erasure. A fill whose eligibility precedes the effective cancellation may still win according to canonical event order. Unsupported amendments, order types or quantities fail before order creation and release the reservation atomically.

V1 supports long-only market entry and deterministic engine-generated exits. Scale-in/pyramiding is unavailable. Partial fills remain disabled until a later profile defines deterministic liquidity allocation, remainder reservation, protection and performance-episode rules. The data model retains cumulative filled quantity and predecessor fields so partial fills can be introduced by a new version without changing ownership or accounting truth.

## Execution resolution

The accepted XNYS and next-eligible-bar rules remain unchanged:

1. A decision sees only records released through the consumed schedule prefix.
2. Eligibility equals submission time plus registered nonnegative latency.
3. A market order uses the first canonical bar open strictly later than eligibility, in the proposal's authoritative XNYS session and no later than expiry/session close.
4. The fill becomes observable only when that source record is causally available.
5. Missing intervals are never synthesized. If no eligible source exists, the order receives a typed terminal no-fill result.
6. A same-session gap uses the next eligible open. An intraday order never carries silently to another session.

The resolver records candidate records considered, the selected record, eligibility/expiry/session boundaries, price policy, liquidity decision, ambiguity policy and reason for every terminal outcome. A profile with a volume participation ceiling must specify whether missing volume blocks execution. V1 full-fill behavior requires the whole approved quantity to pass that deterministic gate; otherwise it records no fill. Future partial-fill behavior needs a new execution-profile version.

## Fixed stop and target lifecycle

Fixed stop plus fixed target remains the first baseline. Protection terms are copied from the immutable proposal/management mandate and cannot be weakened by an agent after entry.

For a long position, each causally released bar is evaluated without using later bars:

- if the open is at or below the stop, the conservative stop execution reference is the open;
- otherwise, if only the low reaches the stop, the stop reference is the stop price;
- if the open is at or above the target and no stop conflict exists, the target reference is the open;
- otherwise, if only the high reaches the target, the target reference is the target price;
- if one OHLC bar can contain both stop and target and ordering is unknowable, V1 applies the accepted `STOP_FIRST` policy;
- missing bars, halts or stale/unavailable records do not fabricate an exit.

An exit is still an order with eligibility, cost and terminal evidence. The system cannot use a bar's high or low to decide and fill earlier in that same bar. Gap, stop, target, strategy exit, risk intervention and end-of-run exit reasons remain distinct.

The run manifest schedules end-of-run liquidation early enough for the registered latency and bar interval. If no eligible fill exists before the data horizon, the run remains `INCOMPLETE_WITH_OPEN_EXPOSURE`; it does not invent a terminal price. A serious historical test must either resolve all positions or report the incomplete run outside completed-performance ranking.

## Atomic economic posting

One journal transaction owns each economic transition. Its input is an expected prior revision plus immutable command/evidence identities. Its commit appends all resulting events, updates projections and advances the monotonic cursor together. On any exception, none becomes authoritative.

For an entry fill the transaction atomically:

1. verifies the exact order, reservation, ownership, revisions and idempotency key;
2. consumes the filled reservation amount and releases any terminal remainder;
3. posts trading-currency cash/notional and every cost component exactly once;
4. posts any required FX conversion legs and FX cost;
5. opens the position and attaches immutable protection terms;
6. records the fill, position change, cost and balanced ledger events;
7. updates portfolio, risk and loss-state projections;
8. appends the portfolio checkpoint and authoritative result evidence;
9. commits the scheduler position and journal high-water mark.

Exit posting similarly reduces/closes the position, posts proceeds and costs, realizes P&L, releases protection commitments and emits a completed trade episode where quantity reaches zero. Reservations are encumbrances, never assets. The following must reconcile at every checkpoint:

```text
cash by currency + marked position value - liabilities = net liquidation value
starting capital + external flows + gross trading P&L - execution/FX costs = equity
parent unallocated capital + all child allocations/reservations/committed capital = parent economic capital
```

External flows are forbidden inside fixed-capital experiment segments. Corrections append compensating events; history is never rewritten.

## Exactly-once and concurrency

Every command has a deterministic key derived from run, scheduler event/position, owner, command kind and causal parent identities. The durable store enforces unique keys for strategy/policy evaluation, order creation, execution resolution, fill application, reservation transition, portfolio posting, policy mutation, sub-agent lifecycle and death transition.

A retry either returns the prior committed result or completes the still-uncommitted transaction. It cannot create a second economic effect. Optimistic revision checks and one fenced writer per economic account/entity serialize conflicting mutations. Read projections may be concurrent, but no reader may observe an intermediate reservation/fill/accounting state. Lock order is fixed: run cursor, parent/economic entity, allocation, instrument/position, artifact publication. A failure releases in reverse order.

The accepted scheduler lease remains the sole cursor authority. Domain services receive the leased transition capability, never a public consumable cursor. Cursor position, authoritative evidence and economic effects share the same commit boundary once durability is implemented.

## Costs

Each resolved cost profile is immutable, content identified and source attributed. It can express entry/exit commission, minimum/per-share/rate components, exchange/regulatory fees, spread, slippage, impact and FX conversion cost with explicit rounding and currency rules. No current IBKR value is assumed.

Phase 4 expected round-trip costs and Phase 6 realized fill costs must reference compatible methodology versions. Expected costs gate proposals; realized costs post from actual quantity and price. The result keeps both and attributes estimation error. A component embedded in fill price is not also debited as cash. Unknown required cost behavior blocks execution.

## EUR/USD FX

FX is causal market evidence, not configuration text containing a convenient rate. An immutable `FxObservation` binds provider/source, EUR/USD pair, observation time, availability time, bid/ask or declared reference, quality/freshness and methodology version. It enters the schedule like other market evidence and cannot be used before `available_at`.

The initial experiment profile should use a separately registered conversion policy, tentatively `INITIAL_CONVERSION_AND_REPORTING_MARK_V1`:

- initial EUR funding is converted to a USD trading balance only through the latest eligible causal observation at the configured conversion event;
- the conversion posts balanced EUR and USD ledger legs plus explicit FX cost;
- equity reporting converts each currency and marked position with the latest eligible causal FX observation at the checkpoint;
- stale or missing required FX marks make valuation unavailable and block new exposure; they are never replaced with a future or hard-coded rate;
- all five comparative arms use the same observation identities and methodology.

The exact FX source, freshness, side/price convention and rounding remain open registration decisions. Multi-currency balances remain explicit; reported EUR equity never pretends USD cash is EUR.

## Durable artifacts and recovery

In-memory correctness is necessary but cannot support promotion evidence after a process crash. The durable design uses an append-only authoritative journal plus derived checkpoints. PostgreSQL remains the intended persistent store under [[00 - Project/Decisions/ADR-010 - PostgreSQL as intended persistent datastore]], accessed through repository contracts so small deterministic tests can use an in-memory implementation.

The durable transaction stores:

- frozen manifest/configuration and referenced artifact hashes;
- ordered immutable input and economic events;
- command/idempotency records and validation outcomes;
- monotonic scheduler position and prior checkpoint identity;
- portfolio, risk, reservation and Agent 5 policy/organization checkpoints;
- hash-chained journal segment identity and storage schema version;
- publication status for derived result artifacts.

Restart loads the greatest committed high-water mark, validates the manifest and event hash chain, verifies checkpoint revisions against journal replay, reconstructs projections, reconciles all balances/ownership and resumes from the next event. A checkpoint with a lower position, unknown predecessor, broken hash, mismatched manifest or economic divergence fails closed. No caller chooses a lower checkpoint. Artifact export uses atomic temporary-write, fsync and rename semantics or an equivalent transactional object-store publication; a derived file is never the commit authority.

Process-local mode remains useful for unit tests and diagnostic fixtures but is labeled `NON_DURABLE` and cannot satisfy serious-test, PAPER or LIVE promotion evidence. Backups and restore drills follow [[07 - Operations/Disaster Recovery]].

## Evidence and results

The immutable run result includes the full manifest, dataset and schedule identities; journal/checkpoint high-water marks; every decision/NO_TRADE, proposal, risk decision, order, resolution, fill, ledger/FX/cost posting, position episode and finalization; final cash/positions/equity; gross/net/realized/unrealized P&L; costs; drawdown/exposure/turnover; completeness and quality limitations. Agent 5 adds the evidence in [[02 - Agents & Strategies/Autonomous Survival Agent]].

Dashboards remain derived. A result is `COMPLETE` only when every order has one terminal resolution, every fill is posted once, all reservations terminate, all required marks exist, final positions follow the registered terminal policy, ledgers reconcile and the durable artifact validates from a fresh process.

## Initial versus later versions

Required for the first complete deterministic profile: market orders, full fills or typed no-fill, long-only single-entry position episodes, fixed stop/target, conservative stop-first ambiguity, explicit costs/FX, no external flows, end-of-run resolution, exact accounting and durable recovery.

Later versioned capabilities include partial fills, limit orders, scale-in, short selling, stochastic/queue models, higher-resolution intrabar evidence, dynamic management and broker-derived profiles. Adding them must preserve old artifacts and cannot silently alter V1 results.

See [[01 - Architecture/Execution/Order Lifecycle]], [[01 - Architecture/Portfolio Accounting/Portfolio Accounting]], [[04 - Costs & Economics/Transaction Costs]], [[05 - Brokers/Simulation]], [[06 - Testing/Backtesting]] and [[06 - Testing/Phase 6 Completion Criteria]].
