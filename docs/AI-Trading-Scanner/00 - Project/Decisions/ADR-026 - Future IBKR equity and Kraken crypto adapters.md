# ADR-026 — Future IBKR equity and Kraken crypto adapters

- Status: ACCEPTED as future-provider direction; integrations are DEFERRED and not authorized.
- Date: 2026-09-13.

## Context

The original ADR-006 named Alpaca as the first intended market-data/paper provider. Current requirements select IBKR as the future equities execution path and Kraken for a separate future crypto experiment.

## Decision

Use SimulationBrokerAdapter for Experiment 1 once implemented; plan IBKRBrokerAdapter for future equity PAPER/LIVE progression and KrakenBrokerAdapter only for future crypto experiments. Adapter presence never enables LIVE or changes a universe.

## Rationale

Provider choice stays replaceable while the current equity experiment remains comparable and credential-free.

## Consequences

This supersedes only ADR-006's future execution-provider preference. Alpaca may remain a separately evaluated data/paper option. Experiment 1 remains US equities; Kraken cannot add crypto. IBKR LIVE remains behind separate readiness and owner decisions.

## Alternatives considered

Delete ADR-006; couple market data to execution; add crypto to the current comparison.

## Conditions for revisiting

Account-specific capability tests, costs, operational constraints and owner choice may change the future provider through another ADR.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specifications: [[01 - Architecture/Broker Architecture]], [[03 - Experiments/Experiment 1]]. Index: [[00 - Project/Decisions/ADRs]].
