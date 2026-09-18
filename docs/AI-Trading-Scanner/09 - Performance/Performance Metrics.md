# Performance metrics

Status: required metric contract. Compute in reporting EUR after fees/FX with a separately available USD trading attribution. Report cash/no-trade control and starting capital. For EUR50, cents, rounding, idle time and fixed costs can dominate ratios; always show money amounts beside percentages. [[04 - Costs & Economics/AI Inference Costs]] owns the strict separation between trading and operating economics.

## Trade and P&L definitions

A **trade** is one position episode from first positive entry fill to fully reconciled flat, with residual entry cancelled. Partials/cancel-replacements are aggregated, not separate wins. No scale-in/pyramiding in V1. Entry counters count first fills; closed-trade metrics exclude still-open episodes but separately report their number, equity impact and incomplete status. An end-of-run position must not disappear.

For closed trade i, Net Trading P_i includes cash flows, allocated trading/FX fees and explicit execution effects already embedded in fill prices. Slippage is a counterfactual attribution, not a second cash debit. Gross Trading P&L, Net Trading P&L and Net Economic P&L are separate fields. AI/data/hosting costs never alter portfolio cash and enter Net Economic P&L only through a registered attribution policy.

Initial R_i is the modeled loss budget allocated to the **actually filled** entry quantity at original authorization/stop, including allocated modeled costs. For partial fills use the same sizing model evaluated at filled quantity, freeze at entry completion/cancellation; disclose changes due to entry overrun separately. R is never recalculated from a later favorable stop. If R_i≤0/unknown the R metric is invalid, not infinite; the run requires diagnosis.

| Metric | Definition | Limitation |
| --- | --- | --- |
| Total/win/loss/breakeven | N closed episodes; W count P>0, L count P<0, Z count P=0; N=W+L+Z | Open trades excluded but separately shown; currency rounding can create apparent zeros |
| Win rate | W/N, denominator includes breakevens | N=0 → unavailable; high rate can hide rare large losses |
| Average winner/loser | mean positive P; mean negative P (signed) | Empty subset → unavailable, not zero; show sample counts |
| Gross profit/loss | GP=Σmax(P,0), GL=−Σmin(P,0) as positive loss magnitude, using trade-net P | “Gross” here partitions winning/losing net trades; separately report pre-cost trading P&L to avoid ambiguity |
| Profit factor | GP/GL | GL=0 → undefined/no-loss sample, never proof of infinite edge; unstable for few losses |
| Net Trading P&L | ΣP for closed trades; portfolio equity change minus external flows also includes open/FX/unallocated trading costs | Reconcile both views; do not force equality while trades are open |
| Net Economic P&L | Net Trading P&L minus attributed AI inference and other explicitly allocated operating costs | Separate non-portfolio ledger; unavailable without a versioned attribution policy |
| Return | (ending equity−starting equity−external flows)/starting equity for no-flow experiment | Mid-run flows require separate flow-adjusted method/version; tiny capital exaggerates cents |
| Expectancy | mean(P_i)=GP/N−GL/N; also show W/N·avgWin + L/N·avgLoss | Clustered trades invalidate naive independent-trade standard errors |
| Average R | mean(P_i/R_i); also show R distribution | Mean money expectancy divided by mean risk is not mean R |
| Max drawdown | Equity peak H_t=max_(s≤t)E_s; max(H_t−E_t) and max((H_t−E_t)/H_t) | Use marked equity including open P&L; sampling frequency can hide intrabar losses |
| Drawdown duration | Elapsed time/session count from peak to recovery; ongoing drawdown censored at end | Distinguish calendar/trading time; no fake recovery at run end |
| Holding time | First entry to final exit, quantity-weighted holding time optional and named separately | Intrabar execution timestamps may be interval estimates |
| Exposure | Time with q>0 / eligible session time; additionally time-weighted gross notional/equity | Data-gap time is reported, not removed to improve denominator |
| Costs/slippage | Trading fees, FX fees, modeled spread, slippage and impact attribution separately | Avoid double-counting spread already in bid/ask and slippage in fills |

## Later descriptive metrics

Sharpe: mean daily net excess return / daily standard deviation × sqrt(registered annualization factor). Include zero-trade days; risk-free assumption explicit. Sortino uses predeclared downside target and downside deviation. Both need enough independent days; no annualized claim from a tiny sample. Calmar divides annualized return by max percentage drawdown; short runs or zero drawdown make it unstable/undefined. Payoff ratio=avgWin/abs(avgLoss), undefined when subset absent. Consecutive wins/losses depend on ordering and breakeven handling (break a streak by default).

Breakdowns by symbol, session time slot, weekday, volatility and market regime must use predefined categories and show N, net costs and uncertainty. Multiple slice comparisons are exploratory unless registered. EUR return combines USD trading and FX changes; report both. Pair monetary expectancy/net return with exposure, coverage, effective sample size and drawdown rather than selecting the prettiest ratio. See [[03 - Experiments/Experiment Framework]].

## Complete trade-lifecycle metrics

For each position episode retain entry-quality definition/version, maximum favorable excursion (MFE), maximum adverse excursion (MAE), realized return, peak unrealized profit, profit retained at exit, giveback from peak, exit reason, holding period, stop-triggered exit, strategy-triggered exit and risk-engine intervention. Excursions use only causal marked observations at the configured sampling granularity and disclose gaps; they never choose an exit with future information. These measures diagnose early exits, excessive giveback, slow loss-cutting and trend capture without imposing a universal profit cap.

## Agent/period and survival reporting

[[09 - Performance/Agent Statistics]] extends these definitions to trade/day/week/month/lifetime with agent/config/allocation/performance-kind scope, explicit equity bridges, non-session postings, flow adjustment and counts/ratio recomputation. [[03 - Experiments/Survival Analysis]] adds endpoint/censoring-aware preservation metrics without a composite survival score. EUR50 remains a profile; normal funding changes cannot be mistaken for return. Counterfactual results are separate diagnostic runs.

The future 4+1 report adds Agent 5 active-survival epochs, opportunity/participation coverage, economic-state and death/estate history, policy revisions, sub-agent creation/retirement, internal allocation transitions and organization snapshots. These accompany ordinary P&L, cost, drawdown, exposure and trade metrics; they do not replace them with one opaque reward. `INACTIVE_FAILURE`, `DEAD`, lockout, intervention, incomplete estate and horizon censoring remain distinct outcomes. See [[02 - Agents & Strategies/Autonomous Survival Agent]] and [[03 - Experiments/4+1 Historical Experiment]].
