# Broker-agnostic execution boundary

Status: architecture specification. No adapter, broker SDK, credentials, connection or order submission exists in the repository. [[05 - Brokers/Simulation]] describes the required Phase 3 implementation; IBKR and Kraken remain safe future placeholders.

Trading agents emit `TRADE_PROPOSAL` or `NO_TRADE`; they never import an SDK, construct broker requests, query broker accounts or invoke exchange APIs. The application execution coordinator alone may call `BrokerAdapter` after deterministic risk, approval/authority and [[01 - Architecture/Execution/Safety Gate]] checks. Provider DTOs terminate at the adapter boundary.

```text
Market Data Sources
  -> Market Data Layer
  -> Market Intelligence Layer
  -> Normalized Market Snapshot
  -> Agent A / B / C / D
  -> TRADE_PROPOSAL or NO_TRADE
  -> Risk Engine
  -> Approval / Execution Policy
  -> BrokerAdapter
  -> Simulation / future IBKR / future Kraken
```

Market data is a separate port. An execution adapter may expose whether the broker can supply data, but agents still consume only normalized, provenance-bearing snapshots. This permits IBKR execution with another data provider, simulation from historical or live external data, and a future Kraken experiment without changing strategy code.

## BrokerAdapter contract

The versioned asynchronous contract contains at minimum:

| Method | Contract result |
| --- | --- |
| `get_account_state(scope)` | Normalized cash, buying power, currency, restrictions, revision and freshness for the configured execution account; internal agent allocations remain authoritative. |
| `get_positions(scope)` | Normalized broker positions with stable instrument identifiers, quantities and as-of/reconciliation metadata. |
| `submit_order(order_intent, idempotency_key, safety_evidence)` | Accepted/rejected/unknown acknowledgement. Requires immutable agent/account/allocation/participant attribution and an execution-environment-scoped idempotency key. |
| `cancel_order(order_identity, idempotency_key)` | Accepted/rejected/unknown cancellation result; ambiguous results require reconciliation. |
| `get_order_status(order_identity)` | Normalized order/fill state while retaining raw provider references and immutable execution IDs. |
| `health_check()` | Connectivity/session/clock/reconciliation status and freshness. Health never grants authority. |
| `get_capabilities(account, instrument, environment)` | Versioned, timestamped capability snapshot or explicit UNKNOWN/UNSUPPORTED result. |

Future reconciliation also needs bounded queries for orders and fills by internal client identity and time range. No adapter may raise risk, change terms, substitute instruments, choose an environment, select credentials, merge portfolios or infer approval.

## Capability model and safe failure

`BrokerCapabilities` records supported asset classes, fractional support, quantity representation and increments, order types/time-in-force, paper/sandbox availability, market-data availability, trading hours/session access, currencies, short-selling support, supported execution environments, precision/minimums, linked-protection semantics and cancel/replace/idempotency behavior. It carries provider, account class, instrument scope, source, checked time, expiry, schema and adapter version.

Capability validation happens before capital reservation and again before dispatch where freshness requires it. UNKNOWN, expired or incompatible capability produces an auditable rejection and no network mutation. Agents never branch on `IBKR` or `KRAKEN`; they request domain requirements such as asset class EQUITY, fractional quantity and LIMIT/STOP support. The coordinator matches those requirements to the snapshot.

Provider documentation is discovery evidence, not certification. Future account-level contract tests must verify exact quantity, order, protection and session combinations. IBKR documentation confirms that paper trading exists with limitations and that capabilities such as order type and fractionality vary by product, order and account; therefore this design never assumes them globally. Kraken documents Spot APIs and client order identifiers, but no Kraken capability is authorized for Experiment 1.

## Adapter portfolio and status

| Adapter | Current state | Intended scope |
| --- | --- | --- |
| `SimulationBrokerAdapter` | **NOT IMPLEMENTED**; Phase 3 contract specified | Deterministic no-network fills, costs, order lifecycle, capabilities and isolated logical accounts for current experiments. No credentials. |
| `IBKRBrokerAdapter` | **DEFERRED placeholder specification only** | Future primary equities execution path: IBKR PAPER, then separately authorized LIVE + MANUAL_APPROVAL, and only later a separately authorized LIVE + FULL_AUTO profile. |
| `KrakenBrokerAdapter` | **DEFERRED placeholder specification only** | Future crypto experiments through the same boundary. It cannot add CRYPTO to Experiment 1 or enable LIVE. |

Adding an adapter to a registry makes only a named implementation discoverable. It does not activate an environment, credentials, instruments or submission authority. `PAPER + FULL_AUTO` remains a valid independent combination. FULL_AUTO never implies LIVE.

ADR-006 selected Alpaca as the first intended data/paper provider in the original design. [[00 - Project/Decisions/ADR-026 - Future IBKR equity and Kraken crypto adapters]] supersedes only that future execution-provider preference: IBKR is now the planned equities adapter, while Alpaca may remain a separately evaluated market-data or paper option. ADR-001–016 remain unchanged and no integration has been built.

## Isolation, idempotency and reconciliation

A shared broker connection is infrastructure, not a portfolio. Each order, fill, fee, position lot, reservation and reconciliation event carries `agent_id`, `allocation_id`, `account_id`, `participant_id` when applicable, `run_id`, environment and intent/client identity. Internal per-agent cash, positions, realized/unrealized P&L, costs, risk state and performance history remain authoritative. Parent-account checks prevent two agents from spending the same real allocation.

Idempotency scope includes adapter, environment, execution account, agent, allocation and immutable intent identity. Retries never manufacture new identities. Conflicting duplicate fills, unexplained positions/cash or unattributed netting lock affected scope. Shared-account same-symbol netting remains unsupported until ownership, protection and allocation tests prove it safe.

## Evidence sources

The capability design was checked on 2026-09-13 against official [IBKR API documentation](https://ibkrcampus.com/campus/ibkr-api-page/), its [paper-trading/TWS setup documentation](https://interactivebrokers.github.io/tws-api/introduction.html), and the official [Kraken API Center](https://docs.kraken.com/). These links do not constitute account certification or permission to connect.
