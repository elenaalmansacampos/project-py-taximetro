from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from taximeter.domain.taximeter import TripSummary


__all__ = ["HistoryEntry", "HistoryRepository"]


@dataclass(frozen=True)
class HistoryEntry:
    date: str
    duration_seconds: float
    amount: float


@runtime_checkable
class HistoryRepository(Protocol):
    """Contrato minimo que la CLI y la GUI necesitan para leer y guardar carreras."""

    def add(self, summary: TripSummary) -> None: ...

    def all(self) -> list[HistoryEntry]: ...
