"""Geracao de chegadas de requisicoes para a simulacao.

Este modulo implementa chegadas segundo um processo de Poisson homogeneo com
taxa ``lambda``. Em um processo de Poisson, os intervalos entre chegadas sao
exponenciais com media ``1/lambda``.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from math import isfinite
from random import Random
from dataclasses import dataclass

import simpy

from load_balancer_sim.request import Request


@dataclass(slots=True)
class PoissonTrafficGenerator:
	"""Gerador de chegadas Poisson acoplado a um ambiente SimPy."""

	environment: simpy.Environment
	arrival_rate: float
	horizon: float
	seed: int | None = None
	first_request_id: int = 0
	burst_id: int = 0

	def __post_init__(self) -> None:
		if not isinstance(self.environment, simpy.Environment):
			raise TypeError("environment deve ser um simpy.Environment")
		self.arrival_rate = _positive_number(self.arrival_rate, "arrival_rate")
		self.horizon = _positive_number(self.horizon, "horizon")
		self.first_request_id = _non_negative_integer(
			self.first_request_id,
			"first_request_id",
		)
		self.burst_id = _non_negative_integer(self.burst_id, "burst_id")
		if self.seed is not None:
			_non_negative_integer(self.seed, "seed")

	def run(
		self,
		on_arrival: Callable[[Request], None],
	) -> Generator[simpy.Event, None, None]:
		"""Executa o processo de chegada chamando ``on_arrival`` a cada requisicao."""
		return poisson_arrival_process(
			environment=self.environment,
			arrival_rate=self.arrival_rate,
			horizon=self.horizon,
			on_arrival=on_arrival,
			seed=self.seed,
			first_request_id=self.first_request_id,
			burst_id=self.burst_id,
		)


def _positive_number(value: float, field_name: str) -> float:
	"""Valida um numero finito estritamente positivo."""
	if isinstance(value, bool) or not isinstance(value, (int, float)):
		raise TypeError(f"{field_name} deve ser um numero")

	normalized_value = float(value)
	if not isfinite(normalized_value):
		raise ValueError(f"{field_name} deve ser finito")
	if normalized_value <= 0:
		raise ValueError(f"{field_name} deve ser positivo")
	return normalized_value


def _non_negative_integer(value: int, field_name: str) -> int:
	"""Valida um identificador inteiro e nao negativo."""
	if isinstance(value, bool) or not isinstance(value, int):
		raise TypeError(f"{field_name} deve ser um numero inteiro")
	if value < 0:
		raise ValueError(f"{field_name} nao pode ser negativo")
	return value


def _non_negative_number(value: float, field_name: str) -> float:
	"""Valida um numero finito e nao negativo."""
	if isinstance(value, bool) or not isinstance(value, (int, float)):
		raise TypeError(f"{field_name} deve ser um numero")

	normalized_value = float(value)
	if not isfinite(normalized_value):
		raise ValueError(f"{field_name} deve ser finito")
	if normalized_value < 0:
		raise ValueError(f"{field_name} nao pode ser negativo")
	return normalized_value


def generate_poisson_arrival_times(
	arrival_rate: float,
	horizon: float,
	seed: int | None = None,
	start_time: float = 0.0,
) -> tuple[float, ...]:
	"""Gera instantes de chegada segundo um processo de Poisson.

	Args:
		arrival_rate: Taxa ``lambda`` de chegadas por unidade de tempo.
		horizon: Limite superior da janela de observacao.
		seed: Semente opcional para reproducao deterministica.
		start_time: Instante inicial da geracao (inclusivo).

	Returns:
		Tupla ordenada de tempos de chegada em ``[start_time, horizon)``.
	"""
	normalized_rate = _positive_number(arrival_rate, "arrival_rate")
	normalized_horizon = _positive_number(horizon, "horizon")
	normalized_start_time = _non_negative_number(start_time, "start_time")
	if normalized_start_time >= normalized_horizon:
		raise ValueError("start_time deve ser menor que horizon")

	if seed is not None:
		_non_negative_integer(seed, "seed")

	rng = Random(seed)
	now = normalized_start_time
	arrivals: list[float] = []

	while True:
		now += rng.expovariate(normalized_rate)
		if now >= normalized_horizon:
			break
		arrivals.append(now)

	return tuple(arrivals)


def poisson_arrival_process(
	environment: simpy.Environment,
	arrival_rate: float,
	horizon: float,
	on_arrival: Callable[[Request], None],
	*,
	seed: int | None = None,
	first_request_id: int = 0,
	burst_id: int = 0,
) -> Generator[simpy.Event, None, None]:
	"""Processo SimPy que cria requisicoes com chegadas Poisson.

	Para cada chegada gerada, este processo instancia :class:`Request` e chama
	``on_arrival(request)`` no proprio instante simulado da chegada.
	"""
	if not isinstance(environment, simpy.Environment):
		raise TypeError("environment deve ser um simpy.Environment")
	if not callable(on_arrival):
		raise TypeError("on_arrival deve ser chamavel")

	normalized_rate = _positive_number(arrival_rate, "arrival_rate")
	normalized_horizon = _positive_number(horizon, "horizon")
	next_request_id = _non_negative_integer(first_request_id, "first_request_id")
	normalized_burst_id = _non_negative_integer(burst_id, "burst_id")

	if seed is not None:
		_non_negative_integer(seed, "seed")

	if environment.now < 0:
		raise ValueError("environment.now nao pode ser negativo")
	if environment.now >= normalized_horizon:
		return

	rng = Random(seed)

	while True:
		delta = rng.expovariate(normalized_rate)
		next_arrival_time = float(environment.now) + delta
		if next_arrival_time >= normalized_horizon:
			break

		yield environment.timeout(delta)
		request = Request(
			id=next_request_id,
			burst_id=normalized_burst_id,
			arrival_time=float(environment.now),
		)
		on_arrival(request)
		next_request_id += 1
