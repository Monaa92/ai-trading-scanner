import pytest
from pydantic import ValidationError

from ai_trading_scanner.domain import (
    ApprovalPolicy,
    DataRunMode,
    ExecutionDimensions,
    ExecutionEnvironment,
    ExperimentId,
    ExperimentType,
    OperatingContext,
    SubmissionMode,
)


def dimensions(**overrides: object) -> ExecutionDimensions:
    values: dict[str, object] = {
        "data_run_mode": DataRunMode.HISTORICAL_REPLAY,
        "execution_environment": ExecutionEnvironment.SIMULATION,
        "submission_mode": SubmissionMode.SIGNAL_ONLY,
        "approval_policy": ApprovalPolicy.MANUAL_APPROVAL,
        "operating_context": OperatingContext.NORMAL,
    }
    values.update(overrides)
    return ExecutionDimensions.model_validate(values)


@pytest.mark.parametrize("policy", list(ApprovalPolicy))
def test_simulation_supports_each_approval_policy_without_changing_environment(
    policy: ApprovalPolicy,
) -> None:
    configured = dimensions(approval_policy=policy)

    assert configured.execution_environment is ExecutionEnvironment.SIMULATION
    assert configured.approval_policy is policy


def test_paper_plus_full_auto_is_valid_in_the_domain_model() -> None:
    configured = dimensions(
        execution_environment=ExecutionEnvironment.PAPER,
        submission_mode=SubmissionMode.ORDER_ENABLED,
        approval_policy=ApprovalPolicy.FULL_AUTO,
    )

    assert configured.execution_environment is ExecutionEnvironment.PAPER
    assert configured.approval_policy is ApprovalPolicy.FULL_AUTO


def test_full_auto_never_mutates_environment_to_live() -> None:
    configured = dimensions(
        execution_environment=ExecutionEnvironment.PAPER,
        approval_policy=ApprovalPolicy.FULL_AUTO,
    )

    assert configured.execution_environment is not ExecutionEnvironment.LIVE


def test_experiment_context_requires_identity() -> None:
    with pytest.raises(ValidationError, match="requires experiment_id"):
        dimensions(operating_context=OperatingContext.EXPERIMENT)


def test_autonomous_experiment_remains_a_separate_dimension() -> None:
    configured = dimensions(
        operating_context=OperatingContext.EXPERIMENT,
        experiment_id=ExperimentId.parse("experiment-1"),
        experiment_type=ExperimentType.AUTONOMOUS_EXPERIMENT,
    )

    assert configured.execution_environment is ExecutionEnvironment.SIMULATION
    assert configured.approval_policy is ApprovalPolicy.MANUAL_APPROVAL
    assert configured.experiment_type is ExperimentType.AUTONOMOUS_EXPERIMENT


def test_normal_context_rejects_experiment_fields() -> None:
    with pytest.raises(ValidationError, match="NORMAL context"):
        dimensions(experiment_id=ExperimentId.parse("experiment-1"))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("data_run_mode", "BACKTEST"),
        ("execution_environment", "PRODUCTION"),
        ("submission_mode", "EXECUTE"),
        ("approval_policy", "AUTOMATIC"),
        ("operating_context", "AUTONOMOUS_EXPERIMENT"),
    ],
)
def test_unknown_dimension_values_fail_without_fallback(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        dimensions(**{field: value})
