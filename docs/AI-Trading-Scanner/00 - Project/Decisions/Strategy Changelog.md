# Strategy changelog

Append-only research history. See [[02 - Agents & Strategies/Strategy Versioning]] and [[03 - Experiments/Experiment Framework]]. No backtester exists and no market experiment or performance evaluation has been performed; Phase 4 synthetic contract fixtures are behavioral tests only.

## 2026-09-14 — four-profile BASELINE_RESEARCH_V1 implementation

| Field | Record |
| --- | --- |
| Hypothesis | Four deterministic strategy families can produce auditable, causally invariant proposal/non-trade contracts from equal information; profitability remains untested |
| Exact change | Registered explicit Momentum, Mean Reversion, Breakout and Multi-Factor configurations and pure evaluators; added structured NO_TRADE, management mandate, expected-economics and approval-sensitive proposal identity contracts |
| Previous version/configuration | Agent A `v0.1.0` specification with unset parameters; Agents B–D profile descriptions only; no accepted predecessor |
| New configuration | `BASELINE_RESEARCH_V1` / `0.1.0`; exact parameters in [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]] and content-derived configuration IDs at runtime |
| Evaluation period / dataset version | NOT RUN / no market dataset; deterministic synthetic branch fixtures only |
| Execution/cost/risk model | Externally supplied test-only normalized round-trip estimate; no broker cost engine, Risk Engine or execution model |
| Previous / new metrics / delta | Unavailable / unavailable / not applicable |
| Result / decision | Contract behavior independently reviewed, APPROVED/PASS and merged; EXPERIMENTAL research baseline only |
| Relevant commit / PR | Candidate `2a52ffdfa4cd0bd9379adb92996fc9764ffaed63`; reviewed by `Dekkerszz`; PR #3 merged/closed at `60d83842f6bb686f2a407db82781d28ff534b355`; remote review branch deleted |
| Notes | Defaults are uncalibrated, not optimized against fixtures and do not authorize trading |

## 2026-09-13 — v0.1.0 specification baseline

| Field | Record |
| --- | --- |
| Hypothesis | Long intraday trend pullbacks may identify useful setups after realistic costs; untested |
| Exact change | Initial completed-5-minute VWAP/EMA trend, pullback/recovery template, causal stop/resistance target and session-reset indicator definitions documented |
| Previous version/configuration | None; no accepted predecessor |
| New configuration | [[02 - Agents & Strategies/Momentum/V1 Trend Pullback]]; required research values unset, not an executable parameter set |
| Evaluation period / dataset version | NOT RUN / none |
| Execution/cost model | [[06 - Testing/Backtesting]] design only; no calibrated model |
| Previous / new metrics / delta | Unavailable / unavailable / not applicable |
| Result / decision | Untested specification / EXPERIMENTAL |
| Relevant commit / PR | None for this change; no commit or PR created |
| Notes | Architecture acceptance does not validate strategy or authorize trading |

## Required future entry

For every material change append date, new and predecessor versions, hypothesis, exact rule diff, previous/new complete config IDs, evaluation period/dataset hash, common execution/cost/risk models, comparison run IDs, before/after/delta table, result, ACCEPTED/REJECTED/EXPERIMENTAL and rationale, reviewer, existing commit/PR references and limitations. Required metric rows: trade count, win rate, average win/loss, expectancy, profit factor, max drawdown and net after modeled costs. Missing comparative evidence means no improvement claim and no evidential promotion.

## 2026-09-13 — multi-agent specification extension

Architecture adds participant-scoped versions, proposal/approval/safety routing, frozen experiments, isolated actual/counterfactual histories and management-policy version references. Initial V1 rules/thresholds and fixed stop/target remain v0.1.0 EXPERIMENTAL; no new strategy assignment or dynamic policy was selected/activated. Before/after performance, dataset and period: NOT RUN. No accepted predecessor or quantitative improvement claim. Commit/PR: none. Future dynamic/agent strategy changes still require material versioning and comparative evidence.
