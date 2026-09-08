"""Testes iniciais para a classe LoadBalancer.

Este arquivo serve como base para expandir os cenarios de politicas de
roteamento (random, round_robin e shortest_queue).
"""

import pytest
import simpy

from load_balancer_sim.load_balancer import LoadBalancer, RoundRobinPolicy, build_policy
from load_balancer_sim.request import Request
from load_balancer_sim.server import Server


def _make_servers(environment: simpy.Environment, count: int = 3) -> list[Server]:
	"""Cria servidores padrao para os cenarios de teste."""
	return [
		Server(
			environment,
			server_id=index,
			service_time_sampler=lambda _: 0.05,
		)
		for index in range(count)
	]


def _build_ready_load_balancer(
	environment: simpy.Environment,
	policy: str = "round_robin",
) -> LoadBalancer:
	"""Monta o balanceador e inicializa a politica para os testes."""
	load_balancer = LoadBalancer(
		environment, 
		_make_servers(environment), 
		policy=policy
	)  # type: ignore[arg-type]
	return load_balancer


def test_load_balancer_routes_and_completes_one_request() -> None:
	"""Teste semente: roteia uma requisicao e finaliza seu ciclo de vida."""
	environment = simpy.Environment()
	load_balancer = _build_ready_load_balancer(environment)
	request = Request(id=0, burst_id=0, arrival_time=environment.now)

	selected_server = load_balancer.route_request(request)
	environment.run()

	assert selected_server.id == 0
	assert request.assigned_server == 0
	assert request.service_start_time == 0.0
	assert request.completion_time == pytest.approx(0.05)


def test_round_robin_policy_cycles_across_servers() -> None:
	"""Garante distribuicao ciclica para usar como base de testes da politica."""
	environment = simpy.Environment()
	servers = _make_servers(environment)
	policy = RoundRobinPolicy()

	selected_ids = [
		policy.select_server(
			Request(id=index, burst_id=0, arrival_time=0.0),
			servers,
		).id
		for index in range(5)
	]

	assert selected_ids == [0, 1, 2, 0, 1]


def test_shortest_queue_policy_selects_least_loaded_server() -> None:
    """Valida que a politica shortest_queue seleciona o servidor com menos carga."""
    environment = simpy.Environment()
    servers = _make_servers(environment)
    load_balancer = LoadBalancer(environment, servers, policy="shortest_queue")
    eps = 0.001

    # Inicialmente todos os servidores estao vazios
    selected_server_1 = load_balancer.route_request(
        Request(id=0, burst_id=0, arrival_time=0.0)
    )

    # É necessário avançar o tempo para que o servidor 0 seja ocupado.
    environment.run(until=eps)

    assert selected_server_1.id == 0

    # O servidor 0 agora esta ocupado, entao o proximo deve ser o servidor 1
    selected_server_2 = load_balancer.route_request(
        Request(id=1, burst_id=0, arrival_time=0.0)
    )
    environment.run(until=2*eps)
    assert selected_server_2.id == 1

    # O servidor 2 ainda esta vazio, entao ele deve ser selecionado
    selected_server_3 = load_balancer.route_request(
        Request(id=2, burst_id=0, arrival_time=0.0)
    )
    assert selected_server_3.id == 2


def test_random_policy_selects_servers() -> None:
    """Valida que a politica randomica seleciona servidores dentro do conjunto."""
    environment = simpy.Environment()
    servers = _make_servers(environment)
    load_balancer = LoadBalancer(environment, servers, policy="random")

    selected_ids = [
        load_balancer.route_request(
            Request(id=index, burst_id=0, arrival_time=0.0)
        ).id
        for index in range(10)
    ]

    assert set(selected_ids).issubset({0, 1, 2})


def test_load_balancer_rejects_empty_server_list() -> None:
	"""Valida contrato basico de construcao do balanceador."""
	with pytest.raises(ValueError, match="servers"):
		LoadBalancer(simpy.Environment(), [], policy="round_robin")


def test_build_policy_rejects_unknown_policy() -> None:
	"""Garante erro claro para politicas nao suportadas."""
	with pytest.raises(ValueError, match="politica desconhecida"):
		build_policy("least_connections")  # type: ignore[arg-type]
