"""Testes unitarios da configuracao da simulacao."""

from dataclasses import FrozenInstanceError
import math

import pytest

from load_balancer_sim import SimulationConfig


def test_config_uses_project_defaults() -> None:
    config = SimulationConfig()

    assert config.policy == "round_robin"
    assert config.server_count == 3
    assert config.server_capacity == 1
    assert config.service_rate == 1.0
    assert config.arrival_rate == 1.8
    assert config.horizon == 5000.0
    assert config.warmup == 500.0
    assert config.seed == 12345


@pytest.mark.parametrize("policy", ["random", "round_robin", "shortest_queue"])
def test_config_accepts_every_supported_policy(policy: str) -> None:
    config = SimulationConfig(policy=policy)  # type: ignore[arg-type]

    assert config.policy == policy


def test_config_normalizes_numeric_durations() -> None:
    config = SimulationConfig(
        service_rate=2,
        arrival_rate=2,
        horizon=10,
        warmup=1,
    )

    assert config.service_rate == 2.0
    assert config.arrival_rate == 2.0
    assert config.horizon == 10.0
    assert config.warmup == 1.0


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
        ("service_rate", 0, ValueError),
        ("service_rate", math.inf, ValueError),
        ("service_rate", "1.0", TypeError),
        ("arrival_rate", 0, ValueError),
        ("arrival_rate", math.inf, ValueError),
        ("arrival_rate", "1.0", TypeError),
        ("horizon", 0, ValueError),
        ("horizon", math.inf, ValueError),
        ("warmup", -1, ValueError),
        ("warmup", math.inf, ValueError),
        ("warmup", "500", TypeError),
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


def test_config_requires_warmup_before_horizon() -> None:
    with pytest.raises(ValueError, match="warmup"):
        SimulationConfig(horizon=500.0, warmup=500.0)
