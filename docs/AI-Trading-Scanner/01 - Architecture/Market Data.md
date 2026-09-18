# Market data and time

Status: Phase 2 canonical historical-data foundation **IMPLEMENTED**; provider ingestion, normalized intelligence snapshots, persisted revisions, aggregation and the full replay engine remain **PLANNED**. See [[08 - Research/External References]], [[02 - Agents & Strategies/Shared Agent Rules/Indicators]], [[01 - Architecture/Scanner]] and [[06 - Testing/Backtesting]].

## Implemented Phase 2 boundary

`src/ai_trading_scanner/market_data` implements immutable Pydantic records for instruments, half-open OHLCV bars and provenance. It supports only `1m`, `5m`, `15m` and `60m`. Each bar binds `InstrumentId`, versioned session ID, timeframe, UTC `start_at`/`end_at`, exact `Decimal` OHLCV, currency, optional source record, `received_at`, `available_at`, `ingested_at` and ACTUAL/MODELED availability. Naive timestamps, binary floats, invalid price/volume relationships, mismatched intervals and impossible timestamp ordering fail validation. Derived values must live in separate records.

`UsEquitiesCalendar` is the project-owned boundary over exactly pinned `exchange-calendars==4.13.2`. It resolves XNYS regular sessions using `America/New_York`, including DST, weekends, holidays and early closes, while returning UTC boundaries and a calendar-versioned local-date session ID. This local reference-data dependency is used because a handwritten weekday/holiday table would be fragile. It makes no network request. Other venue calendars can later implement a separate boundary; no 24×7 crypto calendar exists.

`DatasetValidator` currently validates one instrument/timeframe series. It retains every schema-valid supplied record in the result and reports structured findings. Invalid OHLC/volume/timezone/malformed records, duplicates, out-of-order rows, mixed instruments/timeframes and observations outside or mismatched to a session are fatal. Missing in-session intervals and excessive availability delay are warnings. A missing interval is reported and never synthesized; weekends, holidays and closed periods are excluded from expected intervals.

`DataProvenance` records provider, optional source dataset/version and universe reference, timeframe/source timezone, requested and actual coverage, ingestion time, explicit adjustment method, schema, availability mode/delay, calendar/normalizer versions, quality status, missing intervals and optional source checksum. Unknown provider details remain `None`; provider-defined adjustment requires a description. `CanonicalDataset.create` requires data, rejects fatal sequence findings and mismatched timeframe/availability policy, and requires detected warnings/missing intervals to match WARN provenance rather than disappear. For modeled availability, every bar must respect at least the declared delay.

Dataset identity is `sha256:` plus a SHA-256 hash over canonical JSON containing all provenance fields and bars ordered by instrument/start/timeframe. UTC uses a `Z` representation and decimals use exact base-10 strings. Input ordering does not affect identity. Observation, adjustment, availability, coverage, quality, calendar, normalization or ingestion-vintage changes do. The ID does not include itself or runtime object layout.

`CausalBarReader.slice_as_of` returns a frozen slice containing only records with `available_at <= as_of`, optionally restricted to instrument IDs. The slice has the source dataset ID, its own content hash and quality warnings whose causal visibility deadline has passed. Modeled missing-interval findings appear no earlier than interval end plus modeled publication delay. Phase 3 indicators preserve those findings in each result. The reader itself is not a replay scheduler or a normalized Market Intelligence snapshot and provides no strategy or trading behavior. The Phase 6 orchestration adapter calls it only after a market event is consumed, then intersects its as-of records with consumed event identities and the triggering session so an unconsumed same-time record remains invisible.

## Provider separation and canonical snapshot

Data sources feed a provider-neutral Market Data Layer, then a Market Intelligence Layer that creates one immutable `NormalizedMarketSnapshot` for a decision timestamp. Agents receive references to the same eligible snapshot and cannot query a broker, exchange or paid feed directly. Execution provider and market-data provider are independent configuration fields: a future IBKR adapter may execute orders while another source supplies data, and simulation may consume historical, captured or live external observations.

The snapshot carries schema/version/hash; exact instruments/universe; bars, quotes, status, news/fundamental/sentiment features where configured; `event_at`, `received_at`, `available_at` and snapshot `as_of`; provider and feed; market; REALTIME/DELAYED/HISTORICAL/CAPTURED status; consolidation level when known; subscription/source identifier; freshness and quality results; missing intervals; and references to raw provenance. Missing information is explicit and equal for all Experiment 1 agents. No agent receives extra raw data because its strategy is broader.

Paper or future live execution fails closed when its versioned freshness/quality requirements are unmet. SIMULATION retains the data status and may model delay but never relabel delayed or historical information as realtime. No paid subscription is required for the present architecture.

## Timestamp contract

Canonical bars represent half-open intervals `[start_at, end_at)` in UTC. A label in documentation such as “10:05 bar” means **ending at 10:05 America/New_York**; provider labels must be normalized explicitly. Preserve original labels. Use timezone-aware instants and IANA `America/New_York`, never a fixed EST offset. Store timestamp precision and a sequence tie-breaker; preserve raw nanoseconds if the database projection has lower precision.

