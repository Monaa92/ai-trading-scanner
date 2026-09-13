# Observability and audit

Goal: reconstruct a decision using what the system actually knew then. Operational logs are not a substitute for a durable decision ledger. See [[01 - Architecture/Data Model]] and [[01 - Architecture/Execution/Order Lifecycle]].

Every event envelope carries event ID/type/schema, account/agent/allocation/run, data/run mode, execution environment, submission mode, approval policy and context where applicable, actor/component, event/received/available times, correlation/causation IDs, expected/new aggregate revision, reason code, linked artifact IDs and payload hash. Preserve sequence ordering; append corrections. Redact secrets before persistence, not only before displaying logs.

| Event group | Required evidence |
| --- | --- |
| Data state | Feed/interval/revision/quality, stale/missing/late/duplicate counts, calendar/watermark |
| Signal generated/rejected/expired | Frozen features/input IDs, rule outcomes, strategy/config and selection reason |
| Risk evaluated/reserved/denied | Account/quote/FX snapshots, all gates, exact sizing math, limits, quantity and expiry |
| AI evaluated/failed | Input/output/config hashes, provider/model identity, usage units, pricing/cost record, purpose/cache/retry lineage, parsed decision, deadline and latency; no secrets |
| Intent/submission/acknowledgement | Durable intent/risk/reservation, client/broker IDs, payload hash, attempt/unknown status |
| Fill/cancel/exit | Execution IDs, quantity/price/cost, economic and receipt time, residual/protection state, reason |
| Account/configuration | Ledger movements, snapshots, lockouts, version activation and actor, reconciliation differences |
| Error/recovery | Scope, typed cause, retry/lockout, corrective evidence, operator acknowledgement |

For any trade, a query must answer why it existed, strategy/parameters, data then available, passed/failed risk gates, AI involvement/version, intended versus submitted order, actual fills and costs/slippage, and exit trigger/time. Missing joins block evidential promotion.

Operational metrics: ingestion lag and gaps, clock offset, feature readiness, rejection by reason, risk headroom/reservations, protection gap duration, broker latency/rate-limit errors, unmatched orders/fills, reconciliation age, audit/outbox backlog, AI failures/cost, run completeness. Alert immediately for unknown/unprotected positions, duplicate/over-closing risk, persistent broker ambiguity, lost audit durability or emergency lockout. Dashboard must label stale state and cannot show an old snapshot as current.

Storage/audit failure blocks new entries. Existing native broker protection remains; authorized risk-reducing emergency action uses a last-verified durable intent or minimal redacted local emergency journal when feasible and is reconciled after recovery. It must never be an avenue for new exposure. Notifications and emergency actions need bounded retry and clear failure visibility. Backup/restore tests must prove immutable evidence and ledger recovery before readiness; retention/access budgets remain to be chosen once data volumes are measured.

## Complete agent decision traces

Extend the envelope with agent/allocation/participant, data/run mode, execution environment, submission mode, approval policy, context, config segment, performance kind, proposal hash and scoped permission/lock evidence. Emit every detected candidate, TRADE/NO_TRADE strategy decision, AI evaluation/veto/failure, AI budget reservation/threshold/hard-stop/resume, risk/safety pass/block, approval request/approve/reject, expiration/invalidation, intent/submission, full/partial fill, cancellation, position change/exit, lockout, lifecycle transition and material config/capital change. Log normal no-candidate evaluations with batch/coverage count so “not detected” can be distinguished from missing logging. Terminal outcome counts and repeated rule failures are separate.

Query Agent B/NVDA/10:35 by session timezone and agent/run: candidate/input availability → predicates → AI → proposal → consent/auto mandate → risk/safety → intent/fills. Query Agent C/AMD/13:15 with the same chain to locate veto, risk/safety block, expired/rejected consent, occupied capacity or no candidate; if evidence is absent report unknown. “What baseline would do” links a registered baseline actual path or clearly labeled counterfactual run. “Did AI help” needs paired aggregate evidence, not an isolated profitable rejected signal.

Persist approvals/config transitions transactionally with state changes; missing audit durability blocks new authority. [[03 - Experiments/Counterfactual Analysis]] and [[09 - Performance/Agent Statistics]] preserve actual/shadow separation and consistent rejection denominators. [[09 - Performance/Reporting Architecture]] shows owner-authorized cross-agent timelines without giving participants that access.
