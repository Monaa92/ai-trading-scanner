# Deterministic indicator specification

Status: **IMPLEMENTED AND MERGED TO `main`; INDEPENDENT REVIEW COMPLETE.** The implementation is in `src/ai_trading_scanner/indicators`. It consumes only immutable `MarketDataSlice` inputs, emits one typed point per input bar, and carries dataset/slice/configuration lineage plus visible Phase 2 quality findings. Review evidence is recorded in [[06 - Testing/Phase 3 Independent Review]].

All formulas below are implementation contracts, not evidence of predictive value. Input is ordered, validated, completed RTH bars of one instrument, feed and price basis. Output carries implementation/parameter version, dataset and slice hashes, latest `available_at`, value and `ready/reason`. Missing values are `null` with typed reasons, never JSON NaN or zero substitution. V1 uses a local 34-significant-digit `Decimal` context with round-half-even for authoritative indicator arithmetic; it does not depend on the process-global Decimal context or binary floating point.

EMA requires a positive integer period. RSI and ATR additionally require the explicit `WILDER` smoothing value. VWAP requires `TYPICAL_PRICE` and `SESSION` reset values. Configurations are frozen, reject unknown fields/coercion, serialize through Pydantic and have a canonical SHA-256 `IndicatorConfigurationId`.

## V1 initialization and gaps

To avoid unspecified overnight initialization, V1 EMA, RSI and ATR reset each session. This is a deliberate research definition, not a universal indicator convention. VWAP and session extrema also reset. Cross-session smoothing is a future version. No decisions until every mandatory feature is ready; warm-up bars count as consumed data, never performance trades. EMA 50 thus needs at least 50 valid 5-minute bars, which limits V1 to later-session opportunities; this cost is explicit and must not be “fixed” silently after seeing results.

Any missing/invalid required bar invalidates continuity. EMA/RSI/ATR restart from the next contiguous valid segment. VWAP and true session extrema remain unavailable after a session gap until a verified backfill repairs the entire prefix; restarting those mid-session must not be labeled session VWAP/high/low. Repair can affect future snapshots only. Distinguish insufficient history, gap, zero denominator and incompatible adjustment units.

The implementation derives gaps only from discontinuity between sequential observed bars within the same canonical session; it never infers a reset from a weekend, holiday, overnight closure or wall-clock delay. Each new session resets all four calculators under [[00 - Project/Decisions/ADR-016 - Session-reset indicator initialization]]. Consequently V1 ATR deliberately excludes the previous session’s close from the new session’s first true range. A continuous cross-session ATR that includes overnight gaps is a future versioned research alternative, not this accepted baseline.

`CausalBarReader` exposes quality findings only when their causal visibility deadline has passed. A modeled missing interval becomes visible at interval end plus the dataset’s modeled publication delay. Indicator series retain all visible warnings. Fatal slice findings, forged future-visible bars, mixed series, duplicates and out-of-order inputs fail before calculation.

## Formulas

Let bar i have O,H,L,C,V and let n be a positive integer period.

| Feature | Definition and readiness |
| --- | --- |
| Session VWAP | V1 bar proxy: TP_i=(H_i+L_i+C_i)/3; VWAP_t=Σ(TP_i V_i)/ΣV_i over complete session prefix. Ready once total V>0 and prefix valid. Zero-volume bars add neither numerator nor denominator. Label `bar_typical_price_vwap_v1`; not exact trade VWAP. Provider VWAP cannot silently replace it. |
| EMA n | α=2/(n+1); seed at nth valid close with arithmetic mean of first n closes; thereafter E_t=αC_t+(1−α)E_(t−1). First n−1 values unavailable. V1 periods 9,20,50. |
| RSI 14 | Δ=C_t−C_(t−1), gain=max(Δ,0), loss=max(−Δ,0). Seed average gain/loss using first 14 differences (15 closes); Wilder recurrence A_t=((n−1)A_(t−1)+x_t)/n. RSI=100−100/(1+AG/AL). AL=0, AG>0 →100; AG=0, AL>0 →0; both zero →50 by explicit convention. |
| ATR n | First segment bar TR=H−L; thereafter max(H−L, abs(H−previous C), abs(L−previous C)). Seed mean of first n TR; Wilder smoothing thereafter. Period n is a required research parameter. Overnight gaps are excluded from this session-reset ATR; a separate prior-close gap feature may be recorded. |
| Relative volume | V of current 5-minute session slot divided by mean V of the same slot in the previous N eligible sessions. Exclude current session and sessions without that slot; require N valid observations and positive denominator, otherwise unavailable. N required. Early-close missing slots are not zero volume. Use consistent feed and split-normalized historical units known at decision time. |
| Volume features | Current V, cumulative session V, and V/mean(previous k completed bars' V). Exclude current bar from rolling denominator; k required, positive denominator. These are separate from same-slot RVOL. |
| Intraday extrema | H_session(t)=max H and L_session(t)=min L over valid completed prefix; timestamp each update. For pre-existing resistance/support use extrema through t−1 if the rule demands a level established before the trigger bar. Never today's eventual high/low. |
| Support/resistance candidates | V1 rolling support=min L of previous k bars; resistance=max H of previous k bars, excluding trigger. k required. Previous-session levels require complete prior session and compatible action basis. No visual/manual future level selection. |

Optional confirmed pivots need left/right window lengths: a pivot at i requiring r future bars is only available after bar i+r completes and publishes. Store both pivot_at and confirmed_at; never shift the confirmed value backward. Pivot features are disabled in the initial baseline. Rolling extrema and a pivot must not share an unversioned feature name.

## Resampling and higher timeframes

Aggregate O=first O, H=max H, L=min L, C=last C, V=sum V only from accounted-for contiguous lower bars. Anchor at session open, use half-open intervals and mark truncated session-end buckets. Feature availability is at least max(input availability, bucket end + finalization policy). No partial 15-minute/hourly/daily inputs in V1.

Join higher-timeframe features with a backward as-of join on **available_at**, restricted to the required completed session/bucket; never nearest-neighbor or forward fill across missing required buckets. At 10:05, the 10:00–10:15 bar and 09:30–10:30 hour cannot be read. The 09:45–10:00 bar is usable only if already published. Prior completed daily context can persist across today's decision bars under an explicit age/calendar rule. Session-reset higher-timeframe indicators may be unready for the entire day at long periods; validate feasibility before enabling them.

## Acceptance fixtures

Hand-calculated sequences test seeds, recurrence, constant/rising/falling prices, zero volume, flat RSI, warm-up boundary and gaps. Session fixtures test early close, DST and no overnight accumulation. Prefix-invariance property: changing any data with available_at later than decision_at cannot change that decision's features. Vectorized and incremental outputs must agree within documented absolute/relative tolerances; hashes use canonical stored outputs, not platform-dependent display rounding. See [[06 - Testing/Test Strategy]].

The Phase 3 API supports batch calculation and caller-owned incremental calculators with isolated explicit state. Exact outputs match for all four indicators. No vectorized third-party implementation exists in this phase; “batch” is a deterministic fold over the same incremental transition, which prevents two competing formula paths.
