"""Testes de fumaca da configuracao inicial do projeto."""

import simpy

import load_balancer_sim


def test_package_can_be_imported() -> None:
    assert load_balancer_sim.__version__ == "0.1.0"


def test_simpy_environment_advances_simulated_time() -> None:
    environment = simpy.Environment()

    environment.run(until=1.0)

    assert environment.now == 1.0
