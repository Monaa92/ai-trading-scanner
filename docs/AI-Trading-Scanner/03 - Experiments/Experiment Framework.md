# Experiment design and promotion

Status: required future process, no experiments run. Start with a deterministic baseline, no AI, fixed capital/risk model, and cash/no-trade control. Treat EUR 50 execution infeasibility as a research outcome.

## Registration and splits

Before evaluation register hypothesis, rationale, candidate/accepted predecessor, exact parameter/rule diff, directional expected effect, primary endpoint (net expectancy plus portfolio net return), risk guardrails, minimum economically meaningful effect, universe/date range, exclusions, trial budget/family, planned metrics/uncertainty, execution/cost scenarios and stopping rule. Record who registered it and timestamp. Blank values block confirmatory evaluation; numbers must come from research/power planning and owner risk tolerance, not observing the holdout.

Choose chronological **development**, **validation** and **final holdout** date ranges once data coverage is audited. Do not invent dates or percentages now. Use rolling/expanding walk-forward folds within development and validation: fit/select only on earlier training windows, evaluate on the immediately later window, aggregate without choosing only good folds. Record whether windows overlap; do not count duplicated observations twice. Purge trades/labels crossing boundaries and use an embargo derived from maximum outcome horizon; indicators may warm up on prior observable data, with trading disabled during warm-up. Never fit transforms on validation/holdout.

Final holdout has an access log and a sealed manifest. It is used once for a frozen candidate, metrics and decision rules. After inspection, changes motivated by it are exploratory; use newly accrued future data for a new confirmatory test. An engine defect invalidates the result but does not erase exposure to outcomes; record access and treat any rerun on it as a disclosed diagnostic, not fresh proof. No repeated peeking or early stopping because results look favorable.

## Comparable evidence

Once a functioning backtester exists, every material strategy change must rerun the previous accepted version and the candidate with identical dataset, evaluation period/universe, starting capital, risk, FX, costs, execution model and seeds. Before the first acceptance, the initial registered baseline is the comparator and its absence of acceptance is explicit. Table must include N, win rate, average win/loss, expectancy, profit factor, max drawdown and net result after modeled costs, plus period and manifest IDs.

If data/engine/fees change, rerun **both** on the new common assumptions and separately explain the infrastructure change. Comparing old baseline data with new candidate data is invalid. Risk changes cannot be credited as strategy alpha; isolate them in a factorial or separate paired comparison. Freeze metric definitions and treatment of unresolved/open trades.

## Uncertainty and multiple testing

Use paired day-level portfolio return differences for comparisons and day/block bootstrap intervals preserving within-day symbol/trade dependence. Effective sample size is not raw trade count; regime clustering and autocorrelation matter. Seed and version bootstrap/block choices. Trades from the same event/day cannot be treated as independent evidence just because symbols differ.

Register families of related strategy/prompt hypotheses and report adjusted confirmatory significance (Holm family-wise correction when valid p-values are used). Exploratory searches disclose every trial and require fresh out-of-sample confirmation; a correction cannot rescue an unknown number of hidden trials. Predefine effect-size and power assumptions from development variability, clustered sampling and realistic costs. If coverage/power is insufficient, report inconclusive rather than relax thresholds. No universal minimum trade count establishes an edge.

## Acceptance decision

Decision is ACCEPTED, REJECTED or EXPERIMENTAL. To accept for the next research/paper stage, require reproducible complete artifacts; valid causality/data quality; no unresolved critical tests; comparison against predecessor; prespecified effect/uncertainty and risk guardrails met across required folds/stress costs; reasonable parameter sensitivity and no unexplained concentration. Positive in-sample P&L alone never qualifies. A new version may be accepted for correctness even with lower returns, but the record must state the objective and cannot claim performance improved. No finite dataset guarantees future performance.

Define regime labels before scoring from causal trailing market volatility/trend measures with boundaries fit only on development data. Use a few interpretable fixed categories; do not search many regime definitions to eliminate bad periods. Report all predefined cells, counts, confidence and unsupported cells. Stability across symbols is descriptive for the convenience universe, not proof of broad transfer.

Record all artifacts in [[01 - Architecture/Data Model]], every decision in [[00 - Project/Decisions/Strategy Changelog]], and failures in [[03 - Experiments/Results/Failed Experiments]]. [[06 - Testing/Live Readiness]] is a separate and stronger gate than research acceptance.

## Participant experiments and normal operation

[[03 - Experiments/Autonomous Experiments]] registers four independent EUR50 participant ledgers. [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]] names the four unvalidated hypotheses; exact parameters and model assignments still require preregistration. Freeze all strategy/risk/AI/management/execution-dimension/funding artifacts and adaptive algorithms. Equivalent data access and independent reservations are required; common-market participants are correlated, not independent statistical replications. Predefine comparison families, survival endpoints and administrative intervention treatment. Preserve failed/inactive participants and original outcomes.

NORMAL changes are attributed/versioned configuration segments and capital flows, not the same frozen experiment. Compare like-for-like segments using [[09 - Performance/Agent Statistics]]. [[03 - Experiments/Counterfactual Analysis]] is diagnostic and separately named; hypothetical wins never add to participant equity. Dynamic exits need their own comparison/ablation rather than attributing a multi-factor change entirely to AI.
