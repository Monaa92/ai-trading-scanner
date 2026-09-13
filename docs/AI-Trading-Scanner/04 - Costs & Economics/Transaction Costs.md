# Transaction costs

Status: **versioned contract; numeric schedules REQUIRED BUT UNSET**. No fee profile is executable yet.

Strategies evaluate expected net opportunity before proposing a trade:

`expected_net_profit = expected_gross_profit - entry_commission - exit_commission - spread_cost - slippage - exchange_or_regulatory_fees - applicable_FX_costs`

Both entry and expected exit costs are mandatory. A positive gross forecast that fails the strategy's versioned net-edge threshold returns NO_TRADE/COST_TOO_HIGH. Risk recomputes costs for approved quantity; final validation rejects stale or incompatible assumptions. Costs are never reduced merely to make EUR 50 viable.

Each immutable profile records version/effective date, source and validation status; currency; commission minimum and per-share/rate components; separate entry/exit application; exchange/regulatory fees; spread and slippage model; impact; FX conversion; rounding; asset/account/order scope; and unknown behavior. Results embed or content-address the resolved profile so later changes cannot rewrite history.

| Profile | Intended use | Current state |
| --- | --- | --- |
| `SIMULATED_IBKR_US_TIERED` | Experiment 1 US-equity simulation | REQUIRED, numeric values unselected; no run may start until sourced and versioned |
| `SIMULATED_KRAKEN_SPOT` | Future crypto simulation only | DEFERRED, numeric values unselected; unavailable to Experiment 1 |

Track commission, spread, slippage, exchange/regulatory and FX separately. Fill prices may already include spread/slippage; attribution must not debit them twice. Report total execution costs, average round-trip cost, costs/capital, costs/gross profit and cost-driven rejection rate.
