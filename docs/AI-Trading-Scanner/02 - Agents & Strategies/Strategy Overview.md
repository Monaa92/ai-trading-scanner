# Strategy overview

Status: IMPLEMENTED PHASE 4 RESEARCH CONTRACTS, no validated findings. Four long-only intraday baselines are registered as `BASELINE_RESEARCH_V1`/`0.1.0`. [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]] owns Agent A's exact rule semantics; [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]] owns the shared parameters and four-profile comparison contract. These settings are unoptimized and do not constitute an accepted trading strategy.

Initial convenience universe: SPY, QQQ, AAPL, MSFT, NVDA, AMD, AMZN, META, GOOGL, TSLA, AVGO, NFLX, PLTR, COIN. This is a development list, not an optimized or historically unbiased universe. Validate liquidity, data availability, account eligibility and fractionability at the applicable time; membership does not authorize a trade.

V1 evaluates session VWAP, EMA 9/20/50, RSI 14 and ATR 14 on completed five-minute bars. Relative volume, additional intraday levels and multi-timeframe context remain future hypotheses. No metric or threshold is called optimal.

Separation: Phase 4 strategy evaluation returns `NO_TRADE` or a complete immutable proposal. The proposal requests future risk-engine sizing and cannot reserve capital or submit an order. Future selection may rank candidates; [[01 - Architecture/Risk Engine]] rejects or bounds exposure; order/position services handle execution. [[01 - Architecture/AI Architecture]] may later veto/rank a strategy-valid candidate but cannot rescue a rejected strategy or alter stops/size/risk limits. Strategy configuration contains no model identity.

Research changes follow [[02 - Agents & Strategies/Strategy Versioning]], [[03 - Experiments/Experiment Framework]] and [[00 - Project/Decisions/Strategy Changelog]]. An empty trade set or infeasible EUR 50 sizing is a valid finding, not a reason to relax controls invisibly.
