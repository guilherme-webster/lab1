"""Balanceador que encaminha requisicoes aos servidores simulados."""

from collections.abc import Sequence

import simpy

from load_balancer_sim.config import PolicyName
from load_balancer_sim.policies import RoutingPolicy, build_policy
from load_balancer_sim.request import Request
from load_balancer_sim.server import Server


def _validate_servers(
    environment: simpy.Environment,
    servers: Sequence[Server],
) -> tuple[Server, ...]:
    """Valida e protege a colecao usada pelo balanceador."""
    if not isinstance(servers, Sequence):
        raise TypeError("servers deve ser uma sequencia de Server")
    if not servers:
        raise ValueError("servers nao pode ser vazio")
    if any(not isinstance(server, Server) for server in servers):
        raise TypeError("servers deve conter apenas objetos Server")
    if any(server.environment is not environment for server in servers):
        raise ValueError("todos os servidores devem usar o ambiente do balanceador")

    server_ids = [server.id for server in servers]
    if len(set(server_ids)) != len(server_ids):
        raise ValueError("os identificadores dos servidores devem ser unicos")
    return tuple(servers)


class LoadBalancer:
    """Seleciona um servidor e agenda o atendimento de cada requisicao."""

    def __init__(
        self,
        environment: simpy.Environment,
        servers: Sequence[Server],
        policy: PolicyName = "round_robin",
        seed: int | None = None,
    ) -> None:
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")

        self.environment = environment
        self.servers = _validate_servers(environment, servers)
        self.policy = policy
        self.seed = seed
        self.routing_policy: RoutingPolicy = build_policy(policy, seed)

    def route_request(self, request: Request) -> Server:
        """Atribui e agenda uma requisicao que ja chegou ao sistema."""
        if not isinstance(request, Request):
            raise TypeError("request deve ser uma Request")
        if request.assigned_server is not None:
            raise RuntimeError("request ja foi roteada")
        if request.arrival_time > float(self.environment.now):
            raise ValueError("request ainda nao chegou ao sistema")

        server = self.routing_policy.select_server(request, self.servers)
        request.assign_to(server.id)
        self.environment.process(server.handle(request))
        return server
