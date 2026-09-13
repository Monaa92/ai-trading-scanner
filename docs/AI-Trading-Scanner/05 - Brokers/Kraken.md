# Kraken

Status: **DEFERRED safe placeholder specification**. No SDK, credentials, connection or order path is present.

Kraken is reserved for a separately registered future crypto experiment. Experiment 1 remains US equities only, and its immutable universe rejects CRYPTO regardless of adapter availability. A future experiment must define crypto instruments, 24/7 session policy, quantity/precision rules, risk constraints, market-data provenance and `SIMULATED_KRAKEN_SPOT` costs independently.

Future implementation must use `KrakenBrokerAdapter` behind [[01 - Architecture/Broker Architecture]]. It cannot introduce broker-specific branches into agents or activate LIVE/FULL_AUTO.
