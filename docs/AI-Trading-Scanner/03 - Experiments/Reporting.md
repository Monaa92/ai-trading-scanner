# Experiment summaries

Status: **generation contract planned; no completed runs or generator exist**.

Structured experiment/result storage is the source of truth. A repeatable reporter will select an immutable run and ledger watermark, calculate versioned metrics, write a human-readable Obsidian summary and update [[09 - Performance/Dashboard]] references. It never asks a person to transcribe performance values.

A meaningful run summary includes, where available: run/experiment ID, dates/duration/status, objective, agents/strategies/models and model/prompt versions, universe and market-data provenance/equivalence, tested period, starting capital, risk/management/cost profiles, execution assumptions, evaluated setups, AI calls, TRADE/NO_TRADE decisions, executions, Gross Trading P&L, Net Trading P&L, AI cost, Net Economic P&L, commission/spread/slippage, drawdown, profit factor, cost-driven rejection rate, capital efficiency/MVC, failures/anomalies, observations, conclusion, recommended next action and authoritative data reference.

Comparative summaries include concise agent/strategy/model/capital tables only when metadata supports the comparison. Missing daily/weekly/monthly observations remain unavailable. No note is created per trade, market snapshot, AI call or scanner event.

Generated Markdown and chart paths are deterministic from experiment/run identity plus reporter version. Regeneration creates a reviewable replacement or new version while the underlying event data remains immutable. If authoritative data is unavailable, the note states that the dashboard cannot be regenerated and is not evidence.
