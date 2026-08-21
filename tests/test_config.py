"""Testes unitarios da configuracao da simulacao."""

from dataclasses import FrozenInstanceError
import math

import pytest

from load_balancer_sim import SimulationConfig


def test_config_uses_project_defaults() -> None:
    config = SimulationConfig()

    assert config.policy == "round_robin"
    assert config.server_count == 3
    assert config.server_capacity == 15
    assert config.service_time == 0.05
    assert config.burst_max == 30
    assert config.hurst == 0.8
    assert config.horizon == 200.0
    assert config.seed == 12345


@pytest.mark.parametrize("policy", ["random", "round_robin", "shortest_queue"])
def test_config_accepts_every_supported_policy(policy: str) -> None:
    config = SimulationConfig(policy=policy)  # type: ignore[arg-type]

    assert config.policy == policy


def test_config_normalizes_numeric_durations() -> None:
    config = SimulationConfig(service_time=1, hurst=0.5, horizon=10)

    assert config.service_time == 1.0
    assert config.hurst == 0.5
    assert config.horizon == 10.0


def test_config_is_immutable() -> None:
    config = SimulationConfig()

    with pytest.raises(FrozenInstanceError):
        config.seed = 1  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_exception"),
    [
        ("policy", "least_connections", ValueError),
        ("policy", 1, TypeError),
        ("server_count", 0, ValueError),
        ("server_count", 3.0, TypeError),
        ("server_capacity", -1, ValueError),
        ("server_capacity", True, TypeError),
        ("service_time", 0, ValueError),
        ("service_time", math.inf, ValueError),
        ("service_time", "0.05", TypeError),
        ("burst_max", 20, ValueError),
        ("burst_max", 30.0, TypeError),
        ("hurst", 0, ValueError),
        ("hurst", 1, ValueError),
        ("hurst", math.nan, ValueError),
        ("horizon", 0, ValueError),
        ("horizon", math.inf, ValueError),
        ("seed", -1, ValueError),
        ("seed", 1.5, TypeError),
    ],
)
def test_config_rejects_invalid_values(
    field_name: str,
    invalid_value: object,
    expected_exception: type[Exception],
) -> None:
    config_data = {field_name: invalid_value}

    with pytest.raises(expected_exception, match=field_name):
        SimulationConfig(**config_data)  # type: ignore[arg-type]
