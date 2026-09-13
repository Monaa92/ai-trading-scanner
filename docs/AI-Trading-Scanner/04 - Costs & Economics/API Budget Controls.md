# API budget controls

Status: **PLANNED; amounts and thresholds intentionally unset**.

No EUR 50 API budget is configured. A future prepaid amount may be around EUR 50 when paid testing begins, but the owner must choose versioned warning, critical and hard-stop thresholds at that time. Provider credit is external evidence; the internal append-only usage ledger and explicit budget allocations govern the experiment.

Budgets may be scoped by day, ISO week, month, experiment, run and agent. Balanced allocation events prevent double assignment. Agents and AI services cannot increase, transfer or reload their own budget. There is no automatic provider top-up. Manual owner funding is a new attributed budget event and never changes trading capital.

| State | Required behavior |
| --- | --- |
| NORMAL | Calls within a valid allocation may proceed after purpose/cache/routing checks. |
| WARNING | Notify and expose burn-rate/remaining estimates; do not silently reduce evidence quality. |
| CRITICAL | Apply only preregistered degradation such as deterministic prefiltering or lower-priority call deferral; preserve comparability labels. |
| HARD_STOP | Block new AI-dependent entries/calls, record BUDGET_EXHAUSTED and require explicit owner resume or new allocation. |

Hard stop must not strand positions. Deterministic protection, risk reductions, scheduled exits, broker reconciliation and audit continue. If a frozen experiment did not preregister fallback behavior, an AI-dependent decision becomes NO_TRADE or the affected arm pauses/fails according to its manifest; it never switches model or prompt invisibly. Open positions do not book budget exhaustion as a market loss.

Validate call identity, race-safe reservations, retries, cache attribution, provider reconciliation, threshold transitions and explicit resumption. Budget policy is operational governance, not an AI optimization objective.
