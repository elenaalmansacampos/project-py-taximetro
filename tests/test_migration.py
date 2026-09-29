import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from taximeter.application.ports import HistoryEntry
from taximeter.infrastructure import database
from taximeter.infrastructure.database import TripHistory
from taximeter.infrastructure.migration import (
    MigrationError,
    MigrationReport,
    RejectedRecord,
    format_migration_report,
    migrate_csv_to_database,
)
from taximeter.interfaces import cli, gui


class HistoryMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.source = Path(temporary_directory.name) / "data" / "historial.csv"
        self.database = Path(temporary_directory.name) / "data" / "taximetro.db"

    def _write_csv(self, rows: list[list[str]]) -> None:
        self.source.parent.mkdir(parents=True, exist_ok=True)
        with self.source.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["date", "duration_seconds", "amount"])
            writer.writerows(rows)

    def test_imports_valid_rows_and_keeps_csv_unchanged(self) -> None:
        self._write_csv(
            [
                ["2026-09-25T10:30:00", "30.46", "1.23"],
                ["2026-09-25T11:00:00", "25", "1.10"],
            ]
        )
        original = self.source.read_bytes()

        report = migrate_csv_to_database(self.source, self.database)

        self.assertTrue(report.ok)
        self.assertEqual(report.total_rows, 2)
        self.assertEqual(report.valid_rows, 2)
        self.assertEqual(report.imported, 2)
        self.assertEqual(report.duplicates, 0)
        self.assertEqual(report.rejected_count, 0)
        self.assertTrue(report.verified)
        self.assertTrue(report.source_preserved)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(
            TripHistory(self.database).all(),
            [
                HistoryEntry(
                    date="2026-09-25T10:30:00",
                    duration_seconds=30.46,
                    amount=1.23,
                ),
                HistoryEntry(
                    date="2026-09-25T11:00:00",
                    duration_seconds=25,
                    amount=1.10,
                ),
            ],
        )

    def test_repeated_migration_does_not_create_duplicates(self) -> None:
        self._write_csv(
            [
                ["2026-09-25T10:30:00", "30", "1.20"],
                ["2026-09-25T10:30:00", "30", "1.20"],
            ]
        )

        first = migrate_csv_to_database(self.source, self.database)
        second = migrate_csv_to_database(self.source, self.database)

        self.assertEqual(first.imported, 1)
        self.assertEqual(first.duplicates, 1)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 2)
        self.assertTrue(second.ok)
        self.assertEqual(len(TripHistory(self.database).all()), 1)

    def test_reports_invalid_rows_and_keeps_valid_rows(self) -> None:
        self._write_csv(
            [
                ["2026-09-25T10:30:00", "30", "1.20"],
                ["no-es-fecha", "30", "1.20"],
                ["2026-09-25T10:31:00", "abc", "1.20"],
                ["2026-09-25T10:32:00", "30", "-1"],
                ["2026-09-25T10:33:00", "30", "1.20", "extra"],
                ["", "30", "1.20"],
            ]
        )

        report = migrate_csv_to_database(self.source, self.database)

        self.assertFalse(report.ok)
        self.assertEqual(report.total_rows, 6)
        self.assertEqual(report.valid_rows, 1)
        self.assertEqual(report.imported, 1)
        self.assertEqual(report.rejected_count, 5)
        self.assertTrue(report.verified)
        self.assertEqual(len(TripHistory(self.database).all()), 1)
        rendered = format_migration_report(report)
        self.assertIn("Rechazadas: 5", rendered)
        self.assertIn("linea 3", rendered)
        self.assertIn("linea 5", rendered)
        self.assertIn("Verificacion: correcta", rendered)
        self.assertIn("CSV original conservado: si", rendered)

    def test_missing_source_is_reported(self) -> None:
        with self.assertRaisesRegex(MigrationError, "No existe el CSV"):
            migrate_csv_to_database(self.source, self.database)

    def test_invalid_header_is_reported(self) -> None:
        self.source.parent.mkdir(parents=True, exist_ok=True)
        self.source.write_text(
            "date,amount\n2026-09-25T10:30:00,1.20\n", encoding="utf-8"
        )

        with self.assertRaisesRegex(MigrationError, "cabecera"):
            migrate_csv_to_database(self.source, self.database)


class MigrationCliTest(unittest.TestCase):
    def test_application_uses_database_history(self) -> None:
        self.assertIs(cli.TripHistory, database.TripHistory)
        self.assertIs(gui.TripHistory, database.TripHistory)

    def test_migration_flag_routes_to_migration(self) -> None:
        with (
            patch.object(sys, "argv", ["main.py", "--migrate-history"]),
            patch.object(cli, "configure_logging"),
            patch.object(cli, "run_history_migration") as run_migration,
            patch.object(cli, "run_cli") as run_cli,
        ):
            cli.main()

        run_migration.assert_called_once_with()
        run_cli.assert_not_called()

    def test_rejected_migration_returns_error_exit_code(self) -> None:
        report = MigrationReport(
            source=Path("historial.csv"),
            database=Path("taximetro.db"),
            total_rows=1,
            valid_rows=0,
            imported=0,
            duplicates=0,
            rejected=(RejectedRecord(line=2, reason="fecha no valida"),),
            missing=0,
            verified=True,
            source_preserved=True,
        )
        output = io.StringIO()

        with (
            patch.object(cli, "migrate_csv_to_database", return_value=report),
            redirect_stdout(output),
            self.assertLogs(cli.logger, level="INFO"),
        ):
            with self.assertRaises(SystemExit) as exit_info:
                cli.run_history_migration()

        self.assertEqual(exit_info.exception.code, 1)
        self.assertIn("Rechazadas: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
