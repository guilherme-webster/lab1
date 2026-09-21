"""Servidor de processamento usado na simulacao."""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from random import Random
from typing import Generator, Literal

import simpy

from load_balancer_sim.request import Request


ServerEvent = Literal[
    "initialized",
    "request_received",
    "service_started",
    "service_completed",
]

ServiceTimeSampler = Callable[[Request], float]
ServerEventCallback = Callable[[Request, "Server"], None]


@dataclass(frozen=True, slots=True)
class ServerState:
    """Fotografia imutavel do estado de um servidor em um evento."""

    time: float
    event: ServerEvent
    server_id: int
    request_id: int | None
    active_count: int
    waiting_count: int
    completed_count: int


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


class Server:
    """Processa requisicoes de forma concorrente e com fila FIFO.

    A concorrencia e limitada por um :class:`simpy.Resource`. Requisicoes que
    excedem a capacidade aguardam automaticamente na fila do recurso.
    """

    def __init__(
        self,
        environment: simpy.Environment,
        server_id: int,
        capacity: int = 1,
        service_rate: float = 20.0,
        seed: int | None = None,
        service_time_sampler: ServiceTimeSampler | None = None,
        on_service_started: ServerEventCallback | None = None,
        on_service_completed: ServerEventCallback | None = None,
    ) -> None:
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")
        if seed is not None:
            _non_negative_integer(seed, "seed")
        if service_time_sampler is not None and not callable(service_time_sampler):
            raise TypeError("service_time_sampler deve ser chamavel")
        if on_service_started is not None and not callable(on_service_started):
            raise TypeError("on_service_started deve ser chamavel")
        if on_service_completed is not None and not callable(on_service_completed):
            raise TypeError("on_service_completed deve ser chamavel")

        self.environment = environment
        self.id = _non_negative_integer(server_id, "server_id")
        self.service_rate = _positive_number(service_rate, "service_rate")
        self._rng = Random(seed)
        self._service_time_sampler = service_time_sampler
        self._on_service_started = on_service_started
        self._on_service_completed = on_service_completed
        self._resource = simpy.Resource(
            environment,
            capacity=_positive_integer(capacity, "capacity"),
        )
        self._completed_count = 0
        self._maximum_active_count = 0
        self._maximum_waiting_count = 0
        self._state_history: list[ServerState] = []
        self._record_state("initialized")

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

    @property
    def completed_count(self) -> int:
        """Quantidade de requisicoes concluidas por este servidor."""
        return self._completed_count

    @property
    def maximum_active_count(self) -> int:
        """Maior quantidade observada de requisicoes simultaneas."""
        return self._maximum_active_count

    @property
    def maximum_waiting_count(self) -> int:
        """Maior comprimento observado da fila de espera."""
        return self._maximum_waiting_count

    @property
    def state_history(self) -> tuple[ServerState, ...]:
        """Historico de estados, protegido contra alteracoes externas."""
        return tuple(self._state_history)

    def _record_state(
        self,
        event: ServerEvent,
        request_id: int | None = None,
    ) -> None:
        """Registra o estado corrente e atualiza os maximos observados."""
        self._maximum_active_count = max(
            self._maximum_active_count,
            self.active_count,
        )
        self._maximum_waiting_count = max(
            self._maximum_waiting_count,
            self.waiting_count,
        )
        self._state_history.append(
            ServerState(
                time=float(self.environment.now),
                event=event,
                server_id=self.id,
                request_id=request_id,
                active_count=self.active_count,
                waiting_count=self.waiting_count,
                completed_count=self.completed_count,
            )
        )

    def _next_service_duration(self, request: Request) -> float:
        """Produz uma duracao exponencial ou usa o sampler injetado."""
        if self._service_time_sampler is not None:
            duration = self._service_time_sampler(request)
        else:
            duration = self._rng.expovariate(self.service_rate)
            while duration <= 0:
                duration = self._rng.expovariate(self.service_rate)

        return _positive_number(duration, "service_duration")

    def handle(self, request: Request) -> Generator[simpy.Event, None, None]:
        """Atende uma requisicao previamente atribuida a este servidor."""
        if not isinstance(request, Request):
            raise TypeError("request deve ser uma Request")
        if request.assigned_server != self.id:
            raise ValueError("a requisicao deve estar atribuida a este servidor")

        with self._resource.request() as slot:
            self._record_state("request_received", request.id)
            yield slot
            request.mark_service_started(self.environment.now)
            self._record_state("service_started", request.id)
            if self._on_service_started is not None:
                self._on_service_started(request, self)

            yield self.environment.timeout(self._next_service_duration(request))
            request.mark_completed(self.environment.now)

        self._completed_count += 1
        if self._on_service_completed is not None:
            self._on_service_completed(request, self)
        self._record_state("service_completed", request.id)
