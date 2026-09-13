# Experiment 1 strategy profiles

Status: **PLANNED hypotheses; parameters and implementations are NOT IMPLEMENTED or validated**. These profiles extend [[02 - Agents & Strategies/Strategy Overview]] without replacing the registered V1 trend-pullback baseline.

Experiment 1 compares strategy quality under information parity. Four stable participant identities receive the same immutable US-equity universe, normalized snapshot hash/timestamps, news/information availability, starting-capital profile, hard risk policy, transaction costs and execution assumptions. They may reach different decisions. No strategy is bound to an AI provider or model; `strategy_profile_id` and `model_config_id` are independent manifest fields.

| Agent | Strategy profile | Qualifying thesis and exit responsibility |
| --- | --- | --- |
| A | Momentum / Trend Following | Established directional movement supported by trend, momentum, volume, moving-average structure and persistence. Trade only when expected remaining net edge after costs qualifies. Let valid trends continue; exit on versioned trend invalidation, trailing protection, momentum deterioration or structural change rather than a universal profit cap. |
| B | Mean Reversion | Temporary price dislocation relative to a causal reference, using deviation, volatility, volume and available news/fundamental context. Distinguish temporary overreaction from changed fundamentals. Exit when the registered reversion completes, deviation disappears, thesis fails or net risk/reward changes. |
| C | Breakout / Volatility | Consolidation, support/resistance, compression/expansion, unusual volume and confirmed continuation. Reject weak breakouts after costs. Permit continuation while valid; exit on breakout failure, return to range, deterioration or versioned trailing protection. |
| D | Multi-Factor / Opportunistic | A registered combination of the same available trend, momentum, price, volume, volatility, fundamental, news, sentiment, regime, risk/reward and cost features. Broad decision scope grants no extra raw information, capital or risk authority. Holds, changes and exits require auditable factor reasons. |

Every scheduled evaluation returns a typed `AgentDecision`: TRADE_PROPOSAL or NO_TRADE. NO_TRADE requires a structured primary reason such as INSUFFICIENT_SIGNAL, EXCESSIVE_RISK, INSUFFICIENT_NET_EDGE, COST_TOO_HIGH, CONFLICTING_INDICATORS, UNFAVORABLE_REGIME or PORTFOLIO_CAPACITY_UNAVAILABLE, plus relevant rule results. There is no minimum trade quota and trade count is not a reward.

Transaction costs are part of the strategy decision. Each proposal references a versioned round-trip estimate covering entry/exit commission, spread, exchange/regulatory fees, slippage and applicable FX. Positive gross expectation is insufficient when expected net edge is below the registered threshold. Risk and final safety remain authoritative after a strategy proposes.

Model-comparison experiments hold strategy/data/rules fixed while varying `model_config_id`. Strategy-comparison experiments hold the model policy/data/rules fixed while varying `strategy_profile_id`. A run varying both is factorial or confounded and must be labeled accordingly.
