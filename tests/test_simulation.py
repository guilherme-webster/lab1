"""Testes do executor de uma rodada completa."""

from dataclasses import FrozenInstanceError, replace
import logging
import math

import pytest

from load_balancer_sim import (
    RequestTraceEntry,
    RunSeeds,
    ServerUtilization,
    SimulationConfig,
    SimulationLogger,
    derive_run_seeds,
    generate_request_trace,
    run_simulation,
)


def _short_config(
    policy: str = "round_robin",
    seed: int = 123,
) -> SimulationConfig:
    return SimulationConfig(
        policy=policy,  # type: ignore[arg-type]
        server_count=3,
        server_capacity=1,
        service_rate=2.0,
        arrival_rate=2.0,
        horizon=8.0,
        warmup=1.0,
        seed=seed,
    )


def test_run_simulation_executes_known_trace_end_to_end() -> None:
    config = _short_config()
    trace = (
        RequestTraceEntry(0, 0.0, 0.5),
        RequestTraceEntry(1, 0.1, 0.5),
        RequestTraceEntry(2, 0.2, 0.5),
    )
    config = replace(config, horizon=2.0, warmup=0.0)

    result = run_simulation(config, trace=trace)

    assert result.config is config
    assert result.trace == trace
    assert result.metrics.arrival_count == 3
    assert result.metrics.completed_count == 3
    assert result.metrics.pending_count == 0
    assert result.metrics.throughput == pytest.approx(1.5)
    assert result.metrics.average_queue_time == 0.0
    assert result.metrics.average_response_time == pytest.approx(0.5)
    assert result.metrics.average_number_in_system == pytest.approx(0.75)
    assert tuple(
        utilization.server_id
        for utilization in result.metrics.server_utilizations
    ) == (0, 1, 2)
    assert tuple(
        utilization.utilization
        for utilization in result.metrics.server_utilizations
    ) == pytest.approx(
        (0.25, 0.25, 0.25)
    )

    lifecycle_by_request = {
        request_id: [
            event.event
            for event in result.events
            if event.request_id == request_id
        ]
        for request_id in range(3)
    }
    assert lifecycle_by_request == {
        0: ["arrival", "routing", "service_started", "service_completed"],
        1: ["arrival", "routing", "service_started", "service_completed"],
        2: ["arrival", "routing", "service_started", "service_completed"],
    }


def test_run_simulation_is_reproducible() -> None:
    config = _short_config(policy="random", seed=456)

    first = run_simulation(config)
    second = run_simulation(config)

    assert first == second
    assert first.trace


def test_generated_trace_is_independent_from_routing_policy() -> None:
    round_robin = _short_config(policy="round_robin", seed=789)
    random = replace(round_robin, policy="random")
    shortest_queue = replace(round_robin, policy="shortest_queue")

    assert generate_request_trace(round_robin) == generate_request_trace(random)
    assert generate_request_trace(round_robin) == generate_request_trace(
        shortest_queue
    )


def test_run_simulation_reuses_external_trace_across_policies() -> None:
    round_robin = _short_config(policy="round_robin")
    trace = generate_request_trace(round_robin)
    random = replace(round_robin, policy="random")

    round_robin_result = run_simulation(round_robin, trace=trace)
    random_result = run_simulation(random, trace=trace)

    assert round_robin_result.trace == random_result.trace == trace
    assert [entry.service_duration for entry in round_robin_result.trace] == [
        entry.service_duration for entry in random_result.trace
    ]


def test_run_simulation_accepts_empty_trace() -> None:
    result = run_simulation(_short_config(), trace=())

    assert result.trace == ()
    assert result.events == ()
    assert result.metrics.arrival_count == 0
    assert result.metrics.completed_count == 0
    assert result.metrics.average_number_in_system == 0.0
    assert result.metrics.server_utilizations == (
        ServerUtilization(0, 0.0),
        ServerUtilization(1, 0.0),
        ServerUtilization(2, 0.0),
    )


