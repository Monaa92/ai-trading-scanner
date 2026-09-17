# Setup and verified state

Recorded 2026-09-13. Separate observed facts from user-reported facts and intended future technologies.

| Fact | Evidence/status |
| --- | --- |
| Windows development environment | Observed Windows paths and PowerShell tool context |
| Local repository | `C:\Users\Ramon\ai-trading-scanner` inspected |
| GitHub repository | Origin URL observed as `https://github.com/Monaa92/ai-trading-scanner.git` |
| Intended visibility | User requires repository to remain private; remote visibility not independently queried |
| Obsidian vault | Renamed in place from `docs/obsidian` to `docs/AI-Trading-Scanner`; source absent, target present; all 79 pre-rename file paths relative to the vault have identical SHA-256 hashes and sizes (74 Markdown, 5 `.obsidian` JSON files) |
| Vault organization | 84 existing notes moved through an explicit collision-checked map into `00 - Project` through `10 - Archive`; the complete 106-file size/SHA-256 multiset matched before link repair and all internal links resolved afterward |
| Codex assistance / desktop app | Current task is running through Codex desktop, verified by session context |
| Codex CLI successfully started here | User-reported setup fact in initial brief; not independently rerun/verified in this pass |
| Phase 1 runtime | CPython 3.13.15, pinned by `.python-version` and `requires-python`; installed and managed by uv 0.12.13 |
| Phase 1 dependencies | Exact direct versions in `pyproject.toml`; complete transitive resolution committed in `uv.lock` |
| Phase 2 calendar | Project boundary over exactly pinned `exchange-calendars==4.13.2`; local XNYS calendar data, no provider credentials or runtime download |
| Initial Git state | `main` tracking `origin/main`, initial commit `5065408`, tracked README/.gitignore; existing `docs/` untracked and nine Markdown stubs empty |

The initial repository had no production code, package manifest, tests or migrations. Phase 1 added the offline executable safety foundation; Phase 2 added historical market-data records and causal reads; Phase 3 adds deterministic indicators; Phase 4 adds pure strategy/proposal contracts; Phase 5 adds accepted risk sizing and local in-memory reservation contracts; and Phase 6 adds immutable simulation/accounting contracts, deterministic event serialization, an accepted in-memory scheduler and accepted bounded one-event causal orchestration. No complete replay/execution loop, Agent 5, provider adapter, data download, database, scanner, durable portfolio/P&L ledger, broker or external order-execution component exists. Existing Obsidian app/appearance/core-plugins/workspace JSON remains preserved. No duplicate vault exists and no active link or configuration points to the former vault path.

Still absent/unverified: PostgreSQL, Supabase, brokers, credentials, market-data subscriptions, Vercel, completed replay/execution and durable trading-state subsystems. Graphify `graphifyy` v0.9.56 and its CLI help were verified outside the restricted sandbox. No repository Graphify config or generated output exists. No secret was requested or recorded.

## Fresh-clone commands

Install Git and uv, clone the repository, then run:

```powershell
uv sync --locked --all-groups
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv build
uv run --locked ai-trading-scanner health
```

`uv sync` downloads the pinned Python runtime when it is absent and creates ignored `.venv` state. The commands require no `.env`, credentials, broker account or paid API. Do not connect a broker or deploy as a side effect of setup. A future `.env.example` should be added only when a real non-secret variable contract exists; `.env` stays local and ignored. See [[07 - Operations/Security & Secrets]].
