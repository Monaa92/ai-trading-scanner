# Phase 5 independent review

Status: **CHANGES REQUIRED ON ORIGINAL CANDIDATE; REPLACEMENT RE-REVIEW REQUIRED.** PR #4 reviewed candidate `0c36a5de657e749daa0ef987c47c44d299dd67b7` and returned CHANGES REQUIRED. No approval is recorded. Review the exact replacement commit; do not merge until every finding is resolved and that replacement is independently approved.

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
| Duplicate handling | proposal-specific guard and coordinator-wide proposal index | sequential/cross-allocation/cross-parent/concurrent duplicate tests | One economic reservation per proposal in one coordinator; same-owner replay is revalidated | Duplicate capital hold |
| Lifecycle/conservation | coordinator transitions | release/consume/expire/conflict tests | No reactivation, creation or loss of capital | Ledger drift |
| Lock behavior | safety lock models/coordinator | local/parent and lock-race tests | Applicable lock blocks new reservation; existing hold remains | Safety bypass or lost capital |
| Fail-closed validation | Pydantic models and risk taxonomy | config/sizing/reservation tests | Invalid ownership/config/time/environment/currency fails explicitly | Unsafe fallback |
| Proposal fingerprint | risk and preliminary checks | changed proposal/decision test | Material Phase 4 change invalidates downstream artifacts | Consent or risk reused for another trade |
| Approval binding | `ApprovalBinding`, final evaluation | manual missing/exact/stale binding tests | Risk cannot generate consent; manual reservation binds exact sized terms | Approval bypass |
| Staleness/expiry | engine and reservation lifecycle | before/equal/after deadline, replay, lock-race and consume-after-expiry cases | Explicit time only; active replay revalidates; deadline equality blocks and expires | Stale trade proceeds |
| Execution dimensions | policy and engine | PAPER/FULL_AUTO and SIGNAL_ONLY tests | Policy never changes environment; FULL_AUTO does not imply LIVE | Unauthorized environment |
| Side-effect boundary | entire `risk` package | AST coupling scan and serialization tests | No broker/provider/network/AI import or order/fill field | Phase boundary bypass |
| Persistence boundary | `risk/allocation.py` and docs | limitation review | Local atomicity is not reported as durable/multi-process | False recovery guarantees |

The reviewer should independently recompute representative quantities and identities, inspect every mutation point inside the lock scope, challenge exception paths between prepared and published state, repeat concurrency tests, and confirm the implementation never claims an order, fill, position or human approval. Agent self-review is insufficient.

## Original review findings and remediation evidence

The original review found seven issues: daily-loss headroom was not a sizing bound; one proposal could reserve through multiple allocations; active expired replay and post-expiry consume were unsafe; sizing arithmetic could contradict its fields; the cross-parent safety-lock dictionary was unsynchronized; evaluated limits admitted floats and risk decisions omitted safety identity; and review documentation was stale. The replacement implements explicit content-identified loss evidence and remaining-headroom arithmetic, coordinator-wide proposal uniqueness, expiry-safe replay/consume, self-validating sizing arithmetic, parent-partitioned mutable collections, complete safety evidence in `RiskDecision`, and this updated handoff. Adversarial tests in `test_risk_review_remediation.py` exercise each failure path. These changes are candidate evidence, not an approval.

## Candidate verification

Before commit, record exact test splits, lint/type/build/health, isolated installation, security/scope scans, documentation links and whitespace results. The review handoff must identify the exact replacement remote commit. PR #4 exists, but no approval or merge evidence currently exists.
