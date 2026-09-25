import io
import logging
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from taximeter import cli, gui, logging_config
from taximeter.config import Rates, RatesConfigurationError


class LoggingConfigurationTest(unittest.TestCase):
    def test_creates_utf8_log_with_required_fields(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        log_path = Path(temporary_directory.name) / "logs" / "taximetro.log"
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers[:]
        original_level = root_logger.level

        try:
            root_logger.handlers.clear()
            with patch.object(logging_config, "LOG_PATH", log_path):
                logging_config.configure_logging()
                logging.getLogger("taximeter.test").info("operación completada")
                for handler in root_logger.handlers:
                    handler.flush()

            content = log_path.read_text(encoding="utf-8")
            self.assertRegex(
                content.strip(),
                r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} INFO taximeter\.test "
                r"operación completada$",
            )
        finally:
            for handler in root_logger.handlers:
                root_logger.removeHandler(handler)
                handler.close()
            root_logger.handlers = original_handlers
            root_logger.setLevel(original_level)


class CliLoggingTest(unittest.TestCase):
    def test_authentication_failure_is_logged_without_password(self) -> None:
        password = "contraseña-secreta"
        with (
            patch.object(cli, "PasswordAuth") as auth_class,
            patch.object(cli, "ensure_cli_password"),
            patch.object(cli, "_ask_password", return_value=password),
            redirect_stdout(io.StringIO()),
        ):
            auth_class.return_value.verify.return_value = False
            with self.assertLogs(cli.logger, level=logging.ERROR) as logs:
                with self.assertRaises(SystemExit) as exit_info:
                    cli.run_cli()

        self.assertEqual(exit_info.exception.code, 1)
        self.assertTrue(any("login_failed" in message for message in logs.output))
        self.assertNotIn(password, "\n".join(logs.output))

    def test_operation_errors_are_logged_with_exception_details(self) -> None:
        rates = Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05)
        taximeter = MagicMock()
        taximeter.set_status.side_effect = RuntimeError("fallo de estado")

        with (
            patch.object(cli, "PasswordAuth") as auth_class,
            patch.object(cli, "ensure_cli_password"),
            patch.object(cli, "_ask_password", return_value="password"),
            patch.object(cli, "load_rates", return_value=rates),
            patch.object(cli, "Taximeter", return_value=taximeter),
            patch.object(cli, "TripHistory"),
            patch("builtins.input", side_effect=["marcha", "salir"]),
            redirect_stdout(io.StringIO()),
        ):
            auth_class.return_value.verify.return_value = True
            with self.assertLogs(cli.logger, level=logging.ERROR) as logs:
                cli.run_cli()

        log_output = "\n".join(logs.output)
        self.assertIn("operation_error", log_output)
        self.assertIn("fallo de estado", log_output)


class GuiLoggingTest(unittest.TestCase):
    def test_operation_errors_are_logged(self) -> None:
        app = gui.TaximeterApp.__new__(gui.TaximeterApp)
        app.taximeter = MagicMock()
        app.taximeter.start_trip.side_effect = RuntimeError("No se pudo iniciar")

        with patch.object(gui.messagebox, "showinfo") as show_info:
            with self.assertLogs(gui.logger, level=logging.ERROR) as logs:
                app._start()

        log_output = "\n".join(logs.output)
        self.assertIn("gui_operation_error", log_output)
        self.assertIn("No se pudo iniciar", log_output)
        show_info.assert_called_once_with("Taximetro", "No se pudo iniciar")

    def test_configuration_errors_are_shown_and_logged(self) -> None:
        root = MagicMock()
        error = RatesConfigurationError("No existe el fichero de tarifas")

        with (
            patch.object(gui.tk, "Tk", return_value=root),
            patch.object(gui, "TaximeterApp", side_effect=error),
            patch.object(gui.messagebox, "showerror") as show_error,
            self.assertLogs(gui.logger, level=logging.ERROR) as logs,
        ):
            with self.assertRaises(SystemExit) as exit_info:
                gui.run_gui()

        self.assertEqual(exit_info.exception.code, 1)
        self.assertIn("gui_configuration_error", "\n".join(logs.output))
        show_error.assert_called_once_with("Error de configuración", str(error))
        root.destroy.assert_called_once_with()
        root.mainloop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
