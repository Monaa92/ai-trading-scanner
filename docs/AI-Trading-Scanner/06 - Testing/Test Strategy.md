# Testing strategy

Status: Phase 1–4 suites are complete on `main`. The Phase 5 candidate adds focused risk, sizing, allocation, lifecycle, authority and real threaded-concurrency cases and requires independent review. Trading, full replay, portfolio P&L and frontend tests remain future work. See [PROJECT_RULES](../../PROJECT_RULES.md), [[06 - Testing/Phase 4 Independent Review]] and [[06 - Testing/Phase 5 Independent Review]].

The initial 111 Phase 1 cases remain regression coverage for valid/malformed IDs, exact enum rejection, dimension independence, PAPER + FULL_AUTO representation, safe defaults, forbidden authority fields, disabled capability switches, redacted validation errors, non-fallback LIVE failure, CLI exit behavior and the in-memory FastAPI health route.

Phase 2 adds 60 collected cases, including expanded `InstrumentId`/`DatasetId` validation. They exercise immutable and decimal-safe bars; half-open/timezone-aware timestamps; actual/modeled availability; session identity; regular, DST, weekend, holiday and early-close behavior; invalid and missing observations; structured severity; dataset hash determinism and sensitivity; modeled-delay enforcement; and causal visibility/equivalent four-consumer slices. Tests use tiny synthetic records and locally packaged calendar data. The suite patches socket connection creation during CLI health to detect unintended network use. No trading behavior is claimed because none exists.

Phase 3 adds 48 collected cases across configuration, EMA, RSI, ATR, VWAP and cross-cutting causality. They verify strict periods/method selection, formula seeds and recurrences, unavailable reasons and units/lineage invariants, constant/rising/falling/mixed values, zero denominators, missing intervals, regular and early-close sessions, weekend/holiday/DST transitions, prefix invariance at multiple lengths, batch/incremental equivalence, global-context-independent Decimal results, causal reader integration, warning visibility/retention, incompatible units and fatal-input rejection. The health check adds one compact four-indicator fixture without network or credentials.

Phase 4 adds 84 focused cases for the four registered identities and parameter validation; strategy/model separation; agent attribution and common-information equality; explicit NO_TRADE taxonomy; immutable decisions/proposals/management; approval-sensitive content fingerprints; Momentum, Mean Reversion, Breakout and Multi-Factor predicates; unready/gapped/stale/quality/fatal inputs; cost-driven rejection; canonical serialization; repeated-evaluation idempotence; and strategy-level prefix invariance. Tests assert no network side effect and repository scans enforce no broker/provider/AI imports in strategy code. Synthetic fixtures demonstrate branches, not profitability. The merged implementation passes 303 tests, with all 219 Phase 1–3 regression cases retained.

Phase 5 now has 116 focused cases. The original 68 cover typed ownership/content identities; research-policy validation; float/non-finite/LIVE rejection; exact sizing/downward rounding; final-quantity immutability; risk, position, cash, agent, parent and concentration caps; capital scaling; proposal time/configuration/currency/ownership; structured rejections; reservation conservation/lifecycle; duplicate/idempotent behavior; approval binding; scoped locks; rollback; and core races. The first 27 remediation cases add eligible-equity and daily-headroom boundaries, current loss-state revision, outstanding downside lifecycle, stale-preflight revalidation, proposal uniqueness, exact expiry replay/consume behavior, lock-before-replay, sizing arithmetic, Decimal enforcement, safety-decision identity and cross-parent lock concurrency. The second 21 adversarial cases cover sequential/concurrent same-agent allocation rejection, downside/exposure/count fragmentation prevention, post-lifecycle allocation identity, coherent proposal/configuration/allowed-risk forgery rejection, legitimate JSON reconstruction, cross-scope loss misuse, session/freshness/causal timestamp failures, revision/time regression and final freshness revalidation. Tests scan the `risk` package AST for forbidden broker/provider/network/AI imports. The complete local second-remediation workspace passes 419 tests, including 303 Phase 1–4 regressions.

## Required evidence layers

