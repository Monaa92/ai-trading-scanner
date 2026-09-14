# Phase 4 completion criteria

Status: **IMPLEMENTED AND LOCALLY VERIFIED; INDEPENDENT REVIEW REQUIRED.**

Phase 4 is complete only when the exact candidate satisfies this invariant: given identical causal market/indicator inputs, strategy configuration and agent-scoped context, evaluation deterministically returns an auditable `NO_TRADE` or complete immutable trade proposal without future information, I/O, account mutation or order placement.

| Criterion | Candidate evidence |
| --- | --- |
| Four explicit strategy identities | Registered Momentum, Mean Reversion, Breakout and Multi-Factor configuration types and IDs |
| Strategy/model separation | No model field or AI import in configuration/evaluation; `StrategyId` and `ModelId` remain separate |
| Agent attribution and fairness | Context, decision and proposal carry `AgentId`; common slice and six indicator configuration IDs are tested equal across four participants |
| First-class NO_TRADE | Discriminated immutable outcome with structured strategy-only reasons; risk/approval/broker rejection absent |
| Complete proposal intent | Long side, entry reference, future-risk sizing, stop, objective, management, economics, evidence, expiry and authority context |
| Approval-sensitive immutability | Proposal/mandate/config/decision SHA-256 content identities; material mutations require new identity |
| Causal and quality safety | As-of, bar availability, slice hash, indicator alignment/readiness, warning retention, gap and fatal paths validated |
| Determinism | Decimal arithmetic, canonical JSON, repeated evaluation and appended-future prefix tests |
| Cost awareness | Separate versioned supplied round-trip estimate; missing or edge-eliminating costs produce NO_TRADE |
| Scope boundary | No scanner, risk, portfolio, broker, AI, persistence, order or execution implementation |

The baselines are `BASELINE_RESEARCH_V1` / `0.1.0`, EXPERIMENTAL and uncalibrated. Passing these tests proves contract behavior, not profitability or readiness to trade. See [[02 - Agents & Strategies/Experiment 1 Strategy Profiles]] and [[06 - Testing/Phase 4 Independent Review]].

Candidate verification on 2026-09-14: 303 total tests passed, comprising 219 Phase 1–3 regressions and 84 focused Phase 4 cases. Ruff lint/format, strict mypy, lock validation, package build, source and isolated installed-package health, scope/security scans, whitespace, ADR fields and documentation links passed. The only test warning is an upstream Starlette `BlockingPortal` deprecation.
