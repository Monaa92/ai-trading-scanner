# Conceptual data model

Specification only: no schema DDL or migrations. PostgreSQL is intended for transactional records and metadata; large immutable dataset artifacts may later live in private object/file storage referenced by checksum. Hosting, retention sizes and physical partitioning await measured data volume. See [[07 - Operations/Configuration]] and [[07 - Operations/Logging & Observability]].

## Common conventions

IDs are stable opaque identifiers, never ticker symbols. Every relevant record carries schema version, created/observed time, account, data/run mode, execution environment, submission/approval/context and run/experiment scope where applicable. Money is decimal + ISO currency; quantities/ticks have explicit precision; UTC instants preserve original precision/sequence. `event_at`, `received_at`, `available_at` and effective-dated validity are distinct. Hashes use canonical serialization and SHA-256; IDs reference retained content, not just labels. Raw secret-bearing headers are never stored.

Legend: **I** append-only immutable fact/artifact; **V** immutable versions with supersedes links; **P** rebuildable mutable projection with optimistic revision. Correct facts through new compensating/superseding records. No cascade deletion of experiment evidence. Historical “as known then” queries use knowledge/availability time as well as effective time.

## Market and research input entities

| Entity | Purpose and key fields | Relationships and reproducibility |
| --- | --- | --- |
| Instrument (V) | Permanent ID, security type, exchange, currency, listing/delisting, validity interval | Ticker mappings and provider IDs separate; instrument versions referenced by bars/universe |
| SymbolMapping (V) | Instrument/provider/ticker, effective_from/to, known_at | Prevents reuse/rename ambiguity |
| DataSource (V) | Provider, feed, entitlement description without secrets, source schema, coverage/adjustment policy | Referenced by every market record and dataset; feed changes are new versions |
| RawMarketRecord (I) | Source event ID, payload content/reference/hash, event/receipt times, channel, revision lineage | Input evidence for normalized bars/status/quotes; duplicate receipts can reference same payload |
| BarRevision (I) | Instrument, source, interval start/end, OHLCV, currency, quality, available_at, revision, raw IDs | Logical bar key=(instrument,source,interval,start,adjustment version); revision distinguishes corrections |
| Quote/FXObservation (I) | Pair/instrument, bid/ask, sizes if present, source/time/available_at, validity flags | Risk/account snapshots bind exact observed rates/quotes; FX is never an implicit constant |
| CorporateAction (V) | Split/dividend/rename/delisting type, announcement/known/effective times, factor/cash and currency | Adjustment versions reference actions; unresolved actions marked, not silently omitted |
| CalendarVersion/Session (V) | Calendar/tzdb version, exchange, local session date, open/close UTC, breaks, early-close/holiday status | Bars, daily counters and cutoff policy reference session IDs |
| InstrumentStatus (I) | Tradability/halt/resume, effective and available times, source | Completeness/capability gates use status as of decision |
| UniverseVersion (V) | Membership IDs and effective/known intervals, inclusion rationale, selection method | Dataset/run binds version; convenience current universe explicitly labeled |
| FeatureSnapshot (I) | Instrument/as_of, values/units/readiness/reasons, indicator+feature versions, parameters, input revision IDs/hash | Fully traceable to bars/actions; new revisions create new snapshots |
| DatasetManifest (V) | Content root, canonical ordered partition hashes, source/feed, query range/cursors, universe, raw/adjustment/calendar versions, availability mode, quality/exclusion report | Dataset ID hashes full manifest; immutable raw/normalized artifacts retained. Same dates with different rows/revisions give different IDs |

Dataset manifests record actual coverage, not just requested start/end. Include normalization code/version, download time/vintage and source query semantics. A source URL is not a dataset backup. Point-in-time coverage and unavailable revision history are explicit limitations.

## Decisions, execution and account entities

