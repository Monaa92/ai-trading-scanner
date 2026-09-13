# Position sizing and currencies

Canonical sizing contract. Money/quantity/ticks use decimal arithmetic. Round only at documented instrument/broker boundaries, then recheck every constraint. Inputs must share compatible units and be valid at decision/submission time.

## Currency model

Initially track EUR and USD cash separately and report in EUR. General profiles use explicit reporting/instrument currencies through the same conversion functions, without EUR50-specific logic. A versioned FX observation contains base/quote currency, bid/ask, source, event/receipt/availability time and validity window. Never assume EUR=USD or hard-code an exchange rate. USD purchases use actual available USD cash; conversion from EUR requires an explicit modeled/recorded conversion with spread/fees and settlement. A rate used to report value does not imply currency is spendable.

For a historical EUR 50 experiment, convert at an identified initial FX observation under a declared policy, retain conversion costs and any EUR residual, then account in both currencies. Mark USD assets in EUR at each valuation. Paper can use an internal EUR 50-equivalent shadow ledger constrained below the broker paper balance. Distinguish virtual initial allocation from executed FX. FX replay may use explicit historical quote observations or a labeled conservative historical-rate model; missing model/rates blocks an evidential run.

Define `convert_loss(x USD,t)` using a conservative EUR-per-USD rate plus applicable adverse FX buffer. Define conversion for proceeds and buying cash separately using the unfavorable side and fees. For sizing, positive USD risk must not be converted with an optimistic rate. Shock FX jointly with execution in stress tests. An FX buffer is an assumption, not a guarantee.

## Feasible quantity

Let P be maximum modeled entry USD/share, S the fixed sell-stop trigger, T target, q the quantity. Require T>P>S>0. Normalize levels to valid ticks first: entry buy limit rounds down to its allowed cap; a long protective stop rounds up toward entry (never silently down/wider); target rounds down. Reject if normalization destroys geometry or feasibility, including a stop already at/above the current valid bid for a proposed new long entry. A subsequent gap after submission remains execution risk, not grounds for retroactive rejection.

Let a be adverse entry slippage/spread allowance not already included in P, z adverse stop slippage/gap allowance, and C_loss(q) total modeled entry+stop-exit fees and conversion costs in EUR. Define:

`Loss(q) = convert_loss(q * ((P + a) - (S - z)), t) + C_loss(q)`

`Reward(q) = convert_proceeds(q * ((T - target_slippage) - (P + a)), t) - C_win(q)`

`SpendUSD(q) = q * (P + a) + entry_fees_USD(q) + cash_buffer_USD(q)`

P derived from ask already includes spread; do not add the full spread again. If using a midpoint/bar proxy, explicitly model the entry ask and exit bid once. Do not count slippage both in fill price and as a cash debit. Fees are cash debits. Fixed/minimum/tiered fees mean quantity cannot always be obtained by simple division.

Budget uses [[01 - Architecture/Portfolio Accounting/Capital Allocation]]'s B_i formula: risk fraction times eligible agent equity, bounded by monetary cap and agent/account/portfolio headroom. Initial EUR50 risk remains 1%. Spendable capital C is the minimum of agent-attributed settled cash net of reservations, parent-account spendable cash excluding leverage and allocation constraints. In currencies other than USD, first resolve actual permitted conversion and spendable USD.

Choose the greatest broker-valid quantity q such that:

- q>0 and q is on the allowed quantity increment grid (whole shares if not fractionable).
- Loss(q)≤B, SpendUSD(q)≤C_USD, Reward(q)>0 and Reward(q)/Loss(q)≥2.0.
- Entry and protective/closing order requirements, price ticks, minimum notional/quantity and tradability all pass.
- Account/session/exposure restrictions in [[01 - Architecture/Risk Engine]] pass.

For linear loss and fees, start from min(risk-limited q, cash-limited q), floor to the quantity increment, then verify the exact functions. For nonlinear fees solve over the valid bounded quantity domain; only use bisection when the relevant predicate is demonstrably monotonic. Net RR/minimum constraints may not be monotonic, so verify them explicitly. Never round up to a minimum: if no feasible quantity exists, reject with all binding constraints. Reserve modeled fees and capital before submitting. Quantity-first intents avoid inconsistent notional-to-quantity conversion; adapter conversion must not enlarge authorization.

## Illustrative arithmetic, not an FX or cost assumption

Synthetic fixture only: E=EUR50, B=EUR0.50, 1 EUR=1.20 USD, modeled stop loss USD3/share after allowances, no fixed fees. Risk-limited q=0.50×1.20/3=0.20 shares. At USD100 entry the spend is about USD20 before cash buffer, so it fits USD60 starting cash; a separately valid target must still pass net RR. With whole shares only, flooring gives zero and the trade is rejected. Actual runs must replace these fixture inputs with recorded observations/configuration.

Market fills may exceed P+a. After each fill recompute actual risk/capital, protect filled quantity, cancel remaining entry when exposure exceeds authorization, and request controlled reduction if necessary. Do not widen S. Record breach even if quickly corrected. Partial quantities below a broker close minimum/protection capability block the proposed entry unless verified liquidation support covers them. No sizing formula guarantees the exit price.
