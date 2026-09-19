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

@dataclass
class RandomPolicy:
    rng: Random

    def select_server(
        self,
        request: Request,
        servers: list[Server],
        seed: int | None = None,
    ) -> Server:
        if seed is not None:
            self.rng.seed(seed)
        return self.rng.choice(servers)


@dataclass 
class RoundRobinPolicy:
    _next_index: int = 0

    def select_server(
        self,
        request: Request,
        servers: list[Server],
    ) -> Server:
        server = servers[self._next_index]
        self._next_index = (self._next_index + 1) % len(servers)
        return server


@dataclass 
class ShortestQueuePolicy:
    rng: Random | None = None

    def select_server(
        self,
        request: Request,
        servers: list[Server],
    ) -> Server:
        minimum_load = min(s.active_count + s.waiting_count for s in servers)
        candidates = [
            s for s in servers if s.active_count + s.waiting_count == minimum_load
        ]
        if len(candidates) == 1 or self.rng is None:
            return candidates[0]
        return self.rng.choice(candidates)


def build_policy(
    policy_name: PolicyName,
    seed: int | None = None,
) -> RoutingPolicy:
    if policy_name == "random":
        return RandomPolicy(Random(seed))
    elif policy_name == "round_robin":
        return RoundRobinPolicy()
    elif policy_name == "shortest_queue":
        return ShortestQueuePolicy(Random(seed) if seed is not None else None)
    else:
        raise ValueError(f"politica desconhecida: {policy_name}")


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
