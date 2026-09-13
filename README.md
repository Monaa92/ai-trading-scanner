# AI Trading Scanner

Private research project investigating a systematic AI-assisted intraday scanner through deterministic rules, risk controls, realistic backtesting and eventual paper validation. Profitability is unproven; negative results are retained.

Current state: architecture, governance and specifications only. No trading application or integrations exist.

- [Project rules](docs/PROJECT_RULES.md) — authoritative governance.
- [Agent instructions](AGENTS.md) — required entry point for future agents.
- [Knowledge base](docs/AI-Trading-Scanner/00%20-%20Project/Overview.md) — open `docs/AI-Trading-Scanner` as the `AI-Trading-Scanner` Obsidian vault.
- [Current status](docs/AI-Trading-Scanner/00%20-%20Project/Current%20Status.md) — actual implementation/readiness and blockers.
- [Roadmap](docs/AI-Trading-Scanner/00%20-%20Project/Roadmap.md) — gated implementation phases.
- [Architecture review](docs/AI-Trading-Scanner/10%20-%20Archive/Reviews/Architecture%20Review.md) — decisions, unresolved evidence and next milestone.

Initial scope: long-only US equities/ETFs, 5-minute trend-pullback hypothesis, EUR 50-equivalent simulation, optional AI filtering behind deterministic risk controls. Live trading is not authorized.

Architecture extension: independently configured trading agents, isolated capital, broker-agnostic execution, four strategy profiles, capital-efficiency and AI-cost accounting, frozen autonomous experiments, recovery and derived performance reporting. EUR50 is an initial virtual-capital profile, not an engine or API-budget limit. No agent, adapter, approval service, database, test suite or automatic trading has been implemented.
