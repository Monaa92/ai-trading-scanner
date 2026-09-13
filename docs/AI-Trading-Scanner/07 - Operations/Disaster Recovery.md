# Disaster recovery and backup

Status: **PARTIAL**. The architecture, governance and human-readable vault are protected by the repository after this task's foundation commit/push. Future authoritative experiment data still needs a separately selected and tested durable backup.

## Current protection inventory

| State | Current classification | Recovery treatment |
| --- | --- | --- |
| Source/governance, `AGENTS.md`, `README.md`, `docs/PROJECT_RULES.md` and vault Markdown | Protected on `origin/main` after the verified foundation push | Clone from GitHub. |
| Stable vault settings: `.obsidian/app.json`, `appearance.json`, `core-plugins.json`, `graph.json` | Protected with the vault | Restore with the clone; these contain no credentials. |
| `.obsidian/workspace.json` and local UI/session state | Intentionally ignored; safe to lose/regenerable | Obsidian recreates it; project knowledge does not depend on it. |
| Generated performance notes/charts | Regenerable by design; none exist | Rebuild from authoritative experiment data, never treat charts as the only evidence. |
| Authoritative experiment/market/decision/order/fill/P&L/AI-cost data | No store or data exists yet | Future store needs integrity-checked backup outside a single computer; large telemetry is not assumed suitable for Git. |
| Secrets/credentials | None found; `.env` is ignored | Recreate securely from the provider/secret manager on a new machine; never copy through Git/Obsidian/Graphify. |

The reviewed foundation commit tracks all current vault Markdown and four stable Obsidian settings files. Machine-specific workspace state remains ignored. No raw experiment telemetry exists yet.

Pre-commit classification covered every untracked file: 101 vault Markdown notes and four stable `.obsidian` JSON settings belong in Git; `AGENTS.md` and `docs/PROJECT_RULES.md` belong in Git; `.obsidian/workspace.json` remains ignored as machine/session state. No cache, temporary file, Graphify output, generated dashboard asset or credential file is included.

## Fresh-machine recovery procedure

1. Install Git, Obsidian and a future pinned project runtime once documented.
2. Run `git clone https://github.com/Monaa92/ai-trading-scanner.git` and enter the clone.
3. Install dependencies using the future lockfile command; no valid command exists yet because there is no package manifest.
4. Open `docs/AI-Trading-Scanner` as the Obsidian vault. Restore only intentionally retained `.obsidian` configuration; workspace state is optional.
5. Restore/reconnect the future authoritative experiment store and verify its checksums, schema and backup watermark.
6. Recreate required environment variables/secrets from the approved secure source. Never recover them from docs or logs.
7. Run future configuration validation and the documented test command.
8. Verify all internal links, dataset identities, ledger/run manifests, Graphify integration and dashboard regeneration.
9. Keep PAPER/LIVE disabled until their independent readiness gates and owner decisions.

A fresh clone reconstructs the current non-secret architecture, governance and important Obsidian knowledge. Full disaster-recovery readiness still cannot be claimed: the later Phase 3 persistence design must choose a durable backup target and tested restore procedure for authoritative experiment data without introducing a paid service by default.
