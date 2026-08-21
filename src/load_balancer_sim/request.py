"""Entidade que representa uma requisicao durante a simulacao."""

from dataclasses import dataclass, field
from math import isfinite


def _non_negative_integer(value: int, field_name: str) -> int:
    """Valida identificadores inteiros e nao negativos."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} deve ser um numero inteiro")
    if value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return value


def _non_negative_time(value: float, field_name: str) -> float:
    """Normaliza um instante da simulacao para ``float``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} deve ser um numero")

    normalized_value = float(value)
    if not isfinite(normalized_value):
        raise ValueError(f"{field_name} deve ser finito")
    if normalized_value < 0:
        raise ValueError(f"{field_name} nao pode ser negativo")
    return normalized_value


@dataclass(slots=True)
class Request:
    """Armazena os instantes do ciclo de vida de uma requisicao.

    A requisicao e criada na chegada e depois percorre, em ordem, as etapas de
    atribuicao a um servidor, inicio do servico e conclusao. Cada transicao pode
    acontecer apenas uma vez.
    """

    id: int
    burst_id: int
    arrival_time: float
    assigned_server: int | None = field(default=None, init=False)
    service_start_time: float | None = field(default=None, init=False)
    completion_time: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.id = _non_negative_integer(self.id, "id")
        self.burst_id = _non_negative_integer(self.burst_id, "burst_id")
        self.arrival_time = _non_negative_time(self.arrival_time, "arrival_time")

    def assign_to(self, server_id: int) -> None:
        """Associa a requisicao a um servidor uma unica vez."""
        if self.assigned_server is not None:
            raise RuntimeError("a requisicao ja foi atribuida a um servidor")

        self.assigned_server = _non_negative_integer(server_id, "server_id")

    def mark_service_started(self, start_time: float) -> None:
        """Registra o inicio do servico depois da atribuicao."""
        if self.assigned_server is None:
            raise RuntimeError("a requisicao ainda nao foi atribuida")
        if self.service_start_time is not None:
            raise RuntimeError("o servico da requisicao ja foi iniciado")

        normalized_time = _non_negative_time(start_time, "start_time")
        if normalized_time < self.arrival_time:
            raise ValueError("o servico nao pode iniciar antes da chegada")

        self.service_start_time = normalized_time

    def mark_completed(self, completion_time: float) -> None:
        """Registra a conclusao depois do inicio do servico."""
        if self.service_start_time is None:
            raise RuntimeError("o servico da requisicao ainda nao foi iniciado")
        if self.completion_time is not None:
            raise RuntimeError("a requisicao ja foi concluida")

        normalized_time = _non_negative_time(completion_time, "completion_time")
        if normalized_time < self.service_start_time:
            raise ValueError("a conclusao nao pode ocorrer antes do inicio do servico")

        self.completion_time = normalized_time

    @property
    def queue_time(self) -> float | None:
        """Retorna o tempo de espera, quando o servico ja tiver iniciado."""
        if self.service_start_time is None:
            return None
        return self.service_start_time - self.arrival_time

    @property
    def response_time(self) -> float | None:
        """Retorna o tempo de resposta, quando a requisicao estiver concluida."""
        if self.completion_time is None:
            return None
        return self.completion_time - self.arrival_time
