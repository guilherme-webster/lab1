"""Configuracao de uma rodada da simulacao."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal


PolicyName = Literal["random", "round_robin", "shortest_queue"]

SUPPORTED_POLICIES: tuple[PolicyName, ...] = (
    "random",
    "round_robin",
    "shortest_queue",
)
SUPPORTED_BURST_MAX_VALUES = (30, 60, 90, 120)


def _positive_integer(value: int, field_name: str) -> int:
    """Valida um parametro inteiro estritamente positivo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} deve ser um numero inteiro")
    if value <= 0:
        raise ValueError(f"{field_name} deve ser positivo")
    return value


def _non_negative_integer(value: int, field_name: str) -> int:
    """Valida um parametro inteiro e nao negativo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} deve ser um numero inteiro")
    if value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return value


def _positive_number(value: float, field_name: str) -> float:
    """Normaliza e valida um numero finito estritamente positivo."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError(f"{field_name} deve ser finito")
    if normalized_value <= 0:
        raise ValueError(f"{field_name} deve ser positivo")
    return normalized_value


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Parametros imutaveis usados para executar uma rodada."""

    policy: PolicyName = "round_robin"
    server_count: int = 3
    server_capacity: int = 15
    service_time: float = 0.05
    burst_max: int = 30
    hurst: float = 0.8
    horizon: float = 200.0
    seed: int = 12345

    def __post_init__(self) -> None:
        if not isinstance(self.policy, str):
            raise TypeError("policy deve ser uma string")
        if self.policy not in SUPPORTED_POLICIES:
            raise ValueError(f"policy desconhecida: {self.policy}")

        _positive_integer(self.server_count, "server_count")
        _positive_integer(self.server_capacity, "server_capacity")
        object.__setattr__(
            self,
            "service_time",
            _positive_number(self.service_time, "service_time"),
        )

        if isinstance(self.burst_max, bool) or not isinstance(self.burst_max, int):
            raise TypeError("burst_max deve ser um numero inteiro")
        if self.burst_max not in SUPPORTED_BURST_MAX_VALUES:
            raise ValueError(
                f"burst_max deve pertencer a {SUPPORTED_BURST_MAX_VALUES}"
            )

        normalized_hurst = _positive_number(self.hurst, "hurst")
        if normalized_hurst >= 1:
            raise ValueError("hurst deve ser menor que 1")
        object.__setattr__(self, "hurst", normalized_hurst)

        object.__setattr__(
            self,
            "horizon",
            _positive_number(self.horizon, "horizon"),
        )
        _non_negative_integer(self.seed, "seed")
