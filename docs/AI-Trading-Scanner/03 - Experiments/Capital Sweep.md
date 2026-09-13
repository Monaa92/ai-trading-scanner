# Capital sweep

Status: **PLANNED; NOT IMPLEMENTED or executed**.

For every registered strategy/configuration, run the tested starting-capital vector `EUR 50, 100, 250, 500, 1000`. Capital is an immutable experiment parameter supplied to portfolio/risk/sizing services, never a branch embedded in strategy code.

Hold constant where technically valid: strategy and model/prompt versions, market-data snapshot/dataset, universe, period, risk and management policies, costs, execution assumptions, data-availability schedule, code/config versions and random streams. Any unavoidable difference is recorded and equivalence claims are withheld.

Each capital arm has a separate allocation and ledger. Results report absolute Net Trading P&L and Net Economic P&L beside returns, drawdown, costs and rejected opportunities. The largest arm is not automatically best. See [[03 - Experiments/Minimum Viable Capital]] and [[03 - Experiments/Decision Replay]].

Comparison table schema:

| Strategy | EUR 50 | EUR 100 | EUR 250 | EUR 500 | EUR 1,000 | MVC | Capital-efficient range |
| --- | --- | --- | --- | --- | --- | --- | --- |
| versioned profile | underlying metric-set references | underlying metric-set references | underlying metric-set references | underlying metric-set references | underlying metric-set references | classification + method version | classification + method version |

Do not store only the classification. Every cell retains its run/manifest/metric versions and detailed source metrics.
