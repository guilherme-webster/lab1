"""Configuracao de uma rodada da simulacao."""

from dataclasses import dataclass
from math import isfinite
from typing import Literal


PolicyName = Literal[
    "random", 
    "round_robin", 
    "shortest_queue"
]

SUPPORTED_POLICIES: tuple[PolicyName, ...] = (
    "random",
    "round_robin",
    "shortest_queue",
)


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


def _non_negative_number(value: float, field_name: str) -> float:
    """Normaliza e valida um numero finito e nao negativo."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError(f"{field_name} deve ser finito")
    if normalized_value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return normalized_value


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Parametros imutaveis usados para executar uma rodada."""

    policy: PolicyName = "round_robin"
    server_count: int = 3
    server_capacity: int = 1
    service_rate: float = 1.0
    arrival_rate: float = 1.8
    horizon: float = 5000.0
    warmup: float = 500.0
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
            "service_rate",
            _positive_number(self.service_rate, "service_rate"),
        )
        object.__setattr__(
            self,
            "arrival_rate",
            _positive_number(self.arrival_rate, "arrival_rate"),
        )

        object.__setattr__(
            self,
            "horizon",
            _positive_number(self.horizon, "horizon"),
        )
        object.__setattr__(
            self,
            "warmup",
            _non_negative_number(self.warmup, "warmup"),
        )
        if self.warmup >= self.horizon:
            raise ValueError("warmup deve ser menor que horizon")
        _non_negative_integer(self.seed, "seed")
