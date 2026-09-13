# Strategy overview

Status: HYPOTHESIS, no validated findings. V1 investigates long intraday trend pullbacks in US equities/ETFs on 5-minute bars. [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]] owns that benchmark's exact proposed rule semantics; numerical research parameters remain unselected. [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]] specifies four broader comparison hypotheses without claiming implementation or validation.

Initial convenience universe: SPY, QQQ, AAPL, MSFT, NVDA, AMD, AMZN, META, GOOGL, TSLA, AVGO, NFLX, PLTR, COIN. This is a development list, not an optimized or historically unbiased universe. Validate liquidity, data availability, account eligibility and fractionability at the applicable time; membership does not authorize a trade.

V1 evaluates session VWAP, EMA 9/20/50 and causal pullback structure. RSI 14, ATR, relative volume, volume, intraday levels and optional multi-timeframe context are defined in [[02 - Agents & Strategies/Shared Agent Rules/Indicators]]; adding filters is a registered experiment. No metric or threshold is called optimal. Later 15-minute/hourly/daily context is optional and may be unavailable early in a session.

Separation: strategy proposes setups; selection ranks eligible candidates; [[01 - Architecture/Risk Engine]] rejects or bounds exposure; order/position services handle execution. [[01 - Architecture/AI Architecture]] may veto/rank a strategy-valid candidate but cannot rescue a rejected strategy or alter stops/size/risk limits.

Research changes follow [[02 - Agents & Strategies/Strategy Versioning]], [[03 - Experiments/Experiment Framework]] and [[00 - Project/Decisions/Strategy Changelog]]. An empty trade set or infeasible EUR 50 sizing is a valid finding, not a reason to relax controls invisibly.
