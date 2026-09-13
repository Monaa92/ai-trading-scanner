# ADR-028 — Strategy and model are independent experiment dimensions

- Status: ACCEPTED as experiment-design policy; profiles remain unvalidated.
- Date: 2026-09-13.

## Context

Binding a strategy to a model would confound strategy comparison with model comparison and could give broader profiles unequal information.

## Decision

Version strategy profile and model/prompt configuration independently. Experiment 1 gives all four strategy profiles equivalent normalized information and hard constraints; NO_TRADE is first-class.

## Rationale

Independent factors permit interpretable strategy-only, model-only and registered factorial experiments.

## Consequences

Multi-Factor receives no extra raw data. No minimum trade count is imposed. Runs varying both factors are labeled accordingly.

## Alternatives considered

One model per strategy; reward trade frequency; give broad strategies private feeds.

## Conditions for revisiting

New experiment factors require an updated manifest/schema and preregistered comparison design.

Governance: [PROJECT_RULES](../../../PROJECT_RULES.md). Specification: [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]]. Index: [[00 - Project/Decisions/ADRs]].
