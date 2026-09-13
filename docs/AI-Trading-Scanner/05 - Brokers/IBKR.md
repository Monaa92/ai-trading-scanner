# IBKR

Status: **DEFERRED safe placeholder specification**. No SDK, credentials, connection or account configuration is present.

IBKR is the planned future equities execution provider. Intended progression is SIMULATION -> IBKR PAPER -> separately authorized IBKR LIVE + MANUAL_APPROVAL -> potentially IBKR LIVE + FULL_AUTO only after another deliberate owner decision and evidence for that exact profile.

Future implementation must translate only through `IBKRBrokerAdapter`, discover and certify account/instrument capabilities, preserve internal agent allocations, reconcile ambiguous submissions and keep IBKR market data optional. Adapter availability never selects LIVE. See [[01 - Architecture/Broker Architecture]], [[05 - Brokers/Broker Capabilities]] and [[06 - Testing/Live Readiness]].
