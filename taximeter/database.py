from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from taximeter import paths
from taximeter.history import HistoryEntry
from taximeter.taximeter import TripSummary


DEFAULT_DATABASE_PATH = paths.database_path()
SCHEMA = """
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_local TEXT NOT NULL,
    duration_seconds REAL NOT NULL CHECK (duration_seconds >= 0),
    amount REAL NOT NULL CHECK (amount >= 0),
    record_key TEXT UNIQUE,
    source TEXT NOT NULL DEFAULT 'app',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trips_date_local
    ON trips (date_local);
"""


class TripHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = paths.database_path() if path is None else Path(path)

    def add(self, summary: TripSummary) -> None:
        date_local = datetime.now().isoformat(timespec="seconds")
        self._insert(date_local, summary.duration_seconds, summary.amount, None, "app")

    def add_migrated(self, entry: HistoryEntry) -> bool:
        record_key = record_key_for(
            entry.date, entry.duration_seconds, entry.amount
        )
        return self._insert(
            entry.date,
            entry.duration_seconds,
            entry.amount,
            record_key,
            "csv",
        )

    def all(self) -> list[HistoryEntry]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT date_local, duration_seconds, amount "
                "FROM trips ORDER BY date_local, id"
            ).fetchall()
        return [_entry_from_row(row) for row in rows]

    def migrated_entries(self) -> list[HistoryEntry]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT date_local, duration_seconds, amount "
                "FROM trips WHERE record_key IS NOT NULL "
                "ORDER BY date_local, id"
            ).fetchall()
        return [_entry_from_row(row) for row in rows]

    def _insert(
        self,
        date_local: str,
        duration_seconds: float,
        amount: float,
        record_key: str | None,
        source: str,
    ) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT INTO trips "
                "(date_local, duration_seconds, amount, record_key, source) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(record_key) DO NOTHING",
                (date_local, duration_seconds, amount, record_key, source),
            )
            return cursor.rowcount == 1

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(SCHEMA)
            with connection:
                yield connection
        finally:
            connection.close()


def record_key_for(date_local: str, duration_seconds: float, amount: float) -> str:
    try:
        normalized_date = datetime.fromisoformat(date_local).isoformat()
    except ValueError:
        normalized_date = date_local
    canonical_value = (
        f"{normalized_date}|{format(duration_seconds + 0.0, '.15g')}|"
        f"{format(amount + 0.0, '.15g')}"
    )
    return hashlib.sha256(canonical_value.encode("utf-8")).hexdigest()


def _entry_from_row(row: sqlite3.Row) -> HistoryEntry:
    return HistoryEntry(
        date=row["date_local"],
        duration_seconds=row["duration_seconds"],
        amount=row["amount"],
    )
