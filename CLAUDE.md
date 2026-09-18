# Claude Code entry point

Read [AGENTS.md](AGENTS.md) first — it is the mandatory entry point for every agent working on this
repository and links to the authoritative [docs/PROJECT_RULES.md](docs/PROJECT_RULES.md). This file
adds Claude Code-specific operating rules on top of AGENTS.md; it does not restate, duplicate, or
override any rule in AGENTS.md or docs/PROJECT_RULES.md. Where anything here appears to conflict,
AGENTS.md and docs/PROJECT_RULES.md govern.

Purpose: let Claude Code and OpenAI Codex work interchangeably on this repository, handing off through
committed Git/GitHub state rather than shared memory, since the two tools do not see each other's
conversations.

## Startup check (every session, before any work)

Establish ground truth directly from the repository, not from memory of a prior conversation:

1. `git branch --show-current` and `git rev-parse HEAD` — current branch and exact commit.
2. `git fetch` the remote, then compare local `HEAD` with its upstream (e.g.
   `git rev-parse HEAD` vs `git rev-parse @{u}`, or `git status`). If they differ, report the
   divergence to the user and stop there — do not automatically pull, reset, rebase, fast-forward, or
   otherwise overwrite local or remote history to reconcile it.
3. `git status --short` and `git diff --stat` — uncommitted/untracked changes; identify which are
   pre-existing and unrelated to the assigned task (e.g. `.obsidian/graph.json`) versus part of it.
4. `git log --oneline -10` — recent commit history for context.
5. Read [Current Status.md](docs/AI-Trading-Scanner/00%20-%20Project/Current%20Status.md) and
   [Roadmap.md](docs/AI-Trading-Scanner/00%20-%20Project/Roadmap.md) for the current phase/milestone,
   its actual status, and the documented "next recommended action" — the detailed docs are
   authoritative over any one-line summary, per docs/PROJECT_RULES.md's precedence order.

## Role: implementer or independent reviewer

Claude may be assigned either role per task; the two are never combined in the same request.

- **Implementer**: writes/edits code or docs under the same rules as any other contributor — read
  affected specs first, keep docs and implementation synchronized, no silent threshold/rule changes,
  tests for behavioral changes. Risk-critical changes still require independent **competent human**
  review before merge, per docs/PROJECT_RULES.md.
- **Independent reviewer**: reviews another party's candidate (including Codex's) against the stated
  requirements and previously recorded findings, verifies claims against actual source and actual
  command output rather than trusting a commit message or prior summary, and records results in the
  relevant `docs/AI-Trading-Scanner/06 - Testing/*.md` review log. Any such review must be labeled
  explicitly as an AI/agent technical review — never phrased as formal project acceptance or merge
  authorization, which remain a separate, human-only gate under docs/PROJECT_RULES.md.

## Handover between Claude and Codex

The only trustworthy handover surface is committed Git/GitHub state plus documentation:

- Treat the last commit on the working branch, `git log`, and the docs under
  `docs/AI-Trading-Scanner/06 - Testing/` and `00 - Project/` as the complete record of what the other
  tool did — never assume additional unstated context from "a previous Codex/Claude session."
- When handing off, leave a concise status note (in the relevant doc, or in the final chat reply if
  nothing is committed) stating: exact commit SHA, what was verified and how, what remains unfinished,
  and any blockers.
- Do not infer that Codex, or a prior Claude session, already validated something beyond what is
  actually recorded in committed docs or test output.

## Authorization gate

Never commit, push, create/modify a pull request, or merge without the user's explicit authorization
on the current turn — a prior approval, even for a similar action earlier in the same session, does
not carry forward. Read-only inspection, local edits kept uncommitted, and reporting findings never
require authorization.

## Preserve unrelated local state

Before any commit, run `git status` and stage only the files that belong to the assigned task. Never
stage, commit, discard, or revert unrelated pre-existing local changes (for example the Obsidian
`docs/AI-Trading-Scanner/.obsidian/graph.json` diff) unless the user explicitly asks for that file to
be included.

## Verification and reporting

Report only checks actually executed in this session, with their actual results, per
docs/PROJECT_RULES.md's "report exact checks and limitations" and AGENTS.md rule 16. Never state or
imply that tests, lint, type checks, or a build passed unless the corresponding command was run in
this session and its output was inspected. If a check was not run, say so explicitly.
