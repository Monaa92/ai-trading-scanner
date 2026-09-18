# Survival and capital preservation

Specification, not evidence that an agent survives. No composite survival score is proposed. Present separate capital, time, drawdown, activity and intervention measures. [[03 - Experiments/Autonomous Experiments]] owns frozen starting conditions/endpoints; [[02 - Agents & Strategies/Shared Agent Rules/Agent Lifecycle]] owns operational states. The future [[02 - Agents & Strategies/Autonomous Survival Agent]] uses these measurements plus a separate preregistered active-survival protocol; that protocol does not replace the ordinary metrics here.

## Endpoint and observation contract

Register time origin, common valuation schedule, horizon, failure predicate and cause before start. Financial ruin (e.g. equity reaches a defined floor), configured drawdown termination, persistent broker-minimum infeasibility, autonomy-ending human intervention and infrastructure/protocol failure are distinct endpoints. No final floor, warning percentage or inactivity duration is selected now. Missing marks cannot be counted as known safe capital. The four-agent study reports each trajectory and observed outcome, not a population probability from four correlated strategies.

For no-flow experiments let E0>0 be initial marked equity, E(t) observed equity, H(t)=max_(s≤t)E(s), K(t)=min_(s≤t)E(s), and DD(t)=1−E(t)/H(t). All include accrued modeled costs/FX under a pinned accounting policy. Use marked equity, not just closed-trade profits. Administrative horizon endings without failure are right-censored observations: survival beyond the last observation is unknown, not infinite. See [NIST on censoring](https://www.itl.nist.gov/div898/handbook/apr/section1/apr131.htm). Outage/intervention censoring may be informative; report it separately and perform registered sensitivity, not automatic favorable exclusion.

| Metric | Definition / limitation |
| --- | --- |
| Starting/current/ending equity | E0, latest valid E(t), E at terminal/horizon; provisional stale marks visibly flagged |
| Peak/trough/minimum equity | H(t), K(t); trough and minimum are aliases, not different evidence |
| Trading days survived | Number of fully observed eligible exchange sessions completed before defined failure or censoring; separately report fractional final-session elapsed time and cause |
| Calendar days survived | Elapsed UTC seconds/86400 from start to event/last observation; weekends do not provide extra trading evidence |
| Trades survived | Closed position episodes before endpoint, with open/entry counts separately; splitting fills does not extend survival |
| Maximum drawdown/duration | Worst DD and peak-to-recovery duration from common marked schedule; ongoing duration censored |
| Recovery duration | For each drawdown episode, trough-to-first return to the prior peak; also retain peak-to-recovery total. Trough is descriptive hindsight, never a strategy input. Unrecovered episode censored |
| Time to threshold | First observed DD≥registered threshold, with event/interval precision; never inferred exact from sparse marks |
| Time to lockout / lockouts | First lock transition minus start; distinct latched episodes by reason/scope, not each repeated warning poll |
| Capital-preservation ratio | E(t)/E0 and minimum ratio K(t)/E0 for no-flow cohorts, including costs. Ratio 1 from inactivity alone is not successful trading |
| Day outcomes | Positive/negative/zero net equity-P&L sessions, with no-entry/activity tags separately; a no-trade day can lose fees or FX value |
| Expectancy per trade | Net closed-trade mean with N/uncertainty per [[09 - Performance/Performance Metrics]] |
| Expectancy per trading day | Total daily net equity P&L / all observed eligible sessions, including zero-trade days; show incomplete sessions and pre/post-termination coverage |
| Survival/equity curves | Per-agent observed E(t), normalized E/E0 and endpoint markers; an individual alive/dead step line is not an estimated population survival probability |

Keep failure dates and retained final capital on the common leaderboard timeline; never count post-failure days as survived. For economic comparisons, pre-register either frozen terminal proceeds or cash-only post-termination accrual over the common horizon and label it, separately from active survival. Do not compare winners' full horizons to losers' truncated active periods without disclosure. Lockout can preserve capital while reducing activity; report both.

## Probabilities and uncertainty

Risk-of-ruin probability requires a precise ruin event/horizon, enough defensible repeat observations or a validated generative model, dependency assumptions, uncertainty and model sensitivity. Four correlated concurrent paths cannot identify that probability. Do not use a simple independent win/loss gambler's-ruin formula for stateful sizing, fees, correlated days, changing regimes and lockouts.

Later, a registered repeated-run cohort with defensible censoring could estimate `S_hat(t)=product_(t_j≤t)(1−d_j/n_j)` with risk-set sizes and intervals. [NIST's Kaplan–Meier description](https://itl.nist.gov/div898/handbook/apr/section2/apr215.htm) supports estimation from censored observations; suitability for these dependent trading runs still requires separate justification. Different strategies are not interchangeable replicates. Simulation/bootstrap ruin estimates must be labeled model-conditional, preserve regime/day dependence and cannot be presented as observed live probabilities. If support is inadequate, display NOT_ESTIMABLE and the reason.

Normal-account deposits/withdrawals invalidate raw E/E0 as a preservation measure; display net flows, segmented/time-weighted returns and allocation history instead. Never rank a topped-up agent as surviving fixed-capital failure. Thresholds and analysis plans remain OPEN until preregistered using development evidence.

For Agent 5, economic `DEAD` and protocol `INACTIVE_FAILURE` are distinct. Death uses conservative net liquidation value and registered execution viability, includes positions/costs/FX/liabilities and is irreversible. Inactivity ends active-survival participation without pretending capital vanished. Sub-agent creation does not add independent survival paths; descendants share one economic entity and one death event. Finite-horizon ALIVE observations remain censored, not infinite survival.
