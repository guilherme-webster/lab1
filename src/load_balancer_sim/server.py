"""Servidor de processamento usado na simulacao."""

from math import isfinite
from typing import Generator

import simpy

from load_balancer_sim.request import Request


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


def _positive_time(value: float, field_name: str) -> float:
    """Normaliza e valida uma duracao estritamente positiva."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError(f"{field_name} deve ser finito")
    if normalized_value <= 0:
        raise ValueError(f"{field_name} deve ser positivo")
    return normalized_value


class Server:
    """Processa requisicoes de forma concorrente e com fila FIFO.

    A concorrencia e limitada por um :class:`simpy.Resource`. Requisicoes que
    excedem a capacidade aguardam automaticamente na fila do recurso.
    """

    def __init__(
        self,
        environment: simpy.Environment,
        server_id: int,
        capacity: int = 15,
        service_time: float = 0.05,
    ) -> None:
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")

        self.environment = environment
        self.id = _non_negative_integer(server_id, "server_id")
        self.service_time = _positive_time(service_time, "service_time")
        self._resource = simpy.Resource(
            environment,
            capacity=_positive_integer(capacity, "capacity"),
        )

    @property
    def capacity(self) -> int:
        """Quantidade maxima de requisicoes processadas simultaneamente."""
        return self._resource.capacity

    @property
    def active_count(self) -> int:
        """Quantidade de requisicoes atualmente em processamento."""
        return self._resource.count

    @property
    def waiting_count(self) -> int:
        """Quantidade de requisicoes aguardando um slot de processamento."""
        return len(self._resource.queue)

    def handle(self, request: Request) -> Generator[simpy.Event, None, None]:
        """Atende uma requisicao previamente atribuida a este servidor."""
        if not isinstance(request, Request):
            raise TypeError("request deve ser uma Request")
        if request.assigned_server != self.id:
            raise ValueError("a requisicao deve estar atribuida a este servidor")

        with self._resource.request() as slot:
            yield slot
            request.mark_service_started(self.environment.now)
            yield self.environment.timeout(self.service_time)
            request.mark_completed(self.environment.now)
