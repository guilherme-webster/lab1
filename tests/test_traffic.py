"""Testes unitarios do gerador de chegadas Poisson."""

import math

import pytest
import simpy

from load_balancer_sim import (
    PoissonTrafficGenerator,
    Request,
    generate_poisson_arrival_times,
    poisson_arrival_process,
)


def test_generate_poisson_arrival_times_is_reproducible_with_seed() -> None:
    arrivals_a = generate_poisson_arrival_times(
        arrival_rate=5.0,
        horizon=10.0,
        seed=123,
    )
    arrivals_b = generate_poisson_arrival_times(
        arrival_rate=5.0,
        horizon=10.0,
        seed=123,
    )

    assert arrivals_a == arrivals_b


def test_generate_poisson_arrival_times_stay_within_horizon_and_sorted() -> None:
    arrivals = generate_poisson_arrival_times(
        arrival_rate=8.0,
        horizon=20.0,
        seed=1,
    )

    assert all(0.0 <= arrival < 20.0 for arrival in arrivals)
    assert all(left < right for left, right in zip(arrivals, arrivals[1:]))


def test_generate_poisson_arrival_times_average_count_matches_lambda_t() -> None:
    samples = [
        len(
            generate_poisson_arrival_times(
                arrival_rate=2.0,
                horizon=40.0,
                seed=seed,
            )
        )
        for seed in range(200)
    ]
    observed_mean = sum(samples) / len(samples)

    # E[N(T)] = lambda * T para processo de Poisson.
    assert observed_mean == pytest.approx(80.0, rel=0.08)


@pytest.mark.parametrize(
    ("field_name", "kwargs", "expected_exception"),
    [
        (
            "arrival_rate",
            {"arrival_rate": 0, "horizon": 10.0},
            ValueError,
        ),
        (
            "arrival_rate",
            {"arrival_rate": math.inf, "horizon": 10.0},
            ValueError,
        ),
        (
            "arrival_rate",
            {"arrival_rate": "1.0", "horizon": 10.0},
            TypeError,
        ),
        (
            "horizon",
            {"arrival_rate": 1.0, "horizon": 0},
            ValueError,
        ),
        (
            "horizon",
            {"arrival_rate": 1.0, "horizon": "10"},
            TypeError,
        ),
        (
            "seed",
            {"arrival_rate": 1.0, "horizon": 10.0, "seed": -1},
            ValueError,
        ),
        (
            "start_time",
            {"arrival_rate": 1.0, "horizon": 10.0, "start_time": -1},
            ValueError,
        ),
        (
            "start_time",
            {"arrival_rate": 1.0, "horizon": 10.0, "start_time": 10.0},
            ValueError,
        ),
    ],
)
def test_generate_poisson_arrival_times_reject_invalid_parameters(
    field_name: str,
    kwargs: dict[str, object],
    expected_exception: type[Exception],
) -> None:
    with pytest.raises(expected_exception, match=field_name):
        generate_poisson_arrival_times(**kwargs)  # type: ignore[arg-type]


def test_poisson_arrival_process_creates_requests_with_monotonic_ids() -> None:
    environment = simpy.Environment()
    arrived_requests: list[Request] = []

    def on_arrival(request: Request) -> None:
        arrived_requests.append(request)

    environment.process(
        poisson_arrival_process(
            environment,
            arrival_rate=4.0,
            horizon=5.0,
            on_arrival=on_arrival,
            seed=99,
            first_request_id=10,
            burst_id=7,
        )
    )
    environment.run(until=5.0)

    assert [request.id for request in arrived_requests] == list(
        range(10, 10 + len(arrived_requests))
    )
    assert all(request.burst_id == 7 for request in arrived_requests)
    assert all(request.arrival_time < 5.0 for request in arrived_requests)


def test_poisson_arrival_process_rejects_invalid_arguments() -> None:
    environment = simpy.Environment()

    with pytest.raises(TypeError, match="environment"):
        list(
            poisson_arrival_process(
                object(),  # type: ignore[arg-type]
                arrival_rate=1.0,
                horizon=10.0,
                on_arrival=lambda _: None,
            )
        )

    with pytest.raises(TypeError, match="on_arrival"):
        list(
            poisson_arrival_process(
                environment,
                arrival_rate=1.0,
                horizon=10.0,
                on_arrival=object(),  # type: ignore[arg-type]
            )
        )


def test_poisson_traffic_generator_runs_process() -> None:
    environment = simpy.Environment()
    arrivals: list[Request] = []
    generator = PoissonTrafficGenerator(
        environment=environment,
        arrival_rate=2.0,
        horizon=5.0,
        seed=5,
        first_request_id=3,
        burst_id=9,
    )

    environment.process(generator.run(arrivals.append))
    environment.run(until=5.0)

    assert all(request.arrival_time < 5.0 for request in arrivals)
    assert [request.id for request in arrivals] == list(range(3, 3 + len(arrivals)))
    assert all(request.burst_id == 9 for request in arrivals)


def test_poisson_traffic_generator_rejects_invalid_environment() -> None:
    with pytest.raises(TypeError, match="environment"):
        PoissonTrafficGenerator(  # type: ignore[arg-type]
            environment=object(),
            arrival_rate=1.0,
            horizon=2.0,
        )
