# Strategy versioning

Use semantic labels plus immutable content hashes. Initial template is `v0.1.0`, EXPERIMENTAL; no accepted trading version exists. Acceptance status is separate from semantic version. `v1.0.0` signifies a reviewed stable strategy contract, not profitability or live permission.

| Change | Version rule |
| --- | --- |
| Documentation/formatting with provably unchanged signals/execution | Patch may be used for a strategy artifact correction; code/docs-only changes can retain strategy hash when content is unaffected |
| Fix to implement already specified behavior | Patch strategy version **if decisions/results change**; still material, needs comparisons and changelog |
| Threshold, lookback, filter, indicator semantics, score, entry/exit change within same family | Minor strategy version; reset patch; new hypothesis and full comparison |
| Different family/direction/timeframe meaning, incompatible signal/risk interface or major causal contract | Major strategy version and ADR; not a way to discard unfavorable history |

Any change capable of altering eligibility, selection, sizing proposal, stops/targets, timing or outcomes is material even if one line or called a bug fix. Version parameters independently by hash and bind to strategy version. Risk/execution/cost/AI versions also change independently; changes affecting strategy semantics require both relevant versions. Preserve original results if a bug invalidates them and label superseded/invalid with reason.

Each change record includes date, hypothesis, predecessor/new version, exact old/new rules/config, datasets/period, common execution/cost/risk assumptions, before/after metrics and delta, decision ACCEPTED/REJECTED/EXPERIMENTAL, rationale, commit/PR references when they exist and reviewer. No invented commits/PRs. Once a backtester functions, compare against the previous accepted version per [PROJECT_RULES](../../PROJECT_RULES.md). Before the first acceptance compare the registered initial baseline and explicitly state no accepted predecessor.

Promote only with [[03 - Experiments/Experiment Framework]] evidence. A rejected version is never relabeled to hide its trial. Reusing a version label with different bytes is forbidden. See [[00 - Project/Decisions/Strategy Changelog]].
