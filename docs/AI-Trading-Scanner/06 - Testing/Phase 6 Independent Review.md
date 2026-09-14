# Phase 6 independent review

Status: **CHANGES REQUIRED — SECOND REMEDIATION AWAITS INDEPENDENT RE-REVIEW.** Phase 6 remains IN PROGRESS.

Independent review examined candidate `d56de875001ac3c18168d4efdd1f35c3f1b82ead` on branch `feat/phase-6-causal-simulation` and returned **REVIEW STATUS: CHANGES REQUIRED**. The review found that replay envelopes did not resolve or causally validate typed payloads, result summaries trusted caller-provided linkage, equivalent Decimal scales produced different Phase 6 identities, execution references were not validated across Phase 4–6 contracts, same-phase tie ordering remained caller-controlled, and several tests claimed more than they proved. No approval or merge is recorded.

The first remediation candidate `61a0d434b78275236cb13f2a527abc44ed010687` also received **REVIEW STATUS: CHANGES REQUIRED**. It added a typed immutable replay artifact registry, Decimal V2 canonicalization, semantic event ordering and a Phase 4→6 execution chain, but its COMPLETE check compared fill IDs without deriving portfolio state. It also failed to bind reservation amounts/downside to sizing, allowed dangling execution-resolution references and allowed next-bar selection to cross sessions. The earlier statement that unreconciled fill accounting already failed closed was therefore too broad. Both rejected review outcomes remain part of the record; neither candidate was approved or merged.

The second remediation derives chronological single-currency V1 accounting from the flat starting portfolio and every uniquely linked fill/position change. It applies notional and execution costs once, conserves cash/equity, derives open quantity/cost basis/unrealized P&L and closed-trade realized P&L, and requires every supplied portfolio snapshot and realized trade to equal the derived state. This is an in-memory validation foundation, not a transactional posting service, durable ledger or complete portfolio lifecycle.

The execution chain now requires the Phase 5 reservation to equal the authoritative sizing decision's quantity, reservation amount, modeled downside, instrument, currency, risk/configuration/ownership identities, authority dimensions, creation time and proposal expiry. Recomputed downstream identities do not make tampered economics valid.

Execution-resolution payload V2 gives unfilled/no-data/rejected outcomes an outcome-specific reason. Every resolution resolves a same-run order; FILL_READY additionally resolves one exact same-run market event and one matching fill. Terminal outcomes are unique and contradictory fill/unfilled states fail closed. COMPLETE artifacts require one terminal resolution per order.

V1 next-bar selection derives the proposal session from its exact causal data-slice hash and the authoritative XNYS calendar. The eligible bar must stay in that session and before both expiry and session close. No next-session open can satisfy an intraday order; early closes and DST use calendar data rather than hard-coded clock times.

Phase 6 identities now use a V2 canonical Decimal representation that removes insignificant scale, canonicalizes signed zero, and normalizes exponent forms without float conversion. This change is confined to the uncompleted Phase 6 contracts and leaves Phase 1–5 identity functions intact. The run manifest now binds `SEMANTIC_PAYLOAD_V1`; equal-time, equal-phase order derives from payload kind and immutable payload identity, with no caller-provided key.

A mandatory offline `ValidatedExecutionChain` reuses the Phase 4 proposal/decision and Phase 5 risk/sizing/reservation/approval contracts and binds them to the simulation manifest, frozen cost and execution configurations, simulated order, canonical dataset, next eligible same-session bar-open fill and position change. It grants no external execution authority.

The second-remediation workspace passes 587 tests: 480 Phase 1–5 regressions and 107 focused Phase 6 cases. The 28 added cases include the original unchanged-portfolio and economically tiny-reservation probes; duplicate/missing/foreign fill applications; cost, net P&L, equity and realized-trade forgeries; terminal-resolution dangling/contradictory/multiple states; and regular, early-close, DST and next-session execution boundaries. Automated results do not replace independent competent human re-review.

Still absent: the scheduler, complete replay engine, transaction-safe reservation/fill/accounting service, durable persistence or crash recovery, complete position lifecycle, four-agent experiment runner, broker/provider/network/AI integrations, PAPER and LIVE.

See [[06 - Testing/Phase 6 Completion Criteria]], [[06 - Testing/Backtesting]], [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]] and [[00 - Project/Current Status]].
