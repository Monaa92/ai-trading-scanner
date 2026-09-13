# Broker capabilities

Status: **PLANNED contract; NOT IMPLEMENTED**. Canonical boundary: [[01 - Architecture/Broker Architecture]].

Agents express provider-neutral requirements. A versioned `BrokerCapabilities` snapshot declares supported asset classes, fractionality, quantity representation/increments, order types and time-in-force, paper/sandbox and market-data availability, execution environments, currencies, trading hours/session access, short selling, precision/minimums, linked protection and cancel/replace behavior.

UNKNOWN, stale or unsupported capability rejects the proposal before submission. No fallback changes quantity, order type, instrument, environment or risk. Capability availability never enables LIVE, CRYPTO or FULL_AUTO.

Experiment 1 requires EQUITY, USD, configured US-session behavior, its versioned quantity model and approved entry/protection/exit order semantics. Kraken capabilities cannot satisfy its immutable equity-only universe.
