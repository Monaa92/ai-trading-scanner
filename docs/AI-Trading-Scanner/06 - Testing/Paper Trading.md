# Paper trading and reconciliation

Status: future design, no connection or automation exists. Start only after deterministic backtest/risk/order tests meet their phase gates. [[06 - Testing/Live Readiness]] is separate.

| Data/run + execution environment | Data and execution | What it can establish |
| --- | --- | --- |
| Historical backtest | Frozen past data and versioned simulated execution | Reproducible behavior under assumptions, not actual fills |
| Shadow/live-signal observation | Incoming market observations, hypothetical intents, no order submission | Timing, data quality, signal stability and prospective evidence |
| Broker paper | Incoming data, broker-provided simulated fills | Adapter behavior, reconciliation and operational handling within simulation limits |
| Live | Real orders/capital | Separate future authorization and gate; never enabled by paper mode fallback |

Record every execution dimension in each account/run/event. Never mix PAPER and SIMULATION equity curves as one continuous account, or confuse HISTORICAL_REPLAY with an execution environment.

## EUR50 overlay

Maintain an internal unlevered account initialized with EUR50-equivalent capital using recorded FX and conversion policy. If broker paper balance is larger, it is only an execution sandbox: internal settled cash, reserved cash, risk and entry limits remain authoritative. Prefer a dedicated account with equivalent capital when verified feasible. Do not reset a losing experiment or silently top up the overlay; a reset creates a new registered run with old results retained.

Broker paper systems have limitations versus live, including possible differences in impact, queue position and costs. Measure discrepancies rather than assuming paper is conservative. See [[08 - Research/External References]]. No exact fractional order/protection capability, fees, account eligibility or market-data entitlement is verified for an IBKR, Kraken or Alpaca account.

Broker fills/fees are facts; add clearly separated modeled missing-cost adjustments to the internal research ledger for economic analysis, never mislabel them broker debits. Overlay limits use conservative costs. Reconcile broker cash excluding documented virtual initial-allocation and modeled-cost differences; every difference must have an explanation, not a tolerance chosen after the discrepancy appears.

## Continuous and restart reconciliation

Consume broker order updates idempotently and periodically query orders/fills/positions/account. Retain event IDs and high-water marks, query with overlap, deduplicate; reconnect does not prove no events were missed. Reconcile cumulative quantities, fills, fees, settled/unsettled cash, positions and working protection. Unknown order/position or inconsistent cumulative fill locks all new entries. Detailed restart algorithm: [[07 - Operations/Runbooks/Incident and Failure Procedures]].

Measure paper versus backtest using a paired replay of the **captured available data** with the frozen strategy/model: candidate agreement, eligibility timing, acceptance/rejection, fill/no-fill rate, fill-price difference in basis points and EUR, partial-fill rate, entry/exit latency, stop/target ambiguity, fees/FX and daily equity differences. Classify discrepancy into feed, publication/revision, model, execution or bug. Keep original model results when calibrating a new version on development captures; evaluate the new model on fresh captures. Acceptance tolerances must be registered before prospective validation.

No direct inference from paper win rate to live profitability. Log failed protection, disconnects, missing fills and successful recovery drills as readiness evidence, not only executed trades.

## Independent participants and execution permissions

The mode table above describes broker-backed paper operation, not approval policy. [[01 - Architecture/Execution/Execution Modes]] keeps data/run mode, SIMULATION/PAPER/LIVE environment, SIGNAL_ONLY/ORDER_ENABLED submission mode, MANUAL_APPROVAL/FULL_AUTO policy and NORMAL/EXPERIMENT context separate. AUTONOMOUS_EXPERIMENT is an experiment type. Four-agent paper experiments start only after historical and paper operational gates; each participant has its own funding ledger, counters, locks and statistics. Prefer separate paper accounts or isolated simulator accounts. Sharing a broker account requires verified attribution/protection and parent-account allocation constraints; a net symbol position is not proof of agent ownership.

[[03 - Experiments/Autonomous Experiments]] freezes configurations/starting funding; all agents receive equivalent market availability and measured delivery latency. No losing participant reset/top-up. Normal paper operation may use controlled manual approval and later general capital profiles without changing the engine. Scope incident locks correctly: one agent's daily loss must not freeze an independent account, while shared reconciliation failures must block all affected agents. See [[01 - Architecture/Portfolio Accounting/Capital Allocation]].
