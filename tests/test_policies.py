"""Testes unitarios das politicas de roteamento."""

from collections import Counter

import pytest
import simpy

from load_balancer_sim import (
    RandomPolicy,
    Request,
    RoundRobinPolicy,
    Server,
    ShortestQueuePolicy,
    build_policy,
)


def _make_servers(environment: simpy.Environment) -> list[Server]:
    return [
        Server(
            environment,
            server_id=index,
            service_time_sampler=lambda _: 10.0,
        )
        for index in range(3)
    ]


def _request(request_id: int) -> Request:
    return Request(id=request_id, burst_id=0, arrival_time=0.0)


def _occupy_server(
    environment: simpy.Environment,
    server: Server,
    request_id: int,
) -> None:
    request = _request(request_id)
    request.assign_to(server.id)
    environment.process(server.handle(request))


def test_round_robin_policy_cycles_across_servers() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    policy = RoundRobinPolicy()

    selected_ids = [
        policy.select_server(_request(index), servers).id for index in range(8)
    ]

    assert selected_ids == [0, 1, 2, 0, 1, 2, 0, 1]


def test_random_policy_is_reproducible_and_reaches_every_server() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    first = RandomPolicy(seed=123)
    second = RandomPolicy(seed=123)

    first_ids = [
        first.select_server(_request(index), servers).id for index in range(30)
    ]
    second_ids = [
        second.select_server(_request(index), servers).id for index in range(30)
    ]

    assert first_ids == second_ids
    assert set(first_ids) == {0, 1, 2}


def test_random_policy_is_approximately_uniform() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    policy = RandomPolicy(seed=12345)

    selected_counts = Counter(
        policy.select_server(_request(index), servers).id for index in range(3000)
    )

    assert set(selected_counts) == {0, 1, 2}
    assert all(
        count == pytest.approx(1000, rel=0.10)
        for count in selected_counts.values()
    )


def test_shortest_queue_selects_unique_least_loaded_server() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    _occupy_server(environment, servers[0], request_id=100)
    _occupy_server(environment, servers[0], request_id=101)
    _occupy_server(environment, servers[1], request_id=102)
    environment.run(until=0.001)

    selected = ShortestQueuePolicy(seed=123).select_server(_request(0), servers)

    assert [server.active_count + server.waiting_count for server in servers] == [
        2,
        1,
        0,
    ]
    assert selected.id == 2


@pytest.mark.parametrize("busy_server_id", [0, 1, 2])
def test_shortest_queue_randomizes_every_two_server_tie(
    busy_server_id: int,
) -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    _occupy_server(environment, servers[busy_server_id], request_id=100)
    environment.run(until=0.001)
    policy = ShortestQueuePolicy(seed=123)
    expected_ids = {0, 1, 2} - {busy_server_id}

    selected_ids = {
        policy.select_server(_request(index), servers).id for index in range(30)
    }

    assert selected_ids == expected_ids


def test_shortest_queue_randomizes_three_server_tie_reproducibly() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    first = ShortestQueuePolicy(seed=321)
    second = ShortestQueuePolicy(seed=321)

    first_ids = [
        first.select_server(_request(index), servers).id for index in range(30)
    ]
    second_ids = [
        second.select_server(_request(index), servers).id for index in range(30)
    ]

    assert first_ids == second_ids
    assert set(first_ids) == {0, 1, 2}


@pytest.mark.parametrize(
    ("policy_name", "expected_type"),
    [
        ("random", RandomPolicy),
        ("round_robin", RoundRobinPolicy),
        ("shortest_queue", ShortestQueuePolicy),
    ],
)
def test_build_policy_builds_every_supported_policy(
    policy_name: str,
    expected_type: type[object],
) -> None:
    policy = build_policy(policy_name, seed=123)  # type: ignore[arg-type]

    assert isinstance(policy, expected_type)


@pytest.mark.parametrize(
    ("policy_name", "expected_exception"),
    [
        ("least_connections", ValueError),
        (1, TypeError),
    ],
)
def test_build_policy_rejects_unknown_policy(
    policy_name: object,
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match="politica|policy"):
        build_policy(policy_name)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "policy",
    [RandomPolicy(seed=1), RoundRobinPolicy(), ShortestQueuePolicy(seed=1)],
)
def test_policies_reject_empty_server_sequence(policy: object) -> None:
    with pytest.raises(ValueError, match="servers"):
        policy.select_server(_request(0), [])  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "policy",
    [RandomPolicy(seed=1), RoundRobinPolicy(), ShortestQueuePolicy(seed=1)],
)
def test_policies_reject_invalid_request(policy: object) -> None:
    environment = simpy.Environment()

    with pytest.raises(TypeError, match="request"):
        policy.select_server(object(), _make_servers(environment))  # type: ignore[attr-defined,arg-type]
