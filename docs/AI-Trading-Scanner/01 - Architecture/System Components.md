# Backend architecture

Status: mostly design specification. Phase 1 implements only domain identities, execution dimensions, configuration validation and local health boundaries. Parent: [[01 - Architecture/System Architecture]]. Other proposed module names remain documentation, not created packages.

## Ownership and dependency direction

| Boundary | Owns | May depend on |
| --- | --- | --- |
| Domain primitives | Money, quantity, IDs, time intervals, immutable records, reason codes | Standard numeric/time abstractions only |
| Calendar/session | Versioned sessions, open/close and cutoff lookup | Primitives, calendar port |
| Market data normalization | Provider-independent bars, revisions, provenance, quality | Primitives, session contracts |
| Indicators | Defined recurrences and readiness | Canonical bars, implementation version |
| Features | Causal combinations, support/resistance and multi-timeframe alignment | Indicators, available-data view |
| Strategy | Pure rule evaluation and proposed levels | Frozen feature snapshot, strategy config |
| Signals | Lifecycle, deduplication, expiry and candidate batch | Strategy results, clock port |
| Selection | Stable ranking or validated AI veto/ranking | Candidate records, optional AI port |
| Portfolio/account | Cash, settlements, fills, positions, reservations, equity | Primitives and immutable events |
| Risk | Size/reject with reasons and constraint calculations | Immutable account/quote/FX/capability snapshots |
| Order intents | Submission authorization, protective/exit intent linkage | Risk decision and order policy |
| Execution | Submission, cancellation and reconciliation orchestration | Broker port, ledger and persistence ports |
| Backtest | Replay clock, event ordering and execution simulator | Same domain services, dataset reader |
| Analytics | Trade aggregation and metrics | Ledger/trade/run records; never signals |
| Registry/configuration | Version validation, manifests and artifact identities | Primitives and persistence port |
| Application | Use cases, atomic transactions, locks, lifecycle routing | Domain services and ports |
| Adapters | SimulationBroker, future IBKR/Kraken, market-data providers, PostgreSQL, AI vendor, files, clock | Inner port contracts, external libraries |
| FastAPI | Authentication, input validation, read models, commands | Application use cases only |
| Frontend | Presentation and explicit user commands | Versioned API only |
| Audit/security | Event envelope, redaction, secret resolution, access checks | Shared interfaces injected at boundaries |

No strategy→broker, strategy→market-data provider, indicator→LLM, domain→FastAPI, or risk→UI dependency. Avoid global service locators. Orchestration supplies normalized snapshots to pure domain functions. The execution coordinator alone calls [[01 - Architecture/Broker Architecture]]. Reconciliation updates the internal ledger before subsequent risk evaluation. An independent account-writer lease/fencing token prevents two processes from submitting concurrently after restart.

## Conceptual contracts

| Port/service | Request → response |
| --- | --- |
| MarketDataProvider | HistoricalQuery(instrument IDs, half-open UTC range, interval, feed, adjustment mode, cursor) → page of raw records + next cursor + source metadata |
| MarketDataProvider | subscribe(instruments, channels, resume token if supported) → raw market/status/revision envelopes; gaps explicitly reported |
| AvailableData | snapshot(as_of, instrument, requirements) → only records with availability ≤ as_of, plus missing/quality flags |
| IndicatorEngine | evaluate(ordered bars, implementation version, state) → values, ready flags, dependency IDs, next state |
| StrategyEngine | evaluate(feature snapshot, immutable parameters) → pass/reject, rule results, proposed entry/stop/target, score components |
| RiskEngine | assess(proposal, account, quote, FX, limits, capabilities, time) → reject or bounded quantity, modeled loss/cost, expiry and snapshot IDs |
| BrokerPort | capabilities/account/orders/fills/positions; submit(intent, stable client ID); cancel(order ID); lookup(client ID) → typed result/event |
| AIProvider | evaluate(allowlisted context, frozen model/prompt/schema config, deadline) → untrusted structured response envelope |
| UnitOfWork | atomically persist decision, reservation, intent, audit and outbox using expected account revision → commit/retry conflict |

All errors are typed: invalid input, stale, unsupported capability, rate limited, authentication failure, temporary unavailability, ambiguous submission, conflict. An ambiguous submission is not a safe retry signal. Contracts carry trace IDs and explicit currency/unit types; monetary JSON values use decimal strings, not ambiguous floats.

## Future API and operations

Read endpoints expose run manifests, candidates/rejections, risk decisions, order/fill timelines, portfolio state and metrics with freshness timestamps. Commands request lockout, cancel or approved run configuration through application validation. Responses include command IDs and states; a UI click never implies a fill. Authentication and account/environment authorization belong on every command. No endpoint accepts arbitrary code or a client-supplied “risk passed” flag.

Configuration resolves before a run and becomes immutable. Structured logs, audit records and metrics use [[07 - Operations/Logging & Observability]]. PostgreSQL transactions provide reservation/outbox consistency; do not start with microservices. Supabase hosting remains optional, not an existing connection.

## Extension boundaries

AgentRegistry supplies immutable agent/config/allocation context. AllocationCoordinator owns funding/reservations per account. ProposalService freezes terms; ApprovalService records hash-bound owner decisions. SafetyGate validates authority/health and risk binding. TradeManagement proposes bounded amendments. ExperimentSupervisor verifies frozen manifests/lifecycle/scoped locks. Reporting has owner-authorized cross-agent reads, not participant privileges. These are logical services, not new deployed infrastructure.

Extend risk.assess with agent+parent snapshots; safety.evaluate returns rule outcomes, valid_until and permission epoch; approve(proposal_id,version,hash,decision,expected_revision) authenticates actor server-side; activate_config requires owner authority/safe cutover; allocation.transfer commits balanced entries. UnitOfWork binds consent/auto mandate, risk/safety, scoped reservations, intent and outbox. All write ports reject cross-agent/run references. See [[01 - Architecture/Agent Architecture]] and [[01 - Architecture/Execution/Safety Gate]].
