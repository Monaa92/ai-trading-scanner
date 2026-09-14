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
- Evidence: 68 focused Phase 5 cases and 371 total local tests passed before review handoff; independent competent review is still required. Commit/PR not yet recorded.
- See [[06 - Testing/Phase 5 Completion Criteria]] and [[06 - Testing/Phase 5 Independent Review]].
