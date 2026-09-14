# Agent entry point

Read [docs/PROJECT_RULES.md](docs/PROJECT_RULES.md) before any modification. It is the authoritative project governance document. Start navigation at [the vault overview](docs/AI-Trading-Scanner/00%20-%20Project/Overview.md); consult the relevant specifications and ADRs before changing behavior.

## Non-negotiable rules

1. Read relevant documentation before modifying behavior.
2. Keep implementation and documentation synchronized.
3. Never silently change strategy rules/thresholds, risk controls, execution assumptions, cost assumptions, or AI scoring.
4. Every material strategy change requires a new strategy version.
5. Once a functioning backtester exists, compare every material strategy change with the previous accepted version under identical evaluation conditions.
6. Update `docs/AI-Trading-Scanner/00 - Project/Decisions/Strategy Changelog.md` for material strategy changes.
7. Update `docs/AI-Trading-Scanner/00 - Project/Decisions/Risk History.md` for material risk changes.
8. Update `docs/AI-Trading-Scanner/00 - Project/Decisions/AI History.md` for material AI behavior, model, or prompt changes.
9. Never bypass deterministic risk controls. AI and UI cannot increase authorized exposure.
10. Never expose or commit secrets; `.env` stays local and ignored.
11. Never claim profitability or improvement without sufficient quantitative evidence.
12. Retain failed, rejected, aborted, and negative experiments.
13. Never repeatedly optimize against the final holdout.
14. Behavioral changes require meaningful tests, including regression/comparative tests where applicable.
15. Risk-critical code requires the stronger review and evidence specified in project rules.
16. Report exactly which tests/checks ran, their results, and what remains untested.
17. Use Obsidian links between vault notes and ordinary relative Markdown links outside the vault.
18. Important architecture changes require an ADR and consistency review.
19. Do not commit, push, or open a pull request unless explicitly instructed by the user.
20. Implementation existence never authorizes live trading.

21. Isolate trading agents' decisions, allocations, positions, risk state and results. Shared data does not authorize shared account state.
22. Keep data/run mode, execution environment, submission mode, approval policy and operating context separate. `AUTONOMOUS_EXPERIMENT` is an experiment type. FULL_AUTO never implies LIVE or bypasses risk/safety.
23. Manual consent binds immutable proposal terms/version; material changes require new consent and every submission requires fresh revalidation.
24. Freeze autonomous experiment strategy/risk/AI/management/configuration; only preregistered adaptive algorithms may evolve state.
25. Allocate capital atomically without double allocation; agent equity is not total broker equity. Agents cannot grant themselves funds or risk.
26. Record attributed, timestamped configuration/capital changes and separate performance segments; never rewrite prior versions.
27. Counterfactual/shadow outcomes cannot alter actual-path equity, risk budgets, trades or survival.
28. AI/agent runtimes cannot enable FULL_AUTO/LIVE, switch credentials/environment, clear their own locks or disable safety. Live autonomy requires separate explicit owner configuration and readiness evidence.
29. Trading agents never call broker/exchange or market-data provider APIs; the execution coordinator alone calls BrokerAdapter after risk, authority and safety gates.
30. Keep trading capital, execution costs and AI/API operating budgets in separate ledgers. AI spend never changes portfolio cash or risk.
31. Experiment 1 remains US equities with equivalent normalized information for all four strategy profiles. Adapter availability cannot change its universe.
32. Treat NO_TRADE as a first-class decision and never impose a minimum trade count.
33. Reuse AI decisions across capital arms only with an explicit replay-equivalence proof; portfolio-dependent decisions require separate inference.
34. Generated Obsidian reports are derived from authoritative structured experiment data and never replace it.

Current phase: Phases 1–4 are complete on `main`. PR #4 candidates `0c36a5d`, `7ea3dc0` and `d1da3a0` received CHANGES REQUIRED. The third Phase 5 remediation candidate binds deterministic Decimal sizing to immutable proposal, configuration and evaluated state; conserves exclusive parent allocation ownership; relationally validates approved and rejected risk evidence; and preserves one allocation per agent, attributed/fresh loss evidence, daily headroom, proposal uniqueness, expiry, reservation and lock behavior. Independent competent human review of the exact new candidate is required before merge. `BASELINE_RESEARCH_V1` remains an unvalidated research policy. No scanner, full portfolio/P&L ledger, durable persistence, broker/AI integration, deployment, order submission or trading automation is implemented.