| Entity | Purpose and key fields | Relationships and mutability |
| --- | --- | --- |
| Account (V) | Internal owner/account ID, environment, reporting currency, broker reference, capital policy | Separate paper/live identities; no credentials; account settings versioned |
| StrategyDefinition/Version (V) | Family ID, semantic version, rule/indicator requirements, predecessor, hypothesis, artifact hash | Version binds immutable parameters/config; acceptance history separate |
| ParameterSet (I) | Canonical names/types/units/values and hash | Strategy/experiment references; no mutation behind ID |
| Signal (I + P state) | Dedup key, instrument, trigger interval, direction, decision/expiry, feature snapshot, strategy/config/run IDs | Immutable observation plus event-derived lifecycle projection |
| SignalEvaluation (I) | Signal ID, predicate results, proposed levels, score components, quality/rejection reasons, as_of | Every attempt, including rejected and AI-vetoed candidates |
| RiskDecision (I) | Signal/intent ID, pass/reject, account revision, rule results, E/B/H/cash calculations, quote/FX/capability IDs, approved qty/levels, expiry | Full trace of sizing math and reasons; independent of AI verdict |
| Reservation (I events + P) | Account, intent, position/day slots, cash/risk/currency amounts, revision, status | Updated atomically with ledger/intent; events retain every reserve/release |
| OrderIntent (I) | Entry/stop/target/flatten role, signal/risk ID, parent intent, qty/price bounds, environment/submission/approval fields, client ID, expiry, payload hash | Immutable economic authorization; new amendments reference predecessor and revalidated risk |
| Outbox/DispatchAttempt (P + I attempts) | Intent, committed/claimed time, fencing token, attempt state, request hash, error/ambiguous status | Durable submission workflow; attempts immutable, queue state mutable |
| BrokerOrder (I events + P) | Broker/account/client IDs, intent, predecessor replacement, requested/cumulative qty, state, broker timestamps | External event mapping; no inference that cancelled means zero fills |
| Fill (I) | Unique account/provider execution ID, broker order, qty, price/currency, execution/receipt time or interval bounds, fees, liquidity/model flags | Corrections/busts reference original fill with compensating records |
| LedgerEvent (I) | Account, cash/position/fee/FX/settlement/corporate-action movements, currencies, source fill/event and balancing entries | Sole basis for internal economic state; double-entry balancing per currency with explicit FX legs |
| Position (P) | Account/instrument, qty, cost basis, episode ID, protected qty and pending exit commitments, revision | Rebuilt from fills/ledger; snapshots immutable |
| TradeEpisode (I final, P while open) | Flat→long→flat episode, intent, all entry/exit fills, first/last times, original stop/risk allocation, net P&L/costs, exit reason | One initial entry intent; partials aggregated; no performance trade until closed |
| AccountSnapshot (I) | Cash by currency including settled/unsettled, positions/marks, reporting-currency equity (EUR initially), fees/liabilities, reservations, daily counters/E0/lockouts, revision | Risk references exact snapshot; valuations include quote/FX IDs and freshness |
| Reconciliation/LockoutEvent (I + P) | Compared internal/broker snapshots and watermarks, mismatches, explanations, lock scope/reason, reset actor/evidence | Required restart and incident trace; lock projection survives restart |

## Experiment and AI entities

| Entity | Key fields and purpose | Reproducibility rules |
| --- | --- | --- |
| ExperimentRegistration (I) | Hypothesis/family, predecessor, effect/guardrails, split IDs, trial budget, stopping/acceptance rules | Recorded before outcomes; amendments are additional trials |
| Split/HoldoutAccess (I) | Date/membership boundaries, purge/embargo, artifact access actor/time/purpose | Marks consumed holdout; never reset by renaming |
| ExperimentRun (I status events) | Manifest, experiment ID, timestamps, RUNNING/COMPLETED/FAILED/ABORTED, failures/artifact refs | Every attempted run retained regardless of result |
| BacktestRun (I) | Experiment run, dataset ID, engine/execution/cost/seed versions, replay trace hash | Specialized run metadata; links to fills and equity series |
| ConfigVersion/RunManifest (I) | Complete resolved config, hashes and all bindings in [[07 - Operations/Configuration]] | Secrets excluded; content retrievable; dirty code patch retained when applicable |
| PerformanceSummary (I) | Run, metric implementation version, sample units/counts, period, Gross Trading/Net Trading/Net Economic metrics, uncertainty and quality flags | Can recompute from authoritative ledgers; corrected metric implementation produces new summary |
| AIModel/Prompt/SchemaVersion (V) | Provider/model snapshot ID, release info, prompt text/hash, schema hash, generation params, app policy | Provider alias alone insufficient; unknown backend revision recorded as limitation |
| AIEvaluation (I) | Signal/candidate batch, exact allowlisted input/hash, raw/sanitized output, parsed verdict, provider request/model, seed if supported, timing/tokens/cost, failure/fallback | Preserve response for deterministic replay; never assume remote re-call identical |
| AICallCost (I) | Call/provider/model, usage units, timestamps, experiment/run/agent/strategy/candidate/decision, pricing snapshot, estimated/settled cost, attribution/cache/retry lineage | Separate operating-cost ledger; cannot post to portfolio cash/risk or rewrite with new prices |
| AIBudgetAllocation/Event (I + P) | Owner-funded scope, amount/currency, warning/critical/hard limits, reserved/settled usage and state changes | Atomic no-double-allocation; agents cannot top up; explicit resume after hard stop |
| DecisionArtifact (I) | Capital-independent input/output hashes, strategy/model/prompt versions and replay-equivalence declaration | Reused across capital arms only when portfolio state cannot affect decision |
| AcceptanceDecision (I) | Candidate/predecessor, ACCEPTED/REJECTED/EXPERIMENTAL, comparison IDs, reviewer/date/rationale | Stage-limited approval; no live permission implied |
| AuditEvent (I) | Envelope/event type, actor/account, data-run/environment/submission/approval/context fields, trace/correlation, previous/current IDs, reason, event/receipt time, payload hash | Connects data→signal→risk→intent→order→fill→trade and all config changes |

