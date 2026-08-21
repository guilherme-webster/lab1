"""Eventos basicos usados para coletar metricas da simulacao."""

from dataclasses import dataclass
from collections.abc import Callable
from math import isfinite
from statistics import fmean
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


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """Resumo imutavel das metricas observadas em uma rodada."""

    horizon: float
    arrival_count: int
    completed_count: int
    pending_count: int
    throughput: float
    average_queue_time: float | None
    average_response_time: float | None


class MetricsCollector:
    """Armazena eventos na ordem em que foram observados.

    O coletor tambem resume os eventos ocorridos dentro de uma janela. A
    validacao de invariantes ocorre separadamente. Um tratador opcional recebe
    cada evento logo apos seu registro, permitindo emitir logs sem acoplar o
    coletor a uma configuracao global.
    """

    def __init__(
        self,
        environment: simpy.Environment,
        event_handler: Callable[[MetricEvent], None] | None = None,
    ) -> None:
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")
        if event_handler is not None and not callable(event_handler):
            raise TypeError("event_handler deve ser chamavel")

        self.environment = environment
        self._event_handler = event_handler
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

    def calculate_run_metrics(self, horizon: float) -> RunMetrics:
        """Calcula as metricas dos eventos pertencentes a uma janela.

        Chegadas em ``horizon`` nao pertencem a rodada. Conclusoes exatamente
        nesse instante pertencem, seguindo o protocolo de medicao do projeto.
        O tempo medio de fila considera requisicoes que iniciaram servico na
        janela; o tempo medio de resposta considera as que foram concluidas.
        """
        normalized_horizon = _positive_horizon(horizon)
        arrival_times: dict[int, float] = {}
        service_start_times: dict[int, float] = {}
        completion_times: dict[int, float] = {}

        for event in self._events:
            if event.event == "arrival" and event.time < normalized_horizon:
                arrival_times.setdefault(event.request_id, event.time)
            elif (
                event.event == "service_started"
                and event.time <= normalized_horizon
            ):
                service_start_times.setdefault(event.request_id, event.time)
            elif (
                event.event == "service_completed"
                and event.time <= normalized_horizon
            ):
                completion_times.setdefault(event.request_id, event.time)

        arrived_request_ids = set(arrival_times)
        started_request_ids = arrived_request_ids.intersection(service_start_times)
        completed_request_ids = arrived_request_ids.intersection(completion_times)

        queue_times = [
            service_start_times[request_id] - arrival_times[request_id]
            for request_id in started_request_ids
        ]
        response_times = [
            completion_times[request_id] - arrival_times[request_id]
            for request_id in completed_request_ids
        ]

        arrival_count = len(arrived_request_ids)
        completed_count = len(completed_request_ids)
        return RunMetrics(
            horizon=normalized_horizon,
            arrival_count=arrival_count,
            completed_count=completed_count,
            pending_count=arrival_count - completed_count,
            throughput=completed_count / normalized_horizon,
            average_queue_time=None if not queue_times else fmean(queue_times),
            average_response_time=(
                None if not response_times else fmean(response_times)
            ),
        )

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

        metric_event = MetricEvent(
            time=float(self.environment.now),
            event=event,
            request_id=request.id,
            burst_id=request.burst_id,
            server_id=None if server is None else server.id,
            active_count=None if server is None else server.active_count,
            waiting_count=None if server is None else server.waiting_count,
        )
        self._events.append(metric_event)
        if self._event_handler is not None:
            self._event_handler(metric_event)


def _positive_horizon(value: float) -> float:
    """Normaliza e valida o horizonte usado no calculo das metricas."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("horizon deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError("horizon deve ser finito")
    if normalized_value <= 0:
        raise ValueError("horizon deve ser positivo")
    return normalized_value
