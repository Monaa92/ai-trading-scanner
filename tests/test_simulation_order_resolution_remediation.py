"""Independent adversarial probes for the committed Phase 6.1 review candidate."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from simulation_helpers import execution_configuration
from test_simulation_orchestration import (
    _advance_to_proposal_boundary,
    _fast_bars,
    _fast_proposal_configuration,
    _setup,
)
from test_simulation_order_resolution import (
    _advance_to_terminal,
    _created,
    _custom_environment,
    _dataset_without_coverage,
    _environment,
    _liquidity,
)

from ai_trading_scanner.domain import AgentId
from ai_trading_scanner.simulation import (
    OrderResolutionInvariantError,
    OrderTerminalResolution,
    OrderTerminalResolver,
    SimulatedOrderProjection,
    SimulationRunManifest,
    calculate_order_projection_id,
    calculate_order_terminal_resolution_id,
    calculate_simulation_run_id,
)


def test_order_cannot_be_created_retroactively_after_its_validity_window() -> None:
    orchestrator, result, resolver, command = _environment("review-stale-creation")
    while orchestrator.scheduler.has_events:
        orchestrator.advance()
    view = orchestrator.market_view()
    assert view.causal_at is not None
    with pytest.raises(OrderResolutionInvariantError, match="expired|stale|cursor"):
        resolver.create_order(command, result)


def test_creation_failure_after_receipt_publication_is_exception_atomic() -> None:
    _, result, resolver, command = _environment(
        "review-partial-publication",
        failure_stage="after_creation_receipt_staged",
    )
    with pytest.raises(RuntimeError, match="after_creation_receipt_staged"):
        resolver.create_order(command, result)
    retry = resolver.create_order(command, result)
    assert retry.order_id is not None
    assert resolver.projection(retry.order_id).order.order_id == retry.order_id


def test_reidentified_foreign_terminal_evidence_cannot_enter_projection() -> None:
    orchestrator, _, resolver, receipt = _created("review-terminal-forgery")
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None

    terminal_content = terminal.model_dump(mode="python", exclude={"terminal_resolution_id"})
    terminal_content["agent_id"] = AgentId.parse("agent:forged-terminal")
    forged_terminal = OrderTerminalResolution.model_validate(
        {
            "terminal_resolution_id": calculate_order_terminal_resolution_id(terminal_content),
            **terminal_content,
        }
    )
    projection_content = projection.model_dump(mode="python", exclude={"projection_id"})
    projection_content["terminal_resolution"] = forged_terminal
    with pytest.raises(ValidationError, match="agent|attribution|order"):
        SimulatedOrderProjection.model_validate(
            {
                "projection_id": calculate_order_projection_id(projection_content),
                **projection_content,
            }
        )


def test_cancellation_retry_after_terminalization_returns_original_command() -> None:
    orchestrator, _, resolver, receipt = _created("review-cancel-retry")
    assert receipt.order_id is not None
    position = orchestrator.scheduler.position
    original = resolver.request_cancellation(receipt.order_id, expected_scheduler_position=position)
    terminal = resolver.resolve(receipt.order_id)
    assert terminal.terminal_resolution is not None
    assert (
        resolver.request_cancellation(receipt.order_id, expected_scheduler_position=position)
        == original
    )


def test_first_late_cancellation_after_terminal_is_a_no_effect_idempotent_command() -> None:
    orchestrator, _, resolver, receipt = _created("review-post-terminal-cancel-retry")
    assert receipt.order_id is not None
    while len(orchestrator.released_market_events) < 6:
        orchestrator.advance()
    filled = resolver.resolve(receipt.order_id)
    assert filled.terminal_resolution is not None
    position = orchestrator.scheduler.position
    first = resolver.request_cancellation(receipt.order_id, expected_scheduler_position=position)
    second = resolver.request_cancellation(receipt.order_id, expected_scheduler_position=position)
    final = resolver.projection(receipt.order_id)
    assert first == second
    assert final.terminal_resolution == filled.terminal_resolution
    assert final.cancellation == first


def test_end_of_data_does_not_publish_future_dated_expiry() -> None:
    dataset = _dataset_without_coverage(_fast_bars()[:3])
    orchestrator, _, resolver, receipt = _custom_environment(
        "review-future-expiry",
        dataset=dataset,
        execution=execution_configuration(),
    )
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    view = orchestrator.market_view()
    assert terminal is not None
    assert view.causal_at is not None
    assert terminal.payload.resolved_at <= view.causal_at


def test_liquidity_behavior_is_frozen_by_run_identity() -> None:
    orchestrator, _, first_resolver, _ = _environment("review-liquidity-run-identity")
    second_liquidity = _liquidity("0.0000001")
    with pytest.raises(OrderResolutionInvariantError, match="liquidity configuration"):
        OrderTerminalResolver(
            artifact=first_resolver._artifact,
            dataset=first_resolver._dataset,
            orchestrator=orchestrator,
            execution_configuration=first_resolver._execution_configuration,
            liquidity_configuration=second_liquidity,
        )


def test_v2_run_identity_changes_with_complete_liquidity_configuration() -> None:
    _, _, resolver, _ = _environment("review-liquidity-manifest-identity")
    manifest = resolver._artifact.manifest
    assert manifest.schema_version == "simulation-run-manifest-v2"
    content = manifest.model_dump(mode="python", exclude={"run_id"})
    content["liquidity_configuration"] = _liquidity("0.0000001")
    changed = SimulationRunManifest.model_validate(
        {"run_id": calculate_simulation_run_id(content), **content}
    )
    assert changed.run_id != manifest.run_id


def test_resolver_rejects_v1_manifest_without_bound_liquidity() -> None:
    orchestrator, artifact, dataset, _ = _setup(
        "review-v1-manifest-block",
        configuration=_fast_proposal_configuration(),
        bars=_fast_bars(),
    )
    _advance_to_proposal_boundary(orchestrator)
    assert orchestrator.advance() is not None
    with pytest.raises(OrderResolutionInvariantError, match="V2 manifest"):
        OrderTerminalResolver(
            artifact=artifact,
            dataset=dataset,
            orchestrator=orchestrator,
            execution_configuration=execution_configuration(),
            liquidity_configuration=_liquidity(),
        )


def test_reidentified_terminal_is_rejected_by_resolver_authority() -> None:
    orchestrator, _, resolver, receipt = _created("review-authoritative-terminal")
    assert receipt.order_id is not None
    projection = _advance_to_terminal(orchestrator, resolver, receipt.order_id)
    terminal = projection.terminal_resolution
    assert terminal is not None and terminal.maximum_fill_quantity is not None
    content = terminal.model_dump(mode="python", exclude={"terminal_resolution_id"})
    content["maximum_fill_quantity"] = terminal.maximum_fill_quantity + 1
    forged = OrderTerminalResolution.model_validate(
        {
            "terminal_resolution_id": calculate_order_terminal_resolution_id(content),
            **content,
        }
    )
    with pytest.raises(OrderResolutionInvariantError, match="not issued"):
        resolver.validate_terminal_resolution(forged)


def test_stale_cancellation_cursor_is_rejected() -> None:
    orchestrator, _, resolver, receipt = _created("review-stale-cancellation")
    assert receipt.order_id is not None
    expected = orchestrator.scheduler.position
    orchestrator.advance()
    with pytest.raises(OrderResolutionInvariantError, match="cursor changed"):
        resolver.request_cancellation(receipt.order_id, expected_scheduler_position=expected)


def test_concurrent_immediate_cancellation_and_resolution_have_one_terminal_result() -> None:
    orchestrator, _, resolver, receipt = _created("review-concurrent-cancellation")
    assert receipt.order_id is not None
    position = orchestrator.scheduler.position
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellation_future = pool.submit(
            resolver.request_cancellation,
            receipt.order_id,
            expected_scheduler_position=position,
        )
        resolution_future = pool.submit(resolver.resolve, receipt.order_id)
        cancellation = cancellation_future.result()
        resolution_future.result()
    terminal = resolver.resolve(receipt.order_id)
    assert terminal.terminal_resolution is not None
    assert terminal.cancellation == cancellation
    assert terminal.terminal_resolution.payload.outcome.value == "CANCELLED"


def test_concurrent_late_cancellation_and_resolution_use_execution_precedence() -> None:
    orchestrator, _, resolver, receipt = _created("review-concurrent-late-cancellation")
    assert receipt.order_id is not None
    while len(orchestrator.released_market_events) < 6:
        orchestrator.advance()
    position = orchestrator.scheduler.position
    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellation_future = pool.submit(
            resolver.request_cancellation,
            receipt.order_id,
            expected_scheduler_position=position,
        )
        resolution_future = pool.submit(resolver.resolve, receipt.order_id)
        cancellation = cancellation_future.result()
        resolution_future.result()
    final = resolver.projection(receipt.order_id)
    assert final.revision == 3
    assert final.cancellation == cancellation
    assert final.terminal_resolution is not None
    assert final.terminal_resolution.payload.outcome.value == "FILL_READY"
    assert final.terminal_resolution.cancellation_command_id is None
