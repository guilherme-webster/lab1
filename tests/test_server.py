"""Testes unitarios do servidor simulado."""

import math

import pytest
import simpy

from load_balancer_sim import Request, Server


def _submit(server: Server, request: Request) -> None:
    request.assign_to(server.id)
    server.environment.process(server.handle(request))


def test_server_processes_one_request_in_constant_time() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=environment.now)

    _submit(server, request)
    environment.run()

    assert request.service_start_time == 0.0
    assert request.completion_time == pytest.approx(0.05)
    assert server.active_count == 0
    assert server.waiting_count == 0


def test_server_limits_concurrency_and_queues_excess_requests() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0, capacity=15, service_time=0.05)
    requests = [Request(id=index, burst_id=0, arrival_time=0.0) for index in range(16)]

    for request in requests:
        _submit(server, request)

    environment.run(until=0.001)

    assert server.active_count == 15
    assert server.waiting_count == 1
    assert sum(request.service_start_time == 0.0 for request in requests) == 15
    assert requests[-1].service_start_time is None

    environment.run()

    assert requests[-1].service_start_time == pytest.approx(0.05)
    assert requests[-1].completion_time == pytest.approx(0.10)


def test_server_uses_fifo_queue() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=2, capacity=1, service_time=0.05)
    requests = [Request(id=index, burst_id=0, arrival_time=0.0) for index in range(3)]

    for request in requests:
        _submit(server, request)

    environment.run()

    assert [request.service_start_time for request in requests] == pytest.approx(
        [0.0, 0.05, 0.10]
    )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_exception"),
    [
        ("server_id", -1, ValueError),
        ("server_id", True, TypeError),
        ("capacity", 0, ValueError),
        ("capacity", 1.5, TypeError),
        ("service_time", 0, ValueError),
        ("service_time", -0.1, ValueError),
        ("service_time", math.inf, ValueError),
        ("service_time", "0.05", TypeError),
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
        "capacity": 15,
        "service_time": 0.05,
    }
    server_data[field_name] = invalid_value

    with pytest.raises(expected_exception, match=field_name):
        Server(**server_data)  # type: ignore[arg-type]


def test_server_only_handles_requests_assigned_to_it() -> None:
    environment = simpy.Environment()
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=1)

    process = environment.process(server.handle(request))

    with pytest.raises(ValueError, match="atribuida a este servidor"):
        environment.run(until=process)
