# Security and secrets

Status: requirements for future implementation. Repository is intended to remain private; privacy is not a substitute for secret hygiene.

Never store credentials/tokens in Git, GitHub, Obsidian, logs, screenshots or documentation. `.env` is already covered by the existing ignore rule. Keep it local; provide a credentials-free `.env.example` in a later authorized foundation task. Audit ignore coverage for future variants such as `.env.local` before use; do not assume the current `.env` rule covers all names. No real credentials or example credential-looking values are added now.

Separate market-data read access, paper execution and future live execution identities. Use minimum permissions and explicit endpoint/account allowlists. Do not load live secrets in development. Every run/event/adapter carries data/run mode and execution-environment identity; startup and submission both reject mismatches. Unknown dimension values default to SIGNAL_ONLY/SIMULATION with no dispatch, never LIVE. Neither frontend nor AI receives broker secrets. Resolve secret references only in adapters at runtime; redact headers, URLs/query fields and error payloads before logging.

Future API requires authentication, server-side account authorization, validated commands, CSRF protection where cookie authentication is used, restricted origins and rate limits. Database credentials have scoped access; frontend has no direct permission to mutate risk/ledger/orders. If Supabase is later chosen, service-role credentials remain backend-only and account row-access policies require tests. Multi-user identifiers can exist now in contracts; actual tenancy and subscription logic are deferred.

Dependencies must be pinned/reviewed in the future foundation; no installation is claimed. Protect backups/artifacts with private access, encryption where available and documented retention. AI inputs use a field allowlist; plain-text explanations are untrusted content rendered safely.

On suspected exposure, disable affected requests/new exposure, revoke/rotate credentials through authorized account tooling, investigate access logs without copying secrets, preserve redacted evidence and verify replacement scopes. Never merely delete the visible string and assume history is clean. See [[07 - Operations/Runbooks/Incident and Failure Procedures]]. Live credential provisioning requires the separate live gate and explicit owner action.

## Agent and administrative privileges

Trading/AI principals receive only agent-scoped data/evaluation/proposal ports, never allocation/config activation, lock-clear, FULL_AUTO/LIVE activation or secret-selection permissions. Owner/research read access across agents is separate from participant access. Backend validates ownership and immutable proposal consent regardless of UI. Permissions are versioned/revocable; kill-switch epochs invalidate pending dispatch leases. Shared-account coordinator may enforce aggregate limits without exposing another agent's private state. Live/manual/auto changes use deliberate authenticated flows in [[09 - Performance/Reporting Architecture]].