| Layer | Fixtures and expected behavior |
| --- | --- |
| Unit — indicators | Hand-computed VWAP/EMA seeds/Wilder RSI+ATR, flat/zero cases, exact warm-up, gaps and session resets match [[02 - Agents & Strategies/Shared Agent Rules/Indicators]] |
| Unit — strategy | Equality boundaries fail/pass exactly as specified; missing research config blocks evaluation; future resistance/pivot data cannot trigger candidate |
| Unit — sizing | Zero/negative stop distance, fees/minima, EUR/USD units, cash limitation, downward quantity rounding, RR after costs; all invalid inputs reject |
| Unit — daily limits | Realized+unrealized loss, dynamic ceiling, profits not increasing ceiling, late fills, latch persistence and session reset |
| Unit — time/state | UTC vs New York DST, holidays/early closes, close/open labels, deadlines, valid/invalid lifecycle transitions |
| Property/invariant | For every approved q: modeled risk≤budget and reserved spend≤available cash under same valid inputs; actual gap loss is not asserted bounded |
| Property/invariant | AI cannot enlarge cap/change stops; no post-decision availability influences result; duplicate events do not double cash/quantity; lockout prevents new entry intents |
| Property/invariant | Two concurrent approvals cannot occupy two slots; cancel/fill races cannot release committed cash early or intentionally over-close; per-currency ledger balances |
| Integration | Provider pages/cursors/revisions, normalized feed/time semantics, broker capability/error mapping, durable transaction/outbox, API auth/account/mode scope |
| Backtest regression | Tiny fixtures pin ordered trace, candidate/rejection count, fills, fees, cash, drawdown and end-state; matching P&L alone insufficient |
| Simulation/failure | Gaps/halts, same-bar stop+target, partials, API timeout before/after acceptance, cancel race, restart, duplicate/out-of-order fills, stale FX/quotes, DB loss and clock drift |
| End-to-end later | Paper entry→partial fill→protection→exit→reconciliation; emergency stop; UI displays freshness and cannot bypass rejected risk |

## Mandatory adversarial scenarios

1. A 10:05 decision cannot see the 10:15 quarter-hour or 10:30 hour, or fill at 10:05 open. Adding/changing later bars leaves earlier decision trace unchanged.
2. Two symbols compete for the final slot/day entry. One atomic reservation wins; loser re-evaluates or expires. Stable input order produces identical winner on replay.
3. Broker accepts entry but network times out. Restart queries the same client ID and records one order/position, not a second submission.
4. Cancel request races with partial fill. Fill is recorded/protected, remainder retained until terminal reconcile; counters increment once.
5. Daily unrealized loss crosses the dynamic ceiling then recovers. New entries stay locked until verified next session; emergency lock remains until explicit clearance.
6. Fractional q rounds below minimum. Reject, never round up. If filled residual cannot be protected/liquidated under capability rules, entry capability test fails.
7. AI returns extra quantity field, mismatched candidate IDs, NaN, malformed JSON, stale response or outage. Treatment makes no new entry; existing exit control proceeds.
8. End-of-day flatten misses its execution window/encounters halt. End state reports an open unresolved position and incomplete run; no fake closing fill.
9. Revised bar/corporate action arrives late. Old decisions remain immutable; future features use repaired input with new lineage and no retroactive order.
10. Database commit fails before submission. No network order occurs. Lost acknowledgement after successful commit remains UNKNOWN and reserved.

Fixture numeric values are synthetic tests, not strategy optimization. Precision tolerances must be justified per computation; monetary invariants use exact decimal comparisons. Any stochastic scenario fixes seed and event-indexed random draws; nondeterministic live/provider behavior is validated via captured events, not asserted reproducible.

## Risk-critical merge and release checks

Behavioral changes require relevant unit+property+integration/failure and deterministic replay tests, documented results, comparison with previous accepted strategy where applicable, synchronized histories/ADRs, diff review and independent competent reviewer approval. Changed expected outputs need an explained causal diff; do not bless a new golden result solely to make tests pass. Critical test failures or missing evidence block merge. Network contract tests use isolated paper credentials/mode only and require authorized setup; unrun checks are explicitly reported.

Documentation-only checks: all created/changed files in scope, no secrets, coherent Markdown/wiki links, all mandatory ADR fields, governance/spec consistency and Git state. Do not report design fixtures as executed tests.

## Agent, mode and experiment invariants

The following are required future tests, not executed in this documentation pass. Use independent contexts plus adversarial shared-account fixtures, every valid execution-mode/environment combination, races and restart boundaries.

