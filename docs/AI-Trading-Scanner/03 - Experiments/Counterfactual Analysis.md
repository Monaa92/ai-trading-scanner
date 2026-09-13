# Rejected opportunities and counterfactual analysis

Keep **ACTUAL_PATH** performance separate from **COUNTERFACTUAL** performance. ACTUAL_PATH means the recorded realized path of a specific execution environment: SIMULATION fills, PAPER broker-simulated fills, or future LIVE fills. HISTORICAL_REPLAY is a data/run mode and never relabels simulation as real-money performance. Shadow/counterfactual observations have no broker submission. A COUNTERFACTUAL run has an isolated synthetic ledger with no broker permission and cannot post events to an actual participant allocation.

For every candidate, retain all strategy/AI/risk/safety/approval outcomes, even if rejected or no order follows. A hypothetical replay references original candidate/proposal hash, decision and available inputs, rejection gate/reason, intervention definition (e.g. remove only AI veto), frozen hypothetical policy/config, evaluation horizon, data/execution/cost versions and parent run. Do not fabricate a feasible quantity for a risk-blocked setup; without defensible proposal terms record not evaluable or an explicitly separate changed-constraint diagnostic, never a valid missed trade.

## Two analysis units

1. **Single rejected opportunity:** replay the predefined hypothetical entry/exit under causal latency, costs, protection and ambiguity assumptions. It diagnoses what one frozen alternative might have done; isolated opportunities can overlap and their profits cannot be summed into attainable portfolio performance.
2. **Full alternative policy path:** fork a synthetic account snapshot at a declared point and replay the baseline over the common remaining stream with its own subsequent positions, risk, capital and locks. This answers what the baseline policy would have done subject to capital competition. It is still a model, not an actual fill history.

Only change the registered intervention. Removing AI rejection does not remove risk/safety or give earlier data. A manual-rejection counterfactual needs a declared approval/latency assumption. Future observations are allowed only in offline outcome scoring, never copied into the historical decision snapshot or an online agent's inputs. Revisions and reanalysis create new run IDs; negative/no-fill/ambiguous outcomes remain.

Dashboard always labels shadow/hypothetical values, shows model assumptions and limits, and cannot include them in actual equity, win counts, daily loss headroom, survival or leaderboard defaults. Research reporting has read access across paths; agent services do not. Unique keys and foreign-key scope include performance_kind and run, and the actual ledger rejects counterfactual sources.

Limitations: no observed broker fill/queue priority, uncertain intra-bar order, alternative execution can alter later choices/capital, omitted intervention costs/latency, multiple testing of rejected candidates and historical model leakage. “AI vetoed a later winner” does not prove AI worsened expected performance. Use preregistered aggregate paired evaluation and all vetoes, not anecdotal winners. See [[02 - Agents & Strategies/Model Benchmarking]] and [[08 - Research/Research Integrity]].
