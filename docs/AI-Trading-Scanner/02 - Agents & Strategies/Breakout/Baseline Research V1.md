# Breakout / Volatility — Baseline Research V1

Status: implemented Phase 4 research contract; EXPERIMENTAL, uncalibrated and not validated.

Agent C uses the same common five-minute bars and indicator family as every participant. It forms a causal reference high from 20 completed bars, then requires two completed closes above that level plus latest volume of at least 1.2 times the reference-window average. One close above a local high is therefore insufficient.

A qualifying proposal references the completed-bar close, uses the reference high minus 0.25 ATR as invalidation and records a non-mandatory breakout-continuation objective. The 2 ATR expected-move value is an economic evaluation assumption, not a universal take-profit. Future management triggers are protective stop, breakout failure, range re-entry and trailing protection. All parameters are `BASELINE_RESEARCH_V1` research defaults requiring empirical calibration.

See [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]], [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]] and [[01 - Architecture/Risk Engine]].
