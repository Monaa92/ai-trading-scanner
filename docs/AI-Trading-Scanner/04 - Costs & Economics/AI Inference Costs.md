# AI inference cost accounting

Status: **architecture and metric contract; NOT IMPLEMENTED**.

Trading capital and AI/API budget are different resources and use separate ledgers, schemas, permissions and reports. Virtual trading cash sizes/reserves positions and records trading P&L. AI budget pays for model calls. An inference debit never changes agent cash, buying power, risk equity or position size; adding API credit never funds a portfolio; budget exhaustion is an operational state, not a trading loss.

For each call retain: `ai_call_id`, provider/model/model snapshot, input/output token or provider usage units, cached units, request/start/end times, experiment/run/agent/strategy/candidate/decision IDs, prompt/template/schema/config hashes, purpose, retry/parent call, status/error, pricing version/source/currency, estimated and settled cost, attribution method and reusable decision-artifact ID. Do not store secret headers or raw credentials. Development-tool/Codex usage is outside experiment economics unless an explicit future allocation policy says otherwise.

Pricing is a versioned snapshot effective for the call. Historical call costs do not change when current prices change. Estimates and provider-settled amounts remain separate with reconciliation status. Shared calls/caches use a preregistered allocation rule; they are never silently charged multiple times.

Economic reporting keeps three layers:

1. Gross Trading P&L before trading/execution costs.
2. Net Trading P&L = Gross Trading P&L minus commissions, spread, slippage, exchange/regulatory fees and trading FX costs.
3. Net Economic P&L = Net Trading P&L minus attributable AI inference costs and other explicitly attributed operating costs.

Primary trading evaluation uses Net Trading P&L; strategy/model economic comparisons also report Net Economic P&L. Running out of AI budget does not create a negative trade or alter actual equity. See [[04 - Costs & Economics/API Budget Controls]] and [[03 - Experiments/Decision Replay]].
