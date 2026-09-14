# Risk history

Append-only record for material risk, sizing, cash, FX, daily-limit and protection changes. Risk changes require independent risk-critical review; do not optimize limits to hide strategy losses.

## 2026-09-13 — risk-v0.1.0

- Previous: no formal risk specification.
- New: EUR50-equivalent simulation; risk ≤1% current conservative equity; one occupied position/entry reservation; three distinct first-filled entry intents/session; no leverage/shorting/options/CFDs; net modeled RR≥2.0.
- Daily policy: realized plus unrealized net equity loss, ceiling `3% × min(session-start equity, current flow-adjusted equity)`; remaining headroom constrains new risk; latch for session after breach.
- FX/cash: explicit per-currency ledgers/rates, settled spendable cash, adverse cost buffers, downward quantity rounding and exact rechecks.
- Protection: partial-fill coverage, persistent lockouts, no blind retry of ambiguous submissions, no AI override.
- Classification: RISK CONSTRAINTS plus PROVISIONAL modeling buffers. Status: EXPERIMENTAL implementation specification, no test evidence.
- Evidence: none yet; no backtest/paper data. Commit/PR for this entry: none.

Future entries must retain old/new formulas and configs, rationale, owner/reviewer, adversarial tests, comparable stress/backtest results, exposure/drawdown impact, date and actual commit/PR references. Link strategy changelog if outcomes/strategy contract change. See [[01 - Architecture/Risk Engine]].

## 2026-09-13 — risk-contract-v0.2.0 allocation/authority extension

Previous contract used a single-account scope. New contract scopes E/cash/limits to an agent allocation and additionally enforces parent-account limits; normal profiles parameterize r, monetary cap, d, position/day limits while EUR50 risk-v0.1.0 remains 1%/3%/one/three. No limits are loosened or profiles activated. Pending consent holds no funds; final validated intent reserves both scopes atomically. Compounding/flows are explicit; no double allocation or self-unlock. Stop amendments cannot widen long risk. Status EXPERIMENTAL specification; owner requested this design extension, implementation/independent risk review still pending. Tests/comparative runs: NOT RUN. Commit/PR: none. See [[01 - Architecture/Portfolio Accounting/Capital Allocation]] and [[01 - Architecture/Execution/Safety Gate]].

## 2026-09-14 — Phase 5 risk/allocation candidate

- Previous: `risk-contract-v0.2.0` architecture specification only.
- New: immutable content-identified `BASELINE_RESEARCH_V1` risk policy, Decimal sizing decision, typed parent/allocation snapshots, structured risk rejection, proposal-bound reservation, optional external approval binding and local scoped-lock coordinator.
- Arithmetic: long unit risk is entry minus stop plus the supplied Phase 4 round-trip cost return; policy/cash/position/agent/parent/instrument limits bound quantity; `FUTURE_RISK_ENGINE` floors to generic increment and `FINAL_QUANTITY` either fits exactly or rejects.
- Atomicity/lifecycle: parent then allocation lock order; complete replacement snapshots publish together; active duplicate is idempotent; RELEASED/CONSUMED/EXPIRED terminal transitions conserve capital; no unlock API.
- Classification: risk-critical implementation candidate, research-only and unvalidated. No threshold is claimed optimal; no strategy result, order, fill, broker, P&L engine or live authority exists.
- Evidence: 68 focused Phase 5 cases and 371 total local tests passed before review handoff. Original candidate `0c36a5de657e749daa0ef987c47c44d299dd67b7` was reviewed in PR #4 and received CHANGES REQUIRED; it was not approved or merged.
- See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].

## 2026-09-14 — Phase 5 review remediation

- Review evidence: PR #4 reviewed original candidate `0c36a5de657e749daa0ef987c47c44d299dd67b7`; result **CHANGES REQUIRED**. No approval or merge is recorded.
- Corrected risk basis: sizing now uses explicit eligible current equity and remaining agent/parent daily-loss headroom. Content-identified loss observations retain session-start equity, current equity, current loss, latch state and revision. The risk decision binds the composed safety identity and monetary ceiling/loss/outstanding/headroom evidence.
- Corrected reservation behavior: ACTIVE and conservatively CONSUMED reservations contribute modeled downside; final reserve recomposes this state under the parent/allocation transaction boundary. A proposal-specific guard enforces one economic reservation across allocations/accounts within one coordinator.
- Corrected lifecycle: active replay revalidates time, locks, loss state and authority without double-counting itself; equality at expiry fails closed and post-expiry consume atomically expires before rejecting.
- Corrected integrity/concurrency: sizing artifacts validate their own normalized cost, per-unit loss/cash and aggregate arithmetic; binary floats are rejected in evaluated limits; safety-lock and reservation iteration is partitioned by parent.
- Classification: risk-critical corrective candidate. No risk threshold changed, no strategy result was produced and no execution authority was added. Independent competent re-review of the exact replacement commit remains mandatory.
- Evidence: 27 new adversarial cases cover the reported findings; final candidate verification is recorded in [[06 - Testing/Phase 5 Completion Criteria]].

## 2026-09-14 — Phase 5 second review remediation

- Review evidence: independent re-review of PR #4 candidate `7ea3dc007e212d9f391bb6cc4e9b36139d005322` returned **CHANGES REQUIRED**. No approval or merge is recorded.
- Agent-risk scope: the implementation now enforces the documented one-registered-allocation-per-agent rule for one coordinator/run context. The registry lock makes sequential and concurrent duplicate-agent registration fail atomically. No agent lock or multi-allocation agent ledger is claimed; a future change to permit multiple allocations per agent requires a new reviewed scope design.
- Sizing provenance: `SizingDecision` schema v3 embeds the self-validating immutable proposal and risk configuration. It validates proposal/configuration identities, entry, stop, currency, costs, sizing intent, increment, configured daily ceilings, allowed risk and arithmetic. Coherently changed/reidentified financial fields cannot retain stale source attribution.
- Loss evidence: `LossStateSnapshot` schema v2 binds parent or agent-allocation scope, ownership, session identity/boundaries, observation/effective/valid-until timestamps and monotonic revision. `SafetyStateSnapshot` v2 and `RiskDecision` v3 retain this evidence. Registration/update/evaluation/final reservation fail closed on cross-scope, previous-session, stale, future or regressing evidence.
- Lock order: reservation remains proposal guard → parent → allocation. Agent uniqueness registration uses the registry lock without introducing a nested agent lock. Parent/allocation conservation and previously corrected headroom, duplicate, expiry and lock behavior remain unchanged.
- Classification: risk-critical corrective candidate. No threshold was loosened, no strategy result was produced and no execution authority was added. Independent competent re-review of the exact second-remediation commit remains mandatory.
- Evidence: 21 additional adversarial cases bring Phase 5 to 116 focused tests and the repository to 419 tests; final verification passed. See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].
