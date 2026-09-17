# Architecture decisions

Recorded 2026-09-13. ACCEPTED means adopted for this initial design, not validated profitability, deployed behavior or live permission. [PROJECT_RULES](../../../PROJECT_RULES.md) remains authoritative. Amend with a superseding ADR, retaining previous rationale and links.

- [[00 - Project/Decisions/ADR-001 - US equities and ETFs first]]
- [[00 - Project/Decisions/ADR-002 - 5-minute primary timeframe for V1]]
- [[00 - Project/Decisions/ADR-003 - Long-only V1]]
- [[00 - Project/Decisions/ADR-004 - Initial 1 percent risk-per-trade rule]]
- [[00 - Project/Decisions/ADR-005 - AI cannot override deterministic risk controls]]
- [[00 - Project/Decisions/ADR-006 - Alpaca as initial market-data and paper-trading provider]]
- [[00 - Project/Decisions/ADR-007 - Material strategy changes require comparative validation]]
- [[00 - Project/Decisions/ADR-008 - EUR50 paper account before any live-capital experiment]]
- [[00 - Project/Decisions/ADR-009 - Deterministic calculations are authoritative over AI]]
- [[00 - Project/Decisions/ADR-010 - PostgreSQL as intended persistent datastore]]
- [[00 - Project/Decisions/ADR-011 - Provider abstractions for market data broker and AI]]
- [[00 - Project/Decisions/ADR-012 - Final holdout data must not be repeatedly optimized against]]
- [[00 - Project/Decisions/ADR-013 - Causal hybrid backtesting and conservative ambiguity]]
- [[00 - Project/Decisions/ADR-014 - Daily loss includes unrealized equity changes]]
- [[00 - Project/Decisions/ADR-015 - Durable intents and capability-gated protection]]
- [[00 - Project/Decisions/ADR-016 - Session-reset indicator initialization]]

Each ADR records status, date, context, decision, rationale, consequences, alternatives and revisit conditions. Revisit decisions when evidence warrants it, with affected strategy/risk/AI/execution versions and comparative tests rather than silent implementation changes.

## Multi-agent extension — 2026-09-13

- [[00 - Project/Decisions/ADR-017 - Multi-agent isolation]]
- [[00 - Project/Decisions/ADR-018 - Explicit execution modes]]
- [[00 - Project/Decisions/ADR-019 - Frozen autonomous experiment configurations]]
- [[00 - Project/Decisions/ADR-020 - Immutable manual approvals]]
- [[00 - Project/Decisions/ADR-021 - Normal operation and experimental profiles]]
- [[00 - Project/Decisions/ADR-022 - Isolated capital allocation]]
- [[00 - Project/Decisions/ADR-023 - Final deterministic safety gate]]
- [[00 - Project/Decisions/ADR-024 - Versioned trade management]]

ADRs 017–024 extend the initial design. ADR-021 clarifies that ADR-004/008/014 values describe the initial experiment profile; it does not loosen that profile. ADR-020/023 refine ADR-015's authorization before durable submission; its no-duplicate/durability guarantees remain. No prior ADR or research result is deleted.

## Broker, economics and recovery extension — 2026-09-13

- [[00 - Project/Decisions/ADR-025 - Broker-agnostic execution boundary]]
- [[00 - Project/Decisions/ADR-026 - Future IBKR equity and Kraken crypto adapters]]
- [[00 - Project/Decisions/ADR-027 - Versioned transaction costs in decisions]]
- [[00 - Project/Decisions/ADR-028 - Strategy and model are independent experiment dimensions]]
- [[00 - Project/Decisions/ADR-029 - Capital sweep and replay equivalence]]
- [[00 - Project/Decisions/ADR-030 - Separate AI operating-cost ledger]]
- [[00 - Project/Decisions/ADR-031 - Durable recovery by storage class]]
- [[00 - Project/Decisions/ADR-032 - Strategy-specific profit management]]

ADRs 025–032 are design decisions only. ADR-026 supersedes only ADR-006's future execution-provider preference while retaining ADR-006 and the provider-abstraction principle. ADR-032 extends ADR-024: the fixed baseline remains unchanged and dynamic policies still require separate validation. No adapter, cost schedule, budget, strategy or storage service is implemented by these decisions.

## Phase 6 foundation — 2026-09-14

- [[00 - Project/Decisions/ADR-033 - Deterministic Phase 6 replay foundation]]

ADR-033 specifies the content-identified discrete-event ordering, next-eligible-bar-open fill boundary, explicit no-double-count cost treatment and canonical local event serialization for the Phase 6 foundation. It does not mark Phase 6 complete or authorize broker, PAPER or LIVE execution.

## Phase 6 replay/execution and 4+1 architecture — 2026-09-17

- [[00 - Project/Decisions/ADR-034 - Atomic deterministic simulation execution]]
- [[00 - Project/Decisions/ADR-035 - Autonomous survival economic entity]]

ADR-034 defines the target atomic order/fill/accounting, causal cost/FX and durable recovery architecture. ADR-035 defines Agent 5 as one conserved economic entity with a frozen adaptation envelope, opportunity-aware active-survival objective and irreversible economic death. Both are design decisions only. They do not implement replay/execution, Agent 5, AI, broker connectivity, PAPER or LIVE authority and do not add Agent 5 to Experiment 1.
