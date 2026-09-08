"""Politicas de roteamento suportadas pelo balanceador de carga."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Protocol

from load_balancer_sim.config import PolicyName
from load_balancer_sim.request import Request
from load_balancer_sim.server import Server


class RoutingPolicy(Protocol):
    """Contrato comum das politicas de selecao de servidor."""

    def select_server(
        self,
        request: Request,
        servers: Sequence[Server],
    ) -> Server:
        """Seleciona um servidor para a requisicao."""
        ...


def _validated_seed(seed: int | None) -> int | None:
    """Valida uma semente pseudoaleatoria opcional."""
    if seed is None:
        return None
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed deve ser um numero inteiro")
    if seed < 0:
        raise ValueError("seed nao pode ser negativo")
    return seed


def _validate_selection_inputs(
    request: Request,
    servers: Sequence[Server],
) -> None:
    """Valida os argumentos comuns das politicas publicas."""
    if not isinstance(request, Request):
        raise TypeError("request deve ser uma Request")
    if not isinstance(servers, Sequence):
        raise TypeError("servers deve ser uma sequencia de Server")
    if not servers:
        raise ValueError("servers nao pode ser vazio")
    if any(not isinstance(server, Server) for server in servers):
        raise TypeError("servers deve conter apenas objetos Server")


@dataclass(slots=True)
class RandomPolicy:
    """Seleciona qualquer servidor com probabilidades iguais."""

    seed: int | None = None
    _rng: Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.seed = _validated_seed(self.seed)
        self._rng = Random(self.seed)

    def select_server(
        self,
        request: Request,
        servers: Sequence[Server],
    ) -> Server:
        _validate_selection_inputs(request, servers)
        return self._rng.choice(servers)


@dataclass(slots=True)
class RoundRobinPolicy:
    """Percorre os servidores ciclicamente, na ordem recebida."""

    _next_index: int = field(default=0, init=False, repr=False)

    def select_server(
        self,
        request: Request,
        servers: Sequence[Server],
    ) -> Server:
        _validate_selection_inputs(request, servers)
        server = servers[self._next_index % len(servers)]
        self._next_index = (self._next_index + 1) % len(servers)
        return server


@dataclass(slots=True)
class ShortestQueuePolicy:
    """Seleciona uma das menores ocupacoes, com desempate aleatorio."""

    seed: int | None = None
    _rng: Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.seed = _validated_seed(self.seed)
        self._rng = Random(self.seed)

    def select_server(
        self,
        request: Request,
        servers: Sequence[Server],
    ) -> Server:
        _validate_selection_inputs(request, servers)
        minimum_load = min(
            server.active_count + server.waiting_count for server in servers
        )
        candidates = [
            server
            for server in servers
            if server.active_count + server.waiting_count == minimum_load
        ]
        return self._rng.choice(candidates)


def build_policy(
    policy_name: PolicyName,
    seed: int | None = None,
) -> RoutingPolicy:
    """Constroi uma politica suportada com semente reproduzivel."""
    if not isinstance(policy_name, str):
        raise TypeError("policy_name deve ser uma string")
    normalized_seed = _validated_seed(seed)
    if policy_name == "random":
        return RandomPolicy(normalized_seed)
    if policy_name == "round_robin":
        return RoundRobinPolicy()
    if policy_name == "shortest_queue":
        return ShortestQueuePolicy(normalized_seed)
    raise ValueError(f"politica desconhecida: {policy_name}")
