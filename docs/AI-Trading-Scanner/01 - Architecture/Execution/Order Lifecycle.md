# Order lifecycle and durable submission

See [[01 - Architecture/Risk Engine]], [[01 - Architecture/Broker Architecture]] and [[01 - Architecture/Data Model]]. Orders are external facts; signal approval is not proof of an order or position.

## Before any submission

After proposal authorization and fresh risk/safety validation, one transaction must persist: immutable proposal hash/version and signal/feature/input IDs; agent/allocation/participant, strategy/management/config/run/environment/context/execution versions; human approval ID or explicit auto mandate; SafetyEvaluation and permission epoch; current account/quote/FX/capability snapshot IDs; full deterministic risk decision and reasons; proposed entry/stop/target and approved quantity/price/cash/risk bounds; reservation and daily slot; intent expiry; stable client order ID and dedup key; request payload hash; audit event; pending outbox record. Commit succeeds before network submission. If this transaction fails, submit nothing. Secrets are never part of these records.

The account writer checks its fencing token and current lockouts, verifies intent has not expired and risk bounds remain fresh, then submits through the mode-specific adapter. Dispatch attempts append status and timestamps. A durable outbox gives at-least-once delivery attempts; it does **not** make a network/broker operation exactly once. Stable client IDs plus lookup/reconciliation prevent blind duplicate submissions.

## Intent and broker projections

| State | Allowed progress and key invariant |
| --- | --- |
| RESERVED | Persisted approval; may become READY or CANCELLED/EXPIRED if never sent |
| READY | Dispatcher claims once under lease; becomes SUBMITTING |
| SUBMITTING | ACKNOWLEDGED, REJECTED or UNKNOWN; timeout is UNKNOWN, never assumed rejected |
| UNKNOWN | Query by client ID, open/recent orders and fills; retain all reservations until resolved |
| ACKNOWLEDGED/WORKING | PARTIALLY_FILLED, FILLED, CANCEL_PENDING, REJECTED/EXPIRED subject to actual broker events |
| PARTIALLY_FILLED | Protect actual quantity; remainder may fill or cancel/expire; cash/risk for remainder stays reserved |
| CANCEL_PENDING | Fill may still arrive; do not release funds/slot or send an over-closing exit |
| FILLED/CANCELLED/REJECTED/EXPIRED | Terminal order projection only after cumulative fills reconcile; subsequent correction events are appended |

A broker order can be cancelled with a nonzero cumulative fill. Thus order status never erases a position. Deduplicate fills by provider/account/execution ID; cumulative-fill updates cannot be summed as incremental fills. Validate monotonic cumulative quantity except explicit corrections/bust events. A fill bust/correction adjusts the ledger by compensating events, never deleting history. Unknown event types lock reconciliation instead of inventing a state.

Each replacement has its own order ID/client child ID and predecessor link under the same intent; V1 entry price/quantity replacements are disabled unless a future explicit policy revalidates risk. Cancellation intent is not cancellation confirmation. No new reservation may reuse capital from an ambiguous order.

## Position and exit policy

A position episode starts at the first positive entry fill, remains OPEN/PARTIALLY_EXITED while q>0, and becomes CLOSED when reconciled q=0 and no residual entry can reopen it. One episode is one performance trade. Track aggregate entry/exit VWAP plus every fill, fee and initial risk allocation; scale-ins are prohibited. See [[09 - Performance/Performance Metrics]].

Protection must cover each filled fraction promptly with a verified broker-supported mechanism. Prefer native linked protective orders where verified. Do not assume fractional brackets/OCO work. Without verified safe fractional protection/cancellation and liquidation, broker paper automation remains blocked; use backtests/shadow observation instead. A client-side stop substitute is a separate ADR and failure-tested capability, not an automatic fallback.

All exits are bounded by reconciled held quantity minus competing executable sell commitments. Use verified native linkage or a serialized cancel/confirm/replace coordinator so target, stop and emergency exit cannot produce a short. Partial-entry fills require cancelling residual entry before final closeout; a racing fill is reconciled and protected. Stop rejection or stale protection triggers an incident and new-entry lockout.

At configured flatten time before calendar close, cancel pending entry orders and request closing remaining positions, coordinating protective orders. The flatten lead time must allow the execution model's latency and bar granularity; validate this when starting the run. If closure fails, do not mark flat or fabricate a close price. Keep position risk visible, continue authorized exit/reconciliation where possible, notify owner and block further entries. See [[06 - Testing/Backtesting]].

## Agent ownership, consent and amendments

[[01 - Architecture/Execution/Approval Workflow]] owns pre-intent consent; awaiting approval reserves no funds. [[01 - Architecture/Execution/Safety Gate]] requires current agent/account/allocation revisions and permission epoch at final transaction and dispatch. Material economic changes require a new proposal/manual consent, including smaller quantity; unchanged terms may use fresh validation snapshots. SIGNAL_ONLY has no dispatchable outbox. Automatic policies replace the click with an administrative mandate only.

Each order/fill has one attributable agent/allocation/run. Broker execution-ID dedup remains account-wide; adding agent IDs must not duplicate a single broker fill. Ownership constraints reject cross-agent attribution. Shared-account reconciliation precedes projections. Fixed stop/target/EOD remains initial policy; future [[01 - Architecture/Execution/Trade Management]] amendments bind predecessor, mandate, risk/safety evidence and acknowledgement time. No dynamic extension is active.

## Simulation specialization

[[01 - Architecture/Execution/Replay and Simulation Architecture]] specializes these invariants for offline SIMULATION. A simulated order is immutable internal evidence and never enters a broker outbox. The unreviewed milestone 6.1 candidate now implements only authoritative idempotent order creation, an immutable in-memory projection, engine-stamped cancellation and pure fill-ready/terminal resolution from the released causal prefix. It uses explicit versioned full-fill volume participation and creates no `SimulatedFill`. Reservation, fill, cash/cost/FX, position and cursor effects still require one future atomic journal transition; fixed stop/target and accounting behavior remain unimplemented.
