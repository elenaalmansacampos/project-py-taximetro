import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taximeter.history import TripHistory
from taximeter.taximeter import TripSummary


class TripHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "data" / "historial.csv"
        self.history = TripHistory(self.path)

    def test_add_creates_directory_header_and_entry(self) -> None:
        summary = TripSummary(duration_seconds=30.456, amount=1.234)

        with patch("taximeter.history.datetime") as datetime_mock:
            datetime_mock.now.return_value.isoformat.return_value = (
                "2026-09-25T10:30:00"
            )
            self.history.add(summary)

        self.assertTrue(self.path.parent.is_dir())
        with self.path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = list(reader)

        self.assertEqual(reader.fieldnames, ["date", "duration_seconds", "amount"])
        self.assertEqual(
            rows,
            [
                {
                    "date": "2026-09-25T10:30:00",
                    "duration_seconds": "30.46",
                    "amount": "1.23",
                }
            ],
        )

    def test_entries_are_available_from_a_new_history_instance(self) -> None:
        dates = ["2026-09-25T10:30:00", "2026-09-25T11:00:00"]

        with patch("taximeter.history.datetime") as datetime_mock:
            datetime_mock.now.return_value.isoformat.side_effect = dates
            self.history.add(TripSummary(duration_seconds=30, amount=1.20))
            self.history.add(TripSummary(duration_seconds=25, amount=1.10))

        entries = TripHistory(self.path).all()

        self.assertEqual([entry.date for entry in entries], dates)
        self.assertAlmostEqual(entries[0].duration_seconds, 30)
        self.assertAlmostEqual(entries[0].amount, 1.20)
        self.assertAlmostEqual(entries[1].duration_seconds, 25)
        self.assertAlmostEqual(entries[1].amount, 1.10)

    def test_missing_history_is_empty(self) -> None:
        self.assertEqual(self.history.all(), [])


if __name__ == "__main__":
    unittest.main()
