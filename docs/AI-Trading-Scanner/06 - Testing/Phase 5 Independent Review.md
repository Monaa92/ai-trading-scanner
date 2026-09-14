# Phase 5 independent review

Status: **INDEPENDENT COMPETENT HUMAN REVIEW REQUIRED; no approval is recorded.** Review the exact future candidate commit for the Phase 5 implementation. Do not merge until critical findings are resolved and the exact candidate is approved.

| Area | Implementation | Behavioral evidence | Intended invariant | Failure impact |
| --- | --- | --- | --- | --- |
| Decimal sizing | `risk/engine.py`, `risk/models.py` | `test_risk_sizing.py`, `test_risk_config.py` | No float/non-finite values; quantity never exceeds risk or capacity | Hidden excess loss/exposure |
| Stop/unit risk | `RiskEngine._size` | sizing and inherited proposal tests | Long stop remains below entry; costs included once in modeled unit loss | Understated risk |
| Safe rounding | `_floor_to_increment` | boundary and exact-final-quantity cases | Future sizing floors; exact approved quantity rejects if infeasible | Silent approval mutation or risk increase |
| Ownership hierarchy | snapshots and coordinator | config/reservation/concurrency cases | Proposal agent, allocation and parent scope match | Cross-agent capital use |
| Agent isolation | scoped snapshots/locks | two-agent and local-lock tests | Peer available capital/locks do not silently alter another allocation | Contaminated experiments |
| Parent capacity | sizing plus coordinator | shared-parent concurrency test | Aggregate reservations never exceed parent capital | Double spending real/shared capital |
| Atomic reservation | `InMemoryCapitalCoordinator.reserve` | same-agent/shared-parent/rollback races | Parent+allocation publish all-or-none after fresh validation | Partial debit or over-reservation |
| Transaction ordering | `_scope_locks` | all concurrency/lifecycle tests | Parent lock acquired before allocation lock | Deadlock or split state |
| Duplicate handling | proposal reservation index | sequential/concurrent duplicate tests | One active reservation per proposal/allocation; replay returns it | Duplicate capital hold |
| Lifecycle/conservation | coordinator transitions | release/consume/expire/conflict tests | No reactivation, creation or loss of capital | Ledger drift |
| Lock behavior | safety lock models/coordinator | local/parent and lock-race tests | Applicable lock blocks new reservation; existing hold remains | Safety bypass or lost capital |
| Fail-closed validation | Pydantic models and risk taxonomy | config/sizing/reservation tests | Invalid ownership/config/time/environment/currency fails explicitly | Unsafe fallback |
| Proposal fingerprint | risk and preliminary checks | changed proposal/decision test | Material Phase 4 change invalidates downstream artifacts | Consent or risk reused for another trade |
| Approval binding | `ApprovalBinding`, final evaluation | manual missing/exact/stale binding tests | Risk cannot generate consent; manual reservation binds exact sized terms | Approval bypass |
| Staleness/expiry | engine and reservation lifecycle | future/stale/expired cases | Explicit time only; no hidden clock; deadline equality blocks | Stale trade proceeds |
| Execution dimensions | policy and engine | PAPER/FULL_AUTO and SIGNAL_ONLY tests | Policy never changes environment; FULL_AUTO does not imply LIVE | Unauthorized environment |
| Side-effect boundary | entire `risk` package | AST coupling scan and serialization tests | No broker/provider/network/AI import or order/fill field | Phase boundary bypass |
| Persistence boundary | `risk/allocation.py` and docs | limitation review | Local atomicity is not reported as durable/multi-process | False recovery guarantees |

The reviewer should independently recompute representative quantities and identities, inspect every mutation point inside the lock scope, challenge exception paths between prepared and published state, repeat concurrency tests, and confirm the implementation never claims an order, fill, position or human approval. Agent self-review is insufficient.

## Candidate verification

Before commit, record exact test splits, lint/type/build/health, isolated installation, security/scope scans, documentation links and whitespace results. After the candidate is pushed, record branch and commit here only if the document is amended in a later reviewed change; the review handoff must identify the exact remote commit. No approval, PR or merge evidence currently exists.
