from __future__ import annotations


from dataclasses import dataclass
from random import Random 
from typing import Protocol
import simpy

from load_balancer_sim.server import Server
from load_balancer_sim.config import PolicyName, SimulationConfig
from load_balancer_sim.request import Request


'''
Define a interface de politica de roteamento para o balanceador de carga.
'''
class RoutingPolicy(Protocol):
    def select_server(
        self,
        request: Request,
        servers: list[Server],
    ) -> Server:
        pass


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
    def select_server(
        self,
        request: Request,
        servers: list[Server],
    ) -> Server:
        return min(servers, key=lambda s: s.active_count + s.waiting_count)


def build_policy(
    policy_name: PolicyName,
    seed: int | None = None,
) -> RoutingPolicy:
    if policy_name == "random":
        return RandomPolicy(Random(seed))
    elif policy_name == "round_robin":
        return RoundRobinPolicy()
    elif policy_name == "shortest_queue":
        return ShortestQueuePolicy()
    else:
        raise ValueError(f"politica desconhecida: {policy_name}")


class LoadBalancer:
    def __init__(
        self,
        environment: simpy.Environment,
        servers: list[Server],
        policy: PolicyName = "round_robin",
        **kwargs: object,
    ):
        if not isinstance(environment, simpy.Environment):
            raise TypeError("environment deve ser um simpy.Environment")
        if not servers:
            raise ValueError("servers nao pode ser vazio")

        self.environment = environment
        self.servers = servers
        self.policy = policy
        self.simulation_config = kwargs.get("simulation_config")

        self.routing_policy = build_policy(self.policy, self.simulation_config.seed if self.simulation_config else None)


    def route_request(
        self,
        request: Request,
    ) -> Server:
        server = self.routing_policy.select_server(request, self.servers)

        request.assign_to(server.id)
        self.environment.process(server.handle(request))

        return server


    