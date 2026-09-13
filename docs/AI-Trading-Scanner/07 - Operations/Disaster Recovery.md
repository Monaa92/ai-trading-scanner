# Disaster recovery and backup

Status: **PARTIAL**. The architecture, governance and human-readable vault are protected by the repository after this task's foundation commit/push. Future authoritative experiment data still needs a separately selected and tested durable backup.

## Current protection inventory

| State | Current classification | Recovery treatment |
| --- | --- | --- |
| Source/governance, Phase 1–2 package/tests/lockfile, `AGENTS.md`, `README.md`, `docs/PROJECT_RULES.md` and vault Markdown | Protected on `origin/main` after the approved Phase 2 merge | Clone from GitHub and run the locked setup below. |
| Stable vault settings: `.obsidian/app.json`, `appearance.json`, `core-plugins.json`, `graph.json` | Protected with the vault | Restore with the clone; these contain no credentials. |
| `.obsidian/workspace.json` and local UI/session state | Intentionally ignored; safe to lose/regenerable | Obsidian recreates it; project knowledge does not depend on it. |
| Generated performance notes/charts | Regenerable by design; none exist | Rebuild from authoritative experiment data, never treat charts as the only evidence. |
| Authoritative external market/experiment/decision/order/fill/P&L/AI-cost data | No store or real data exists yet; Phase 2 fixtures are small synthetic Python definitions in Git | Future store needs integrity-checked backup outside a single computer; large telemetry is not assumed suitable for Git. |
| Secrets/credentials | None found; `.env` is ignored | Recreate securely from the provider/secret manager on a new machine; never copy through Git/Obsidian/Graphify. |

The reviewed foundation commit tracks all current vault Markdown and four stable Obsidian settings files. Machine-specific workspace state remains ignored. No raw experiment telemetry exists yet.

Pre-commit classification covered every untracked file: 101 vault Markdown notes and four stable `.obsidian` JSON settings belong in Git; `AGENTS.md` and `docs/PROJECT_RULES.md` belong in Git; `.obsidian/workspace.json` remains ignored as machine/session state. No cache, temporary file, Graphify output, generated dashboard asset or credential file is included.

## Fresh-machine recovery procedure

1. Install Git, Obsidian and uv; uv will obtain the pinned CPython 3.13.15 runtime.
2. Run `git clone https://github.com/Monaa92/ai-trading-scanner.git` and enter the clone.
3. Run `uv sync --locked --all-groups`.
4. Open `docs/AI-Trading-Scanner` as the Obsidian vault. Restore only intentionally retained `.obsidian` configuration; workspace state is optional.
5. Restore/reconnect the future authoritative experiment store and verify its checksums, schema and backup watermark.
6. Recreate required environment variables/secrets from the approved secure source. Never recover them from docs or logs.
7. Run `uv run --locked pytest`, `uv run --locked ruff check .`, `uv run --locked mypy` and `uv run --locked ai-trading-scanner health`.
8. Verify all internal links, dataset identities, ledger/run manifests, Graphify integration and dashboard regeneration.
9. Keep PAPER/LIVE disabled until their independent readiness gates and owner decisions.

A fresh clone reconstructs the non-secret architecture, governance, Phase 1–3 executable foundations, synthetic fixtures and important Obsidian knowledge. Full disaster-recovery readiness still cannot be claimed: the phase that first creates authoritative external market or experiment data must choose a durable backup target and tested restore procedure without introducing a paid service by default.
