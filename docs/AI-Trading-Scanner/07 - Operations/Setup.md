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
| Initial Git state | `main` tracking `origin/main`, initial commit `5065408`, tracked README/.gitignore; existing `docs/` untracked and nine Markdown stubs empty |

Initial repository had no production code, package manifest, tests or migrations. Existing Obsidian app/appearance/core-plugins/workspace JSON was inspected and preserved. No duplicate vault exists and no active link or configuration points to the former vault path. Existing ignore rules were preserved and extended only for Obsidian workspace/session state, vault trash and regenerable Graphify output. This pass populates specifications only; no runtime setup is performed.

Unknown/unverified: Python version, installed project dependencies, PostgreSQL connection, Supabase project, broker credentials/account capabilities/data subscription and Vercel project. Node v24.19.0 and uv 0.12.13 were observed. Graphify `graphifyy` v0.9.56 and its CLI help were verified outside the restricted sandbox. No repository Graphify config or generated output exists, so there was no project-specific old path to update and no graph build to validate; repository references use the new vault path. Path-specific Graphify integration remains NOT CONFIGURED rather than broken. No secret was requested or recorded.

Next authorized implementation should inspect environment versions, choose/pin the foundation runtime and dependency manager, then create the scoped skeleton described in [[00 - Project/Roadmap]]. Do not connect a broker or deploy as a side effect of setup. Future `.env.example` must contain names/placeholders only; `.env` stays local and ignored. See [[07 - Operations/Security & Secrets]].
