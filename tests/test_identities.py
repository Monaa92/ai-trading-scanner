import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import (
    AccountId,
    AgentId,
    AllocationId,
    ConfigurationVersionId,
    DatasetId,
    ExperimentId,
    InstrumentId,
    ModelId,
    StrategyId,
)

IDENTITY_TYPES = (
    AgentId,
    AccountId,
    AllocationId,
    ExperimentId,
    StrategyId,
    ModelId,
    ConfigurationVersionId,
    InstrumentId,
    DatasetId,
)


@pytest.mark.parametrize("identity_type", IDENTITY_TYPES)
@pytest.mark.parametrize("value", ["agent-a", "phase1.v1", "provider:model/v1", "A_123"])
def test_valid_identifiers_are_accepted(identity_type: type[AgentId], value: str) -> None:
    assert str(identity_type.parse(value)) == value


@pytest.mark.parametrize("identity_type", IDENTITY_TYPES)
@pytest.mark.parametrize(
    "value",
    ["", " leading", "trailing ", "contains space", "../escape", "a//b", "x" * 129],
)
def test_malformed_identifiers_are_rejected(identity_type: type[AgentId], value: str) -> None:
    with pytest.raises(ValidationError):
        identity_type.parse(value)


def test_identity_types_remain_distinct() -> None:
    agent = AgentId.parse("participant-a")
    strategy = StrategyId.parse("participant-a")

    assert type(agent) is AgentId
    assert type(strategy) is StrategyId
    assert agent != strategy
