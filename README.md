# AI Trading Scanner

Private research project investigating a systematic AI-assisted intraday scanner through deterministic rules, risk controls, realistic backtesting and eventual paper validation. Profitability is unproven; negative results are retained.

Current state: Phases 1–5 are complete on `main`. Phase 6 — causal backtesting and simulation — is
in progress on `feat/phase-6-causal-simulation`. The foundation defines content-identified causal
run/events, next-eligible-bar-open order/fill contracts, versioned costs, conserved Decimal portfolio
records, deterministic trace serialization and an in-memory deterministic event scheduler. Only a
fully validated typed replay artifact can create an executable scheduler. Process-local cursor
authority issues current-state checkpoints and prevents in-process skip/rewind; content identity is
not authentication and durable cross-process anti-rollback remains unimplemented. The bounded
one-event causal orchestrator through `b76891f7a1d787c2c07d26c0f4dd6a42df55aada` is accepted. It
evaluates the accepted Phase 3/4 contracts and Phase 5 reservation boundary with authoritative
reconstruction checks. The first milestone 6.1 candidate failed independent review; its bounded
workspace remediation uses cursor-bound creation, atomic resolver publication, authoritative terminal
validation and a V2 run manifest containing the complete liquidity configuration. Claude's independent
technical review (2026-09-18) found its six targeted defects resolved and full verification passing;
independent competent human reviewer `Dekkerszz` then approved it via GitHub PR #5 (2026-09-18) within
the stated Phase 6.1 scope, so Milestone 6.1 is accepted, though PR #5/the feature branch remain
unmerged and Milestone 6.2 has not started. It creates no
fill and performs no accounting or reservation transition. Atomic economic posting, causal cost/FX,
durable recovery and future 4+1/Autonomous Survival Agent architecture remain unimplemented.
Research baselines remain unvalidated. No complete execution loop, Agent 5, scanner,
broker/provider/AI integration, PAPER/LIVE execution or external order authority exists.

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
