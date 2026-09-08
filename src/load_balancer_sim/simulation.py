"""Montagem e execucao de uma rodada completa da simulacao."""

from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from math import isfinite
from random import Random

import simpy

from load_balancer_sim.config import SimulationConfig
from load_balancer_sim.invariants import validate_simulation_invariants
from load_balancer_sim.load_balancer import LoadBalancer
from load_balancer_sim.logs import SimulationLogger
from load_balancer_sim.metrics import MetricEvent, MetricsCollector, RunMetrics
from load_balancer_sim.request import Request
from load_balancer_sim.server import Server
from load_balancer_sim.traffic import generate_poisson_arrival_times


@dataclass(frozen=True, slots=True)
class RunSeeds:
    """Sementes independentes usadas por uma rodada."""

    base_seed: int
    arrival_seed: int
    service_seed: int
    routing_seed: int

    def __post_init__(self) -> None:
        for field_name in (
            "base_seed",
            "arrival_seed",
            "service_seed",
            "routing_seed",
        ):
            _non_negative_integer(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class RequestTraceEntry:
    """Chegada e demanda de servico de uma requisicao."""

    request_id: int
    arrival_time: float
    service_duration: float

    def __post_init__(self) -> None:
        if isinstance(self.request_id, bool) or not isinstance(self.request_id, int):
            raise TypeError("request_id deve ser um numero inteiro")
        if self.request_id < 0:
            raise ValueError("request_id nao pode ser negativo")
        object.__setattr__(
            self,
            "arrival_time",
            _non_negative_number(self.arrival_time, "arrival_time"),
        )
        object.__setattr__(
            self,
            "service_duration",
            _positive_number(self.service_duration, "service_duration"),
        )


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Resultado autocontido e imutavel de uma rodada."""

    config: SimulationConfig
    seeds: RunSeeds
    trace: tuple[RequestTraceEntry, ...]
    metrics: RunMetrics
    events: tuple[MetricEvent, ...]


def derive_run_seeds(base_seed: int) -> RunSeeds:
    """Deriva fluxos independentes e reproduziveis de uma semente base."""
    normalized_seed = _non_negative_integer(base_seed, "base_seed")
    rng = Random(normalized_seed)
    return RunSeeds(
        base_seed=normalized_seed,
        arrival_seed=rng.getrandbits(64),
        service_seed=rng.getrandbits(64),
        routing_seed=rng.getrandbits(64),
    )


def generate_request_trace(
    config: SimulationConfig,
    seeds: RunSeeds | None = None,
) -> tuple[RequestTraceEntry, ...]:
    """Gera chegadas Poisson e demandas exponenciais antes do roteamento."""
    if not isinstance(config, SimulationConfig):
        raise TypeError("config deve ser uma SimulationConfig")
    if seeds is not None and not isinstance(seeds, RunSeeds):
        raise TypeError("seeds deve ser uma RunSeeds")

    run_seeds = derive_run_seeds(config.seed) if seeds is None else seeds
    arrival_times = generate_poisson_arrival_times(
        arrival_rate=config.arrival_rate,
        horizon=config.horizon,
        seed=run_seeds.arrival_seed,
    )
    service_rng = Random(run_seeds.service_seed)
    entries: list[RequestTraceEntry] = []
    for request_id, arrival_time in enumerate(arrival_times):
        service_duration = service_rng.expovariate(config.service_rate)
        while service_duration <= 0:
            service_duration = service_rng.expovariate(config.service_rate)
        entries.append(
            RequestTraceEntry(
                request_id=request_id,
                arrival_time=arrival_time,
                service_duration=service_duration,
            )
        )
    return tuple(entries)


def run_simulation(
    config: SimulationConfig,
    *,
    trace: Sequence[RequestTraceEntry] | None = None,
    simulation_logger: SimulationLogger | None = None,
) -> SimulationResult:
    """Monta todos os componentes e executa uma rodada ate o horizonte."""
    if not isinstance(config, SimulationConfig):
        raise TypeError("config deve ser uma SimulationConfig")
    if simulation_logger is not None and not isinstance(
        simulation_logger,
        SimulationLogger,
    ):
        raise TypeError("simulation_logger deve ser uma SimulationLogger")

    seeds = derive_run_seeds(config.seed)
    request_trace = (
        generate_request_trace(config, seeds)
        if trace is None
        else _validate_trace(trace, config.horizon)
    )
    logger = SimulationLogger() if simulation_logger is None else simulation_logger
    environment = simpy.Environment()
    collector = MetricsCollector(environment, event_handler=logger.log_event)
    service_duration_by_request = {
        entry.request_id: entry.service_duration for entry in request_trace
    }

    def sample_service_time(request: Request) -> float:
        return service_duration_by_request[request.id]

    servers = tuple(
        Server(
            environment,
            server_id=server_id,
            capacity=config.server_capacity,
            service_rate=config.service_rate,
            service_time_sampler=sample_service_time,
            on_service_started=collector.record_service_started,
            on_service_completed=collector.record_service_completed,
        )
        for server_id in range(config.server_count)
    )
    load_balancer = LoadBalancer(
        environment,
        servers,
        policy=config.policy,
        seed=seeds.routing_seed,
    )

    def on_arrival(request: Request) -> None:
        collector.record_arrival(request)
        server = load_balancer.route_request(request)
        collector.record_routing(request, server)

    logger.log_run_started(config)
    environment.process(
        _replay_trace(
            environment=environment,
            trace=request_trace,
            on_arrival=on_arrival,
        )
    )
    environment.run(until=config.horizon)

    validate_simulation_invariants(config, servers, collector)
    metrics = collector.calculate_run_metrics(
        horizon=config.horizon,
        warmup=config.warmup,
        servers=servers,
    )
    logger.log_run_completed(metrics)
    return SimulationResult(
        config=config,
        seeds=seeds,
        trace=request_trace,
        metrics=metrics,
        events=collector.events,
    )


def _replay_trace(
    environment: simpy.Environment,
    trace: Sequence[RequestTraceEntry],
    on_arrival: Callable[[Request], None],
) -> Generator[simpy.Event, None, None]:
    """Reproduz um traço validado no relogio do SimPy."""
    for entry in trace:
        delay = entry.arrival_time - float(environment.now)
        if delay > 0:
            yield environment.timeout(delay)
        on_arrival(
            Request(
                id=entry.request_id,
                burst_id=0,
                arrival_time=entry.arrival_time,
            )
        )


def _validate_trace(
    trace: Sequence[RequestTraceEntry],
    horizon: float,
) -> tuple[RequestTraceEntry, ...]:
    """Valida um traço externo antes de alterar o estado da simulacao."""
    if not isinstance(trace, Sequence):
        raise TypeError("trace deve ser uma sequencia de RequestTraceEntry")
    if any(not isinstance(entry, RequestTraceEntry) for entry in trace):
        raise TypeError("trace deve conter apenas objetos RequestTraceEntry")

    entries = tuple(trace)
    request_ids = [entry.request_id for entry in entries]
    if len(set(request_ids)) != len(request_ids):
        raise ValueError("request_id deve ser unico no trace")
    if any(entry.arrival_time >= horizon for entry in entries):
        raise ValueError("arrival_time deve ser menor que horizon")
    if any(
        current.arrival_time < previous.arrival_time
        for previous, current in zip(entries, entries[1:])
    ):
        raise ValueError("trace deve estar ordenado por arrival_time")
    return entries


def _non_negative_integer(value: int, field_name: str) -> int:
    """Valida um inteiro nao negativo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} deve ser um numero inteiro")
    if value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return value


def _non_negative_number(value: float, field_name: str) -> float:
    """Normaliza um numero finito nao negativo."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} deve ser um numero")
    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError(f"{field_name} deve ser finito")
    if normalized_value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return normalized_value


def _positive_number(value: float, field_name: str) -> float:
    """Normaliza um numero finito estritamente positivo."""
    normalized_value = _non_negative_number(value, field_name)
    if normalized_value <= 0:
        raise ValueError(f"{field_name} deve ser positivo")
    return normalized_value
