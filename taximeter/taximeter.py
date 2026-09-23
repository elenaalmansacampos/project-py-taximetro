from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from taximeter.config import Rates


class TaxiStatus(str, Enum):
    STOPPED = "parado"
    MOVING = "en movimiento"


@dataclass(frozen=True)
class TripSummary:
    duration_seconds: float
    amount: float


class Taximeter:
    def __init__(self, rates: Rates, clock: Callable[[], float] | None = None) -> None:
        self.rates = rates
        self.clock = clock or time.monotonic
        self.active = False
        self.status = TaxiStatus.STOPPED
        self._started_at = 0.0
        self._last_tick = 0.0
        self._amount = 0.0

    def start_trip(self) -> None:
        if self.active:
            raise RuntimeError("Ya hay una carrera activa")
        now = self.clock()
        self.active = True
        self.status = TaxiStatus.STOPPED
        self._started_at = now
        self._last_tick = now
        self._amount = 0.0

    def set_status(self, status: TaxiStatus) -> None:
        self._require_active_trip()
        self._charge_elapsed_time()
        self.status = status

    def current_amount(self) -> float:
        self._require_active_trip()
        return round(self._amount + self._elapsed_amount(), 2)

    def elapsed_seconds(self) -> float:
        self._require_active_trip()
        return self.clock() - self._started_at

    def finish_trip(self) -> TripSummary:
        self._require_active_trip()
        self._charge_elapsed_time()
        duration = self.clock() - self._started_at
        summary = TripSummary(duration_seconds=duration, amount=round(self._amount, 2))
        self.active = False
        return summary

    def _require_active_trip(self) -> None:
        if not self.active:
            raise RuntimeError("No hay ninguna carrera activa")

    def _charge_elapsed_time(self) -> None:
        self._amount += self._elapsed_amount()
        self._last_tick = self.clock()

    def _elapsed_amount(self) -> float:
        seconds = self.clock() - self._last_tick
        rate = (
            self.rates.moving_rate_per_second
            if self.status == TaxiStatus.MOVING
            else self.rates.stopped_rate_per_second
        )
        return seconds * rate

