"""Eventos basicos usados para coletar metricas da simulacao."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
class ServerUtilization:
    """Utilizacao temporal de um servidor na janela de medicao."""

    server_id: int
    utilization: float


@dataclass(frozen=True, slots=True)
class RunMetrics:
    """Resumo imutavel das metricas observadas em uma rodada."""

    horizon: float
    warmup: float
    measurement_duration: float
    arrival_count: int
    completed_count: int
    pending_count: int
    throughput: float
    average_queue_time: float | None
    average_response_time: float | None
    average_number_in_system: float
    server_utilizations: tuple[ServerUtilization, ...]


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

    def calculate_run_metrics(
        self,
        horizon: float,
        warmup: float,
        servers: Sequence[Server],
    ) -> RunMetrics:
        """Calcula contagens e medias temporais em ``[warmup, horizon)``.

        Tempos de fila e resposta preservam a chegada original, inclusive
        quando ela ocorreu antes do warm-up. A ocupacao e integrada a partir
        das transicoes de roteamento, inicio e conclusao registradas. As
        contagens de chegadas e conclusoes pertencem a janela; ``pending`` e a
        populacao que permanece no sistema imediatamente antes do horizonte.
        """
        normalized_horizon = _positive_horizon(horizon)
        normalized_warmup = _valid_warmup(warmup, normalized_horizon)
        validated_servers = _validate_servers(
            servers,
            self.environment,
            self._events,
        )
        measurement_duration = normalized_horizon - normalized_warmup
        arrival_times: dict[int, float] = {}
        service_start_times: dict[int, float] = {}
        completion_times: dict[int, float] = {}
        all_completion_times: dict[int, float] = {}

        for event in self._events:
            if event.event == "arrival" and event.time < normalized_horizon:
                arrival_times.setdefault(event.request_id, event.time)
            elif (
                event.event == "service_started"
                and normalized_warmup <= event.time < normalized_horizon
            ):
                service_start_times.setdefault(event.request_id, event.time)
            elif event.event == "service_completed":
                if event.time < normalized_horizon:
                    all_completion_times.setdefault(event.request_id, event.time)
                if normalized_warmup <= event.time < normalized_horizon:
                    completion_times.setdefault(event.request_id, event.time)

        measurement_arrival_ids = {
            request_id
            for request_id, arrival_time in arrival_times.items()
            if arrival_time >= normalized_warmup
        }
        started_request_ids = set(arrival_times).intersection(service_start_times)
        completed_request_ids = set(arrival_times).intersection(completion_times)

        queue_times = [
            service_start_times[request_id] - arrival_times[request_id]
            for request_id in started_request_ids
        ]
        response_times = [
            completion_times[request_id] - arrival_times[request_id]
            for request_id in completed_request_ids
        ]

        arrival_count = len(measurement_arrival_ids)
        completed_count = len(completed_request_ids)
        pending_count = len(set(arrival_times) - set(all_completion_times))
        average_number, utilizations = _calculate_time_averages(
            self._events,
            validated_servers,
            normalized_warmup,
            normalized_horizon,
        )
        return RunMetrics(
            horizon=normalized_horizon,
            warmup=normalized_warmup,
            measurement_duration=measurement_duration,
            arrival_count=arrival_count,
            completed_count=completed_count,
            pending_count=pending_count,
            throughput=completed_count / measurement_duration,
            average_queue_time=None if not queue_times else fmean(queue_times),
            average_response_time=(
                None if not response_times else fmean(response_times)
            ),
            average_number_in_system=average_number,
            server_utilizations=utilizations,
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


def _valid_warmup(value: float, horizon: float) -> float:
    """Normaliza e valida o inicio da janela de medicao."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("warmup deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError("warmup deve ser finito")
    if normalized_value < 0:
        raise ValueError("warmup nao pode ser negativo")
    if normalized_value >= horizon:
        raise ValueError("warmup deve ser menor que horizon")
    return normalized_value


def _validate_servers(
    servers: Sequence[Server],
    environment: simpy.Environment,
    events: Sequence[MetricEvent],
) -> tuple[Server, ...]:
    """Valida os servidores cujos estados serao integrados."""
    if not isinstance(servers, Sequence):
        raise TypeError("servers deve ser uma sequencia de Server")
    if not servers:
        raise ValueError("servers nao pode ser vazio")
    if any(not isinstance(server, Server) for server in servers):
        raise TypeError("servers deve conter apenas objetos Server")
    if any(server.environment is not environment for server in servers):
        raise ValueError("todos os servidores devem usar o ambiente do coletor")

    server_ids = [server.id for server in servers]
    if len(set(server_ids)) != len(server_ids):
        raise ValueError("os identificadores dos servidores devem ser unicos")

    known_server_ids = set(server_ids)
    unknown_server_ids = {
        event.server_id
        for event in events
        if event.server_id is not None
        and event.server_id not in known_server_ids
    }
    if unknown_server_ids:
        raise ValueError(
            "eventos possuem servidores nao informados: "
            f"{sorted(unknown_server_ids)}"
        )
    return tuple(sorted(servers, key=lambda server: server.id))


def _calculate_time_averages(
    events: Sequence[MetricEvent],
    servers: Sequence[Server],
    warmup: float,
    horizon: float,
) -> tuple[float, tuple[ServerUtilization, ...]]:
    """Integra ocupacao e atividade dos servidores na janela informada."""
    duration = horizon - warmup
    total_number_area = 0.0
    utilizations: list[ServerUtilization] = []

    for server in servers:
        active_count = 0
        number_in_system = 0
        previous_time = 0.0
        active_area = 0.0
        number_area = 0.0

        for event in events:
            if event.server_id != server.id:
                continue
            if event.time >= horizon:
                break

            interval_start = max(previous_time, warmup)
            interval_end = min(event.time, horizon)
            if interval_end > interval_start:
                interval_duration = interval_end - interval_start
                active_area += active_count * interval_duration
                number_area += number_in_system * interval_duration

            if event.event == "routing":
                number_in_system += 1
            elif event.event == "service_started":
                active_count += 1
            elif event.event == "service_completed":
                active_count -= 1
                number_in_system -= 1

            if (
                active_count < 0
                or active_count > server.capacity
                or number_in_system < active_count
            ):
                raise ValueError(
                    f"ciclo de eventos invalido no servidor {server.id}"
                )
            previous_time = event.time

        interval_start = max(previous_time, warmup)
        if horizon > interval_start:
            interval_duration = horizon - interval_start
            active_area += active_count * interval_duration
            number_area += number_in_system * interval_duration

        total_number_area += number_area
        utilizations.append(
            ServerUtilization(
                server_id=server.id,
                utilization=active_area / (duration * server.capacity),
            )
        )

    return total_number_area / duration, tuple(utilizations)
