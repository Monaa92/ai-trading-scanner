# Versioned trade-management policies

Baseline `management-fixed-v0.1.0` remains a fixed initial stop, fixed target and scheduled session-end exit. No dynamic extension is activated by this documentation. Bind management version/parameters to strategy, agent config, proposal, intent and position episode; an exit change can materially alter strategy outcomes and requires a strategy-version/history update plus controlled comparison.

There is no universal maximum profit or mandatory fixed take-profit percentage in the reusable engine. The current fixed target is a deliberately versioned baseline hypothesis. A future qualified strategy-specific policy may let a profitable position continue while its causal thesis remains valid and no hard risk rule intervenes. Momentum may use trend invalidation/trailing protection; Mean Reversion may exit when the reversion is complete; Breakout may use failure/return-to-range or continuation protection; Multi-Factor may react to its registered factor state. These are planned policy families, not active rules.

| Optional policy | Must specify before independent testing |
| --- | --- |
| Break-even stop | Causal trigger, entry/fee-adjusted break-even definition, spread/slippage limits and tick rounding; name does not guarantee zero loss |
| Trailing stop | Reference price/window, update cadence, distance, tick/latency rules, monotone stop invariant |
| Partial profits / multiple targets | Trigger prices, allocated fractions, quantity rounding, residual broker minima and linked-order conflict handling |
| Volatility exit | Causal ATR/volatility inputs, period, trigger, missing-data behavior; no same-bar high/low leakage |
| Momentum exit | Feature/version and exact trigger; no retrospective selection of best exit |
| Time-based exit | Session-relative deadline/calendar, latency and failure behavior; fixed end-of-day baseline remains mandatory |
| Dynamic deterministic exit | Explicit state machine, allowed actions, input as_of and transition bounds |
| AI-assisted recommendation | Separate strict schema limited to HOLD/TIGHTEN_STOP/REDUCE/EXIT with proposal references, bounded quantity/stop suggestion; no mode/config/limit changes, independently validated |

Every extension needs a preregistered hypothesis, exact versioned semantics, independent historical test, comparison against the previous accepted fixed/management baseline under common entry/cost/data assumptions, full portfolio rerun, failure tests and audit events. No accepted predecessor exists yet; use the initial registered baseline until one does. Matching only trades which exit successfully biases comparison. A separate dynamic treatment is required before inclusion in the four-agent experiment.

## Stop amendments and risk

For long-only V1 require `new_stop >= last_acknowledged_stop >= initial_stop` after valid tick rounding; no widening, even if unrealized gains or partial profits appear to “fund” more risk. Proposed tightening is not effective protection until acknowledged. A rejected replacement leaves the previous confirmed stop authoritative; ambiguity locks further discretionary amendments and invokes reconciliation. If a suggested stop is already at/above current bid, use a separately validated close intent rather than pretend a non-triggered stop was installed.

Risk recomputes residual quantity, worst-case remaining modeled loss, costs, current FX and aggregate agent/account exposure with the proposed action and any still-working exits. A candidate stop may not increase modeled downside beyond current authorization; FX/gaps can nevertheless increase actual risk, so record/reduce breaches instead of claiming a guarantee. Partial profit must never permit an add-on entry, a lowered stop or reusing released money while a cancellation remains uncertain. Initial R denominator stays frozen for performance metrics.

Every amendment passes [[01 - Architecture/Execution/Safety Gate]], binds owned position and expected revision, persists an Amendment/OrderIntent with predecessor and reason, then uses the same outbox/idempotency/cancel-reconcile mechanisms as entries. Broker supports safe linked replacement or the adapter is not certified for that policy. No temporary cancellation of protection followed by an assumed successful new stop. Multiple exit children in total cannot oversell the remaining attributable quantity; OCO/native netting support is verified, not assumed.

## Approval and timing

MANUAL_APPROVAL consents to the displayed fixed protective/target, scheduled exit and bounded emergency instructions. Every discretionary dynamic stop/target/quantity amendment requires a fresh immutable approval; choosing a dynamic policy is not blanket consent to changed order terms. Refusal/nonresponse leaves safe existing protection in force. Executing originally specified exits or the disclosed emergency-reduction instruction does not rewrite the initial approval. FULL_AUTO can generate new amendments only within its deliberately enabled policy after risk/safety validation. Autonomous experiments may use only the frozen management algorithm; no discretionary prompt/threshold edits.

Backtests evaluate dynamic rules only on data available at amendment decision time; a stop calculated from a candle's high cannot be treated as active earlier in that candle. Model replacement latency, racing fills, rejection and old-stop activity until acknowledgement. On AI management failure, baseline confirmed protection and scheduled exit continue; unlike an entry filter failure, an exit recommendation failure must not strand or remove protection. AI assistance never becomes required for liquidation.

## Authority and lifecycle evaluation

The agent may propose HOLD, TIGHTEN_STOP, REDUCE or EXIT only within its registered management contract. Entry, stop, target, quantity, order type, validity and management-mandate changes are execution-critical. In MANUAL_APPROVAL, every material change invalidates prior consent and requires a new immutable proposal/approval. FULL_AUTO removes only that human step. Every proposal still passes risk and safety; no agent may weaken/remove mandatory protection, widen the downside envelope, add capital or disable a circuit breaker because it forecasts more profit.

The central Risk Engine owns configurable/versioned maximum risk per trade, position size, total exposure, agent loss/drawdown, required protection, concentration and circuit-breaker limits. Strategies may be stricter but never looser. Numeric permanent thresholds remain unset except the existing initial profile constraints.

Evaluation covers the complete position episode through [[09 - Performance/Performance Metrics]]: entry quality, MFE, MAE, realized return, peak unrealized profit, retained profit, peak giveback, exit reason, holding time, stop/strategy exits and risk interventions. No look-ahead optimization is permitted.
