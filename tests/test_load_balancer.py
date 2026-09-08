"""Testes do balanceador e de seus contratos de entrada."""

import pytest
import simpy

from load_balancer_sim import LoadBalancer, Request, Server


def _make_servers(
    environment: simpy.Environment,
    count: int = 3,
) -> list[Server]:
    """Cria servidores rapidos e deterministicos para os testes."""
    return [
        Server(
            environment,
            server_id=index,
            service_time_sampler=lambda _: 0.05,
        )
        for index in range(count)
    ]


def test_load_balancer_routes_and_completes_one_request() -> None:
    environment = simpy.Environment()
    load_balancer = LoadBalancer(environment, _make_servers(environment))
    request = Request(id=0, burst_id=0, arrival_time=environment.now)

    selected_server = load_balancer.route_request(request)
    environment.run()

    assert selected_server.id == 0
    assert request.assigned_server == 0
    assert request.service_start_time == 0.0
    assert request.completion_time == pytest.approx(0.05)


def test_load_balancer_protects_server_collection_from_external_changes() -> None:
    environment = simpy.Environment()
    servers = _make_servers(environment)
    load_balancer = LoadBalancer(environment, servers)

    servers.clear()

    assert len(load_balancer.servers) == 3
    assert isinstance(load_balancer.servers, tuple)


def test_load_balancer_rejects_invalid_environment() -> None:
    with pytest.raises(TypeError, match="environment"):
        LoadBalancer(object(), [])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "servers",
    [
        [],
        [object()],
    ],
)
def test_load_balancer_rejects_invalid_server_collections(
    servers: list[object],
) -> None:
    environment = simpy.Environment()

    with pytest.raises((TypeError, ValueError), match="servers"):
        LoadBalancer(environment, servers)  # type: ignore[arg-type]


def test_load_balancer_requires_a_server_sequence() -> None:
    environment = simpy.Environment()

    with pytest.raises(TypeError, match="servers"):
        LoadBalancer(environment, iter(_make_servers(environment)))  # type: ignore[arg-type]


def test_load_balancer_rejects_servers_from_another_environment() -> None:
    environment = simpy.Environment()
    foreign_server = Server(simpy.Environment(), server_id=0)

    with pytest.raises(ValueError, match="ambiente"):
        LoadBalancer(environment, [foreign_server])


def test_load_balancer_rejects_duplicate_server_ids() -> None:
    environment = simpy.Environment()
    servers = [
        Server(environment, server_id=0),
        Server(environment, server_id=0),
    ]

    with pytest.raises(ValueError, match="identificadores"):
        LoadBalancer(environment, servers)


@pytest.mark.parametrize(
    ("policy", "expected_exception"),
    [
        ("least_connections", ValueError),
        (1, TypeError),
    ],
)
def test_load_balancer_rejects_invalid_policy(
    policy: object,
    expected_exception: type[Exception],
) -> None:
    environment = simpy.Environment()

    with pytest.raises(expected_exception, match="politica|policy"):
        LoadBalancer(
            environment,
            _make_servers(environment),
            policy=policy,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("seed", "expected_exception"),
    [
        (-1, ValueError),
        (1.5, TypeError),
        (True, TypeError),
    ],
)
def test_load_balancer_rejects_invalid_seed(
    seed: object,
    expected_exception: type[Exception],
) -> None:
    environment = simpy.Environment()

    with pytest.raises(expected_exception, match="seed"):
        LoadBalancer(
            environment,
            _make_servers(environment),
            seed=seed,  # type: ignore[arg-type]
        )


def test_load_balancer_rejects_removed_simulation_config_argument() -> None:
    environment = simpy.Environment()

    with pytest.raises(TypeError, match="simulation_config"):
        LoadBalancer(
            environment,
            _make_servers(environment),
            simulation_config=object(),  # type: ignore[call-arg]
        )


def test_load_balancer_rejects_invalid_request() -> None:
    environment = simpy.Environment()
    load_balancer = LoadBalancer(environment, _make_servers(environment))

    with pytest.raises(TypeError, match="request"):
        load_balancer.route_request(object())  # type: ignore[arg-type]


def test_load_balancer_rejects_request_that_has_not_arrived() -> None:
    environment = simpy.Environment()
    load_balancer = LoadBalancer(environment, _make_servers(environment))
    request = Request(id=0, burst_id=0, arrival_time=1.0)

    with pytest.raises(ValueError, match="ainda nao chegou"):
        load_balancer.route_request(request)


def test_load_balancer_rejects_request_routed_twice() -> None:
    environment = simpy.Environment()
    load_balancer = LoadBalancer(environment, _make_servers(environment))
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    load_balancer.route_request(request)

    with pytest.raises(RuntimeError, match="ja foi roteada"):
        load_balancer.route_request(request)
