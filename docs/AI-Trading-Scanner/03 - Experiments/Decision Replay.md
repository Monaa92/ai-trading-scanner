# Decision replay and inference reuse

Status: **PLANNED validity contract; NOT IMPLEMENTED**.

Record the strategy decision stream separately from portfolio execution. A decision artifact binds normalized snapshot hash, candidate, strategy/model/prompt/config versions, causal inputs, output and inference-cost record. A capital arm may reuse it only when the strategy decision is provably independent of portfolio state and the replay contract version declares all portfolio-derived inputs absent.

Replay is equivalent only when starting capital, available cash, prior positions, position sizing, risk state, exposure, allocation capacity and past executions cannot change the strategy or model input/output. Execution and risk then evaluate the same decision artifact independently at each capital level. Reuse avoids model calls solely caused by capital variation while preserving separate simulated outcomes.

If any portfolio-derived value enters the prompt, features, strategy state, candidate selection, learning/adaptation, position-management decision or available opportunity set, mark `replay_equivalence=FALSE` with reason and run a separate inference experiment. A post-hoc claim based on coincidentally equal outputs is invalid. Partial reuse is allowed only for the capital-independent prefix with a new derived-decision identity.

Tests must include a stateless strategy that replays identically and a stateful strategy whose available cash/position changes the next decision and therefore forces separate inference. See [[03 - Experiments/Counterfactual Analysis]] for ledger separation.
