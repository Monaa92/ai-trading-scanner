# Immutable proposals and manual approval

Proposal, human approval and executable order intent are distinct records. Strategy/risk validity is not human consent. Existing signals link to ProposalVersion; [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]] no longer uses APPROVED to ambiguously mean both risk and user approval.

Phase 5 implements validation of an optional immutable `ApprovalBinding` only. The binding contains the exact proposal, sizing decision, quantity, management mandate, configuration, execution dimensions and validity window. Manual reservation requires the immutable proposal itself to carry `FINAL_QUANTITY`; a future-sized proposal must first become a new proposal version before consent. The binding is supplied externally; risk and allocation never generate or infer human consent. No ApprovalService, authenticated user workflow or order intent exists yet.

## Proposal contents

Persist proposal_id/version/content hash, agent/account/allocation, run/participant, data/run mode, execution environment, submission mode, approval policy, context, source candidate/features/as_of, strategy/config versions, symbol/instrument/direction, order type/TIF, intended entry and permitted entry-price bound, stop, target, exact quantity, estimated notional/currency/fees/FX, modeled monetary and percentage risk (with equity denominator), intended net RR, trade-management version/mandate, AI result/version where applicable, all strategy/risk/safety results and reasons, creation/expiry times, account/allocation revisions and display schema. Numeric unknowns remain explicitly unavailable; a blocked proposal is not presented as approvable.

For market orders, approval authorizes the displayed order type, quantity and modeled price/risk envelope, not a guaranteed fill price. Actual adverse fills remain accountable under existing breach procedures. Changing the envelope, entry, stop, target, quantity, instrument, direction, execution environment, submission mode, approval policy, configuration or management mandate is material and requires a new ProposalVersion. Any other execution-critical content change does too. Even a smaller quantity is new content and needs new manual consent. Fresh observation/snapshot IDs can accompany revalidation without changing immutable approved economic terms if they still satisfy all limits; no silent resizing.

## Lifecycle

| From | To | Guard/action |
| --- | --- | --- |
| CANDIDATE | STRATEGY_VALID | Deterministic predicates pass; strategy rejection otherwise retained |
| STRATEGY_VALID | RISK_VALID | Preflight deterministic sizing/constraints pass; else BLOCKED_BY_RISK |
| RISK_VALID | SAFETY_VALID | Preflight identity/environment/health/capability pass; else BLOCKED_BY_SAFETY |
| SAFETY_VALID | RECORDED_SIGNAL_ONLY | No submission authority; terminal observation |
| SAFETY_VALID | AWAITING_APPROVAL | MANUAL_APPROVAL; immutable proposal/request created |
| AWAITING_APPROVAL | USER_APPROVED / REJECTED_BY_USER | Authenticated authorized actor decides exact proposal hash before expiry |
| SAFETY_VALID | AUTO_AUTHORIZED | ORDER_ENABLED + FULL_AUTO under a valid administrative mandate; an AUTONOMOUS_EXPERIMENT additionally requires a matching frozen registration, never a forged user decision |
| USER_APPROVED / AUTO_AUTHORIZED | REVALIDATING | Fresh strategy relevance, risk, safety, ownership and capability checks |
| REVALIDATING | ORDER_INTENT | Same terms still valid; atomic reservation + risk/safety results + consent reference + intent/audit/outbox commit |
| REVALIDATING | BLOCKED_BY_RISK / BLOCKED_BY_SAFETY | Record fresh failure; do not submit or silently amend |
| Any pre-intent nonterminal state | EXPIRED / INVALIDATED | Deadline/cutoff reached, input correction, relevant config/mode change, material terms changed or invalidated permission |

User rejection/expiry/invalidation/block is terminal for that proposal version. A new evaluation gets a new version and fresh consent if manual. Once an intent exists, cancellation uses [[01 - Architecture/Execution/Order Lifecycle]]; a user reject command cannot erase an already submitted order. Interface shows “cancellation requested” until confirmed and keeps any fills visible.

Use compare-and-swap state revision and idempotent decision ID to resolve concurrent approval/rejection/expiry. Server time is authoritative; at `now >= expires_at` approval fails. Repeated identical approve is idempotent, not a second order; conflicting decisions after a terminal transition fail and are logged. Approval tokens cannot be transferred across agent, owner, execution environment, submission mode, approval policy, account, run or proposal version. Append actor/auth context and received_at; never trust a browser-supplied approved flag/time.

Preflight/AWAITING_APPROVAL consumes no durable trading capital or daily slot. This prevents idle approvals starving another agent. Immediately before intent creation, atomically reserve both agent and parent account capacity using fresh revisions; losing a race blocks the proposal. Immediately before actual dispatch, repeat final checks within the bounded validation lease; expiry, lock or adverse economics still blocks. If dispatch terms would change, cancel the unsubmitted intent and issue a new proposal/approval; do not reassign old consent. UNKNOWN broker submission retains its reservation and must reconcile.

Approval expiry is bounded by candidate lifetime, entry cutoff and configured approval TTL. A short-lived quote can require fresh evaluation before dispatch without extending proposal expiry. Historical manual-policy studies must model actual decision latency, rejection and nonresponse; future prices cannot choose retrospectively which proposals “would” have been approved.
