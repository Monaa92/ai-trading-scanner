# Deterministic scanner

Status: **PLANNED; NOT IMPLEMENTED**.

The scanner is a deterministic pre-filter between normalized market intelligence and agent evaluation. It processes a canonical [[01 - Architecture/Market Data|NormalizedMarketSnapshot]], applies versioned liquidity, freshness, universe, session and cheap feature gates, and emits an ordered candidate batch with pass/reject reasons. It does not call an AI model, choose a strategy winner, size a position or submit an order.

Every eligible scan interval records coverage: instruments evaluated, candidates passed, candidates rejected by reason, missing/invalid inputs, snapshot hash and scanner/config version. A zero-candidate interval is evidence, not missing telemetry. Stable tie-breaks make replay independent of worker ordering.

The same candidate batch and normalized information availability are offered to all four Experiment 1 agents. Each strategy may return TRADE_PROPOSAL or first-class NO_TRADE. Deterministic filtering reduces avoidable inference calls without hiding opportunities from selected participants.
