from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError
from strategy_helpers import evaluation_context, strategy_bars

from ai_trading_scanner.domain import ConfigurationVersionId, DatasetId
from ai_trading_scanner.domain.content_identity import sha256_content_id
from ai_trading_scanner.domain.execution import ExecutionEnvironment
from ai_trading_scanner.strategies import (
    ManagementStyle,
    ManagementTrigger,
    MomentumConfiguration,
    NoTradeDecision,
    NoTradeReason,
    SizingIntent,
    SizingMethod,
    StrategyDecision,
    StrategyOutcome,
    TradeProposalDecision,
    calculate_management_mandate_id,
    calculate_strategy_decision_id,
    calculate_trade_proposal_id,
    create_management_mandate,
    evaluate_strategy,
)


def momentum_proposal() -> TradeProposalDecision:
    closes = ["100"] * 54 + ["101", "102", "101", "102", "103", "105"]
    highs = [str(Decimal(close) + Decimal("0.5")) for close in closes]
    highs[50] = "110"
    highs[-2] = "104"
    highs[-1] = "105.5"
    lows = ["99.5"] * 60
    lows[-4] = "100.5"
    decision = evaluate_strategy(
        evaluation_context(MomentumConfiguration(), strategy_bars(closes, highs=highs, lows=lows)),
        MomentumConfiguration(),
    )
    assert isinstance(decision, TradeProposalDecision)
    return decision


def test_decision_is_exactly_one_discriminated_outcome() -> None:
    decision = momentum_proposal()

    assert decision.outcome is StrategyOutcome.TRADE_PROPOSAL
    assert decision.reasons == ()
    assert decision.proposal is not None


def test_no_trade_is_explicit_and_never_null() -> None:
    configuration = MomentumConfiguration()
    bars = strategy_bars(["100"] * 60)
    decision = evaluate_strategy(
        evaluation_context(
            configuration, bars, fast="100", medium="100", slow="100", vwap="100", rsi="50"
        ),
        configuration,
    )

    assert isinstance(decision, NoTradeDecision)
    assert decision.outcome is StrategyOutcome.NO_TRADE
    assert decision.reasons
    assert decision.proposal is None


def test_decisions_and_proposals_are_immutable() -> None:
    decision = momentum_proposal()

    with pytest.raises(ValidationError, match="frozen"):
        decision.proposal.stop_level = Decimal("1")
    with pytest.raises(ValidationError, match="frozen"):
        decision.detail = "changed"


def test_proposal_is_intent_not_approval_execution_or_final_sizing() -> None:
    proposal = momentum_proposal().proposal

    assert proposal.side.value == "LONG"
    assert proposal.sizing.final_quantity is None
    assert proposal.authority_context.execution_dimensions.execution_environment.value == (
        "SIMULATION"
    )
    assert proposal.authority_context.execution_dimensions.submission_mode.value == "SIGNAL_ONLY"
    serialized = proposal.model_dump(mode="json")
    for forbidden in ("approved", "risk_passed", "order_id", "fill_id", "position_id"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stop_level", Decimal("98")),
        ("instrument_id", "XNYS:OTHER"),
        ("entry", None),
        ("objective", None),
        ("valid_until", None),
        ("authority_context", None),
        ("authority_environment", None),
        ("management_mandate", None),
        ("sizing", None),
    ],
)
def test_approval_sensitive_changes_require_new_proposal_identity(
    field: str, value: object
) -> None:
    proposal = momentum_proposal().proposal
    content = proposal.model_dump(mode="python", exclude={"proposal_id"})
    if field == "valid_until":
        value = proposal.valid_until + timedelta(minutes=1)
    elif field == "entry":
        value = proposal.entry.model_copy(
            update={"reference_price": proposal.entry.reference_price + Decimal("0.01")}
        )
    elif field == "objective":
        assert proposal.objective.reference_level is not None
        value = proposal.objective.model_copy(
            update={"reference_level": proposal.objective.reference_level + Decimal("0.01")}
        )
    elif field == "authority_context":
        value = proposal.authority_context.model_copy(
            update={
                "configuration_version_id": ConfigurationVersionId.parse("changed-authority-v2")
            }
        )
    elif field == "authority_environment":
        value = proposal.authority_context.model_copy(
            update={
                "execution_dimensions": proposal.authority_context.execution_dimensions.model_copy(
                    update={"execution_environment": ExecutionEnvironment.PAPER}
                )
            }
        )
        field = "authority_context"
    elif field == "management_mandate":
        value = create_management_mandate(
            ManagementStyle.MOMENTUM_TREND,
            (ManagementTrigger.PROTECTIVE_STOP, ManagementTrigger.TREND_INVALIDATED),
        )
    elif field == "sizing":
        value = SizingIntent(method=SizingMethod.FINAL_QUANTITY, final_quantity=Decimal("1.25"))
    content[field] = value
    new_id = calculate_trade_proposal_id(content)

    assert new_id != proposal.proposal_id
    stale = {**content, "proposal_id": proposal.proposal_id}
    with pytest.raises(ValidationError, match="identity"):
        type(proposal).model_validate(stale)


def test_management_mandate_identity_is_content_derived_and_canonical() -> None:
    first = create_management_mandate(
        ManagementStyle.MOMENTUM_TREND,
        (ManagementTrigger.TREND_INVALIDATED, ManagementTrigger.PROTECTIVE_STOP),
    )
    second = create_management_mandate(
        ManagementStyle.MOMENTUM_TREND,
        (ManagementTrigger.PROTECTIVE_STOP, ManagementTrigger.TREND_INVALIDATED),
    )

    assert first == second
    assert first.mandate_id == calculate_management_mandate_id(first)
    assert first.universal_profit_cap is False


def test_decision_identity_is_content_derived() -> None:
    decision = momentum_proposal()

    assert decision.decision_id == calculate_strategy_decision_id(decision)


def test_decision_cannot_claim_different_lineage_from_nested_proposal() -> None:
    decision = momentum_proposal()
    content = decision.model_dump(mode="python", exclude={"decision_id"})
    content["dataset_id"] = DatasetId.parse("sha256:" + "b" * 64)
    content["decision_id"] = calculate_strategy_decision_id(content)

    with pytest.raises(ValidationError, match="attribution or lineage"):
        TradeProposalDecision.model_validate(content)


def test_union_serialization_round_trip_preserves_exact_contract() -> None:
    decision = momentum_proposal()
    adapter: TypeAdapter[StrategyDecision] = TypeAdapter(StrategyDecision)

    assert adapter.validate_json(adapter.dump_json(decision)) == decision


def test_canonical_hash_ignores_dictionary_insertion_order() -> None:
    assert sha256_content_id({"a": 1, "b": 2}) == sha256_content_id({"b": 2, "a": 1})


def test_no_trade_taxonomy_keeps_future_rejections_distinct() -> None:
    assert "CENTRAL_RISK_REJECTION" not in {reason.value for reason in NoTradeReason}
    assert "PORTFOLIO_CAPACITY_UNAVAILABLE" not in {reason.value for reason in NoTradeReason}
    assert "BROKER_REJECTION" not in {reason.value for reason in NoTradeReason}
