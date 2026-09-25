import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, call, patch

from taximeter import cli
from taximeter.config import Rates
from taximeter.taximeter import TaxiStatus


def _run_cli(
    commands: tuple[str, ...],
    start_error: Exception | None = None,
    status_error: Exception | None = None,
) -> tuple[MagicMock, str, MagicMock]:
    rates = Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05)
    output = io.StringIO()

    with (
        patch.object(cli, "PasswordAuth") as auth_class,
        patch.object(cli, "ensure_cli_password"),
        patch.object(cli, "_ask_password", return_value="password"),
        patch.object(cli, "load_rates", return_value=rates),
        patch.object(cli, "Taximeter") as taximeter_class,
        patch.object(cli, "TripHistory"),
        patch.object(cli.logger, "exception") as log_exception,
        patch("builtins.input", side_effect=[*commands, "salir"]),
        redirect_stdout(output),
    ):
        auth_class.return_value.verify.return_value = True
        taximeter = taximeter_class.return_value
        taximeter.current_amount.return_value = 0.0
        if start_error is not None:
            taximeter.start_trip.side_effect = start_error
        if status_error is not None:
            taximeter.set_status.side_effect = status_error

        cli.run_cli()

    return taximeter, output.getvalue(), log_exception


class CliStartTripTest(unittest.TestCase):
    def test_starts_trip_with_short_and_long_commands(self) -> None:
        for command in ("i", "inicio", "  INICIO  "):
            with self.subTest(command=command):
                _, output, _ = _run_cli((command,))
                self.assertIn("Carrera iniciada. Estado inicial: parado.", output)

    def test_reports_error_when_trip_is_already_active(self) -> None:
        _, output, _ = _run_cli(
            ("inicio",), start_error=RuntimeError("Ya hay una carrera activa")
        )

        self.assertIn("Error: Ya hay una carrera activa", output)


class CliStatusChangeTest(unittest.TestCase):
    def test_changes_status_with_all_aliases(self) -> None:
        cases = (
            ("p", TaxiStatus.STOPPED, "parado"),
            ("parado", TaxiStatus.STOPPED, "parado"),
            ("  PARADO  ", TaxiStatus.STOPPED, "parado"),
            ("m", TaxiStatus.MOVING, "en movimiento"),
            ("marcha", TaxiStatus.MOVING, "en movimiento"),
            ("  MARCHA  ", TaxiStatus.MOVING, "en movimiento"),
        )

        for command, expected_status, expected_label in cases:
            with self.subTest(command=command):
                taximeter, output, _ = _run_cli(("inicio", command))
                taximeter.set_status.assert_called_once_with(expected_status)
                self.assertIn(
                    f"Estado: {expected_label}. Importe actual: 0.00 EUR", output
                )

    def test_can_switch_back_to_stopped(self) -> None:
        taximeter, output, _ = _run_cli(("inicio", "marcha", "parado"))

        self.assertEqual(
            taximeter.set_status.call_args_list,
            [call(TaxiStatus.MOVING), call(TaxiStatus.STOPPED)],
        )
        self.assertIn("Estado: parado. Importe actual: 0.00 EUR", output)

    def test_reports_error_and_continues_without_active_trip(self) -> None:
        taximeter, output, log_exception = _run_cli(
            ("marcha",), status_error=RuntimeError("No hay ninguna carrera activa")
        )

        self.assertIn("Error: No hay ninguna carrera activa", output)
        log_exception.assert_called_once_with("operation_error")
        taximeter.set_status.assert_called_once_with(TaxiStatus.MOVING)


if __name__ == "__main__":
    unittest.main()
