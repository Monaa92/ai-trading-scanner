# Mean Reversion — Baseline Research V1

Status: implemented Phase 4 research contract; EXPERIMENTAL, uncalibrated and not validated.

Agent B uses only the common completed five-minute bars and EMA 9/20/50, RSI 14, ATR 14 and session VWAP snapshot. It requires price at least 1.5 ATR below session VWAP, RSI at or below 30 and one completed-bar upward recovery. A strict EMA 9 < EMA 20 < EMA 50 downtrend with price below EMA 9 blocks the setup as an unsuitable regime, so an RSI extreme alone never creates a proposal.

A qualifying proposal references the completed-bar close, places the strategy invalidation stop one ATR below the lowest bar in the confirmation window and uses session VWAP as the strategy-specific mandatory reversion objective. Future management triggers are protective stop, mean reached and thesis invalidation. Final quantity and permission belong to future risk/portfolio layers. The 1.5 ATR, RSI 30 and stop parameters are `BASELINE_RESEARCH_V1` defaults requiring empirical calibration.

See [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]], [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]] and [[01 - Architecture/Risk Engine]].
