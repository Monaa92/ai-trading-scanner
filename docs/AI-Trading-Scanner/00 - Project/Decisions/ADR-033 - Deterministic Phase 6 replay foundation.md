# ADR-033 — Deterministic Phase 6 replay foundation

- Status: ACCEPTED as the Phase 6 foundation policy; complete replay/execution behavior remains unimplemented and unvalidated.
- Date: 2026-09-14.

## Context

Phase 2 records event and availability time, but a backtest also needs deterministic ordering among fills, portfolio updates, newly available data, indicators, decisions, risk and submissions. Bar data cannot justify a fill inside the bar used to decide. Spread/slippage can be represented in fill price or as explicit monetary drag, but using both would debit the same cost twice. Phase 6 also needs replayable artifacts without prematurely selecting a production database.

## Decision

Use a discrete-event V1 ordered by `(scheduled_at, causal_phase, semantic_payload_key)`. The manifest binds `SEMANTIC_PAYLOAD_V1`; callers cannot supply ordering keys. The semantic key is derived from payload kind and its immutable content identity. Same-time phases are: execution resolution, fills, portfolio updates, session controls, market-data availability, indicator updates, strategy evaluation, risk evaluation, order submission and result finalization. This preserves the already accepted [[00 - Project/Decisions/ADR-013 - Causal hybrid backtesting and conservative ambiguity]] boundary.

A V1 market order's eligibility timestamp equals submission plus configured nonnegative latency; zero latency is valid. It may fill only at the first canonical bar open strictly later than that eligibility timestamp and within the proposal's same authoritative XNYS session. The simulated execution time is that later interval open; the fill becomes observable to replay only when the source bar is available. Missing same-session data records an unfilled/no-eligible-data terminal result; an intraday V1 order never carries to the next session. Same-session gaps use the next eligible open, same-interval ambiguity is stop-first, and partial fills and randomness are disabled in this foundation version. Calendar session close, early-close and DST boundaries come from the Phase 2 XNYS layer. These assumptions are immutable, content-identified configuration.

The causal bar-open price remains the gross fill reference. Commission, spread, slippage and other fees are separate exact monetary components and are subtracted once when computing net performance. Phase 6 V1 portfolio contracts use Decimal, long-only weighted-average accounting, one currency per isolated run, and conserved cash/equity identities. A full FX ledger remains blocking for the EUR-funded US-equity experiment.

Canonical UTF-8 NDJSON is the initial ordered event serialization. A typed immutable replay artifact binds the manifest, events, payload kinds and identities, causal timestamps, run/owner attribution, unique terminal execution resolutions, final portfolio, realized trades and finalization. A COMPLETE result derives its trace hash and references from that artifact, then independently derives V1 cash, positions, cost basis, costs, realized/unrealized/gross/net P&L, trades and equity from the chronological fill/application chain; supplied snapshots and trades must match exactly. Open positions use their latest applied fill price as the foundation's explicit valuation input until an external mark contract exists. Phase 6 V2 content identities canonicalize mathematically equivalent finite Decimals to one exact, float-free representation; Phase 1–5 V1 identity behavior remains unchanged. The foundation still has no transactional posting service, atomic filesystem writer, restart recovery, database or complete replay loop.

## Rationale

The ordering makes causal visibility and same-time races reviewable. A later bar open avoids same-bar look-ahead. Explicit cost components keep gross and net economics auditable without double counting. Content identities and canonical serialization give tiny offline fixtures reproducible evidence while preserving the future durable-storage boundary.

## Consequences

Equivalent immutable inputs, including equivalent Decimal scales and exponent forms, produce identical Phase 6 contract identities and event bytes. Correcting the pre-completion Phase 6 identity scheme changes candidate identities relative to rejected candidate `d56de875001ac3c18168d4efdd1f35c3f1b82ead`; no completed historical Phase 6 results exist to migrate. The foundation cannot claim a completed backtest: no scheduler, strategy/risk orchestration service, reservation-to-fill transaction, stop/target lifecycle, atomic store, metrics or four-agent runner exists. One-currency V1 cannot silently assume EUR equals USD. Alternative execution, partial-fill, stochastic, FX or persistence behavior requires a new execution/storage version and relevant adversarial review.

## Alternatives considered

Same-bar close/open fills, arrival-order event processing, wall-clock timestamps, unseeded randomness, optimistic partial fills, spread/slippage embedded in price and debited again, mutable JSON arrays, and immediate production database adoption.

## Conditions for revisiting

Revisit through a new version after causal end-to-end fixtures, higher-resolution market evidence, sourced fee/FX models or measured storage/recovery needs. Preserve old manifests, traces and results and rerun controlled comparators when assumptions change.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Canonical specifications: [[06 - Testing/Backtesting]], [[05 - Brokers/Simulation]], [[01 - Architecture/Portfolio Accounting/Portfolio Accounting]] and [[04 - Costs & Economics/Transaction Costs]]. Index: [[00 - Project/Decisions/ADRs]].
