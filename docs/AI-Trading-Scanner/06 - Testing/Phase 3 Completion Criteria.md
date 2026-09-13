# Full experiment technical completion criteria

Assessment date: 2026-09-13. Evidence inspected: repository tree, Phase 1–2 source/tests/manifests, documentation and Git state.

This note predates the gated roadmap’s narrower Phase 3 indicator milestone. It remains the later full-experiment technical gate and must not be used to describe the indicator foundation as incomplete. The Phase 3 indicator candidate and its review evidence are tracked in [[02 - Agents & Strategies/Shared Agent Rules/Indicators]] and [[06 - Testing/Phase 3 Independent Review]].

**FULL EXPERIMENT STATUS: NOT READY FOR TESTING.** The repository has an executable offline Phase 1–2 foundation and a Phase 3 indicator review candidate, but it has no experiment runner, scanner, four-agent interface, broker simulation, portfolio/risk/accounting, authoritative persistence or completed experiment. An indicator-foundation test is not end-to-end experiment evidence.

| Completion criterion | Classification | Repository evidence / gap |
| --- | --- | --- |
| 1. Executable experiment runner | NOT IMPLEMENTED | The CLI has health only; no experiment entry point. |
| 2. Canonical normalized market snapshot | PARTIAL | Immutable canonical bars and causal `MarketDataSlice` are implemented; the Market Intelligence `NormalizedMarketSnapshot` is not. |
| 3. Deterministic scanner | NOT IMPLEMENTED | Contract in [[01 - Architecture/Scanner]] only. |
| 4. Four-agent decision interface with TRADE/NO_TRADE | NOT IMPLEMENTED | Strategy/profile and data-model specifications only. |
| 5. Decision capture and replay validity | NOT IMPLEMENTED | Contract in [[03 - Experiments/Decision Replay]] only. |
| 6. SimulationBrokerAdapter lifecycle | NOT IMPLEMENTED | Required behavior in [[05 - Brokers/Simulation]] only. |
| 7. Authoritative persistence and restart | NOT IMPLEMENTED | Conceptual data model only; no database/migrations. |
| 8. Reproducible completed run | NOT IMPLEMENTED | No run, manifest or trace exists. |
| 9. Deterministic market fixture | PARTIAL | Small synthetic regular-session bars and edge-case constructions test Phase 2 data behavior; no executable experiment fixture exists. |
| 10. End-to-end fixture execution | NOT IMPLEMENTED | The offline unit suite exists, but no full decision/risk/order/fill/accounting trace exists. |
| 11. Per-agent capital/portfolio isolation behavior | NOT IMPLEMENTED | Strong invariant specified; no executable ledger tests. |
| 12. EUR 50/100/250/500/1,000 capital sweep | NOT IMPLEMENTED | Experiment contract only. |
| 13. Complete observability and metrics output | NOT IMPLEMENTED | Schema requirements only. |
| 14. Tested safe failure behavior | PARTIAL | Configuration and malformed historical-data failures are tested; trading/execution failure paths do not exist. |
| 15. Typed configuration/startup validation | IMPLEMENTED | Phase 1 Pydantic/TOML startup rejects unsafe capabilities and unknown fields. |
| 16. No secrets, credentials or external dependency for simulation | PARTIAL | Foundation health/tests run offline without credentials; no SimulationBroker exists. |
| 17. Documented one-command test/experiment entry | PARTIAL | Locked test and health commands exist; no experiment command exists. |

No placeholder, TODO or stub is reported as completed production implementation. IBKR and Kraken are future adapter specifications. Simulation is the only current experiment environment but its adapter still must be built. Phase 1 and Phase 2 are complete; the deterministic indicator candidate awaits independent review, followed by the remaining gated sequence in [[00 - Project/Roadmap]].
