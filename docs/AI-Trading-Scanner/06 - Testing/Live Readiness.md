# Live-readiness gate

Status: **BLOCKED / NOT AUTHORIZED**. No tested implementation or performance evidence exists. A EUR50 amount does not waive this gate. Passing it permits an owner review of whether a small experiment is justified; it does not guarantee appropriateness or authorize automatic live activation.

## Evidence dossier

| Gate | Required evidence before recommendation |
| --- | --- |
| Frozen strategy | Accepted version and complete config/data/execution/AI manifests frozen throughout confirmatory paper period; material change restarts affected evidence collection |
| Trade and time coverage | Working floor of at least 300 closed prospective paper trades, plus independent day/regime/symbol coverage and prespecified precision/power targets; unresolved whether 300 is sufficient |
| Net performance | Positive out-of-sample and prospective net expectancy after realistic trading/FX costs, plus all-in economics reported; lower uncertainty bound and economically meaningful effect meet registered criteria |
| Profit factor | Above 1 and the stricter registered acceptance threshold with uncertainty; a zero-loss/undefined estimate cannot satisfy the gate |
| Drawdown | Maximum marked-equity drawdown and stress losses within owner-approved absolute-EUR and percentage limits fixed before evaluation; duration acceptable |
| Robustness | Prespecified symbol/regime/fold coverage, no unacceptable single-symbol/day concentration, no unknown multiple-testing burden or consumed-holdout presented as fresh |
| Model realism | Costs/spreads/latency/gaps/ambiguous fills stressed; paper-versus-captured replay discrepancies within registered tolerances, explained and reviewed |
| Risk correctness | Sizing/FX/rounding/cash/limits tests and adversarial property tests pass; no assumed leverage or settlement availability; fractional exit/protection actually verified |
| Order correctness | Duplicate/timeout/partial-fill/cancel-race/rejection tests pass; native or explicitly approved protection prevents uncontrolled unprotected quantities/over-closing |
| Recovery | Restart/reconnect and broker/internal cash-position reconciliation demonstrated, persistent emergency stop tested, stale data and outages block new exposure |
| Audit/security | Reconstructable complete decisions/fills, restorable evidence backups, secret/mode isolation, authentication, critical alerts and operator runbook verified |
| Review | No unresolved critical bugs or unknown open positions; independent competent review and explicit owner acceptance of measured limitations |
| Account feasibility | Current broker/account/jurisdiction/instrument permissions, settled-cash restrictions, minimums, costs and data licensing verified for actual intended account; no reliance on paper privileges |

Three hundred correlated trades in one regime can contain much less evidence than their count suggests. Use day/block uncertainty, effect-size/power planning, sufficient calendar duration and predefined adverse regimes; do not invent a universal confidence guarantee. Positive point estimates with wide intervals are inconclusive. Operational drills are required even if the market sample happens to avoid outages or gaps.

Thresholds still OPEN: minimum independent sessions/duration, power/precision, confidence level, minimum economic effect, PF margin above 1, absolute/percentage drawdown tolerance, concentration and discrepancy tolerances. An owner/research reviewer must set and preregister these using development evidence before confirmatory validation. Any unset required threshold keeps the gate blocked; do not back-fit thresholds to make a result pass.

If all evidence passes, prepare a signed/versioned dossier, define bounded capital/duration/unwind policy and obtain separate explicit user authorization. Verify live capabilities again, since paper support is not live permission. Never auto-enable live credentials or an execution switch. Any new critical defect, unexplained reconciliation difference, model/config drift or failed evidence reopens the gate. “Never proceed live” remains a valid permanent outcome.

## Additional agent and autonomy gates

Evidence is specific to the proposed agent/configuration/capital scale, management policy, data/run mode, execution environment, submission mode and approval policy. Four small paper ledgers do not authorize sharing one live account or scaling capital. Require isolation/no-double-allocation, parent-account constraints, exact manual-consent semantics, full-auto safety parity, permission-epoch/kill-switch tests, frozen-config enforcement and amendment/protection tests. Survival/leaderboard results are descriptive supplements, never replacements for net out-of-sample evidence.

Future equity progression is SIMULATION, separately configured IBKR PAPER, extended validation, separately authorized IBKR LIVE + MANUAL_APPROVAL, then only potentially IBKR LIVE + FULL_AUTO after a further deliberate owner decision for that specifically validated profile. Adapter availability, trade approval, AI response or agent configuration write cannot enable LIVE. Credentials remain separated and default-disabled; no agent may increase its own risk, clear its own locks or change PAPER to LIVE. AUTONOMOUS_EXPERIMENT in LIVE is unsupported by current [[01 - Architecture/Execution/Execution Modes]].
