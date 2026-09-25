import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from taximeter import cli
from taximeter.config import Rates


class CliStartTripTest(unittest.TestCase):
    def test_starts_trip_with_short_and_long_commands(self) -> None:
        for command in ("i", "inicio", "  INICIO  "):
            with self.subTest(command=command):
                output = self._run_start_command(command)
                self.assertIn("Carrera iniciada. Estado inicial: parado.", output)

    def test_reports_error_when_trip_is_already_active(self) -> None:
        output = self._run_start_command(
            "inicio", start_error=RuntimeError("Ya hay una carrera activa")
        )

        self.assertIn("Error: Ya hay una carrera activa", output)

    def _run_start_command(
        self, command: str, start_error: Exception | None = None
    ) -> str:
        rates = Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05)
        output = io.StringIO()

        with (
            patch.object(cli, "PasswordAuth") as auth_class,
            patch.object(cli, "ensure_cli_password"),
            patch.object(cli, "_ask_password", return_value="password"),
            patch.object(cli, "load_rates", return_value=rates),
            patch.object(cli, "Taximeter") as taximeter_class,
            patch.object(cli, "TripHistory"),
            patch.object(cli.logger, "exception"),
            patch("builtins.input", side_effect=[command, "salir"]),
            redirect_stdout(output),
        ):
            auth_class.return_value.verify.return_value = True
            taximeter = taximeter_class.return_value
            if start_error is not None:
                taximeter.start_trip.side_effect = start_error

            cli.run_cli()

        taximeter.start_trip.assert_called_once_with()
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
