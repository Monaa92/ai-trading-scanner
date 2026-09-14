# Phase 4 independent review

Status: **INDEPENDENT COMPETENT HUMAN REVIEW REQUIRED; no approval is recorded.** Review the exact candidate commit on `review/phase-4-strategy-proposals`. Do not merge until critical findings are resolved and that exact commit is approved.

| Area | Implementation | Behavioral evidence | Intended invariant | Failure impact |
| --- | --- | --- | --- | --- |
| Four identities and registry | `strategies/configurations.py` | `test_strategy_configurations.py` | One stable versioned baseline per authoritative profile | Misattribution or changed experiment treatment |
| Strategy/model separation | configurations/domain identities | configuration tests | Strategy identity never depends on model identity | Confounded model/strategy experiments |
| NO_TRADE semantics | `strategies/models.py`, evaluators | contract/evaluator tests | Exactly one explicit outcome; structured strategy reasons only | Forced trades or collapsed rejection provenance |
| Baseline parameters | `strategies/configurations.py` | validation and evaluator tests | Every predicate/threshold is typed, versioned and labeled uncalibrated | Hidden or irreproducible strategy change |
| Momentum | `MomentumEvaluator` | momentum scenarios | Documented V1 trend/pullback/trigger/stop/resistance semantics | Different strategy or look-ahead target |
| Mean Reversion | `MeanReversionEvaluator` | reversion scenarios | Deviation + recovery required; strong trend blocks | Blind extreme trading |
| Breakout | `BreakoutEvaluator` | breakout scenarios | Causal range plus two closes and volume confirmation | Single-bar false breakouts |
| Multi-Factor | `MultiFactorEvaluator` | factor scenarios | Same inputs, named contributions and explicit weighted threshold | Privileged inputs or opaque score |
| Causal/quality boundary | evaluation context/shared validation | causality tests | No future bars/findings; hashes/alignment verified; fatal fails closed | Look-ahead or invalid-data decisions |
| Prefix invariance/idempotence | evaluators/content identity | causality/contract tests | Same causal prefix/context always yields identical decision | Replay drift or duplicate semantic proposals |
| Proposal completeness | `TradeProposal` models | contract tests | Intent has entry/stop/objective/economics/expiry/authority, no executable quantity | Ambiguous future risk/approval input |
| Proposal/mandate identity | models/content serialization | mutation/canonical tests | Every material approval-sensitive change changes SHA-256 identity | Consent could bind modified intent |
| Cost boundary | cost/economics models | cost tests | Entry+exit+spread+slippage+other are separate external inputs | Gross-only or broker-coupled decisions |
| Agent fairness | context/snapshot | four-agent equality tests | Same canonical raw/derived information, isolated attribution | Invalid comparison |
| Side effects and failure paths | evaluator module | I/O/fatal/mismatch tests and coupling scan | No network, broker, AI, account mutation or order action | Phase boundary bypass |

Reviewer should recompute representative fixtures, challenge threshold equalities and stop/target geometry, mutate every approval-sensitive field, inspect content canonicalization, and confirm no future layer is impersonated. Record reviewer, exact commit, outcome, PR and merge evidence only when they exist. Agent self-review is insufficient.

## Candidate verification

Recorded before candidate commit on 2026-09-14: 303 total tests passed, including 111 original Phase 1 cases, 60 Phase 2 cases, 48 Phase 3 cases and 84 focused Phase 4 cases. Ruff lint/format, strict mypy, lock validation, sdist/wheel build, source-tree health and fresh isolated offline wheel-install health passed. Repository-wide secret, forbidden-coupling, whitespace, ADR-field and Markdown/Obsidian-link checks passed. The sole pytest warning is the existing upstream Starlette `BlockingPortal` deprecation. No market experiment, profitability test or independent review is implied.
