import io
import logging
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, call, patch

from taximeter import cli
from taximeter.config import Rates, RatesConfigurationError
from taximeter.taximeter import TaxiStatus, TripSummary


def _run_cli(
    commands: tuple[str, ...],
    start_error: Exception | None = None,
    status_error: Exception | None = None,
    finish_error: Exception | None = None,
    finish_summary: TripSummary | None = None,
    finish_summaries: tuple[TripSummary, ...] | None = None,
    history: MagicMock | None = None,
) -> tuple[MagicMock, str, MagicMock]:
    rates = Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05)
    output = io.StringIO()

    with (
        patch.object(cli, "PasswordAuth") as auth_class,
        patch.object(cli, "ensure_cli_password"),
        patch.object(cli, "_ask_password", return_value="password"),
        patch.object(cli, "load_rates", return_value=rates),
        patch.object(cli, "Taximeter") as taximeter_class,
        patch.object(cli, "TripHistory") as history_class,
        patch.object(cli.logger, "exception") as log_exception,
        patch("builtins.input", side_effect=[*commands, "salir"]),
        redirect_stdout(output),
    ):
        auth_class.return_value.verify.return_value = True
        taximeter = taximeter_class.return_value
        taximeter.current_amount.return_value = 0.0
        if history is not None:
            history_class.return_value = history
        if start_error is not None:
            taximeter.start_trip.side_effect = start_error
        if status_error is not None:
            taximeter.set_status.side_effect = status_error
        if finish_error is not None:
            taximeter.finish_trip.side_effect = finish_error
        elif finish_summaries is not None:
            taximeter.finish_trip.side_effect = finish_summaries
        elif finish_summary is not None:
            taximeter.finish_trip.return_value = finish_summary

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


class CliConfigurationTest(unittest.TestCase):
    def test_loads_current_rates_for_each_execution(self) -> None:
        configured_rates = (
            Rates(stopped_rate_per_second=0.10, moving_rate_per_second=0.20),
            Rates(stopped_rate_per_second=0.30, moving_rate_per_second=0.40),
        )

        for rates in configured_rates:
            with self.subTest(rates=rates):
                with (
                    patch.object(cli, "PasswordAuth") as auth_class,
                    patch.object(cli, "ensure_cli_password"),
                    patch.object(cli, "_ask_password", return_value="password"),
                    patch.object(cli, "load_rates", return_value=rates) as load_rates_mock,
                    patch.object(cli, "Taximeter") as taximeter_class,
                    patch.object(cli, "TripHistory"),
                    patch("builtins.input", return_value="salir"),
                    redirect_stdout(io.StringIO()),
                ):
                    auth_class.return_value.verify.return_value = True
                    cli.run_cli()

                load_rates_mock.assert_called_once_with()
                taximeter_class.assert_called_once_with(rates)

    def test_configuration_error_stops_startup_with_clear_message(self) -> None:
        error = RatesConfigurationError("Falta la clave 'moving_rate_per_second'")
        errors = io.StringIO()

        with (
            patch.object(cli, "load_rates", side_effect=error) as load_rates_mock,
            patch.object(cli, "PasswordAuth") as auth_class,
            patch.object(cli, "ensure_cli_password") as ensure_password,
            patch.object(cli, "Taximeter") as taximeter_class,
            patch("builtins.input") as input_mock,
            redirect_stderr(errors),
            self.assertLogs(cli.logger, level=logging.ERROR) as logs,
        ):
            with self.assertRaises(SystemExit) as exit_info:
                cli.run_cli()

        self.assertEqual(exit_info.exception.code, 1)
        load_rates_mock.assert_called_once_with()
        auth_class.assert_not_called()
        ensure_password.assert_not_called()
        taximeter_class.assert_not_called()
        input_mock.assert_not_called()
        self.assertIn("configuration_error", "\n".join(logs.output))
        self.assertIn("Error de configuración", errors.getvalue())
        self.assertIn(str(error), errors.getvalue())


class CliFinishTripTest(unittest.TestCase):
    def test_finishes_trip_with_all_aliases_and_prints_total(self) -> None:
        summary = TripSummary(duration_seconds=30, amount=1.20)

        for command in ("f", "fin", "  FIN  "):
            with self.subTest(command=command):
                taximeter, output, _ = _run_cli((command,), finish_summary=summary)

                taximeter.finish_trip.assert_called_once_with()
                self.assertIn("Total a cobrar: 1.20 EUR", output)

    def test_reports_error_when_there_is_no_active_trip(self) -> None:
        _, output, log_exception = _run_cli(
            ("fin",), finish_error=RuntimeError("No hay ninguna carrera activa")
        )

        self.assertIn("Error: No hay ninguna carrera activa", output)
        log_exception.assert_called_once_with("operation_error")


class CliMultipleTripsTest(unittest.TestCase):
    def test_finishes_and_starts_multiple_trips_without_exiting(self) -> None:
        first_summary = TripSummary(duration_seconds=30, amount=1.20)
        second_summary = TripSummary(duration_seconds=25, amount=1.10)
        history = MagicMock()

        taximeter, output, _ = _run_cli(
            ("inicio", "marcha", "fin", "i", "parado", "f"),
            finish_summaries=(first_summary, second_summary),
            history=history,
        )

        self.assertEqual(taximeter.start_trip.call_count, 2)
        self.assertEqual(
            taximeter.set_status.call_args_list,
            [call(TaxiStatus.MOVING), call(TaxiStatus.STOPPED)],
        )
        self.assertEqual(taximeter.finish_trip.call_count, 2)
        self.assertEqual(
            history.add.call_args_list, [call(first_summary), call(second_summary)]
        )
        self.assertEqual(
            output.count("Carrera iniciada. Estado inicial: parado."), 2
        )
        self.assertIn("Total a cobrar: 1.20 EUR", output)
        self.assertIn("Total a cobrar: 1.10 EUR", output)
        self.assertIn("Fin del turno.", output)


if __name__ == "__main__":
    unittest.main()
