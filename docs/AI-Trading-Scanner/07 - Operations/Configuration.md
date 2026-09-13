# Configuration and version manifests

Status: specification. Configuration is data, separately versioned from code; no runtime files are created in Phase 0.

| Namespace | Required contents | Classification |
| --- | --- | --- |
| strategy | Rule IDs, indicator periods, pullback/stop/target definitions, lookbacks, candidate ordering | HYPOTHESIS |
| risk | 1% risk ceiling, 3% daily ceiling, one position, three filled entries, net RR ≥ 2, no leverage/shorting, cash buffer | RISK CONSTRAINT; buffer provisional |
| session | Calendar version, RTH policy, entry cutoff, flatten lead time, timezone | Engineering; timing buffers provisional |
| quality | Quote/FX/account age ceilings, reorder window, finalization grace, clock drift budget | PROVISIONAL operational constraints |
| execution | Supported order types, latency, ambiguity policy, fill capacity, expiry | Versioned engineering/model assumptions |
| costs | Commission/fees, FX conversion charges, spread source/proxy, slippage and impact model | REQUIRES VALIDATION |
| data | Provider, explicit feed, raw/adjusted mode, universe/version, dataset manifest | Engineering/provenance |
| AI | Mode OFF/FILTER, provider/model snapshot, prompt/schema hashes, deadline, generation config | EXPERIMENTAL |
| run | HISTORICAL_REPLAY/LIVE_FEED/CAPTURED_REPLAY and clock/source identity | Engineering |
| environment | SIMULATION/PAPER; adapter/account identity and secret references when applicable | Engineering; LIVE disabled |
| authority | SIGNAL_ONLY/ORDER_ENABLED plus MANUAL_APPROVAL/FULL_AUTO | Owner-controlled; FULL_AUTO never implies LIVE |
| experiment | NORMAL/EXPERIMENT context and optional immutable experiment type/registration | Engineering/research governance |

Parameters without defensible defaults are required-but-unset. In particular pullback lookback, stop buffer, RVOL history, strategy filters, fee/FX models, latency, spread and freshness ceilings must be registered before relevant execution. Selecting numbers for a fixture does not select production values. A completeness validator blocks runs with missing mandatory fields, unknown keys, NaN/infinity, invalid units, inconsistent ranges or incompatible capabilities. Feature flags cannot disable risk controls. Risk values may be more restrictive within an approved profile; loosening the baseline requires a material risk review/history, not an ordinary experiment sweep.

Resolve configuration once; serialize canonically with sorted keys, explicit units/currencies, decimal strings, UTC instants and a schema version; hash with SHA-256. Retain the complete non-secret resolved artifact, not just a hash. Never overwrite an artifact behind an existing ID. Environment variables supply secret references/environment identity, not hidden strategy overrides. Mid-session behavior changes require a controlled stop, new manifest and review; open positions retain original intent/version linkage and cannot have their stops widened through a reload.

Each run manifest binds code commit and dirty patch hash/archive if applicable, dependency lock/runtime/platform, strategy/indicator/feature versions, parameter and risk profiles, dataset ID and raw content hashes, provider/feed, calendar and timezone database version, range/universe, execution/cost/slippage/FX models, configuration hash, AI artifacts, random seeds, metric implementation version and experiment/split IDs. An uncommitted run must not claim its commit alone reproduces it. This initial pass has no run manifest or executed experiment.

Startup checks environment allowlist, capability snapshot, valid manifest hashes, healthy ledger/reconciliation and single-writer lease. Invalid configuration fails closed for new exposure; controlled exits retain the last verified exit policy. See [[07 - Operations/Security & Secrets]] and [[01 - Architecture/Execution/Order Lifecycle]].

## Composed agent configuration

AgentConfigVersion binds strategy/parameters, risk fraction/monetary/daily/portfolio/position/trade limits, allocation/currencies, universe/session, management, AI, data/run mode, execution environment, submission mode, approval policy, NORMAL/EXPERIMENT context, optional experiment registration, approval TTL/mandate and lifecycle/safety policy. [[01 - Architecture/Execution/Execution Modes]] owns valid combinations. EUR50 and baseline risk numbers are profile values, not universal schema constants.

Frozen manifests bind exact participant hashes and adaptive algorithm bounds; agents cannot update config or accept a changed model alias. NORMAL changes such as risk 0.50%→0.75% record old/new values, actor, requested/effective times, rationale, checks and a new segment. Initial cutover requires flat/reconciled state at session boundary, invalidated proposals and new permission epoch. See [[01 - Architecture/Portfolio Accounting/Capital Allocation]] and [[03 - Experiments/Autonomous Experiments]].
