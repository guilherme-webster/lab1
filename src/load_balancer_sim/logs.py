"""Logs estruturados da simulacao."""

import logging

from load_balancer_sim.config import SimulationConfig
from load_balancer_sim.metrics import MetricEvent, RunMetrics


LOGGER_NAME = "load_balancer_sim"
EVENT_LOG_HEADER = (
    "time,event,request_id,burst_id,server_id,active,queue_length"
)


class SimulationLogger:
    """Emite configuracoes e resumos em INFO e eventos em DEBUG."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        if logger is not None and not isinstance(logger, logging.Logger):
            raise TypeError("logger deve ser um logging.Logger")
        self.logger = logging.getLogger(LOGGER_NAME) if logger is None else logger

    def log_run_started(self, config: SimulationConfig) -> None:
        """Registra a configuracao de uma rodada e o cabecalho dos eventos."""
        if not isinstance(config, SimulationConfig):
            raise TypeError("config deve ser uma SimulationConfig")

        self.logger.info(
            "run_started,policy=%s,server_count=%d,server_capacity=%d,"
            "service_time=%.6f,burst_max=%d,hurst=%.6f,horizon=%.6f,seed=%d",
            config.policy,
            config.server_count,
            config.server_capacity,
            config.service_time,
            config.burst_max,
            config.hurst,
            config.horizon,
            config.seed,
        )
        self.logger.debug(EVENT_LOG_HEADER)

    def log_event(self, event: MetricEvent) -> None:
        """Registra uma linha DEBUG com os campos de um evento."""
        if not isinstance(event, MetricEvent):
            raise TypeError("event deve ser um MetricEvent")

        self.logger.debug(
            "%.6f,%s,%d,%d,%s,%s,%s",
            event.time,
            event.event,
            event.request_id,
            event.burst_id,
            _optional_value(event.server_id),
            _optional_value(event.active_count),
            _optional_value(event.waiting_count),
        )

    def log_run_completed(self, metrics: RunMetrics) -> None:
        """Registra o resumo INFO de uma rodada concluida."""
        if not isinstance(metrics, RunMetrics):
            raise TypeError("metrics deve ser uma RunMetrics")

        self.logger.info(
            "run_completed,horizon=%.6f,arrivals=%d,completed=%d,pending=%d,"
            "throughput=%.6f,average_queue_time=%s,average_response_time=%s",
            metrics.horizon,
            metrics.arrival_count,
            metrics.completed_count,
            metrics.pending_count,
            metrics.throughput,
            _optional_float(metrics.average_queue_time),
            _optional_float(metrics.average_response_time),
        )


def _optional_value(value: int | None) -> str:
    """Converte um inteiro opcional para uma celula de log."""
    return "" if value is None else str(value)


def _optional_float(value: float | None) -> str:
    """Converte uma media opcional para o resumo da rodada."""
    return "none" if value is None else f"{value:.6f}"
