# Phase 2 independent review

Status: **REVIEW REQUIRED; no human approval is recorded.** This checklist accompanies the `review/phase-2-market-data` candidate. It does not authorize a merge, trading, broker connection, or data-provider connection.

| Area | Implementation | Behavioral tests | Intended invariant | Failure impact |
| --- | --- | --- | --- | --- |
| Timestamp and bar intervals | `market_data/models.py` | `test_market_records.py` | Bars are immutable UTC `[start_at, end_at)` intervals with only supported timeframes. | Misaligned or mutable records can change historical results. |
| Event, receipt, availability and ingestion time | `models.py` | `test_market_records.py`, `test_causal_reader.py` | `event_at` is bar end; receipt, eligibility and ingestion remain distinct and ordered. | Future knowledge or impossible audit history can enter research. |
| ACTUAL versus MODELED availability | `models.py`, `dataset.py` | `test_market_records.py`, `test_dataset_identity.py` | ACTUAL requires receipt; MODELED requires explicit nonnegative delay, enforced for every bar. | Historical simulation can overstate information timeliness. |
| Completed-bar and look-ahead boundary | `models.py`, `dataset.py` | `test_market_records.py`, `test_causal_reader.py` | A bar is unavailable before end and until `available_at`; reader exposes only `available_at <= as_of`. | Strategies may see incomplete or future bars. |
| XNYS session calendar and DST | `calendar.py` | `test_market_calendar.py` | Version-pinned local XNYS calendar defines UTC open/close and local-date session identity. | Incorrect session membership or shifted decisions around DST. |
| Weekend, holiday and early-close handling | `calendar.py`, `quality.py` | `test_market_calendar.py`, `test_dataset_quality.py` | Legitimate closure is not a data gap; early close limits valid intervals. | False data-quality failures or use of nonexistent market time. |
| Missing interval handling | `calendar.py`, `quality.py`, `dataset.py` | `test_dataset_quality.py`, `test_dataset_identity.py` | Expected in-session gaps are warnings, never synthesized, and must be retained in provenance. | Artificial continuity or hidden coverage limitations. |
| Duplicate and ordering checks | `quality.py`, `dataset.py` | `test_dataset_quality.py`, `test_dataset_identity.py` | Duplicate and out-of-order records are fatal to a canonical dataset. | Double counting or non-deterministic replay. |
| OHLC and volume validation | `models.py`, `quality.py` | `test_market_records.py`, `test_dataset_quality.py` | Prices are finite positive decimals with valid OHLC relations; volume is finite and nonnegative. | Invalid inputs contaminate indicators and decisions. |
| Fatal versus warning findings | `quality.py`, `dataset.py` | `test_dataset_quality.py`, `test_dataset_identity.py` | Fatal findings block datasets; warnings remain explicit and provenance-bound. | Unsafe data can be treated as clean. |
| Provenance and adjustments | `models.py`, `dataset.py` | `test_market_records.py`, `test_dataset_identity.py` | Source, coverage, timezone, availability, calendar, normalizer, quality and adjustment facts are immutable; provider-defined adjustments require detail. | Results cannot be audited or compared fairly. |
| Deterministic dataset identity | `dataset.py` | `test_dataset_identity.py` | Canonical SHA-256 identity is order-independent and changes with content or relevant provenance. | Different datasets can be confused as equivalent. |
| Four-agent canonical equivalence | `dataset.py` | `test_causal_reader.py` | Equivalent consumers receive the same immutable slice, dataset ID and content hash at the same `as_of`. | Future agent comparisons can have unequal information. |

Reviewer focus: inspect rejection paths, timestamp comparisons, quality/provenance consistency, calendar edge conditions, and whether later strategy/replay code is constrained to `CausalBarReader`/`MarketDataSlice` rather than unrestricted future data.

Required review record before merge: reviewer identity, approval date, reviewed commit hash, scope, failure-path observations, any findings, and explicit approval or rejection. Record it without rewriting this candidate's historical facts.
