# Agent lifecycle and capital preservation

Separate operational lifecycle from experiment outcome and scoped lock reasons. Registry/supervisor owns transitions; trading/AI agents cannot set lifecycle or clear locks. All transitions append old/new state, reason, scope, as_of, equity/threshold inputs, frozen config, actor and correlated incident. A displayed state never substitutes for checking all locks at dispatch.

| State | Meaning and allowed activity |
| --- | --- |
| CREATED / READY | Configuration registered / prerequisites validated; no execution until authorized activation |
| ACTIVE | Ordinary configured policy within all agent/account/system gates |
| DRAWDOWN_WARNING | Prespecified warning threshold crossed; alert and continue only within original limits; no automatic risk increase |
| CAPITAL_PRESERVATION | Frozen restrictive policy applies, e.g. multiplier in [0,1] on entry cap or no-new-entry; exits/protection continue |
| LOCKED | At least one applicable lock; no new exposure, bounded protection/reduction/reconciliation remain active |
| STOPPING | Planned termination/administrative stop; cancel entry remainders and flatten via verified policy |
| EXPERIMENT_FAILED | Participant terminal endpoint/protocol failure recorded; no new exposure; unresolved liquidation remains mandatory and visible |
| EXPERIMENT_COMPLETED | Planned completion with orders terminal and flat reconciled ledger; no further experiment trading |
| STOPPED | Normal-operation administrative stop, reconciled flat; may resume only by authorized new activation |

Warning/preservation triggers, reset thresholds/hysteresis, definition of drawdown (lifetime peak vs session loss), persistent infeasibility duration and failure endpoint are mandatory versioned configuration when enabled. No final percentages or durations are selected. Startup validates sensible ordering and nonnegative ranges. If warnings/preservation are disabled, record that explicitly; risk/daily/emergency locks are never disabled. Financial ruin, drawdown failure, inability to place broker-minimum trades, protocol violation and infrastructure failure are different reason codes.

## Transitions and authority

- READY→ACTIVE: administrator starts a validated normal agent or frozen experiment supervisor starts its authorized participant.
- ACTIVE→DRAWDOWN_WARNING→CAPITAL_PRESERVATION: trusted supervisor automatically applies registered thresholds; transitions can skip directly to a stricter state when multiple thresholds cross.
- Any nonterminal state→LOCKED: supervisor applies agent/account/system risk, health or emergency locks immediately. Severity precedence is terminal failure/stopping restriction, then lock, preservation, warning, active; retain underlying drawdown state while a lock masks it.
- Daily-loss LOCKED→underlying valid state: only trusted calendar/risk supervisor at verified next session with reconciliation; a process restart or agent request cannot reset it. Other locks require their defined repair evidence and authorized administrator clearance; clearing one reason does not clear others.
- Preservation/warning→less restrictive state: only if the registered automatic recovery rule explicitly permits it and all gates pass. Default when no recovery rule exists is latched until administrative review. Experiment administrators cannot relax the frozen policy to rescue a losing run; end/version the run instead.
- Any running state→STOPPING: registered end criterion or administrative stop. Then →EXPERIMENT_COMPLETED for a successful planned experiment close, or →STOPPED for normal operation, only after confirmed flat/no residual orders.
- Any experiment state→EXPERIMENT_FAILED: registered failure predicate or protocol-integrity decision with cause/evidence. This terminal result never resets within that run; a replacement agent/run is separate.

An experiment supervisor tracks REGISTERED→FROZEN→RUNNING→STOPPING→COMPLETED or FAILED/ABORTED with participant outcome references. It can complete collection even with failed participants; that does not relabel them as completed successfully. Planned end with unresolved holdings stays STOPPING or becomes FAILED by its registered timeout rule. The trading worker cannot set these results.

For normal operation, an unregistered experimental failure threshold cannot suddenly liquidate an account; use its own approved preservation/stop policy and operational locks. Carry original stop mandates across locks. See [[01 - Architecture/Portfolio Accounting/Capital Allocation]], [[01 - Architecture/Execution/Trade Management]] and [[03 - Experiments/Survival Analysis]].
