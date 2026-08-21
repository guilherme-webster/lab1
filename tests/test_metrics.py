"""Testes unitarios dos eventos basicos de metricas."""

from dataclasses import FrozenInstanceError

import pytest
import simpy

from load_balancer_sim import MetricEvent, MetricsCollector, Request, Server


def test_collector_starts_with_no_events() -> None:
    collector = MetricsCollector(simpy.Environment())

    assert collector.events == ()


def test_collector_records_basic_request_events_in_order() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=2)
    request = Request(id=7, burst_id=3, arrival_time=environment.now)

    collector.record_arrival(request)
    request.assign_to(server.id)
    collector.record_routing(request, server)
    collector.record_service_started(request, server)
    collector.record_service_completed(request, server)

    assert collector.events == (
        MetricEvent(0.0, "arrival", 7, 3, None, None, None),
        MetricEvent(0.0, "routing", 7, 3, 2, 0, 0),
        MetricEvent(0.0, "service_started", 7, 3, 2, 0, 0),
        MetricEvent(0.0, "service_completed", 7, 3, 2, 0, 0),
    )


def test_collector_uses_simulated_time_and_server_snapshot() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0, capacity=1)
    first = Request(id=0, burst_id=0, arrival_time=0.0)
    second = Request(id=1, burst_id=0, arrival_time=0.0)

    for request in (first, second):
        request.assign_to(server.id)
        environment.process(server.handle(request))

    environment.run(until=0.01)
    collector.record_service_started(first, server)

    assert collector.events == (
        MetricEvent(0.01, "service_started", 0, 0, 0, 1, 1),
    )


def test_collector_history_and_events_are_immutable() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    collector.record_arrival(request)
    event = collector.events[0]

    with pytest.raises(FrozenInstanceError):
        event.time = 1.0  # type: ignore[misc]

    copied_events = collector.events
    copied_events += (event,)

    assert len(copied_events) == 2
    assert len(collector.events) == 1


def test_collector_rejects_invalid_environment() -> None:
    with pytest.raises(TypeError, match="environment"):
        MetricsCollector(object())  # type: ignore[arg-type]


def test_collector_rejects_invalid_request() -> None:
    collector = MetricsCollector(simpy.Environment())

    with pytest.raises(TypeError, match="request"):
        collector.record_arrival(object())  # type: ignore[arg-type]


def test_collector_rejects_invalid_server() -> None:
    collector = MetricsCollector(simpy.Environment())
    request = Request(id=0, burst_id=0, arrival_time=0.0)

    with pytest.raises(TypeError, match="server"):
        collector.record_routing(request, object())  # type: ignore[arg-type]
