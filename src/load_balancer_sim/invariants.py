"""Invariantes verificadas ao final de uma rodada da simulacao."""

from collections.abc import Sequence

from load_balancer_sim.config import SimulationConfig
from load_balancer_sim.metrics import MetricEvent, MetricEventType, MetricsCollector
from load_balancer_sim.server import Server


class SimulationInvariantError(RuntimeError):
    """Indica que o estado observado da simulacao e inconsistente."""


_EXPECTED_EVENT: dict[MetricEventType | None, MetricEventType | None] = {
    None: "arrival",
    "arrival": "routing",
    "routing": "service_started",
    "service_started": "service_completed",
    "service_completed": None,
}


def validate_simulation_invariants(
    config: SimulationConfig,
    servers: Sequence[Server],
    collector: MetricsCollector,
) -> None:
    """Valida topologia, capacidade e ciclos de vida na janela oficial."""
    if not isinstance(config, SimulationConfig):
        raise TypeError("config deve ser uma SimulationConfig")
    if not isinstance(collector, MetricsCollector):
        raise TypeError("collector deve ser um MetricsCollector")

    server_by_id = _validate_servers(config, servers, collector)
    _validate_events(config, server_by_id, collector)


def _validate_servers(
    config: SimulationConfig,
    servers: Sequence[Server],
    collector: MetricsCollector,
) -> dict[int, Server]:
    """Valida a colecao de servidores contra a configuracao da rodada."""
    if not isinstance(servers, Sequence):
        raise TypeError("servers deve ser uma sequencia de Server")
    if any(not isinstance(server, Server) for server in servers):
        raise TypeError("servers deve conter apenas objetos Server")
    if len(servers) != config.server_count:
        raise SimulationInvariantError(
            "quantidade de servidores diferente da configuracao"
        )

    server_by_id = {server.id: server for server in servers}
    expected_ids = set(range(config.server_count))
    if set(server_by_id) != expected_ids or len(server_by_id) != len(servers):
        raise SimulationInvariantError(
            f"identificadores dos servidores devem ser {sorted(expected_ids)}"
        )

    for server in servers:
        if server.environment is not collector.environment:
            raise SimulationInvariantError(
                f"servidor {server.id} usa um ambiente diferente do coletor"
            )
        if server.capacity != config.server_capacity:
            raise SimulationInvariantError(
                f"capacidade do servidor {server.id} diferente da configuracao"
            )
        if server.service_time != config.service_time:
            raise SimulationInvariantError(
                f"tempo de servico do servidor {server.id} diferente da configuracao"
            )
        if not 0 <= server.active_count <= server.capacity:
            raise SimulationInvariantError(
                f"quantidade ativa invalida no servidor {server.id}"
            )
        if server.waiting_count < 0:
            raise SimulationInvariantError(
                f"tamanho de fila invalido no servidor {server.id}"
            )

    return server_by_id


def _validate_events(
    config: SimulationConfig,
    server_by_id: dict[int, Server],
    collector: MetricsCollector,
) -> None:
    """Valida snapshots, ordem de eventos e conservacao de requisicoes."""
    lifecycle: dict[int, MetricEventType] = {}
    burst_by_request: dict[int, int] = {}
    server_by_request: dict[int, int] = {}
    previous_time = 0.0

    for event in collector.events:
        if event.time < previous_time:
            raise SimulationInvariantError(
                "eventos devem estar em ordem nao decrescente de tempo"
            )
        previous_time = event.time

        if event.event == "arrival" and event.time >= config.horizon:
            raise SimulationInvariantError(
                "chegadas devem ocorrer antes do horizonte"
            )
        if event.time > config.horizon:
            continue

        _validate_event_snapshot(event, server_by_id)

        previous_burst = burst_by_request.setdefault(
            event.request_id,
            event.burst_id,
        )
        if event.burst_id != previous_burst:
            raise SimulationInvariantError(
                f"rajada inconsistente para a requisicao {event.request_id}"
            )

        previous_event = lifecycle.get(event.request_id)
        expected_event = _EXPECTED_EVENT[previous_event]
        if event.event != expected_event:
            raise SimulationInvariantError(
                f"evento {event.event} inesperado para a requisicao "
                f"{event.request_id}; esperado: {expected_event}"
            )
        lifecycle[event.request_id] = event.event

        if event.event == "routing":
            if event.server_id is None:
                raise SimulationInvariantError("roteamento sem servidor")
            server_by_request[event.request_id] = event.server_id
        elif event.event in ("service_started", "service_completed"):
            if event.server_id != server_by_request[event.request_id]:
                raise SimulationInvariantError(
                    f"servidor mudou durante a requisicao {event.request_id}"
                )

    completed_count = sum(
        event == "service_completed" for event in lifecycle.values()
    )
    active_at_end = sum(
        event == "service_started" for event in lifecycle.values()
    )
    waiting_at_end = sum(event == "routing" for event in lifecycle.values())
    arrival_count = len(lifecycle)

    if arrival_count != completed_count + active_at_end + waiting_at_end:
        raise SimulationInvariantError(
            "conservacao violada: chegadas != concluidas + ativas + aguardando"
        )


def _validate_event_snapshot(
    event: MetricEvent,
    server_by_id: dict[int, Server],
) -> None:
    """Valida os campos de servidor fotografados em um evento."""
    if event.event == "arrival":
        if any(
            value is not None
            for value in (
                event.server_id,
                event.active_count,
                event.waiting_count,
            )
        ):
            raise SimulationInvariantError(
                "evento de chegada nao deve possuir estado de servidor"
            )
        return

    server_id = event.server_id
    if server_id not in server_by_id:
        raise SimulationInvariantError(f"servidor desconhecido no evento: {server_id}")
    if event.active_count is None or event.waiting_count is None:
        raise SimulationInvariantError("evento de servidor deve possuir um snapshot")

    server = server_by_id[server_id]
    if not 0 <= event.active_count <= server.capacity:
        raise SimulationInvariantError(
            f"quantidade ativa invalida no snapshot do servidor {server_id}"
        )
    if event.waiting_count < 0:
        raise SimulationInvariantError(
            f"tamanho de fila invalido no snapshot do servidor {server_id}"
        )
