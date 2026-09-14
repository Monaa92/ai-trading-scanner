# Portfolio accounting

Status: **PARTIAL — PHASE 6 CONTRACT FOUNDATION ONLY**. `ai_trading_scanner.simulation.portfolio` implements immutable Decimal accounting records plus a pure chronological verifier that derives COMPLETE V1 state from fills and position changes. It does not operate a transactional ledger, persist state, recover after failure or implement the complete runtime position lifecycle.

## Implemented V1 boundary

Each `SimulationRunManifest` binds one account, agent and allocation. A `CashLedgerSnapshot` partitions `total_cash = available_cash + reserved_cash + committed_cash`; reservations and commitments are encumbrances inside cash, never new assets. Negative/non-finite values and binary floats fail validation.

One open `PositionSnapshot` represents a long-only position episode under `WEIGHTED_AVERAGE_LONG_ONLY`. It binds run/account/allocation/agent, strategy, management mandate, instrument and opening proposal. Exact derived fields must satisfy:

- `gross_cost_basis = quantity × average_entry_price`
- `market_value = quantity × mark_price`
- `unrealized_gross_pnl = market_value - gross_cost_basis`

A `PortfolioSnapshot` accepts at most one open position per instrument, requires canonical position ordering and prevents cross-agent/run/allocation records. In one V1 currency:

- `unrealized_gross_pnl = sum(open position unrealized gross P&L)`
- `gross_trading_pnl = realized_gross_pnl + unrealized_gross_pnl`
- `net_trading_pnl = gross_trading_pnl - total_execution_costs`
- `total_equity = total_cash + sum(position market value)`
- `total_equity = starting_capital + net_trading_pnl`

The last equality assumes no external flows inside a run segment. Capital changes require a new attributed segment under [[01 - Architecture/Portfolio Accounting/Capital Allocation]]. Execution costs are cash losses; spread/slippage are explicit cost components rather than a second adjustment to the stored gross fill price.

`PositionChange` binds proposal, order, fill and management mandate to OPEN, DECREASE or CLOSE quantity transitions. `RealizedTradeResult` binds all entry/exit fill identities and requires `net_pnl = gross_pnl - total_execution_costs`. For COMPLETE artifacts, the pure verifier starts from one flat unencumbered snapshot, applies each fill exactly once in causal order, debits its notional/cost once, derives open positions and closed trades, and requires every supplied snapshot and trade to equal the derived result. Open positions are marked at their latest applied fill price in this foundation until an authoritative external mark contract exists. This verifier validates an artifact already in memory; it is not a posting transaction or ledger service. Position IDs include run, account, allocation, agent, instrument and opening proposal so shared infrastructure cannot merge participants.

## Explicitly unavailable

No fill-to-ledger posting, weighted-average recalculation service, reservation consumption/release orchestration, stop/target lifecycle, cash settlement, corporate actions, dividends, FX, multi-currency accounting, allocation retirement, durable transaction, crash recovery or multi-process coordination exists. The one-currency contract cannot execute the future EUR-funded US-equity experiment until explicit FX observations and ledgers are implemented. Open-position increases are unavailable in V1; the no-pyramiding baseline remains unchanged.

The Phase 5 coordinator remains the authoritative in-process reservation boundary. Phase 6 must later prove one transaction-safe causal transition from reservation through fill/cash/position update and exact idempotent replay. See [[01 - Architecture/Portfolio Accounting/Position Sizing]], [[01 - Architecture/Execution/Order Lifecycle]], [[04 - Costs & Economics/Transaction Costs]] and [[06 - Testing/Phase 6 Completion Criteria]].
