import ast
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from risk_helpers import risk_policy, state, trade_proposal

from ai_trading_scanner.risk import RiskDecision, RiskDecisionStatus, RiskEngine


def test_risk_evaluation_has_no_side_effects() -> None:
    proposal = trade_proposal()
    snapshot = state()
    configured = risk_policy()

    result = RiskEngine().evaluate(proposal, configured, snapshot, evaluated_at=proposal.as_of)

    assert result.status is RiskDecisionStatus.APPROVED_FOR_RESERVATION
    assert snapshot == state()


def test_risk_package_has_no_broker_provider_network_or_ai_imports() -> None:
    package = Path("src/ai_trading_scanner/risk")
    forbidden = {
        "alpaca",
        "anthropic",
        "httpx",
        "ib_insync",
        "kraken",
        "openai",
        "requests",
        "socket",
        "urllib",
        "yfinance",
    }
    imported: set[str] = set()
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])

    assert forbidden.isdisjoint(imported)


def test_phase5_contracts_contain_no_order_or_fill_authority() -> None:
    result = RiskEngine().evaluate(
        trade_proposal(), risk_policy(), state(), evaluated_at=trade_proposal().as_of
    )
    serialized = result.model_dump(mode="json")

    for forbidden in ("order_id", "fill_id", "broker", "submit_order", "place_order"):
        assert forbidden not in serialized


def test_risk_decision_is_immutable_and_content_identified() -> None:
    proposal = trade_proposal()
    decision = RiskEngine().evaluate(proposal, risk_policy(), state(), evaluated_at=proposal.as_of)
    with pytest.raises(ValidationError, match="frozen"):
        decision.status = RiskDecisionStatus.REJECTED
    content = decision.model_dump(mode="python")
    content["evaluated_at"] = decision.evaluated_at + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="identity"):
        RiskDecision.model_validate(content)
