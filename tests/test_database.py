import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from taximeter.database import TripHistory
from taximeter.history import HistoryEntry
from taximeter.taximeter import TripSummary


class DatabaseHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "data" / "taximetro.db"
        self.history = TripHistory(self.path)

    def test_add_and_read_from_a_new_repository_instance(self) -> None:
        summary = TripSummary(duration_seconds=30.456, amount=1.234)

        with patch("taximeter.database.datetime") as datetime_mock:
            datetime_mock.now.return_value.isoformat.return_value = (
                "2026-09-25T10:30:00"
            )
            self.history.add(summary)

        entries = TripHistory(self.path).all()
        self.assertEqual(
            entries,
            [
                HistoryEntry(
                    date="2026-09-25T10:30:00",
                    duration_seconds=30.456,
                    amount=1.234,
                )
            ],
        )
        self.assertTrue(self.path.exists())

    def test_new_entries_are_not_deduplicated(self) -> None:
        summary = TripSummary(duration_seconds=30, amount=1.20)

        with patch("taximeter.database.datetime") as datetime_mock:
            datetime_mock.now.return_value.isoformat.return_value = (
                "2026-09-25T10:30:00"
            )
            self.history.add(summary)
            self.history.add(summary)

        self.assertEqual(len(self.history.all()), 2)
        with closing(sqlite3.connect(self.path)) as connection:
            keys = connection.execute(
                "SELECT record_key FROM trips ORDER BY id"
            ).fetchall()
        self.assertEqual(keys, [(None,), (None,)])

    def test_migrated_entry_is_not_duplicated(self) -> None:
        entry = HistoryEntry(
            date="2026-09-25T10:30:00", duration_seconds=30, amount=1.20
        )

        self.assertTrue(self.history.add_migrated(entry))
        self.assertFalse(self.history.add_migrated(entry))

        self.assertEqual(self.history.all(), [entry])
        self.assertEqual(self.history.migrated_entries(), [entry])

    def test_entries_are_ordered_by_date(self) -> None:
        entries = [
            HistoryEntry(date="2026-09-25T11:00:00", duration_seconds=25, amount=1.10),
            HistoryEntry(date="2026-09-25T10:30:00", duration_seconds=30, amount=1.20),
        ]
        for entry in entries:
            self.history.add_migrated(entry)

        self.assertEqual([entry.date for entry in self.history.all()], [
            "2026-09-25T10:30:00",
            "2026-09-25T11:00:00",
        ])


if __name__ == "__main__":
    unittest.main()
