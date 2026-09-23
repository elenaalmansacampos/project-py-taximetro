from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from taximeter.taximeter import TripSummary


HISTORY_PATH = Path("data/historial_carreras.csv")


@dataclass(frozen=True)
class HistoryEntry:
    date: str
    duration_seconds: float
    amount: float


class TripHistory:
    def __init__(self, path: Path = HISTORY_PATH) -> None:
        self.path = path

    def add(self, summary: TripSummary) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()

        with self.path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=["date", "duration_seconds", "amount"])
            if new_file:
                writer.writeheader()
            writer.writerow(
                {
                    "date": datetime.now().isoformat(timespec="seconds"),
                    "duration_seconds": round(summary.duration_seconds, 2),
                    "amount": f"{summary.amount:.2f}",
                }
            )

    def all(self) -> list[HistoryEntry]:
        if not self.path.exists():
            return []

        with self.path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            return [
                HistoryEntry(
                    date=row["date"],
                    duration_seconds=float(row["duration_seconds"]),
                    amount=float(row["amount"]),
                )
                for row in reader
            ]

