# Bias prevention

This is an enforcement map, not a disclaimer. Every run must report failures of these controls. See [[03 - Experiments/Experiment Framework]] and [[06 - Testing/Test Strategy]].

| Failure | Concrete prevention and evidence |
| --- | --- |
| Look-ahead | available_at-bounded view; separate execution engine access; prefix-invariance fixtures and input IDs in each decision |
| Data leakage | Fit transformations/scalers/regime boundaries only on training folds; freeze artifacts; purge label-overlap around splits; no outcome fields in strategy/AI schemas |
| Survivorship bias | Permanent instrument IDs, effective membership/listing/delisting history; label current convenience universe; block broad claims if delisted data missing |
| Selection bias | Pre-register universe, date range, exclusions and capital constraints; publish all excluded/failed observations with reasons |
| Overfitting | Small justified search space, chronological validation, walk-forward stability, parameter-neighborhood sensitivity rather than best single point |
| Data snooping | Append-only trial registry including manual/AI-assisted trials and failed variants; separate confirmatory from exploratory results |
| Multiple hypotheses | Register hypothesis families and trial budget; Holm adjustment for confirmatory p-values when used; resampling must preserve day clusters/dependence; report all trials |
| Cherry-picking | Freeze reports covering every fold/symbol/regime and all cost scenarios; retain negative and zero-trade results |
| Unrealistic fills | No decision-bar execution; adverse gaps, latency/capacity/cancellation, stop-first ambiguity and full scenario replays |
| Ignoring spread | Explicit side quotes or versioned proxy; distinguish signal feed from execution feed |
| Ignoring slippage | Adverse fill model and sensitivity grid registered before results; paper fill quality cannot justify zero slippage |
| Ignoring fees | Cash ledger fees, minima, FX conversion and separately reported AI/operating cost; report gross and net |
| Future support/resistance | Rolling levels exclude future bars; pivots available only at confirmation time; freeze level source in signal |
| Multi-timeframe leakage | Complete aggregates and backward join on available_at; test 10:05 against 10:15/10:30 data |
| Repeated holdout tuning | Holdout access log, one frozen candidate/spec per confirmatory release; consumed holdout cannot become “untouched” again |
| Post-hoc parameter changes | New version, explicit diff/hypothesis and another trial; immutable prior run outputs |
| Revised historical data | Snapshot content/vintage and modeled-vs-observed availability; never silently substitute corrected data |
| AI training contamination | Record model/version release date and possible historical knowledge; mask symbols/date when feasible; historical AI uplift exploratory until prospective frozen evaluation |
| Reporting only filled signals | Retain candidate/rejection/fill denominators and opportunity selectivity; separate candidate quality from portfolio outcomes |

Tests detect some bugs, not all biases. A structurally biased dataset remains limited even when code passes every test. If controls fail, diagnose and rerun on the appropriate split under a new run ID; do not alter results in place.