Every observation has `event_at` (market occurrence), `received_at` (local observation), `available_at` (first eligible use after validation/finalization), `ingested_at`, provider/source/feed, revision and raw payload hash. Signals also have `decision_at`; intents have `created_at`, `submitted_at`; fills have `executed_at` and `received_at`. Late fills affect accounting when known; preserve economic execution time for reporting. No decision may retroactively use a record whose available_at is later than its decision_at.

Historical vendor downloads often lack original receipt/revision times. Tag them `availability_mode=modeled`, pin a nonnegative publication delay and snapshot vintage, and label resulting tests historical simulations, not exact as-observed replays. Captured paper streams use actual receipt histories. Never backdate a correction into an existing run.

## V1 normalization and finalization

Prefer retained 1-minute raw bars aggregated to 5-minute decision bars, with historical 5-minute imports allowed only under equivalent documented provenance. Sort by event interval, then revision. Validate positive prices, nonnegative volume, `low ≤ open/close ≤ high`, instrument/currency, expected interval and session membership. Persist raw records before normalization. Distinguish a verified no-trade interval from a feed gap; neither silently becomes a synthetic tradable candle.

At end + configured finalization grace, emit one decision-eligible snapshot only if required constituent intervals are accounted for and valid. `available_at` is at least end + grace and latest receipt/validation time. A missing constituent blocks that bar; a later backfill may repair future indicator state but does not generate retroactive orders. Reject stale candidates after their expiry. Updated data creates a new revision, invalidates dependent caches and repairs future state; never mutates recorded decisions or fills. Future signals consume the latest revision known then.

| Condition | V1 behavior |
| --- | --- |
| Exact duplicate | Deduplicate on provider/source ID or canonical key + payload hash; keep receipt provenance |
| Conflicting duplicate | New revision/quarantine; never arbitrarily choose one by arrival race |
| Out-of-order | Bounded reorder buffer; beyond watermark mark late, repair future state, no historical order creation |
| Missing bar | Flag unavailable; block required features/signals until contiguous readiness restored |
| Zero volume | Preserve if authentic; no assumed fill liquidity; VWAP contribution zero |
| Delayed/stale data | Store delay; prohibit real-time entry if beyond configured age; historical research may use explicit delay model |
| Halt/unknown trading state | Disable entries; preserve exits/protection; resume only after status and freshness reconciliation |
| Invalid OHLC or clock drift | Quarantine and lock affected scope; do not clip data into validity |
| Provider outage/rate limit | Backoff with bounded retries; report gap; no stale-data substitution |

Freshness thresholds, grace, reorder window and allowable delay are mandatory versioned operational parameters requiring measurement. Unknown is not fresh. Clock freshness compares receipt age and event age; a recently received old quote still fails.

## Sessions and aggregation

V1 signals/entries use regular trading hours only. Use a versioned exchange calendar with normal 09:30–16:00 New York sessions, actual holidays and early closes, and instrument-specific closures. Pre-market/after-hours may be retained but are excluded from V1 features, fills and session VWAP. Session ID is exchange-local trading date plus calendar version, not UTC date.

Anchor 5/15/60-minute aggregates at session open. A 60-minute bucket 09:30–10:30 is unavailable at 10:05. The 15-minute bucket 09:45–10:00 is the latest possible completed context at 10:05, and only if its available_at has passed; 10:00–10:15 is forbidden. Session-end shortened higher-timeframe buckets are marked partial and excluded from V1 higher-timeframe features. Daily context uses only prior completed, published sessions. No cross-session resampling or joining by calendar date alone.

## Instruments, actions and coverage

Permanent instrument IDs with effective-dated ticker mappings prevent symbol reuse/changes from merging securities. Record listing/delisting dates, exchange, asset type, currency and historical universe membership; current tradability is not evidence of past eligibility. SPY/QQQ and the requested stocks form a convenience development list with survivorship/selection limitations.

Execution always uses unadjusted executable prices. V1 intraday indicator state resets daily, reducing split discontinuities; historical relative-volume comparisons must use point-in-time split-normalized volume or be unavailable around unresolved actions. Store corporate-action announcement/known/effective timestamps and adjustment factors separately. Do not apply future split/dividend information as if known earlier. Previous-session price levels require compatible point-in-time units. Unresolved split/symbol/action data blocks affected experiments/entries.

No routine overnight holding is intended. Full dividend/overnight corporate-action accounting, delisting payouts and broad historical universe reconstruction are deferred. A run touching unsupported events is marked incomplete/ineligible for promotion, not silently stripped of losing rows. Paper unexpected overnight holdings require reconciliation of broker action/cash events before resuming. Dataset manifests declare action and survivorship coverage; no broad historical claim until coverage is adequate.

Provider interface is in [[01 - Architecture/System Components]]. Explicit feed selection is mandatory: never combine volume from different feed coverage or accept provider-default feed changes silently. Historical page cursors, requested/actual ranges, gaps and revision vintages are retained in [[01 - Architecture/Data Model]].