def test_run_simulation_emits_start_events_and_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.simulation")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    simulation_logger = SimulationLogger(logger)
    trace = (RequestTraceEntry(0, 0.0, 0.5),)
    config = replace(_short_config(), horizon=2.0, warmup=0.0)

    run_simulation(
        config,
        trace=trace,
        simulation_logger=simulation_logger,
    )

    messages = [record.getMessage() for record in caplog.records]
    assert messages[0].startswith("run_started,")
    assert messages[1].startswith("time,event,")
    assert any(",arrival,0,0," in message for message in messages)
    assert any(",service_completed,0,0," in message for message in messages)
    assert messages[-1].startswith("run_completed,")


def test_derive_run_seeds_is_reproducible_and_separates_streams() -> None:
    first = derive_run_seeds(123)
    second = derive_run_seeds(123)

    assert first == second
    assert first.base_seed == 123
    assert len(
        {first.arrival_seed, first.service_seed, first.routing_seed}
    ) == 3
    assert first != derive_run_seeds(124)


def test_simulation_result_and_trace_are_immutable() -> None:
    trace_entry = RequestTraceEntry(0, 0.0, 0.5)
    result = run_simulation(
        replace(_short_config(), horizon=2.0, warmup=0.0),
        trace=(trace_entry,),
    )

    with pytest.raises(FrozenInstanceError):
        trace_entry.service_duration = 1.0  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        result.metrics = result.metrics  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_exception"),
    [
        ("request_id", -1, ValueError),
        ("request_id", True, TypeError),
        ("arrival_time", -0.1, ValueError),
        ("arrival_time", math.inf, ValueError),
        ("arrival_time", "0.1", TypeError),
        ("service_duration", 0, ValueError),
        ("service_duration", -0.1, ValueError),
        ("service_duration", math.inf, ValueError),
        ("service_duration", "1.0", TypeError),
    ],
)
def test_request_trace_entry_rejects_invalid_values(
    field_name: str,
    invalid_value: object,
    expected_exception: type[Exception],
) -> None:
    values: dict[str, object] = {
        "request_id": 0,
        "arrival_time": 0.0,
        "service_duration": 1.0,
    }
    values[field_name] = invalid_value

    with pytest.raises(expected_exception, match=field_name):
        RequestTraceEntry(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "invalid_trace",
    [
        [object()],
        [RequestTraceEntry(0, 0.0, 1.0), RequestTraceEntry(0, 1.0, 1.0)],
        [RequestTraceEntry(0, 0.0, 1.0), RequestTraceEntry(1, 8.0, 1.0)],
        [RequestTraceEntry(0, 1.0, 1.0), RequestTraceEntry(1, 0.5, 1.0)],
    ],
)
def test_run_simulation_rejects_invalid_trace(
    invalid_trace: list[object],
) -> None:
    with pytest.raises((TypeError, ValueError), match="trace|request_id|arrival_time"):
        run_simulation(
            _short_config(),
            trace=invalid_trace,  # type: ignore[arg-type]
        )


def test_run_simulation_requires_a_trace_sequence() -> None:
    with pytest.raises(TypeError, match="trace"):
        run_simulation(
            _short_config(),
            trace=iter(()),  # type: ignore[arg-type]
        )


def test_run_simulation_rejects_invalid_arguments() -> None:
    with pytest.raises(TypeError, match="config"):
        run_simulation(object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="simulation_logger"):
        run_simulation(
            _short_config(),
            simulation_logger=object(),  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match="config"):
        generate_request_trace(object())  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="seeds"):
        generate_request_trace(
            _short_config(),
            seeds=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("seed", "expected_exception"),
    [
        (-1, ValueError),
        (1.5, TypeError),
        (True, TypeError),
    ],
)
def test_derive_run_seeds_rejects_invalid_seed(
    seed: object,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match="base_seed"):
        derive_run_seeds(seed)  # type: ignore[arg-type]


def test_run_seeds_reject_invalid_fields() -> None:
    with pytest.raises(ValueError, match="service_seed"):
        RunSeeds(
            base_seed=0,
            arrival_seed=1,
            service_seed=-1,
            routing_seed=2,
        )
