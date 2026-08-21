"""Testes unitarios da entidade Request."""

import math

import pytest

from load_balancer_sim import Request


def test_request_starts_with_only_arrival_data() -> None:
    request = Request(id=7, burst_id=2, arrival_time=1)

    assert request.id == 7
    assert request.burst_id == 2
    assert request.arrival_time == 1.0
    assert request.assigned_server is None
    assert request.service_start_time is None
    assert request.completion_time is None
    assert request.queue_time is None
    assert request.response_time is None


def test_request_records_lifecycle_and_calculates_metrics() -> None:
    request = Request(id=1, burst_id=0, arrival_time=2.0)

    request.assign_to(server_id=2)
    request.mark_service_started(start_time=2.25)
    request.mark_completed(completion_time=2.30)

    assert request.assigned_server == 2
    assert request.queue_time == pytest.approx(0.25)
    assert request.response_time == pytest.approx(0.30)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_exception"),
    [
        ("id", -1, ValueError),
        ("id", True, TypeError),
        ("burst_id", -1, ValueError),
        ("burst_id", 1.5, TypeError),
        ("arrival_time", -0.1, ValueError),
        ("arrival_time", math.inf, ValueError),
        ("arrival_time", math.nan, ValueError),
        ("arrival_time", "1.0", TypeError),
    ],
)
def test_request_rejects_invalid_creation_data(
    field_name: str,
    invalid_value: object,
    expected_exception: type[Exception],
) -> None:
    request_data = {"id": 1, "burst_id": 1, "arrival_time": 0.0}
    request_data[field_name] = invalid_value

    with pytest.raises(expected_exception):
        Request(**request_data)  # type: ignore[arg-type]


def test_request_cannot_be_assigned_twice() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=0)

    with pytest.raises(RuntimeError, match="ja foi atribuida"):
        request.assign_to(server_id=1)


def test_request_rejects_invalid_server_id() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)

    with pytest.raises(ValueError, match="server_id"):
        request.assign_to(server_id=-1)


def test_service_cannot_start_before_assignment() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)

    with pytest.raises(RuntimeError, match="ainda nao foi atribuida"):
        request.mark_service_started(start_time=0.0)


def test_service_cannot_start_before_arrival() -> None:
    request = Request(id=1, burst_id=0, arrival_time=1.0)
    request.assign_to(server_id=0)

    with pytest.raises(ValueError, match="antes da chegada"):
        request.mark_service_started(start_time=0.9)


def test_service_cannot_start_twice() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=0)
    request.mark_service_started(start_time=0.0)

    with pytest.raises(RuntimeError, match="ja foi iniciado"):
        request.mark_service_started(start_time=0.1)


def test_request_cannot_complete_before_service_starts() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=0)

    with pytest.raises(RuntimeError, match="ainda nao foi iniciado"):
        request.mark_completed(completion_time=0.05)


def test_request_cannot_complete_before_service_start_time() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=0)
    request.mark_service_started(start_time=1.0)

    with pytest.raises(ValueError, match="antes do inicio"):
        request.mark_completed(completion_time=0.9)


def test_request_cannot_complete_twice() -> None:
    request = Request(id=1, burst_id=0, arrival_time=0.0)
    request.assign_to(server_id=0)
    request.mark_service_started(start_time=0.0)
    request.mark_completed(completion_time=0.05)

    with pytest.raises(RuntimeError, match="ja foi concluida"):
        request.mark_completed(completion_time=0.10)
