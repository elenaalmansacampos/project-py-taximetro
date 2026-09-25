import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from taximeter import cli, gui
from taximeter.config import Rates
from taximeter.history import HistoryEntry
from taximeter.taximeter import TripSummary


SUMMARY = TripSummary(duration_seconds=30, amount=1.20)
ENTRY = HistoryEntry(
    date="2026-09-25T10:30:00",
    duration_seconds=30,
    amount=1.20,
)


def _run_history_cli(
    commands: tuple[str, ...], history: MagicMock
) -> tuple[MagicMock, str]:
    rates = Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05)
    output = io.StringIO()

    with (
        patch.object(cli, "PasswordAuth") as auth_class,
        patch.object(cli, "ensure_cli_password"),
        patch.object(cli, "_ask_password", return_value="password"),
        patch.object(cli, "load_rates", return_value=rates),
        patch.object(cli, "Taximeter") as taximeter_class,
        patch.object(cli, "TripHistory", return_value=history),
        patch("builtins.input", side_effect=[*commands, "salir"]),
        redirect_stdout(output),
    ):
        auth_class.return_value.verify.return_value = True
        taximeter = taximeter_class.return_value
        taximeter.finish_trip.return_value = SUMMARY
        cli.run_cli()

    return taximeter, output.getvalue()


class CliHistoryTest(unittest.TestCase):
    def test_successful_finish_is_added_to_history(self) -> None:
        history = MagicMock()

        _, output = _run_history_cli(("inicio", "fin"), history)

        history.add.assert_called_once_with(SUMMARY)
        self.assertIn("Total a cobrar: 1.20 EUR", output)

    def test_prints_history_with_all_aliases(self) -> None:
        for command in ("historial", "h", "  HISTORIAL  "):
            with self.subTest(command=command):
                history = MagicMock()
                history.all.return_value = [ENTRY]

                _, output = _run_history_cli((command,), history)

                self.assertIn("Historial de carreras", output)
                self.assertIn(
                    "2026-09-25T10:30:00 | 30s | 1.20 EUR", output
                )

    def test_reports_empty_history(self) -> None:
        history = MagicMock()
        history.all.return_value = []

        _, output = _run_history_cli(("historial",), history)

        self.assertIn("Todavia no hay carreras guardadas.", output)


class GuiHistoryTest(unittest.TestCase):
    def _app_with_history(self, history: MagicMock) -> gui.TaximeterApp:
        app = gui.TaximeterApp.__new__(gui.TaximeterApp)
        app.history = history
        return app

    def test_finishing_trip_is_added_to_history(self) -> None:
        history = MagicMock()
        app = self._app_with_history(history)
        app.taximeter = MagicMock()
        app.taximeter.finish_trip.return_value = SUMMARY

        with patch.object(gui.messagebox, "showinfo") as show_info:
            app._finish()

        history.add.assert_called_once_with(SUMMARY)
        show_info.assert_called_once_with("Total", "Total a cobrar: 1.20 EUR")

    def test_shows_only_ten_most_recent_entries(self) -> None:
        history = MagicMock()
        history.all.return_value = [
            HistoryEntry(
                date=f"2026-09-25T10:{index:02d}:00",
                duration_seconds=index,
                amount=index / 100,
            )
            for index in range(12)
        ]
        app = self._app_with_history(history)

        with patch.object(gui.messagebox, "showinfo") as show_info:
            app._show_history()

        show_info.assert_called_once()
        title, text = show_info.call_args.args
        lines = text.splitlines()
        self.assertEqual(title, "Ultimas carreras")
        self.assertEqual(len(lines), 10)
        self.assertEqual(lines[0], "2026-09-25T10:02:00 | 2s | 0.02 EUR")
        self.assertEqual(lines[-1], "2026-09-25T10:11:00 | 11s | 0.11 EUR")

    def test_reports_empty_history(self) -> None:
        history = MagicMock()
        history.all.return_value = []
        app = self._app_with_history(history)

        with patch.object(gui.messagebox, "showinfo") as show_info:
            app._show_history()

        show_info.assert_called_once_with(
            "Historial", "Todavia no hay carreras guardadas."
        )


if __name__ == "__main__":
    unittest.main()
