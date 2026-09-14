# Experiment 1 strategy profiles

Status: **IMPLEMENTED RESEARCH BASELINES ON `main`; NOT VALIDATED**. These profiles extend [[02 - Agents & Strategies/Strategy Overview]]. Agent A preserves the registered V1 trend-pullback semantics; all four use explicit `BASELINE_RESEARCH_V1` configuration version `0.1.0` and require empirical calibration.

Experiment 1 compares strategy quality under information parity. Four stable participant identities receive the same immutable US-equity universe, normalized snapshot hash/timestamps, news/information availability, starting-capital profile, hard risk policy, transaction costs and execution assumptions. They may reach different decisions. No strategy is bound to an AI provider or model; `strategy_profile_id` and `model_config_id` are independent manifest fields.

| Agent | Strategy profile | Qualifying thesis and exit responsibility |
| --- | --- | --- |
| A | Momentum / Trend Following | Established directional movement supported by trend, momentum, volume, moving-average structure and persistence. Trade only when expected remaining net edge after costs qualifies. Let valid trends continue; exit on versioned trend invalidation, trailing protection, momentum deterioration or structural change rather than a universal profit cap. |
| B | Mean Reversion | Temporary price dislocation relative to a causal reference, using deviation, volatility, volume and available news/fundamental context. Distinguish temporary overreaction from changed fundamentals. Exit when the registered reversion completes, deviation disappears, thesis fails or net risk/reward changes. |
| C | Breakout / Volatility | Consolidation, support/resistance, compression/expansion, unusual volume and confirmed continuation. Reject weak breakouts after costs. Permit continuation while valid; exit on breakout failure, return to range, deterioration or versioned trailing protection. |
| D | Multi-Factor / Opportunistic | A registered combination of the same available trend, momentum, price, volume, volatility, fundamental, news, sentiment, regime, risk/reward and cost features. Broad decision scope grants no extra raw information, capital or risk authority. Holds, changes and exits require auditable factor reasons. |

Every evaluation returns exactly one immutable typed `StrategyDecision`: `TRADE_PROPOSAL` or `NO_TRADE`. `NO_TRADE` uses structured strategy-level codes for insufficient signal/confirmation, conflicting factors, unsuitable regime, visible quality or incomplete-session concerns, unready indicators, inadequate edge/costs, invalidated thesis, unsupported context or unauthorized direction. Central risk, approval and broker rejections are deliberately absent from this taxonomy. There is no minimum trade quota and trade count is not a reward.

Transaction costs are part of the strategy decision. Each proposal references a versioned round-trip estimate covering entry/exit commission, spread, exchange/regulatory fees, slippage and applicable FX. Positive gross expectation is insufficient when expected net edge is below the registered threshold. Risk and final safety remain authoritative after a strategy proposes.

Model-comparison experiments hold strategy/data/rules fixed while varying `model_config_id`. Strategy-comparison experiments hold the model policy/data/rules fixed while varying `strategy_profile_id`. A run varying both is factorial or confounded and must be labeled accordingly.

## Registered Phase 4 research defaults

All profiles use completed 5-minute XNYS bars, EMA 9/20/50, RSI 14, ATR 14, session VWAP, a 60-second maximum input age, a two-primary-interval strategy candidate lifetime and minimum expected net return of 0.001. These are deterministic development parameters, not optimized or profitable settings.

| Profile | Additional `BASELINE_RESEARCH_V1` parameters |
| --- | --- |
| Momentum | pullback lookback 5; resistance lookback 20; one-bar trigger confirmation; 0.25 ATR stop buffer; RSI range 50–80 |
| Mean Reversion | deviation at least 1.5 ATR from VWAP; RSI at most 30; one-bar recovery confirmation; 1 ATR stop buffer |
| Breakout | 20-bar reference range; two closes beyond the range; volume at least 1.2× reference average; 0.25 ATR stop buffer; 2 ATR expected-move assumption |
| Multi-Factor | explicit trend/momentum/VWAP/volatility weights 0.30/0.25/0.20/0.25; momentum RSI band 50–80; minimum score 0.60; ATR/price at most 0.05; 1 ATR stop; 2 ATR expected-move assumption |

The common `StrategyEvaluationContext` supplies the same canonical market-data slice and the same six-series indicator family to every profile. No external information exists in Phase 4. A supplied versioned round-trip return-drag estimate is required before a proposal; it is a contract input, not a fee engine or broker quote. See [[04 - Costs & Economics/Transaction Costs]] and [[06 - Testing/Phase 4 Completion Criteria]].
