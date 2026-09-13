# Simulation broker

Status: **NOT IMPLEMENTED**. This is the required current-experiment adapter specification, not completed production functionality.

`SimulationBrokerAdapter` will implement every method in [[01 - Architecture/Broker Architecture]] without network access or credentials. It will consume immutable order intents and causal market events, enforce an explicit capability snapshot, model partial fills/cancellations/rejections/ambiguity, apply the frozen transaction-cost/execution profile and emit deterministic events under a fixed run manifest and random seed policy.

Each `(run_id, agent_id, allocation_id)` owns independent cash, reservations, positions, realized/unrealized P&L, costs, risk state and order attribution. Equivalent shared market snapshots are read-only inputs. Simulation must reject unsupported order features, stale required data and cross-agent access. NO_TRADE produces a decision event only.

Phase 3 completion requires executable lifecycle behavior, restart/idempotency tests and reconciliation with the authoritative ledger. Interface existence alone is insufficient.
