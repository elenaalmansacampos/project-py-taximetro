from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from taximeter.application.ports import HistoryEntry
from taximeter.domain.taximeter import TripSummary
from taximeter.infrastructure import paths


CSV_HISTORY_PATH = paths.history_path()
HISTORY_PATH = CSV_HISTORY_PATH

__all__ = ["CSV_HISTORY_PATH", "HISTORY_PATH", "CsvTripHistory"]


class CsvTripHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = paths.history_path() if path is None else Path(path)

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


TripHistory = CsvTripHistory
