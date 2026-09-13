# Phase 3 independent review

Status: **INDEPENDENT COMPETENT HUMAN REVIEW REQUIRED; no approval is recorded.** Review the commit on `review/phase-3-indicators`. Do not merge until all critical findings are resolved and the exact reviewed commit is approved.

| Area | Implementation | Behavioral evidence | Intended invariant | Failure impact |
| --- | --- | --- | --- | --- |
| Causal input boundary | `market_data/dataset.py`, `indicators/calculators.py` | `test_indicator_causality.py` | Only bars with `available_at <= as_of` and warnings whose visibility deadline passed can affect output. | Look-ahead and invalid research results. |
| Numeric determinism | `indicators/calculators.py` | configuration/cross-cutting tests | 34-digit Decimal half-even arithmetic is isolated from process-global precision; no floats. | Platform/run drift and changed predicates. |
| EMA | `EMACalculator` | `test_ema_indicator.py` | α=2/(n+1), nth-close SMA seed, session/gap reset, period 1 defined. | Trend features differ silently. |
| RSI | `RSICalculator` | `test_rsi_indicator.py` | First value after n differences; Wilder smoothing; 100/0/50 zero-loss/gain/flat conventions. | Momentum filters shift or divide by zero. |
| ATR | `ATRCalculator` | `test_atr_indicator.py` | Session-first TR=H−L; later TR includes previous close; Wilder seed/recurrence; V1 excludes overnight gap by ADR-016. | Stops/sizing could use understated or inconsistent volatility later. |
| Session VWAP | `VWAPCalculator` | `test_vwap_indicator.py` | Typical-price volume weighting, zero volume unavailable, session reset, incomplete prefix never labeled VWAP. | Cross-session contamination or fabricated price. |
| Gap semantics | all calculators | per-indicator and causality tests | No interpolation; EMA/RSI/ATR restart and rewarm; VWAP remains unavailable until next complete session. | Missing data becomes hidden synthetic continuity. |
| Session/calendar boundaries | calculators plus Phase 2 calendar | ATR/EMA/RSI/VWAP tests | V1 state resets by canonical session ID across normal, early-close, weekend, holiday and DST boundaries. | State contamination or false resets. |
| Prefix invariance | batch functions | parameterized multi-prefix tests | Extending a slice cannot change points already emitted for any indicator. | Future dependence/look-ahead. |
| Batch/incremental equivalence | calculators and batch fold | each indicator test file | Caller-owned sequential state and batch results are identical. | Replay/live divergence. |
| Input quality | `CanonicalDataset`, `CausalBarReader`, calculator validation | Phase 2 regressions and causality tests | Fatal findings reject; visible warnings survive into output; modeled warning visibility respects delay. | Invalid data passes or warnings leak/vanish. |
| Configuration/output lineage | `indicators/models.py` | `test_indicator_config.py` | Strict immutable semantics and content ID; each point binds bar time/config and series binds dataset/slice. | Unreproducible feature values. |
| Health boundary | `indicators/fixtures.py`, `health.py` | `test_health.py` | Four-formula fixture remains offline, fast, credential-free and broker-free. | Startup claims readiness without deterministic local evidence. |

Reviewer should independently recompute the small fixtures, inspect reset transitions and unavailable reasons, mutate later bars to challenge prefix invariance, and confirm no scanner, strategy, risk, broker, AI or execution authority entered the change. Record reviewer identity, exact commit, approval outcome, PR, merge commit/date if merged, material findings and their resolution. Agent self-review is insufficient.

## Candidate verification

Recorded 2026-09-13 before candidate commit: 219 total tests passed, comprising the established 171 Phase 1–2 regressions and 48 focused Phase 3 cases. Repository-wide Ruff lint/format, strict mypy, lock verification, package build, isolated wheel install, installed and source-tree offline health, secret signatures, whitespace, 32 ADR required-field checks and all 643 links across 103 Obsidian notes passed. The only pytest warning is an upstream Starlette `BlockingPortal` deprecation. No network, provider, broker or credential is required.

No approval, PR or merge is asserted by this note.
