# V1 trend pullback

Status: implemented research baseline `BASELINE_RESEARCH_V1` / `0.1.0` on the Phase 4 review branch; EXPERIMENTAL and not validated. The registered implementation uses p=5, b=0.25 ATR, k=20, one completed-bar confirmation, RSI 50–80, minimum expected net return 0.001 and maximum input age 60 seconds. These are development defaults requiring empirical calibration, not optimized settings. See [[02 - Agents & Strategies/Shared Agent Rules/Indicators]] and [[01 - Architecture/Portfolio Accounting/Position Sizing]].

## A. Mandatory deterministic strategy conditions

Safety eligibility first requires valid available inputs, allowed instrument/direction/session and readiness. These are engineering gates independent of strategy performance.

The initial **hypothesis** rule template, evaluated only at trigger bar t completion, is:

1. C_t > session VWAP_t and EMA9_t > EMA20_t > EMA50_t.
2. In the previous p complete bars, at least one bar j has L_j ≤ EMA20_j and C_j ≥ EMA50_j. All compared values were available at that bar; `p` is required research configuration.
3. Trigger recovery: C_t > EMA9_t and C_t > H_(t−1). Strict inequalities make equality fail; no intrabar trigger evaluation.
4. Proposed stop S=min(L over bars t−p through t)−b·ATR_t, with nonnegative buffer b required; tick normalization and risk checks follow. This is causal, includes the trigger, and requires ATR readiness.
5. Entry reference P is the latest eligible ask at decision time, or an explicitly modeled bar-data proxy in historical research. Target T is the lowest previously established resistance strictly above P from the configured rolling lookback k; absent a qualifying level, reject. Resistance uses bars ending before t. Do not invent a target solely to make RR pass.

These choices define a testable template, not a claim that this setup works. Changing pullback definition, entry type, stop/target source or ordering changes strategy version. Initially fixed exits: stop, target or scheduled end-of-day exit; no trailing/breakeven adjustments or pyramiding. Proposed levels are immutable within the intent except risk-reducing exit handling; never widen a stop to accommodate an adverse fill.

## B. Candidate scoring features

Record normalized distance to VWAP/EMAs, EMA slopes, depth/duration of pullback, RSI14, ATR/P, RVOL, volume, available resistance distance, time in session and optional completed market-context features. Missing optional features are explicitly null. V1 deterministic selection uses descending proposed net RR, then instrument ID, then signal ID; evaluation occurs over the frozen eligible batch. No unspecified weighted score. A scoring formula/weight change is a material strategy change. AI ranking is a separate treatment.

## C. Research parameters and ablations

Phase 4 registers p=5, ATR period 14, b=0.25 and k=20 so the contract is executable. Entry is the completed trigger-bar close and the externally supplied cost estimate is a normalized research input; neither is a broker quote or fill model. RVOL and multi-timeframe filters remain disabled. Development searches must be small, recorded and separated from validation/holdout. Testing continuous EMA state is a separate hypothesis, motivated in advance by the late-session warm-up constraint.

## D. Rejections

Record every failed predicate and input version: not ready, data gap, stale context, invalid instrument/session, trend failed, no pullback, no trigger, invalid levels, no resistance, unsupported capability, expired, duplicate observation or lost selection. Strategy rejection cannot be reversed by AI. No signal is regenerated on each quote tick from the same trigger bar; key is agent/allocation/participant-run + strategy version + instrument + trigger interval + direction. Data revisions append evaluation records and may invalidate unsubmitted signals; no duplicate executing entry is permitted across proposal versions. This routing-scope extension preserves the single-agent trading predicates.

## E. Risk separation

Strategy-valid does not imply tradable. Risk separately enforces P>S>0, T>P, net modeled RR≥2.0, sizing, cost/FX/freshness, capital and daily limits. One selected candidate is assessed/reserved atomically. When the slot is occupied, other candidates remain observed and expire; no queue of stale trades. Risk rejection does not search through parameter alternatives to force acceptance. See [[02 - Agents & Strategies/Shared Agent Rules/Signal Lifecycle]] and [[01 - Architecture/Risk Engine]].
