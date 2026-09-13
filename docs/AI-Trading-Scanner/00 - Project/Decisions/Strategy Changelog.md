# Strategy changelog

Append-only research history. See [[02 - Agents & Strategies/Strategy Versioning]] and [[03 - Experiments/Experiment Framework]]. No backtester exists and no strategy evaluation has been performed.

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
