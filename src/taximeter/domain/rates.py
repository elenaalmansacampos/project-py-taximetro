from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rates:
    """Tarifas por segundo segun el estado del taxi. Valor puro, sin I/O."""

    stopped_rate_per_second: float
    moving_rate_per_second: float
