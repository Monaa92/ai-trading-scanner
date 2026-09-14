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

## 2026-09-14 — Phase 5 third review remediation

- Review evidence: final independent re-review of PR #4 candidate `d1da3a07db417071697730b4acabe220755f22bc` returned **CHANGES REQUIRED**. Earlier candidates `0c36a5d` and `7ea3dc0` also remain rejected; no approval or merge is recorded.
- Parent ownership: registration now atomically enforces aggregate durable allocation capital at or below parent total capital under parent → registry locking. Currency and loss evidence validate before publication. Reservation release, expiry and consumption do not return allocation ownership; no retirement API exists.
- Sizing provenance: `SizingDecision` schema v4 binds proposal, configuration and complete evaluated state, then deterministically re-derives the future-risk quantity, exact-quantity intent and every financial result. Recomputed content IDs cannot legitimize caller-selected derived values.
- Decision evidence: `RiskDecision` schema v4 binds source proposal/configuration/evaluation state for both approved and rejected outcomes and checks derived limits, exact safety evidence, sizing attribution, ownership/configuration/currency reasons and causal safety reasons.
- Lock order: proposal → parent → allocation → registry for reservation publication; allocation registration uses parent → registry. Registry-only lookups release before acquiring proposal or scope locks.
- Classification: risk-critical corrective candidate. No threshold was loosened, no strategy result was produced and no execution authority was added. Independent competent re-review of the exact third-remediation branch head remains mandatory.
- Evidence: 15 additional adversarial/concurrency cases bring Phase 5 to 131 focused tests and the repository to 434 tests. See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].

## 2026-09-14 — Phase 5 fourth remediation candidate

- Previous candidate: `73a12676224d0fab901af69c8dc43fa65e63f707`; independent final re-review returned **CHANGES REQUIRED** because public readers could observe a parent/allocation snapshot before its required lock and related registry state were completely published.
- Change: registry release is now the public registration commit boundary. Public scope resolution obtains stable references in a registry-only section and releases registry before waiting for scope locks. Parent/allocation registration publishes the primary snapshot last and rolls back every related entry after an injected mutation failure.
- Lock order: parent registration uses registry; allocation registration uses registry-only parent resolution, then parent → registry; reservation uses proposal → registry-only scope resolution → parent → allocation → registry. No path holds registry while waiting for a parent/allocation lock.
- Classification: risk-critical corrective candidate. Capital/risk thresholds, strategy behavior and execution authority are unchanged. Independent competent re-review of the exact fourth-remediation branch head remains mandatory.
- Evidence: eight additional deterministic forced-interleaving and rollback cases bring Phase 5 to 139 focused tests and the repository to 442 tests. See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].

## 2026-09-14 — Phase 5 fifth remediation candidate

- Previous candidate: `8023bd8a59951b0bde1a207c73f398e94e921ae7`; independent re-review returned **CHANGES REQUIRED** because exceptions during sequential reservation and lifecycle publication could leave divergent parent, allocation, reservation and index state.
- Change: reservation creation and RELEASED/EXPIRED/CONSUMED publication now use an undo journal recorded before each mutation. A failure at any stage restores every earlier mapping in reverse order with base dictionary operations and re-raises the publication failure. The complete publication stays inside the existing scope and registry locks, so readers and competitors cannot observe or spend intermediate capacity.
- Mutation scope: reserve covers parent, allocation, per-account/global reservation registries, risk-decision linkage and proposal uniqueness. Each lifecycle transition covers parent, allocation and per-account/global reservation state; its risk/proposal links remain immutable.
- Lock order: unchanged at proposal → registry-only scope resolution → parent → allocation → registry. Registration guarantees from the fourth remediation remain unchanged.
- Classification: risk-critical corrective candidate. Risk thresholds, strategy behavior and execution authority are unchanged. Independent competent re-review of the exact fifth-remediation branch head remains mandatory.
- Evidence: 38 additional deterministic cases include 12 reserve publication failures, 24 lifecycle publication failures and two blocked reader/competitor probes. Phase 5 has 177 focused tests and the repository has 480 tests. See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].

## 2026-09-14 — Phase 5 approval and merge

- Review evidence: `Dekkerszz` independently reviewed `90764dc7d6cca035da9fbe28cd4989f23399ea6e` in PR #4 and returned **PASS**.
- Merge: PR #4 was merged and closed as `d08faa7ca3fdd3f35a053838f736d4d709d503d9`.
- Completion: all previously identified Phase 5 findings are resolved. The reviewed candidate passed 480 tests, including 303 Phase 1–4 regressions and 177 focused Phase 5 cases.
- Boundary unchanged: Phase 5 adds no broker/provider/network/AI/order/PAPER/LIVE execution authority. It remains single-process and in-memory, with no crash recovery, multi-process coordination, complete portfolio/P&L lifecycle or allocation-retirement operation.
- Next milestone: Phase 6 — causal backtesting and simulation — is next and has not started.
