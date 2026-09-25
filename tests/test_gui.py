import sys
import unittest
from unittest.mock import MagicMock, call, patch

from taximeter import cli, gui
from taximeter.config import Rates
from taximeter.taximeter import TaxiStatus, TripSummary


SUMMARY = TripSummary(duration_seconds=30, amount=1.20)


class GuiTestCase(unittest.TestCase):
    def _app(self) -> gui.TaximeterApp:
        app = gui.TaximeterApp.__new__(gui.TaximeterApp)
        app.root = MagicMock()
        app.taximeter = MagicMock()
        app.taximeter.active = False
        app.taximeter.status = TaxiStatus.STOPPED
        app.taximeter.current_amount.return_value = 0.0
        app.taximeter.elapsed_seconds.return_value = 0.0
        app.history = MagicMock()
        app._clear = MagicMock()
        return app


class GuiEntryPointTest(unittest.TestCase):
    def test_gui_flag_routes_to_gui(self) -> None:
        with (
            patch.object(sys, "argv", ["main.py", "--gui"]),
            patch.object(cli, "configure_logging"),
            patch.object(cli, "run_gui") as run_gui,
            patch.object(cli, "run_cli") as run_cli,
        ):
            cli.main()

        run_gui.assert_called_once_with()
        run_cli.assert_not_called()


class GuiMeterLayoutTest(GuiTestCase):
    def test_meter_has_large_buttons_and_initial_values(self) -> None:
        app = self._app()
        with (
            patch.object(gui.tk, "Label") as label_class,
            patch.object(gui.tk, "Frame") as frame_class,
            patch.object(gui.tk, "Button") as button_class,
        ):
            app._show_meter()

        expected_buttons = ["Iniciar", "Parado", "Marcha", "Finalizar", "Historial"]
        actual_buttons = [button.kwargs["text"] for button in button_class.call_args_list]
        self.assertEqual(actual_buttons, expected_buttons)
        for button_call in button_class.call_args_list:
            self.assertEqual(button_call.kwargs["font"], ("Arial", 18))
            self.assertEqual(button_call.kwargs["height"], 3)
            self.assertTrue(callable(button_call.kwargs["command"]))

        self.assertEqual(
            [label.kwargs["text"] for label in label_class.call_args_list],
            ["Sin carrera activa", "0.00 EUR", "0 s"],
        )
        self.assertEqual(
            frame_class.return_value.columnconfigure.call_args_list,
            [call(0, weight=1), call(1, weight=1)],
        )
        app.root.after.assert_called_once_with(500, app._refresh)

    def test_refresh_shows_active_trip_values(self) -> None:
        app = self._app()
        app.taximeter.active = True
        app.taximeter.status = TaxiStatus.MOVING
        app.taximeter.current_amount.return_value = 1.23
        app.taximeter.elapsed_seconds.return_value = 4.6
        app.status_label = MagicMock()
        app.amount_label = MagicMock()
        app.time_label = MagicMock()

        app._refresh()

        app.status_label.config.assert_called_once_with(text="Estado: en movimiento")
        app.amount_label.config.assert_called_once_with(text="1.23 EUR")
        app.time_label.config.assert_called_once_with(text="5 s")
        app.root.after.assert_called_once_with(500, app._refresh)

    def test_refresh_shows_initial_values_without_active_trip(self) -> None:
        app = self._app()
        app.status_label = MagicMock()
        app.amount_label = MagicMock()
        app.time_label = MagicMock()

        app._refresh()

        app.status_label.config.assert_called_once_with(text="Sin carrera activa")
        app.amount_label.config.assert_called_once_with(text="0.00 EUR")
        app.time_label.config.assert_called_once_with(text="0 s")
        app.root.after.assert_called_once_with(500, app._refresh)

    def test_controls_delegate_to_central_taximeter(self) -> None:
        app = self._app()
        app.taximeter.finish_trip.return_value = SUMMARY

        with patch.object(gui.messagebox, "showinfo"):
            app._start()
            app._set_status(TaxiStatus.MOVING)
            app._set_status(TaxiStatus.STOPPED)
            app._finish()

        app.taximeter.start_trip.assert_called_once_with()
        self.assertEqual(
            app.taximeter.set_status.call_args_list,
            [call(TaxiStatus.MOVING), call(TaxiStatus.STOPPED)],
        )
        app.taximeter.finish_trip.assert_called_once_with()
        app.history.add.assert_called_once_with(SUMMARY)

    def test_finish_always_shows_total_when_history_write_fails(self) -> None:
        app = self._app()
        app.taximeter.finish_trip.return_value = SUMMARY
        app.history.add.side_effect = OSError("disco no disponible")

        with (
            patch.object(gui.messagebox, "showerror") as show_error,
            patch.object(gui.messagebox, "showinfo") as show_info,
            patch.object(gui.logger, "exception"),
        ):
            app._finish()

        show_error.assert_called_once_with("Error", "No se pudo guardar la carrera")
        show_info.assert_called_once_with("Total", "Total a cobrar: 1.20 EUR")


