"""Simulador de balanceamento de carga do Trabalho 1 de MC714."""

from load_balancer_sim.config import SimulationConfig
from load_balancer_sim.invariants import (
    SimulationInvariantError,
    validate_simulation_invariants,
)
from load_balancer_sim.logs import EVENT_LOG_HEADER, SimulationLogger
from load_balancer_sim.load_balancer import LoadBalancer
from load_balancer_sim.metrics import (
    MetricEvent,
    MetricsCollector,
    RunMetrics,
    ServerUtilization,
)
from load_balancer_sim.policies import (
    RandomPolicy,
    RoundRobinPolicy,
    RoutingPolicy,
    ShortestQueuePolicy,
    build_policy,
)
from load_balancer_sim.request import Request
from load_balancer_sim.server import (
    Server,
    ServerEventCallback,
    ServerState,
    ServiceTimeSampler,
)
from load_balancer_sim.simulation import (
    RequestTraceEntry,
    RunSeeds,
    SimulationResult,
    derive_run_seeds,
    generate_request_trace,
    run_simulation,
)
from load_balancer_sim.traffic import (
    PoissonTrafficGenerator,
    generate_poisson_arrival_times,
    poisson_arrival_process,
)

__version__ = "0.1.0"

__all__ = [
    "EVENT_LOG_HEADER",
    "LoadBalancer",
    "MetricEvent",
    "MetricsCollector",
    "Request",
    "RequestTraceEntry",
    "RandomPolicy",
    "RoundRobinPolicy",
    "RunMetrics",
    "RunSeeds",
    "RoutingPolicy",
    "Server",
    "ServerEventCallback",
    "ServerState",
    "ServerUtilization",
    "ServiceTimeSampler",
    "SimulationConfig",
    "SimulationInvariantError",
    "SimulationLogger",
    "SimulationResult",
    "ShortestQueuePolicy",
    "PoissonTrafficGenerator",
    "generate_poisson_arrival_times",
    "poisson_arrival_process",
    "__version__",
    "build_policy",
    "derive_run_seeds",
    "generate_request_trace",
    "run_simulation",
    "validate_simulation_invariants",
]
