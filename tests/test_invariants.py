"""Testes unitarios das invariantes da simulacao."""

import pytest
import simpy

from load_balancer_sim import (
    MetricEvent,
    MetricsCollector,
    Request,
    Server,
    SimulationConfig,
    SimulationInvariantError,
    validate_simulation_invariants,
)


def _simulation_parts(
    config: SimulationConfig | None = None,
) -> tuple[SimulationConfig, list[Server], MetricsCollector]:
    selected_config = SimulationConfig() if config is None else config
    environment = simpy.Environment()
    servers = [
        Server(
            environment,
            server_id=server_id,
            capacity=selected_config.server_capacity,
            service_rate=selected_config.service_rate,
            seed=selected_config.seed + server_id,
        )
        for server_id in range(selected_config.server_count)
    ]
    return selected_config, servers, MetricsCollector(environment)


def _record_arrival_and_routing(
    collector: MetricsCollector,
    request: Request,
    server: Server,
) -> None:
    collector.record_arrival(request)
    request.assign_to(server.id)
    collector.record_routing(request, server)


def test_valid_run_can_end_with_completed_active_and_waiting_requests() -> None:
    config, servers, collector = _simulation_parts()

    completed = Request(id=0, burst_id=0, arrival_time=0.0)
    _record_arrival_and_routing(collector, completed, servers[0])
    collector.record_service_started(completed, servers[0])
    collector.record_service_completed(completed, servers[0])

    active = Request(id=1, burst_id=0, arrival_time=0.0)
    _record_arrival_and_routing(collector, active, servers[1])
    collector.record_service_started(active, servers[1])

    waiting = Request(id=2, burst_id=0, arrival_time=0.0)
    _record_arrival_and_routing(collector, waiting, servers[2])

    validate_simulation_invariants(config, servers, collector)


def test_empty_run_satisfies_invariants() -> None:
    config, servers, collector = _simulation_parts()

    validate_simulation_invariants(config, servers, collector)


def test_invariants_require_configured_server_count() -> None:
    config, servers, collector = _simulation_parts()

    with pytest.raises(SimulationInvariantError, match="quantidade de servidores"):
        validate_simulation_invariants(config, servers[:-1], collector)


def test_invariants_require_configured_server_capacity() -> None:
    config = SimulationConfig(server_capacity=2)
    environment = simpy.Environment()
    servers = [
        Server(environment, server_id=server_id, capacity=1)
        for server_id in range(config.server_count)
    ]
    collector = MetricsCollector(environment)

    with pytest.raises(SimulationInvariantError, match="capacidade"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_require_configured_service_rate() -> None:
    config = SimulationConfig(service_rate=2.0)
    environment = simpy.Environment()
    servers = [
        Server(environment, server_id=server_id, service_rate=1.0)
        for server_id in range(config.server_count)
    ]
    collector = MetricsCollector(environment)

    with pytest.raises(SimulationInvariantError, match="taxa de servico"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_require_shared_environment() -> None:
    config, servers, collector = _simulation_parts()
    servers[-1] = Server(simpy.Environment(), server_id=2)

    with pytest.raises(SimulationInvariantError, match="ambiente diferente"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_reject_event_outside_lifecycle_order() -> None:
    config, servers, collector = _simulation_parts()
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    collector.record_arrival(request)
    request.assign_to(servers[0].id)
    collector.record_service_started(request, servers[0])

    with pytest.raises(SimulationInvariantError, match="esperado: routing"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_reject_server_change_during_request() -> None:
    config, servers, collector = _simulation_parts()
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    _record_arrival_and_routing(collector, request, servers[0])
    collector.record_service_started(request, servers[1])

    with pytest.raises(SimulationInvariantError, match="servidor mudou"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_reject_arrival_at_horizon() -> None:
    config, servers, collector = _simulation_parts()
    collector.environment.run(until=config.horizon)
    request = Request(id=0, burst_id=0, arrival_time=config.horizon)
    collector.record_arrival(request)

    with pytest.raises(SimulationInvariantError, match="antes do horizonte"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_enforce_request_conservation() -> None:
    config, servers, collector = _simulation_parts()
    collector.record_arrival(Request(id=0, burst_id=0, arrival_time=0.0))

    with pytest.raises(SimulationInvariantError, match="conservacao violada"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_reject_active_count_above_capacity() -> None:
    config, servers, collector = _simulation_parts(
        SimulationConfig(server_capacity=1)
    )
    collector._events.extend(  # type: ignore[attr-defined]
        [
            MetricEvent(0.0, "arrival", 0, 0, None, None, None),
            MetricEvent(0.0, "routing", 0, 0, 0, 2, 0),
        ]
    )

    with pytest.raises(SimulationInvariantError, match="quantidade ativa"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_reject_inconsistent_burst_id() -> None:
    config, servers, collector = _simulation_parts()
    arrival = Request(id=0, burst_id=1, arrival_time=0.0)
    routed = Request(id=0, burst_id=2, arrival_time=0.0)
    collector.record_arrival(arrival)
    routed.assign_to(servers[0].id)
    collector.record_routing(routed, servers[0])

    with pytest.raises(SimulationInvariantError, match="rajada inconsistente"):
        validate_simulation_invariants(config, servers, collector)


def test_invariants_ignore_completion_during_drainage() -> None:
    config, servers, collector = _simulation_parts(
        SimulationConfig(horizon=1.0, warmup=0.0)
    )
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    _record_arrival_and_routing(collector, request, servers[0])
    collector.record_service_started(request, servers[0])
    collector.environment.run(until=1.1)
    collector.record_service_completed(request, servers[0])

    validate_simulation_invariants(config, servers, collector)
