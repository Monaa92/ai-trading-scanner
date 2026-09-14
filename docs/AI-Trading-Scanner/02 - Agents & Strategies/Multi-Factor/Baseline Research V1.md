# Multi-Factor / Opportunistic — Baseline Research V1

Status: implemented Phase 4 research contract; EXPERIMENTAL, uncalibrated and not validated.

Agent D receives no privileged raw information. It consumes the same canonical bars and EMA 9/20/50, RSI 14, ATR 14 and session VWAP snapshot as Agents A–C. Its transparent factors are trend alignment (weight 0.30), RSI momentum in the configured 50–80 band (0.25), close above VWAP (0.20), and ATR/price at or below 0.05 (0.25). It proposes only at a combined score of at least 0.60 and preserves every named contribution in decision evidence. Mixed evidence remains observable as `CONFLICTING_FACTORS`; there is no opaque or AI-generated score.

A proposal uses a one-ATR invalidation stop and a non-mandatory multi-factor thesis objective. A 2 ATR expected move supports economic screening without creating a universal profit cap. Future management triggers are protective stop, factor deterioration and thesis invalidation. Weights and thresholds are `BASELINE_RESEARCH_V1` research defaults requiring empirical calibration.

See [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]], [[02 - Agents & Strategies/Model Benchmarking]] and [[01 - Architecture/AI Architecture]].
