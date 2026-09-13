# AI versus non-AI evaluation

Question: does AI filtering/ranking add measurable value after cost, latency and uncertainty? Baseline OFF and treatment FILTER share the exact deterministic strategy, candidate feed, feature availability, risk ceiling, universe, data, initial capital and execution/cost models. Only the registered AI selection policy and its actual cost/delay differ.

Freeze strategy, prompt/model/schema, generation configuration, acceptance criteria and evaluation dates before evaluation. Prompt variants and model trials belong to the same documented hypothesis family; selecting a winning prompt on validation consumes that validation budget. Do not tune on final holdout. Historical model training may contain knowledge of the test period; anonymizing identifiers is a mitigation, not proof of isolation. Historical AI tests are exploratory unless contamination can be ruled out; frozen prospective shadow/paper comparison is required for promotion.

## Two complementary comparisons

1. **Candidate-level diagnostic:** store the common pre-AI strategy-valid candidate stream, AI decisions, reasons, failures and latency. Measure selectivity and hypothetical outcome distribution without claiming all candidates could fit the account.
2. **Portfolio-level primary comparison:** two isolated virtual EUR50 accounts receive the same causal stream and independent deterministic reservations/limits. Each trades according to its own eligible selections, so subsequent capital and trade opportunities can differ. Compare full day-level net equity returns, not only the intersection of filled trades. Do not route two arms through one shared position slot.

AI arm execution cannot occur until its response validates; baseline may act earlier. A secondary matched-latency baseline can isolate selection quality, but the primary economic test includes actual AI latency and fees. All failures and no-trade days remain in the assigned treatment (intention-to-treat). Use common pre-indexed random draws by event ID for stochastic execution so filtering does not shift the random stream and create an artificial advantage. Store seeds and response artifacts; replay recorded outputs for exact historical audit.

Report net expectancy, profit factor, drawdown, net return, trade/candidate counts, rejection/failure rates, selectivity, exposure, AI cost, latency distribution and stability across prespecified symbols/regimes. Report after trading costs and after incremental AI costs, plus common operating costs separately. Use paired day/block uncertainty and registered effect size/testing rules from [[03 - Experiments/Experiment Framework]]. More selective trades or a higher win rate with lower total net result is not automatically an improvement.

Broker paper A/B must isolate account ledgers/capital and disclose that external simulated fills may differ. Shadow paired observations avoid changing broker state while validating decision consistency. Unavailable model snapshots or changed provider backends limit reproducibility and can block acceptance. See [[01 - Architecture/AI Architecture]].

## Four-agent and rejected-opportunity extension

Use agent/participant-scoped ledgers and frozen config per [[03 - Experiments/Autonomous Experiments]]. Suggested A/B/C/D roles are illustrative, not assigned/validated strategies. Baseline vs AI filter isolates a factor; AI+dynamic management changes another and needs a separate B/C comparison. All arms receive equivalent input availability but actual processing latency/cost remains part of the outcome. Four same-market paths do not establish independent replication or reliable ruin probabilities.

[[03 - Experiments/Counterfactual Analysis]] defines veto diagnostics and full alternative-policy replays. They never affect actual-path equity/rankings. [[03 - Experiments/Survival Analysis]] adds preregistered preservation and autonomy endpoints, including intervention and censoring limits.
