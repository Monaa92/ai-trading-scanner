# Optional AI architecture

Status: future EXPERIMENTAL layer. Baseline mode is OFF. The deterministic pipeline must operate and be tested without any AI SDK, credentials or network call. See [[02 - Agents & Strategies/Model Benchmarking]] and [[00 - Project/Decisions/AI History]].

## Boundary and output contract

AI receives only an allowlisted, frozen, causally available candidate batch: IDs, deterministic features/units/readiness, strategy version/context, allowed market-regime context and input as_of. No secrets, broker write tools, account mutation APIs, future outcomes or arbitrary retrieved web context. Prompt content is data, never authorization. Provider adapter implements `evaluate(context, model_config, deadline)` behind [[01 - Architecture/System Components]]'s port.

Strict output schema, documented fields only:

| Field | Allowed meaning |
| --- | --- |
| schema_version / input_hash / batch_id | Must exactly match the requested schema/input/batch |
| candidates | Exactly one item per requested candidate ID, with no unknown/duplicate IDs |
| candidate_id | Must refer to a strategy-valid input candidate |
| decision | KEEP or REJECT only |
| rank_score | Finite bounded number in [0,1]; ranking signal, not calibrated probability |
| reason_codes | Array from a versioned bounded enum; unsupported codes reject response |
| explanation | Optional length-bounded plain text for display only, never parsed as a command |

Reject extra control fields such as quantity, equity, order instructions, stop price or risk limits. Validate response length/types, all required fields, bounds, input hash, versions and freshness. Parsed KEEP means only eligible for deterministic selection and **fresh risk assessment**. Ties use the same deterministic instrument/signal ID order as baseline. A late response is never applied to a newer snapshot. No instruction in explanation can trigger a tool/action.

AI may reject, rank or label setup quality. It may not calculate authoritative indicators, modify equity/stops/configuration, authorize a larger size, override strategy/risk failure or place orders directly. V1 AI has no sizing field; future “reduce exposure” requests would only lower an existing deterministic cap and require revalidation. Server-side adapters strip/reject unsupported fields; UI displays cannot become an alternative execution path.

## Failure contract

The treatment is **FILTER**: malformed, unavailable, stale, truncated, mismatched or timed-out AI results cause no new entry for that candidate/batch and a recorded AI failure. It does not silently fall back to baseline, which would contaminate the treatment. OFF remains the independent deterministic baseline; switching FILTER→OFF is a recorded new configuration/experiment segment, not a per-trade emergency default. Existing protection/exits remain fully deterministic and independent of AI.

| Failure | Handling |
| --- | --- |
| Hallucination/excessive confidence | Schema plus input-ID validation; explanations advisory only; rank score cannot bypass gates |
| Inconsistent/nondeterministic output | Retain raw and parsed response; deterministic replay consumes stored response; online re-call is a new observation |
| Malformed structure/context truncation | Reject entire batch, bounded error event, no partial silently accepted set |
| Provider outage/rate limit/latency | Deadline, bounded retry within expiry and same evaluation identity; otherwise veto batch and track failure/cost |
| Model update/deprecation | Pin snapshot where available; unknown change suspends treatment pending regression and version/history update |
| Prompt drift/config drift | Hash verification at startup and request; mismatch fails closed for treatment entries |
| Stale context | Compare input as_of/available_at/quote validity and deadline before selection; late results discarded |
| Accidental secret exposure | Allowlist/redact before transmission, never send credentials/account identifiers unnecessarily; stop requests and use incident procedure if exposure detected |

Provider/model identifier, actual returned model revision, model release info, prompt text/hash, schema, generation parameters (temperature/top-p/seed where supported), input/output, request ID, timing, tokens and cost are immutable experiment artifacts. Some providers cannot guarantee reproducibility even at low temperature; recorded-response replay proves system behavior, not that a remote model can reproduce the answer. All provider changes require [[00 - Project/Decisions/AI History]] and new comparative evidence.

## Participant and autonomy boundary

AI requests/responses are agent/participant/config-scoped even when sharing provider/cache infrastructure. Cache keys bind full input/model/prompt config; one agent's response or context cannot leak into another. AI cannot modify trading capital, AI budget, agent state, lockouts, submission mode, approval policy, execution environment, safety controls or frozen experiment artifacts and has no administrative credentials/tools. FULL_AUTO is not AI authority. Freeze model/prompt/generation policy per participant and record late/model-drift failures. Usage and pricing records follow [[04 - Costs & Economics/AI Inference Costs]].

Entry FILTER remains KEEP/REJECT ranking only. [[01 - Architecture/Execution/Trade Management]] describes a separate future versioned AI exit recommendation schema; it does not silently extend this entry schema or activate dynamic exits. Exit recommendation failures retain confirmed protection/scheduled exits. [[03 - Experiments/Counterfactual Analysis]] scores vetoes in separate ledgers, never adjusts actual equity from hypothetical outcomes.
