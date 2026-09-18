# ADR-034 — Atomic deterministic simulation execution

- Status: ACCEPTED as the target Phase 6 architecture; implementation beyond the accepted foundation, scheduler and causal orchestration remains pending.
- Date: 2026-09-17.

## Context

The accepted Phase 6 foundation defines immutable orders/fills/accounting contracts, canonical event order and a leased deterministic scheduler. Accepted causal orchestration connects Phase 2–5 through a reservation, but it does not resolve orders, post fills, consume/release reservations, maintain a complete position lifecycle or survive process loss. Implementing those concerns as independent side effects would permit cursor/accounting divergence, duplicate fills and unverifiable recovery.

## Decision

Complete Phase 6 as an event-sourced deterministic SIMULATION pipeline. The scheduler remains the only cursor authority; pure resolvers derive order/fill/protection outcomes from frozen profiles and causally released evidence; one fenced economic transaction commits the cursor, command identity, reservation transition, cash/cost/FX legs, position/trade changes, checkpoint and authoritative result evidence together. Failure leaves all authoritative state unchanged. Every command/effect has a durable idempotency key and expected prior revision.

Use conservative, versioned V1 execution: long-only market orders, full fill or typed terminal no-fill, next eligible same-XNYS-session bar open, no randomness, no scale-in, fixed stop/target and stop-first OHLC ambiguity. Missing bars are not synthesized and unresolved terminal exposure makes a result incomplete. Costs remain explicit components; causal FX observations support multi-currency reconciliation without a hard-coded rate.

Persist a frozen manifest, append-only hash-linked event/evidence log, monotonic scheduler high-water mark and economic/policy checkpoints. Restart validates the chain, rebuilds projections and refuses rollback or divergence. Process-local mode is diagnostic and cannot supply serious-test promotion evidence.

## Rationale

One transaction boundary preserves the accepted exception-atomic philosophy across execution and accounting. Pure deterministic resolvers keep market assumptions reviewable. Durable journal facts make replay, reconciliation and crash recovery possible without trusting mutable summaries.

## Consequences

Implementation must add a transaction-capable journal/repository boundary before durable historical evidence is accepted. Costs, FX and protection rules become required run identities. The initial profile is deliberately conservative and may produce no-fill/incomplete outcomes. Partial fills, limit orders, stochastic models, dynamic management, shorting and higher-resolution ambiguity resolution require new versions rather than silent changes.

This decision adds no broker adapter, network call, PAPER/LIVE authority or external order submission. Future broker operations continue through [[00 - Project/Decisions/ADR-025 - Broker-agnostic execution boundary]].

## Alternatives considered

Independent mutable services for orders, fills and accounting; cursor-first commits; optimistic same-bar fills; best-case OHLC path selection; inferred FX; mutable result summaries; and treating local checkpoints as durable anti-rollback evidence.

## Conditions for revisiting

Revisit when higher-resolution data, validated liquidity evidence, partial fills, broker-specific execution or a different durable store is required. Preserve existing execution profiles, journal schemas and run artifacts and compare changes under identical causal inputs.

Specification: [[01 - Architecture/Execution/Replay and Simulation Architecture]]. Completion gate: [[06 - Testing/Phase 6 Completion Criteria]]. Index: [[00 - Project/Decisions/ADRs]].
