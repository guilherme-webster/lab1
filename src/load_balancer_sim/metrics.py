"""Eventos basicos usados para coletar metricas da simulacao."""

from dataclasses import dataclass
from typing import Literal

import simpy

from load_balancer_sim.request import Request
from load_balancer_sim.server import Server


MetricEventType = Literal[
    "arrival",
    "routing",
    "service_started",
    "service_completed",
]


@dataclass(frozen=True, slots=True)
class MetricEvent:
    """Registro imutavel de um evento do ciclo de vida da requisicao."""

    time: float
    event: MetricEventType
    request_id: int
    burst_id: int
    server_id: int | None
    active_count: int | None
    waiting_count: int | None


class MetricsCollector:
    """Armazena eventos na ordem em que foram observados.

    Neste estagio, o coletor apenas registra dados. Calculos agregados,
    invariantes e emissao de logs pertencem a incrementos posteriores.
    """

    def __init__(self, environment: simpy.Environment) -> None:
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")

        self.environment = environment
        self._events: list[MetricEvent] = []

    @property
    def events(self) -> tuple[MetricEvent, ...]:
        """Historico de eventos, protegido contra alteracoes externas."""
        return tuple(self._events)

    def record_arrival(self, request: Request) -> None:
        """Registra a chegada de uma requisicao ao sistema."""
        self._record("arrival", request)

    def record_routing(self, request: Request, server: Server) -> None:
        """Registra a decisao de encaminhamento para um servidor."""
        self._record("routing", request, server)

    def record_service_started(self, request: Request, server: Server) -> None:
        """Registra o inicio do processamento por um servidor."""
        self._record("service_started", request, server)

    def record_service_completed(self, request: Request, server: Server) -> None:
        """Registra a conclusao do processamento por um servidor."""
        self._record("service_completed", request, server)

    def _record(
        self,
        event: MetricEventType,
        request: Request,
        server: Server | None = None,
    ) -> None:
        """Acrescenta um evento e, quando possivel, fotografa o servidor."""
        if not isinstance(request, Request):
            raise TypeError("request deve ser uma Request")
        if server is not None and not isinstance(server, Server):
            raise TypeError("server deve ser um Server")

        self._events.append(
            MetricEvent(
                time=float(self.environment.now),
                event=event,
                request_id=request.id,
                burst_id=request.burst_id,
                server_id=None if server is None else server.id,
                active_count=None if server is None else server.active_count,
                waiting_count=None if server is None else server.waiting_count,
            )
        )
