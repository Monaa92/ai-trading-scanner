# AI Trading Scanner

Private research project investigating a systematic AI-assisted intraday scanner through deterministic rules, risk controls, realistic backtesting and eventual paper validation. Profitability is unproven; negative results are retained.

Current state: Phases 1–3 are complete on `main`. The Phase 4 review candidate adds four explicit
research-baseline strategy profiles, pure causal evaluation, first-class `NO_TRADE`, and immutable
content-identified trade-proposal contracts. It remains unreviewed and unvalidated for trading. No
scanner, central risk engine, portfolio, broker, AI, order submission or execution exists.

- [Project rules](docs/PROJECT_RULES.md) — authoritative governance.
- [Agent instructions](AGENTS.md) — required entry point for future agents.
- [Knowledge base](docs/AI-Trading-Scanner/00%20-%20Project/Overview.md) — open `docs/AI-Trading-Scanner` as the `AI-Trading-Scanner` Obsidian vault.
- [Current status](docs/AI-Trading-Scanner/00%20-%20Project/Current%20Status.md) — actual implementation/readiness and blockers.
- [Roadmap](docs/AI-Trading-Scanner/00%20-%20Project/Roadmap.md) — gated implementation phases.
- [Architecture review](docs/AI-Trading-Scanner/10%20-%20Archive/Reviews/Architecture%20Review.md) — decisions, unresolved evidence and next milestone.

Initial scope: long-only US equities/ETFs, 5-minute trend-pullback hypothesis, EUR 50-equivalent simulation, optional AI filtering behind deterministic risk controls. Live trading is not authorized.

Architecture extension: independently configured trading agents, isolated capital, broker-agnostic execution, four strategy profiles, capital-efficiency and AI-cost accounting, frozen autonomous experiments, recovery and derived performance reporting. EUR50 is an initial virtual-capital profile, not an engine or API-budget limit. These trading capabilities remain specifications.

## Local setup

Install [uv](https://docs.astral.sh/uv/), then run:

```powershell
uv sync --locked --all-groups
uv run --locked pytest
uv run --locked ruff check .
uv run --locked mypy
uv run --locked ai-trading-scanner health
```

`uv` installs the pinned Python 3.13.15 runtime. The health command uses the bundled safe
`SIMULATION + SIGNAL_ONLY` configuration and requires no credentials, network access or paid API.
