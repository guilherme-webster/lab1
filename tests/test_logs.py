"""Testes unitarios dos logs estruturados da simulacao."""

import logging

import pytest
import simpy

from load_balancer_sim import (
    EVENT_LOG_HEADER,
    MetricEvent,
    MetricsCollector,
    Request,
    RunMetrics,
    SimulationConfig,
    SimulationLogger,
)


def _captured_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records]


def test_run_start_logs_configuration_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.start")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    simulation_logger = SimulationLogger(logger)

    simulation_logger.log_run_started(SimulationConfig())

    assert _captured_messages(caplog) == [
        "run_started,policy=round_robin,server_count=3,server_capacity=15,"
        "service_time=0.050000,burst_max=30,hurst=0.800000,"
        "horizon=200.000000,seed=12345",
        EVENT_LOG_HEADER,
    ]
    assert [record.levelno for record in caplog.records] == [
        logging.INFO,
        logging.DEBUG,
    ]


def test_metric_event_logs_csv_line_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.event")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    simulation_logger = SimulationLogger(logger)
    event = MetricEvent(
        time=1.25,
        event="service_started",
        request_id=7,
        burst_id=2,
        server_id=1,
        active_count=4,
        waiting_count=3,
    )

    simulation_logger.log_event(event)

    assert _captured_messages(caplog) == [
        "1.250000,service_started,7,2,1,4,3"
    ]
    assert caplog.records[0].levelno == logging.DEBUG


def test_arrival_log_uses_empty_server_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.arrival")
    caplog.set_level(logging.DEBUG, logger=logger.name)

    SimulationLogger(logger).log_event(
        MetricEvent(0.0, "arrival", 0, 0, None, None, None)
    )

    assert _captured_messages(caplog) == ["0.000000,arrival,0,0,,,"]


def test_run_completion_logs_summary_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.summary")
    caplog.set_level(logging.INFO, logger=logger.name)
    metrics = RunMetrics(
        horizon=200.0,
        arrival_count=12,
        completed_count=10,
        pending_count=2,
        throughput=0.05,
        average_queue_time=None,
        average_response_time=0.075,
    )

    SimulationLogger(logger).log_run_completed(metrics)

    assert _captured_messages(caplog) == [
        "run_completed,horizon=200.000000,arrivals=12,completed=10,pending=2,"
        "throughput=0.050000,average_queue_time=none,"
        "average_response_time=0.075000"
    ]
    assert caplog.records[0].levelno == logging.INFO


def test_info_level_suppresses_debug_event_lines(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.level")
    caplog.set_level(logging.INFO, logger=logger.name)

    SimulationLogger(logger).log_event(
        MetricEvent(0.0, "arrival", 0, 0, None, None, None)
    )

    assert caplog.records == []


def test_collector_forwards_each_event_to_logger(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("load_balancer_sim.test.collector")
    caplog.set_level(logging.DEBUG, logger=logger.name)
    simulation_logger = SimulationLogger(logger)
    collector = MetricsCollector(
        simpy.Environment(),
        event_handler=simulation_logger.log_event,
    )

    collector.record_arrival(Request(id=3, burst_id=1, arrival_time=0.0))

    assert _captured_messages(caplog) == ["0.000000,arrival,3,1,,,"]


def test_collector_rejects_invalid_event_handler() -> None:
    with pytest.raises(TypeError, match="event_handler"):
        MetricsCollector(
            simpy.Environment(),
            event_handler=object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("method_name", "invalid_value", "expected_message"),
    [
        ("log_run_started", object(), "config"),
        ("log_event", object(), "event"),
        ("log_run_completed", object(), "metrics"),
    ],
)
def test_simulation_logger_rejects_invalid_data(
    method_name: str,
    invalid_value: object,
    expected_message: str,
) -> None:
    method = getattr(SimulationLogger(logging.getLogger()), method_name)

    with pytest.raises(TypeError, match=expected_message):
        method(invalid_value)


def test_simulation_logger_rejects_invalid_logger() -> None:
    with pytest.raises(TypeError, match="logger"):
        SimulationLogger(object())  # type: ignore[arg-type]
