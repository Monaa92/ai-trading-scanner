# Incident and failure procedures

Default: fail closed for **new exposure**, while preserving/attempting authorized bounded reductions and reconciliation. “Closed” never means abandon an existing position. A failed reduction is visible unresolved risk, not a successful flatten.

## Failure matrix

| Failure | Immediate response | Recovery evidence |
| --- | --- | --- |
| Market-data outage/stale/delayed/gap | Block affected inputs/entries; maintain native protection; do not forward-fill signals | Verified backfill, contiguous feature readiness, fresh quotes/status |
| Duplicate/out-of-order/revised data | Deduplicate/buffer or append revision; no duplicate/retroactive orders | Watermark/input lineage consistency |
| Broker outage/API timeout | Block entries; ambiguous submitted orders keep reservations; query by stable client ID | Orders/fills/positions/cash reconcile, no unknown submission |
| Rate limit | Bounded exponential backoff with jitter; prioritize reconciliation/cancel/protection; no retry storm | Healthy requests within measured quota |
| Authentication failure | Disable affected adapter/new exposure; alert; no fallback to other credentials/mode | Authorized credential repair and identity/capability verification |
| Database/audit outage | Submit no new entries; retain broker-native protection; bounded exit path from verified state where safe | Durable recovery and reconciled emergency journal, integrity check |
| Process crash/restart/network disconnect | Persistent new-entry lock, no counter reset, restart reconciliation below | Single writer and complete reconciled state |
| Clock drift/timezone/DST defect | Block decisions and expiry-sensitive submissions | Trusted time comparison, versioned calendar tests and repaired timeline |
| Duplicate order/submission ambiguity | Freeze new exposure, enumerate related orders/client IDs, cancel unintended remainder safely | No unexplained duplicate exposure; incident and causal fix |
| Partial fill | Record once, consume one entry count, protect filled quantity, reserve residual | Fill/protection quantities and remaining order reconcile |
| Entry rejected/cancelled | Record reason; release only proven unfilled terminal exposure | Broker fills/current state confirm no residual risk |
| Exit/protective order rejected or stale stop | Emergency lock; cancel residual entries; reconcile quantity and attempt authorized controlled reduction | Verified protection/flat state, cause fixed and reviewed |
| Position mismatch/unexpected open position | Account-wide lock, enumerate orders/fills and alert; do not assume ownership or erase balance | Explained ledger adjustments and approved recovery; no blind duplicate sell |
| AI outage/malformed/model drift | FILTER vetoes new candidate; OFF unaffected; exits continue | Valid frozen model/config and fresh input; drift requires new evaluation |
| Corrupted configuration/hash/mode | Block activation/new exposure; use last verified exit policy only | Valid immutable manifest and identity verification |

Read-only dashboard/analytics failures can fail open for display availability only with explicit stale/error labels; they never authorize trading from cached state. Unknown severity defaults to blocking new exposure in the affected scope; account integrity failures are account-wide.

## Restart reconciliation algorithm

1. Load persistent emergency/daily locks and all data-run/environment/submission/approval/context identities; begin in RECONCILING with new entries disabled. Acquire account-writer lease/fencing token; a second writer cannot submit.
2. Load last durable ledger/checkpoint, pending intents/outbox attempts, known broker IDs/client IDs and event high-water marks. Verify hashes/configuration and clock/calendar.
3. Query broker account, all positions, all open orders, recent terminal orders and fills since checkpoint with overlap. Do not rely solely on a reopened stream. Drain/persist buffered updates and repeat snapshots until internally consistent within a configured bounded window; otherwise remain locked.
4. Resolve each SUBMITTING/UNKNOWN intent by client ID and fill history. Do not resend merely because the first lookup returns nothing; require documented broker consistency/absence evidence. If absence cannot be established safely, remain locked and request operator investigation.
5. Deduplicate executions, replay missing events and explained fee/settlement/FX/action movements, rebuild reservations/counters from original session and fill times. Compare internal cash/position/order/protection totals to broker snapshots. No silent reset to broker equity.
6. Re-establish/correct bounded protective exits for known owned exposure using the verified coordinator. Unknown positions require investigation and explicit recovery ownership; do not liquidate unrelated holdings by assumption.
7. Confirm no unexplained discrepancy, stale required data, duplicate writer, unknown order or unprotected position; append recovery evidence and release only resolved operational locks. Daily latch persists until next verified session, emergency lock until explicit reviewed clearance.

An emergency command disables new intents, requests cancellation of working entry remainders and coordinates exits within known held quantity. It does not promise immediate liquidation during halts/outages. Broker-native protection should survive process loss; its actual fractional behavior must be verified. If local state is too uncertain to size a safe exit, preserve existing protection and escalate for broker/manual reconciliation rather than create a possible short.

Incident record: detection/event times, account/mode, severity, related IDs and versions, known exposure/protection, actions attempted/confirmed, redacted evidence, root cause, tests/corrections, reviewer and reset decision. Critical incidents reopen [[06 - Testing/Live Readiness]].

## Multi-agent recovery and frozen runs

Persist lock scope AGENT/ACCOUNT/EXPERIMENT/SYSTEM, agent/allocation revisions, proposal/consent hashes, permission epochs and participant freeze hashes. Restart never creates approval, extends expiry or resets a failed participant. Reconcile parent account first, then attributable agent ledgers; no allocation borrowing to mask deficits. Clear only resolved authorized lock reasons. Agent-local daily loss stays local; parent integrity faults block all funded agents. Management amendments retain old confirmed protection until acknowledgement.

Emergency interventions in frozen experiments are logged and evaluated against registered autonomy/termination rules; never silently resume as an uninterrupted run. Normal activation/funding/profile changes await the documented flat/session-boundary cutover. Agents/AI cannot invoke administrative recovery. See [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]] and [[01 - Architecture/Execution/Safety Gate]].
