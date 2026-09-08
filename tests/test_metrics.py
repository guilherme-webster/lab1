"""Testes unitarios dos eventos basicos de metricas."""

from collections.abc import Generator
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
    ServerUtilization,
)
from load_balancer_sim.load_balancer import LoadBalancer


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


def test_server_callbacks_collect_complete_request_lifecycle() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(
        environment,
        server_id=2,
        service_time_sampler=lambda _: 0.05,
        on_service_started=collector.record_service_started,
        on_service_completed=collector.record_service_completed,
    )
    load_balancer = LoadBalancer(environment, [server])
    request = Request(id=7, burst_id=3, arrival_time=environment.now)

    collector.record_arrival(request)
    selected_server = load_balancer.route_request(request)
    collector.record_routing(request, selected_server)
    environment.run()

    assert [event.event for event in collector.events] == [
        "arrival",
        "routing",
        "service_started",
        "service_completed",
    ]
    assert [event.time for event in collector.events] == pytest.approx(
        [0.0, 0.0, 0.0, 0.05]
    )
    assert collector.events[2].active_count == 1
    assert collector.events[3].active_count == 0


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
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    servers = [Server(environment, server_id=index) for index in range(3)]

    metrics = collector.calculate_run_metrics(
        horizon=200,
        warmup=20,
        servers=servers,
    )

    assert metrics == RunMetrics(
        horizon=200.0,
        warmup=20.0,
        measurement_duration=180.0,
        arrival_count=0,
        completed_count=0,
        pending_count=0,
        throughput=0.0,
        average_queue_time=None,
        average_response_time=None,
        average_number_in_system=0.0,
        server_utilizations=(
            ServerUtilization(0, 0.0),
            ServerUtilization(1, 0.0),
            ServerUtilization(2, 0.0),
        ),
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

    metrics = collector.calculate_run_metrics(
        horizon=0.1,
        warmup=0.0,
        servers=[server],
    )

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

    metrics = collector.calculate_run_metrics(
        horizon=0.1,
        warmup=0.0,
        servers=[server],
    )

    assert metrics.average_queue_time == pytest.approx(0.02)
    assert metrics.average_response_time == pytest.approx(0.07)


def test_run_metrics_apply_horizon_boundaries() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    completed = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(completed)
    completed.assign_to(server.id)
    collector.record_routing(completed, server)
    collector.record_service_started(completed, server)
    environment.run(until=1.0)
    collector.record_service_completed(completed, server)

    excluded = Request(id=1, burst_id=0, arrival_time=environment.now)
    collector.record_arrival(excluded)

    metrics = collector.calculate_run_metrics(
        horizon=1.0,
        warmup=0.0,
        servers=[server],
    )

    assert metrics.arrival_count == 1
    assert metrics.completed_count == 0
    assert metrics.pending_count == 1
    assert metrics.throughput == 0.0
    assert metrics.average_response_time is None


def test_run_metrics_ignore_completions_after_horizon() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(environment, server_id=0)
    request = Request(id=0, burst_id=0, arrival_time=0.0)

    collector.record_arrival(request)
    request.assign_to(server.id)
    collector.record_routing(request, server)
    collector.record_service_started(request, server)
    environment.run(until=1.01)
    collector.record_service_completed(request, server)

    metrics = collector.calculate_run_metrics(
        horizon=1.0,
        warmup=0.0,
        servers=[server],
    )

    assert metrics.completed_count == 0
    assert metrics.pending_count == 1
    assert metrics.average_response_time is None


def test_run_metrics_integrate_queue_and_utilization_with_window_clipping() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    durations = {0: 4.0, 1: 2.0}
    busy_server = Server(
        environment,
        server_id=0,
        service_time_sampler=lambda request: durations[request.id],
        on_service_started=collector.record_service_started,
        on_service_completed=collector.record_service_completed,
    )
    idle_server = Server(environment, server_id=1)
    second_idle_server = Server(environment, server_id=2)
    load_balancer = LoadBalancer(environment, [busy_server])

    def submit_requests() -> Generator[simpy.Event, None, None]:
        for request_id, arrival_time in ((0, 0.0), (1, 1.0)):
            if environment.now < arrival_time:
                yield environment.timeout(arrival_time - environment.now)
            request = Request(request_id, 0, environment.now)
            collector.record_arrival(request)
            selected_server = load_balancer.route_request(request)
            collector.record_routing(request, selected_server)

    environment.process(submit_requests())
    environment.run(until=6.01)

    metrics = collector.calculate_run_metrics(
        horizon=6.0,
        warmup=2.0,
        servers=[second_idle_server, idle_server, busy_server],
    )

    assert metrics.measurement_duration == 4.0
    assert metrics.arrival_count == 0
    assert metrics.completed_count == 1
    assert metrics.pending_count == 1
    assert metrics.throughput == pytest.approx(0.25)
    assert metrics.average_queue_time == pytest.approx(3.0)
    assert metrics.average_response_time == pytest.approx(4.0)
    assert metrics.average_number_in_system == pytest.approx(1.5)
    assert metrics.server_utilizations == (
        ServerUtilization(server_id=0, utilization=1.0),
        ServerUtilization(server_id=1, utilization=0.0),
        ServerUtilization(server_id=2, utilization=0.0),
    )


def test_run_metrics_include_completion_at_warmup_boundary() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    server = Server(
        environment,
        server_id=0,
        service_time_sampler=lambda _: 2.0,
        on_service_started=collector.record_service_started,
        on_service_completed=collector.record_service_completed,
    )
    load_balancer = LoadBalancer(environment, [server])
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    collector.record_arrival(request)
    collector.record_routing(request, load_balancer.route_request(request))
    environment.run(until=2.01)

    metrics = collector.calculate_run_metrics(
        horizon=3.0,
        warmup=2.0,
        servers=[server],
    )

    assert metrics.arrival_count == 0
    assert metrics.completed_count == 1
    assert metrics.pending_count == 0
    assert metrics.throughput == 1.0
    assert metrics.average_response_time == 2.0
    assert metrics.average_number_in_system == 0.0
    assert metrics.server_utilizations == (ServerUtilization(0, 0.0),)


def test_run_metrics_are_immutable() -> None:
    environment = simpy.Environment()
    metrics = MetricsCollector(environment).calculate_run_metrics(
        horizon=1.0,
        warmup=0.0,
        servers=[Server(environment, server_id=0)],
    )

    with pytest.raises(FrozenInstanceError):
        metrics.arrival_count = 1  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        metrics.server_utilizations[0].utilization = 1.0  # type: ignore[misc]


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
    environment = simpy.Environment()
    collector = MetricsCollector(environment)

    with pytest.raises(expected_exception, match="horizon"):
        collector.calculate_run_metrics(
            horizon=invalid_horizon,  # type: ignore[arg-type]
            warmup=0.0,
            servers=[Server(environment, server_id=0)],
        )


@pytest.mark.parametrize(
    ("invalid_warmup", "expected_exception"),
    [
        (-1, ValueError),
        (10, ValueError),
        (11, ValueError),
        (math.inf, ValueError),
        (math.nan, ValueError),
        (True, TypeError),
        ("2", TypeError),
    ],
)
def test_run_metrics_reject_invalid_warmup(
    invalid_warmup: object,
    expected_exception: type[Exception],
) -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)

    with pytest.raises(expected_exception, match="warmup"):
        collector.calculate_run_metrics(
            horizon=10.0,
            warmup=invalid_warmup,  # type: ignore[arg-type]
            servers=[Server(environment, server_id=0)],
        )


def test_run_metrics_reject_servers_from_another_environment() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)

    with pytest.raises(ValueError, match="ambiente"):
        collector.calculate_run_metrics(
            horizon=10.0,
            warmup=0.0,
            servers=[Server(simpy.Environment(), server_id=0)],
        )


def test_run_metrics_reject_unreported_server_from_events() -> None:
    environment = simpy.Environment()
    collector = MetricsCollector(environment)
    observed_server = Server(environment, server_id=0)
    reported_server = Server(environment, server_id=1)
    request = Request(id=0, burst_id=0, arrival_time=0.0)
    request.assign_to(observed_server.id)
    collector.record_routing(request, observed_server)

    with pytest.raises(ValueError, match="nao informados"):
        collector.calculate_run_metrics(
            horizon=10.0,
            warmup=0.0,
            servers=[reported_server],
        )
