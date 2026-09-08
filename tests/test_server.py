"""Testes unitarios do servidor simulado."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
import math
from statistics import fmean

import pytest
import simpy

from load_balancer_sim import Request, Server, ServerState


def _constant_duration(duration: float) -> Callable[[Request], float]:
    """Cria um sampler deterministico para testes de fila e concorrencia."""

    def sample(_: Request) -> float:
        return duration

    return sample


def _submit(server: Server, request: Request) -> None:
    request.assign_to(server.id)
    server.environment.process(server.handle(request))


def _run_service_durations(seed: int, request_count: int) -> tuple[float, ...]:
    environment = simpy.Environment()
    server = Server(environment, server_id=0, service_rate=1.0, seed=seed)
    requests = [
        Request(id=index, burst_id=0, arrival_time=0.0)
        for index in range(request_count)
    ]

    for request in requests:
        _submit(server, request)
    environment.run()

    return tuple(
        request.completion_time - request.service_start_time
        for request in requests
        if request.completion_time is not None
        and request.service_start_time is not None
    )


def test_server_uses_exponential_service_by_default() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0, seed=7)
    request = Request(id=0, burst_id=0, arrival_time=environment.now)

    _submit(server, request)
    environment.run()

    assert request.service_start_time == 0.0
    assert request.completion_time is not None
    assert request.completion_time > 0.0
    assert server.active_count == 0
    assert server.waiting_count == 0


def test_server_accepts_deterministic_service_sampler() -> None:
    environment = simpy.Environment()
    server = Server(
        environment,
        server_id=0,
        service_time_sampler=_constant_duration(0.05),
    )
    request = Request(id=0, burst_id=0, arrival_time=0.0)

    _submit(server, request)
    environment.run()

    assert request.completion_time == pytest.approx(0.05)


def test_server_limits_concurrency_to_one_and_queues_excess_requests() -> None:
    environment = simpy.Environment()
    server = Server(
        environment,
        server_id=0,
        service_time_sampler=_constant_duration(0.05),
    )
    requests = [Request(id=index, burst_id=0, arrival_time=0.0) for index in range(2)]

    for request in requests:
        _submit(server, request)

    environment.run(until=0.001)

    assert server.capacity == 1
    assert server.active_count == 1
    assert server.waiting_count == 1
    assert requests[0].service_start_time == 0.0
    assert requests[1].service_start_time is None

    environment.run()

    assert requests[1].service_start_time == pytest.approx(0.05)
    assert requests[1].completion_time == pytest.approx(0.10)


def test_server_monitors_state_and_observed_maximums() -> None:
    environment = simpy.Environment()
    server = Server(
        environment,
        server_id=0,
        service_time_sampler=_constant_duration(0.05),
    )
    requests = [Request(id=index, burst_id=0, arrival_time=0.0) for index in range(3)]

    for request in requests:
        _submit(server, request)

    environment.run()

    assert server.completed_count == 3
    assert server.maximum_active_count == 1
    assert server.maximum_waiting_count == 2
    assert server.state_history[0] == ServerState(
        time=0.0,
        event="initialized",
        server_id=0,
        request_id=None,
        active_count=0,
        waiting_count=0,
        completed_count=0,
    )
    assert [state.event for state in server.state_history].count("request_received") == 3
    assert [state.event for state in server.state_history].count("service_started") == 3
    assert [state.event for state in server.state_history].count("service_completed") == 3
    assert [state.time for state in server.state_history] == sorted(
        state.time for state in server.state_history
    )
    assert server.state_history[-1].active_count == 0
    assert server.state_history[-1].waiting_count == 0
    assert server.state_history[-1].completed_count == 3


def test_server_state_history_cannot_be_changed_externally() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0)
    state = server.state_history[0]

    with pytest.raises(FrozenInstanceError):
        state.active_count = 1  # type: ignore[misc]

    copied_history = server.state_history
    copied_history += (state,)

    assert len(copied_history) == 2
    assert len(server.state_history) == 1


def test_server_uses_fifo_queue() -> None:
    environment = simpy.Environment()
    server = Server(
        environment,
        server_id=2,
        service_time_sampler=_constant_duration(0.05),
    )
    requests = [Request(id=index, burst_id=0, arrival_time=0.0) for index in range(3)]

    for request in requests:
        _submit(server, request)

    environment.run()

    assert [request.service_start_time for request in requests] == pytest.approx(
        [0.0, 0.05, 0.10]
    )


def test_exponential_service_is_reproducible_with_seed() -> None:
    assert _run_service_durations(seed=123, request_count=20) == (
        _run_service_durations(seed=123, request_count=20)
    )
    assert _run_service_durations(seed=123, request_count=20) != (
        _run_service_durations(seed=124, request_count=20)
    )


def test_exponential_service_mean_matches_inverse_rate() -> None:
    durations = _run_service_durations(seed=12345, request_count=5000)

    assert all(duration > 0 for duration in durations)
    assert fmean(durations) == pytest.approx(1.0, rel=0.05)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_exception"),
    [
        ("server_id", -1, ValueError),
        ("server_id", True, TypeError),
        ("capacity", 0, ValueError),
        ("capacity", 1.5, TypeError),
        ("service_rate", 0, ValueError),
        ("service_rate", -0.1, ValueError),
        ("service_rate", math.inf, ValueError),
        ("service_rate", "1.0", TypeError),
        ("seed", -1, ValueError),
        ("seed", 1.5, TypeError),
        ("service_time_sampler", object(), TypeError),
    ],
)
def test_server_rejects_invalid_configuration(
    field_name: str,
    invalid_value: object,
    expected_exception: type[Exception],
) -> None:
    server_data = {
        "environment": simpy.Environment(),
        "server_id": 0,
        "capacity": 1,
        "service_rate": 1.0,
        "seed": 1,
        "service_time_sampler": _constant_duration(1.0),
    }
    server_data[field_name] = invalid_value

    with pytest.raises(expected_exception, match=field_name):
        Server(**server_data)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("invalid_duration", "expected_exception"),
    [
        (0, ValueError),
        (-0.1, ValueError),
        (math.inf, ValueError),
        ("1.0", TypeError),
    ],
)
def test_server_rejects_invalid_sampled_duration(
    invalid_duration: object,
    expected_exception: type[Exception],
) -> None:
    environment = simpy.Environment()
    server = Server(
        environment,
        server_id=0,
        service_time_sampler=lambda _: invalid_duration,  # type: ignore[return-value]
    )
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    _submit(server, request)

    with pytest.raises(expected_exception, match="service_duration"):
        environment.run()


def test_server_only_handles_requests_assigned_to_it() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=1)

    process = environment.process(server.handle(request))

    with pytest.raises(ValueError, match="atribuida a este servidor"):
        environment.run(until=process)
