"""Testes unitarios dos eventos basicos de metricas."""

from dataclasses import FrozenInstanceError
import math

import pytest
import simpy

from load_balancer_sim import (
    MetricEvent,
    MetricsCollector,
    Request,
    RunMetrics,
    Server,
)


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
    server = Server(
        environment,
        server_id=0,
        capacity=1,
        service_time_sampler=lambda _: 1.0,
    )
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


def test_empty_run_has_zero_counts_and_no_averages() -> None:
    collector = MetricsCollector(simpy.Environment())

    metrics = collector.calculate_run_metrics(horizon=200)

    assert metrics == RunMetrics(
        horizon=200.0,
        arrival_count=0,
        completed_count=0,
        pending_count=0,
        throughput=0.0,
        average_queue_time=None,
        average_response_time=None,
    )


def test_run_metrics_count_completions_and_pending_requests() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    completed = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(completed)
    completed.assign_to(server.id)
    collector.record_routing(completed, server)
    collector.record_service_started(completed, server)
    environment.run(until=0.05)
    collector.record_service_completed(completed, server)

    pending = Request(id=1, burst_id=0, arrival_time=environment.now)
    collector.record_arrival(pending)
    pending.assign_to(server.id)
    collector.record_routing(pending, server)

    metrics = collector.calculate_run_metrics(horizon=0.1)

    assert metrics.arrival_count == 2
    assert metrics.completed_count == 1
    assert metrics.pending_count == 1
    assert metrics.throughput == pytest.approx(10.0)
    assert metrics.average_queue_time == 0.0
    assert metrics.average_response_time == pytest.approx(0.05)


def test_run_metrics_calculate_average_queue_and_response_times() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(request)
    request.assign_to(server.id)
    collector.record_routing(request, server)
    environment.run(until=0.02)
    collector.record_service_started(request, server)
    environment.run(until=0.07)
    collector.record_service_completed(request, server)

    metrics = collector.calculate_run_metrics(horizon=0.1)

    assert metrics.average_queue_time == pytest.approx(0.02)
    assert metrics.average_response_time == pytest.approx(0.07)


def test_run_metrics_apply_horizon_boundaries() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    completed = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(completed)
    completed.assign_to(server.id)
    collector.record_service_started(completed, server)
    environment.run(until=1.0)
    collector.record_service_completed(completed, server)

    excluded = Request(id=1, burst_id=0, arrival_time=environment.now)
    collector.record_arrival(excluded)

    metrics = collector.calculate_run_metrics(horizon=1.0)

    assert metrics.arrival_count == 1
    assert metrics.completed_count == 1
    assert metrics.pending_count == 0
    assert metrics.throughput == 1.0
    assert metrics.average_response_time == 1.0


def test_run_metrics_ignore_completions_after_horizon() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(request)
    request.assign_to(server.id)
    collector.record_service_started(request, server)
    environment.run(until=1.01)
    collector.record_service_completed(request, server)

    metrics = collector.calculate_run_metrics(horizon=1.0)

    assert metrics.completed_count == 0
    assert metrics.pending_count == 1
    assert metrics.average_response_time is None


def test_run_metrics_are_immutable() -> None:
    metrics = MetricsCollector(simpy.Environment()).calculate_run_metrics(1.0)

    with pytest.raises(FrozenInstanceError):
        metrics.arrival_count = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("invalid_horizon", "expected_exception"),
    [
        (0, ValueError),
        (-1, ValueError),
        (math.inf, ValueError),
        (math.nan, ValueError),
        (True, TypeError),
        ("200", TypeError),
    ],
)
def test_run_metrics_reject_invalid_horizon(
    invalid_horizon: object,
    expected_exception: type[Exception],
) -> None:
    collector = MetricsCollector(simpy.Environment())

    with pytest.raises(expected_exception, match="horizon"):
        collector.calculate_run_metrics(invalid_horizon)  # type: ignore[arg-type]