| Scenario | Required assertion |
| --- | --- |
| Agent A requests B snapshots/orders/approval | Scoped repository/auth/foreign-key checks deny; authorized owner reporting remains possible |
| Agent A exceeds its allocation while B has idle capital | Reject without borrowing; total broker balance does not enlarge A's budget |
| Concurrent allocation/transfer and reservations | Balanced atomic transfers and agent+parent revision conflicts prevent double spending |
| Local daily lockout | A cannot trade, independent B remains eligible |
| Shared account/system integrity lock | All affected agents block; unrelated independent account remains unaffected |
| Manual proposal without consent | No executable intent/outbox/submit; never infer human approval from risk PASS |
| Approval followed by adverse price, loss, insufficient cash or capability change | Fresh risk/safety blocks even though user approved |
| Expired/stale/mutated proposal | Reject at server deadline/version/hash; changed quantity/stop/target requires new consent |
| Duplicate/conflicting approve/reject race | One terminal decision and at most one intent; no replay after restart |
| SIGNAL_ONLY | Full diagnostics recorded, no dispatch authority or durable trading reservation |
| FULL_AUTO | Same failing safety/risk fixture blocks as manual; missing auto administrative mandate also blocks |
| Autonomous frozen mutation | Changed strategy/risk/model/prompt/management hash blocks; allowed preregistered adaptive update logs state without rewriting manifest |
| AI attempts mode/LIVE/risk/lock/config change | Rejected at privilege/API boundary regardless of response format |
| Counterfactual fill or rejected-candidate outcome | Cannot post to actual-path ledger, risk headroom, trade/survival counts or leaderboard default |
| Period aggregation | Daily plus non-session P&L bridges to weekly/monthly/lifetime equity; ratios recompute from totals; open trades/flows/config segments handled |
| Account/agent snapshots | Fills/fees/FX/settlement reconcile; sum allocations plus unallocated equals parent; duplicate fills do not duplicate attribution |
| Restart after accepted-but-timed-out submit | Same client ID reconciles once; no implicit consent, expiry extension or reset lock |
| Dynamic stop/profit-taking | No stop widening, no over-close, no future-bar activation; old protection until acknowledgement, residual minima respected |
| Configuration cutover | Flat/no unknown order/session gate enforced, proposals invalidated, actor/old/new/effective time retained |
| Survival endpoint/no-trade/outage | Failure/censoring/lock episodes distinct; no artificial score/probability from four paths; inactive losses/costs visible |
| Kill switch during dispatch | Permission epoch blocks unsent attempts; possible in-flight acceptance remains reconciled, never declared impossible |

Run projection/ledger and API isolation integration tests as well as domain properties; UI-only controls are insufficient. Dynamic management requires complete portfolio comparative backtests, not only amendment unit tests. Frozen experiment fixtures replay the same data under reordered worker schedules and verify per-agent results apart from explicitly modeled latency. Approval replay must retain actual/scripted latency and no hindsight consent. These join the existing independent-review merge gate.

## Broker, strategy, capital and economics completion tests

These are behavioral tests required in future implementation. Interface/import existence alone does not pass.

| Scenario | Required behavior |
| --- | --- |
| Agent attempts direct SDK/network/provider call | Architectural dependency test and runtime capability boundary deny it; only execution coordinator can invoke BrokerAdapter |
| FULL_AUTO with SIMULATION/PAPER/LIVE | Approval policy never mutates environment; PAPER + FULL_AUTO validates, LIVE remains disabled without a separate owner activation/readiness artifact |
| IBKR/Kraken adapters registered | Registration changes no environment/universe/credentials; Experiment 1 remains EQUITY and Kraken CRYPTO is rejected |
| Unsupported/UNKNOWN capability | Proposal rejects before reservation/network mutation with exact reason |
| Simulation startup | Succeeds with no broker/API credential variables and performs no network access |
| Four agents share one normalized snapshot | Snapshot/data-availability hashes match while cash, reservations, positions, P&L, costs, risk and order attribution remain independent |
| NO_TRADE | Persists as normal decision with structured reason and creates no proposal/reservation/order; zero-trade run remains valid |
| Round-trip cost decision | Both entry and exit costs plus configured spread/slippage/fees are included; sufficient gross but insufficient net edge rejects |
| Gross/net/economic accounting | Gross Trading, Net Trading and Net Economic P&L reconcile through separate execution- and AI-cost ledgers without changing portfolio cash for AI costs |
| Historical fee profile | Changing current profile creates a new version; old run recomputation retains its embedded/content-addressed schedule |
| Stale market snapshot | PAPER/future LIVE entry rejects where freshness policy requires; exits/protection follow safe failure contract |
| Capital sweep replay | Stateless decision artifact reuses inference reproducibly across EUR 50/100/250/500/1000; each execution ledger remains isolated |
| Portfolio-dependent strategy | Capital/cash/prior position/risk input marks replay non-equivalent and forces a separately identified inference/run |
| MVC/reporting | Underlying net P&L/return/drawdown/executable trade/rejection/cost/sample/stability inputs persist; no result is inferred from positive P&L alone |
| AI budget races/hard stop | Atomic usage reservation prevents overspend; hard stop blocks new AI calls but cannot debit portfolio or strand protection/exits; owner resume is explicit |
| Strategy/model dimensions | Same strategy can vary model and same model can vary strategy; Experiment 1 Multi-Factor receives no extra raw information |
| Profit management | No universal profit-cap invariant exists; registered strategy exits obey central hard downside limits, causal inputs and immutable re-approval |

The Phase 3 fixture must execute one deterministic end-to-end run and assert trace contents, balances, attribution and metrics. Until that exists, [[06 - Testing/Phase 3 Completion Criteria]] remains NOT READY FOR TESTING.
