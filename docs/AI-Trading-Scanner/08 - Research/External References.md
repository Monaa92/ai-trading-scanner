# External references and verification boundaries

Checked 2026-09-13 against official provider documentation. These establish design concerns, not account entitlements, working credentials or verified integrations. Recheck and run contract tests before implementation relies on any capability.

| Source | Design implication |
| --- | --- |
| [Alpaca Market Data FAQ](https://docs.alpaca.markets/us/docs/market-data-faq) | IEX and consolidated SIP coverage differ; provider bars label interval starts. Normalize intervals and pin feed provenance. |
| [Alpaca real-time stock data](https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data) | Bar updates can arrive after initial publication; streaming daily aggregates can be incomplete. Retain revisions/availability and enforce completion. |
| [Alpaca fractional trading](https://docs.alpaca.markets/us/docs/fractional-trading) | Eligibility and order constraints are capability inputs. The page currently lists several fractional DAY order types but also contains narrower market-order wording. Treat exact fractional protection/bracket combinations as unverified until tested; do not infer support. |
| [Alpaca order documentation](https://docs.alpaca.markets/us/docs/orders-at-alpaca) | Market orders do not guarantee price; limits do not guarantee fills. Keep price and execution uncertainty separate. |
| [Alpaca paper trading](https://docs.alpaca.markets/us/docs/paper-trading) | Paper fills are simulated and omit important live effects including queue position, impact and some costs. A paper balance is not proof that a EUR 50 cash-constrained account can execute the same trades. |
| [IBKR API documentation](https://ibkrcampus.com/campus/ibkr-api-page/) and [TWS paper overview](https://interactivebrokers.github.io/tws-api/introduction.html) | Paper exists with limitations; account/product/order capabilities must be discovered and certified rather than generalized. No IBKR integration exists. |
| [Kraken API Center](https://docs.kraken.com/) and [client order identifiers](https://docs.kraken.com/api/blog/cl-ord-id/) | Spot execution and client identifiers inform the future adapter boundary. Kraken is not authorized for Experiment 1 and no connection exists. |

Project policies such as conservative OHLC ambiguity, the equity loss-lock formula and statistical promotion rules are explicit design recommendations, not claims that Alpaca or a regulator requires them. Legal/account eligibility, local availability, settlement restrictions, licensing, costs, instrument access and live permissions remain OPEN QUESTIONS to verify when relevant. No recommendation to purchase a subscription or enable live trading is made.
