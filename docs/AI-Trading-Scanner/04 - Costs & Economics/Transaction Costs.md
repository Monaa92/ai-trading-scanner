# Transaction costs

Status: **PARTIAL — VERSIONED PHASE 6 CALCULATION CONTRACT; numeric broker-style schedules REQUIRED BUT UNSET**. No evidential IBKR/Kraken fee profile or complete simulation is executable yet.

Strategies evaluate expected net opportunity before proposing a trade:

`expected_net_profit = expected_gross_profit - entry_commission - exit_commission - spread_cost - slippage - exchange_or_regulatory_fees - applicable_FX_costs`

Both entry and expected exit costs are mandatory. A positive gross forecast that fails the strategy's versioned net-edge threshold returns `NO_TRADE/TRANSACTION_COST_CONCERN`. Risk recomputes costs for approved quantity; final validation rejects stale or incompatible assumptions. Costs are never reduced merely to make EUR 50 viable.

Phase 4 implements the input/output contract, not the cost service: `RoundTripCostEstimate` carries a methodology version plus normalized entry, exit, spread, slippage and other execution return drag. The evaluator verifies `net_expected_return = gross_expected_return - every supplied cost component` using deterministic Decimal arithmetic. Missing cost input returns strategy `NO_TRADE: UNSUPPORTED_CONTEXT`; costs that remove otherwise sufficient gross edge return `TRANSACTION_COST_CONCERN`. The fixture methodology is test-only and is never described as IBKR, Kraken or executable broker economics.

Phase 5 consumes that supplied total return drag in modeled unit loss and conservatively reserves entry notional plus the supplied round-trip drag. It does not implement or name a broker fee schedule. Nonlinear commissions, FX, tick/minimum and venue capability remain blocking dependencies for later executable simulation profiles.

Phase 6 now implements a content-identified `TransactionCostConfiguration` and exact per-fill calculation for minimum commission, per-share commission, spread basis points, slippage basis points and other-fee basis points. The result records every component, reference notional, currency and total. Numeric inputs reject binary floats and negative/non-finite values. No built-in profile values are supplied: tests use an explicitly named synthetic profile only.

The V1 foundation stores the next eligible bar open as gross fill price and represents spread/slippage as separate monetary drag. Portfolio cash and net P&L will debit each component once; callers must not also shift the fill price for the same configured spread/slippage. This convention is versioned by [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]]. Cost rounding, entry-versus-exit asymmetry, nonlinear tiers, regulatory sell-only fees, FX and reconciliation from Phase 4 expected round-trip return drag to realized amounts remain unimplemented.

Each immutable profile records version/effective date, source and validation status; currency; commission minimum and per-share/rate components; separate entry/exit application; exchange/regulatory fees; spread and slippage model; impact; FX conversion; rounding; asset/account/order scope; and unknown behavior. Results embed or content-address the resolved profile so later changes cannot rewrite history.

| Profile | Intended use | Current state |
| --- | --- | --- |
| `SIMULATED_IBKR_US_TIERED` | Experiment 1 US-equity simulation | REQUIRED, numeric values unselected; no run may start until sourced and versioned |
| `SIMULATED_KRAKEN_SPOT` | Future crypto simulation only | DEFERRED, numeric values unselected; unavailable to Experiment 1 |

Track commission, spread, slippage, exchange/regulatory and FX separately. Fill prices may already include spread/slippage; attribution must not debit them twice. Report total execution costs, average round-trip cost, costs/capital, costs/gross profit and cost-driven rejection rate.
