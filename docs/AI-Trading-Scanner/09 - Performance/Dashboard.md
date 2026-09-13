# Trading performance dashboard

Status: **REPORTING CONTRACT PLANNED; generator, charts and experiment data NOT IMPLEMENTED**. No performance claim exists.

Structured experiment/result storage is authoritative. This note and future assets are derived, replaceable artifacts. A dashboard that cannot be regenerated from a named run/ledger watermark is incomplete and must say so. Raw market snapshots, decisions, AI calls, orders, fills and event logs do not belong in Obsidian.

Summary generation follows [[03 - Experiments/Reporting]].

For a selected experiment/run, agent, strategy, model and capital arm, the generated dashboard will show metadata (IDs/status, period, universe/data provenance and equivalence, model/prompt, strategy/risk/management/config versions, starting capital, fee profile, execution assumptions, anomalies) and, when supported:

- equity, drawdown, cumulative Gross Trading P&L, Net Trading P&L and Net Economic P&L curves;
- realized/unrealized P&L, exposure, daily/weekly/monthly/full-period returns without fabricated intervals;
- evaluated setups, TRADE/NO_TRADE, executions, wins/losses, win rate, average/best/worst trade, expectancy, profit factor and holding/lifecycle measures;
- commissions, spread, slippage, other execution costs, AI inference costs, cost ratios and cost-driven rejections;
- Momentum, Mean Reversion, Breakout and Multi-Factor comparison only when metadata proves equivalent conditions;
- EUR 50/100/250/500/1,000 capital comparison, MVC inputs and capital-efficient-range result where a valid sweep exists;
- capital survival, uninterrupted autonomy, lockouts/interventions and experiment completion/failure as separate outcomes.

Generated summaries will include a reference to authoritative structured data and generation/metric versions. Chart assets belong under `09 - Performance/Assets/Charts/` only when data exists; no empty periodic folders or fabricated charts are created now. Meaningful run summaries belong under `03 - Experiments` or this section, never one note per event.

The first useful implementation should produce one reproducible Markdown summary and a compact set of PNG/SVG charts from the Phase 3 fixture run, then verify regeneration from a clean output directory. Advanced interactive styling is deferred.
