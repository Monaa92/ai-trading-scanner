# Experiment 1

Status: **DESIGNED, NOT RUNNABLE, NOT STARTED**.

Objective: compare [[02 - Agents & Strategies/Experiment 1 Strategy Profiles|four strategy profiles]] on the same US-equity opportunity stream while preserving independent portfolios. The initial profile gives each agent EUR 50 virtual capital; EUR 50 is neither live-capital advice nor an AI budget.

Experiment 1 fixes an equity-only universe and equivalent normalized market snapshots, timestamps, information availability, hard risk constraints, starting capital, `SIMULATED_IBKR_US_TIERED` cost profile and simulation assumptions. Kraken availability cannot add CRYPTO. Each `(experiment_id, run_id, participant_id, agent_id, allocation_id)` has independent cash, reservations, positions, realized/unrealized P&L, costs, risk state, performance history and order attribution.

The initial execution tuple is `HISTORICAL_REPLAY + SIMULATION + ORDER_ENABLED + FULL_AUTO + EXPERIMENT`, with experiment type `AUTONOMOUS_EXPERIMENT`, only after required offline components and fixtures exist. FULL_AUTO omits per-proposal consent but preserves risk, safety and final revalidation. A signal-only dry run may precede it. No PAPER or LIVE profile is authorized.

The run records evaluated setups, TRADE/NO_TRADE decisions, proposals, risk/safety outcomes, simulated orders/fills, portfolio events, execution costs, AI calls/costs and failures. Raw telemetry belongs in structured storage; Obsidian receives reproducible summaries. There is no minimum trade requirement and a no-trade outcome may be economically correct.

Open prerequisites: exact universe, data manifest, strategy parameters, model policy, fee rates, slippage/spread model, experimental period, seeds, failure thresholds and statistical plan. Missing values block start.
