# Execution dimensions and privilege boundaries

Status: Phase 1 domain/configuration model IMPLEMENTED; execution, broker connections and operational PAPER/LIVE remain unimplemented.

Five fields remain distinct in every immutable agent configuration and run manifest:

| Dimension | Values | Meaning |
| --- | --- | --- |
| Data/run mode | HISTORICAL_REPLAY, LIVE_FEED or CAPTURED_REPLAY | Selects how time and market observations are supplied. Earlier `BACKTEST` and `SHADOW` labels map here and are not broker environments. |
| Execution environment | SIMULATION, PAPER or future LIVE | Selects where executable intents are resolved. SIMULATION is internal; PAPER and LIVE require separately certified broker/account capabilities. |
| Submission mode | SIGNAL_ONLY or ORDER_ENABLED | Determines whether an evaluation may ever become an executable intent. |
| Approval policy | MANUAL_APPROVAL or FULL_AUTO | Applies only when submission mode is ORDER_ENABLED. It determines whether a person must approve each immutable proposal. |
| Operating context | NORMAL or EXPERIMENT | Selects change-control and evidence rules. An experiment also references an independently versioned experiment type and manifest. |

`AUTONOMOUS_EXPERIMENT` is an experiment type, not an approval policy or execution environment. Its initial profile uses `EXPERIMENT + ORDER_ENABLED + FULL_AUTO + SIMULATION`; a future paper profile requires completed paper gates. It remains unsupported in LIVE. AI mode OFF/FILTER and strategy profile are additional independent fields. Never compress these fields into an ambiguous `mode` value.

## Submission and approval semantics

| Configuration | Behavior and gates |
| --- | --- |
| SIGNAL_ONLY | Evaluate strategy, optional AI, sizing/risk and safety; retain a complete proposal or blocking reasons. No executable intent, outbox dispatch, broker submit or persistent capital reservation is permitted. |
| ORDER_ENABLED + MANUAL_APPROVAL | Produce an immutable fully evaluated proposal. Owner APPROVE/REJECT binds exact content and version. Every material amendment needs new consent. Fresh risk and safety validation may still block submission. |
| ORDER_ENABLED + FULL_AUTO | Deliberately enabled policy omits the per-proposal human step. Identical strategy, risk, safety, broker-capability, durability and final revalidation gates remain mandatory. |

NO_TRADE is valid under every combination and creates no proposal or reservation. A manual rejection, expiry or invalidation cannot fall back to FULL_AUTO. Switching approval policy invalidates pending proposals and starts a new attributed configuration segment.

## Allowed combinations

HISTORICAL_REPLAY normally uses SIMULATION. It may evaluate SIGNAL_ONLY or replay ORDER_ENABLED decisions; MANUAL_APPROVAL replay requires recorded or preregistered scripted approval events and their latency. LIVE_FEED may feed SIGNAL_ONLY, SIMULATION or PAPER without changing agent code. Counterfactual/shadow results always use isolated simulation ledgers and never become actual account facts.

`PAPER + FULL_AUTO` is valid after its gates. FULL_AUTO never implies LIVE. Loading an IBKR or Kraken adapter, discovering credentials, choosing LIVE_FEED or registering an experiment never changes the execution environment. LIVE remains unavailable and default-disabled until a future owner-controlled configuration change passes [[06 - Testing/Live Readiness]]. Future `LIVE + MANUAL_APPROVAL` is the first contemplated live form; future `LIVE + FULL_AUTO` needs a second deliberate owner decision and evidence for that exact profile.

## Transition and authority semantics

Environment, submission-mode, approval-policy and context changes are privileged administrative commands. They are attributed, versioned and effective only after pending proposals are invalidated, unsubmitted intents are cancelled and outstanding orders/positions are reconciled. The initial transition policy requires flat state, no unknown orders and next-session activation. SIGNAL_ONLY cannot be enabled over open automated exposure if that would abandon exit handling; first complete a controlled handover or flatten and reconcile.

Agent and AI services cannot enable ORDER_ENABLED, FULL_AUTO or LIVE; select credentials; allocate additional capital; increase risk; disable safety; or clear their own locks. Owner activation checks identity, target agent/account, environment, adapter capability, manifest, readiness evidence and a confirmation challenge before an audited transition. An emergency disable blocks new exposure while preserving mandatory exit, protection and reconciliation work.

MANUAL_APPROVAL consents only to the exact initial order and displayed fixed protection/target, scheduled closeout and bounded emergency-reduction mandate. A material change to entry, stop, target, quantity, trade-management mandate or any other execution-critical field invalidates approval. Executing already authorized protective actions is not a discretionary amendment. Every dispatch receives final risk and safety revalidation regardless of approval policy. See [[01 - Architecture/Execution/Approval Workflow]], [[01 - Architecture/Execution/Safety Gate]] and [[09 - Performance/Reporting Architecture]].

## Phase 1 executable boundary

`ExecutionDimensions` represents every documented value without coupling the fields. `FoundationConfig` is deliberately narrower: it rejects LIVE, ORDER_ENABLED and experiment execution before startup. PAPER + FULL_AUTO remains structurally valid when SIGNAL_ONLY, and PAPER + ORDER_ENABLED + FULL_AUTO remains valid in the domain model for future gated implementation. No current object grants submission, credential, allocation, risk or lock authority.