## Integrity and persistence boundaries

Unique constraints conceptually enforce signal dedup key, client ID per broker account/environment, and execution ID per provider/account. Foreign-key relationships prevent orphan risk decisions/fills; actor/account scoping prevents cross-account reads/mutations. Reject currency mismatches and non-finite monetary values. A serialized account transaction with version comparison checks position/daily/cash capacity, creates reservation+intent+audit+outbox, and commits together. A concurrent winner forces the loser to reassess fresh state, not retry the old approval.

Ledger and fills are durable before reporting an account transition complete. Rebuildable views serve API/analytics; analytics never writes accounting truth. Raw data/run artifacts need integrity-checked backups and retention for rejected experiments; capacity/retention policy remains a later operational design decision and must not discard evidence selectively. No migrations are created now.

## Multi-agent extensions — reuse existing entities

Extend every decision/execution/account-derived record with agent_id, allocation_id, participant/run_id, config_segment_id, data_run_mode, execution_environment, submission_mode, approval_policy, operating_context and performance_kind. Shared bars/features have no private account state; per-agent consumption/evaluation binds their IDs. Existing Account remains funding-account identity; allocation-scoped snapshots/projections reuse AccountSnapshot/LedgerEvent/Position rather than parallel tables for each agent.

| Concept | Extension/new record and key fields | Integrity/versioning |
| --- | --- | --- |
| Agent | Stable agent_id/owner, lifecycle projection, active configuration reference | State derives from attributed lifecycle events; no self-administration |
| AgentConfigVersion | Composition of existing ConfigVersion artifacts plus data/run, environment, submission, approval, context, management and allocation settings | Immutable content hash, predecessor, actor/reason, requested/effective time; activation events create performance segments |
| AgentAllocation | Agent/funding account/currencies, initial contribution, ceilings, validity and revision | Balanced capital changes use existing LedgerEvent and audit; atomic no-double-allocation |
| ProposalVersion | Immutable full terms/hash, agent/allocation, risk/safety/input versions, expiry/mandate | SignalEvaluation reused for predicates; new versions invalidate old pending authorization |
| ApprovalRequest/Decision | Proposal hash/version, TTL, status projection; immutable actor/decision/time/idempotency/auth scope | Unique terminal decision by expected revision; no decision reused across agent/run/terms |
| SafetyEvaluation | Bound proposal/risk decision, per-check results, scope, permission epoch, health refs, as_of/valid_until | Append-only preflight/final evaluations; failure never overwritten |
| ExperimentParticipant | Existing ExperimentRegistration/Run membership: agent, initial allocation, frozen config/manifest refs, assigned hypothesis, endpoint/outcome | Unique participant per agent run; registration manifest is frozen config snapshot, no redundant mutable experiment-config table |
| AgentLifecycleEvent | Extend existing LockoutEvent/AuditEvent with old/new states, scopes, threshold/input evidence, actor | Projection rebuildable; terminal experiment results immutable, corrections appended |
| TradeManagementVersion | Policy definition/parameters/hash and strategy linkage | Amendments reuse role-specific OrderIntent with predecessor, position/mandate and risk/safety refs |
| Performance period/snapshot | Extend PerformanceSummary with agent/segment/kind/period bounds/as_of, ledger watermark, full metrics/coverage/censoring/flows | Derived immutable revision; no separate daily/week/month tables needed |
| Counterfactual run | Existing ExperimentRun/BacktestRun with performance_kind=COUNTERFACTUAL, parent candidate/run/snapshot and intervention/model/horizon | Separate synthetic allocation/ledger namespace, no actual-posting/dispatch capability |

Composite ownership checks ensure proposal→approval→risk/safety→intent→fill attribution stays within agent/allocation/run. Client IDs include adapter, environment, execution account, agent, allocation and immutable intent scope; provider execution IDs remain deduplicated by provider/account before agent attribution. A fill cannot be copied into two agents. Account coordinator checks parent and agent revisions, permission epoch and reservations atomically. Parent account reconciles to sum(attributed agent balances)+unallocated balances under one valuation basis; reservations are encumbrances, not extra assets. Scope/type checks prohibit a COUNTERFACTUAL ledger event from posting to ACTUAL_PATH.

Market-data provenance includes provider/source, dataset ID, universe/instruments, granularity, timezone, start/end, adjustment method, ingestion time, schema/dataset version, quality warnings, missing intervals and deterministic hashes when available. Absence stays UNKNOWN. Comparative summaries carry dataset-equivalence status and cannot label unmatched data equivalent.

Read models may compare agents for authorized owners, while participant repositories expose only own state and aggregate pass/headroom from parent constraints. Scalar mode fields in older schemas are explicitly interpreted by schema version, never guessed. See [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[01 - Architecture/Execution/Approval Workflow]] and [[09 - Performance/Agent Statistics]].