class GuiAuthenticationTest(unittest.TestCase):
    def test_first_run_uses_hidden_confirmation_and_rejects_short_password(self) -> None:
        root = MagicMock()
        password = MagicMock()
        repeated = MagicMock()
        password.get.side_effect = ["abc", "abc"]
        repeated.get.return_value = "abc"
        auth = MagicMock()
        auth.credentials_exist.return_value = False
        auth.create_password.side_effect = ValueError(
            "La contraseña debe tener al menos 4 caracteres"
        )

        with (
            patch.object(gui, "PasswordAuth", return_value=auth),
            patch.object(gui, "load_rates", return_value=Rates(0.02, 0.05)),
            patch.object(gui, "Taximeter"),
            patch.object(gui, "TripHistory"),
            patch.object(gui.tk, "Label"),
            patch.object(gui.tk, "Entry", side_effect=[password, repeated]) as entry_class,
            patch.object(gui.tk, "Button") as button_class,
            patch.object(gui.messagebox, "showerror") as show_error,
        ):
            gui.TaximeterApp(root)
            save = button_class.call_args.kwargs["command"]
            save()

        self.assertEqual(
            [entry_call.kwargs["show"] for entry_call in entry_class.call_args_list],
            ["*", "*"],
        )
        auth.create_password.assert_called_once_with("abc")
        show_error.assert_called_once_with(
            "Error", "La contraseña debe tener al menos 4 caracteres"
        )
        self.assertEqual(button_class.call_args.kwargs["font"], ("Arial", 18))
        self.assertEqual(button_class.call_args.kwargs["height"], 3)
        auth.verify.assert_not_called()

    def test_existing_credentials_allow_retry_after_wrong_password(self) -> None:
        root = MagicMock()
        password = MagicMock()
        password.get.return_value = "incorrecta"
        auth = MagicMock()
        auth.credentials_exist.return_value = True
        auth.verify.side_effect = [False, True]

        with (
            patch.object(gui, "PasswordAuth", return_value=auth),
            patch.object(gui, "load_rates", return_value=Rates(0.02, 0.05)),
            patch.object(gui, "Taximeter"),
            patch.object(gui, "TripHistory"),
            patch.object(gui.tk, "Label"),
            patch.object(gui.tk, "Entry", return_value=password) as entry_class,
            patch.object(gui.tk, "Button") as button_class,
            patch.object(gui.TaximeterApp, "_show_meter") as show_meter,
            patch.object(gui.messagebox, "showerror") as show_error,
            patch.object(gui.logger, "error"),
        ):
            gui.TaximeterApp(root)
            login = button_class.call_args.kwargs["command"]
            login()
            login()

        show_error.assert_called_once_with("Error", "Contraseña incorrecta")
        self.assertEqual(entry_class.call_args.kwargs["show"], "*")
        self.assertEqual(button_class.call_args.kwargs["font"], ("Arial", 18))
        self.assertEqual(button_class.call_args.kwargs["height"], 3)
        self.assertEqual(auth.verify.call_args_list, [call("incorrecta"), call("incorrecta")])
        show_meter.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
