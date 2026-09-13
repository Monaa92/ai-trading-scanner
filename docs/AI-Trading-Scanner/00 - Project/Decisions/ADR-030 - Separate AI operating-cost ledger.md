# ADR-030 — Separate AI operating-cost ledger

- Status: ACCEPTED as accounting/safety policy; ledger and budgets are not implemented.
- Date: 2026-09-13.

## Context

AI inference spend is an operating cost, while trading capital is portfolio property used for positions and risk.

## Decision

Maintain separate immutable AI usage/cost/budget records. AI costs never debit trading cash or affect sizing. Report Gross Trading, Net Trading and Net Economic P&L separately.

## Rationale

Separate resources prevent false trading losses/gains and make model economics auditable.

## Consequences

Budget hard stop blocks new AI calls/entries but preserves deterministic position protection and exits. Agents cannot top up themselves. No EUR 50 API budget is selected.

## Alternatives considered

Charge API calls to portfolio cash; treat provider credit as trading capital; automatic reload.

## Conditions for revisiting

Attribution/pricing/budget policies may evolve by version without changing historical ledgers.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specifications: [[04 - Costs & Economics/AI Inference Costs]], [[04 - Costs & Economics/API Budget Controls]]. Index: [[00 - Project/Decisions/ADRs]].
