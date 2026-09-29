import time
import tkinter as tk
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from taximeter import gui
from taximeter.auth import PasswordAuth
from taximeter.config import Rates
from taximeter.taximeter import Taximeter, TaxiStatus


STOPPED_RATE = 0.02
MOVING_RATE = 0.05


class FakeClock:
    def __init__(self, value: float = 1000.0) -> None:
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _children_of_type(root: tk.Misc, widget_type: type) -> list:
    return [child for child in root.winfo_children() if isinstance(child, widget_type)]


def _pump_until(root: tk.Misc, predicate, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


class GuiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Sin display disponible: {error}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.credentials_path = Path(directory.name) / "credentials.json"
        self.auth = PasswordAuth(self.credentials_path)
        self.clock = FakeClock()

    def build_meter_app(self, real_clock: bool = False) -> gui.TaximeterApp:
        app = gui.TaximeterApp.__new__(gui.TaximeterApp)
        app.root = self.root
        app.auth = self.auth
        app.history = MagicMock()
        app.taximeter = Taximeter(
            Rates(stopped_rate_per_second=STOPPED_RATE, moving_rate_per_second=MOVING_RATE),
            clock=time.monotonic if real_clock else self.clock,
        )
        return app

    def build_login_app(self) -> gui.TaximeterApp:
        return self.build_meter_app()

    def submit(self, password: str, repeated: str | None = None) -> None:
        entries = _children_of_type(self.root, tk.Entry)
        entries[0].insert(0, password)
        entries[1].insert(0, password if repeated is None else repeated)
        _children_of_type(self.root, tk.Button)[-1].invoke()

    def submit_login(self, password: str) -> None:
        _children_of_type(self.root, tk.Entry)[0].insert(0, password)
        _children_of_type(self.root, tk.Button)[-1].invoke()

    def labels_text(self) -> list[str]:
        return [label.cget("text") for label in _children_of_type(self.root, tk.Label)]

    def meter_buttons(self) -> list[tk.Button]:
        return _children_of_type(self.root.winfo_children()[-1], tk.Button)


class RealTimeCounterTest(GuiTestCase):
    def test_meter_shows_status_amount_and_time(self) -> None:
        app = self.build_meter_app()
        app.taximeter.start_trip()
        app.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(120)

        app._show_meter()
        app._refresh()

        self.assertEqual(
            self.labels_text(),
            ["Estado: en movimiento", "6.00 EUR", "120 s"],
        )

    def test_meter_shows_idle_state_without_active_trip(self) -> None:
        app = self.build_meter_app()

        app._show_meter()

        self.assertEqual(
            self.labels_text(), ["Sin carrera activa", "0.00 EUR", "0 s"]
        )

    def test_refresh_reschedules_itself_every_500_ms(self) -> None:
        app = self.build_meter_app()
        app._show_meter()
        scheduled: list[tuple[int, object]] = []
        real_after = self.root.after

        def recording_after(milliseconds, callback=None, *args):
            scheduled.append((milliseconds, callback))
            return real_after(milliseconds, callback, *args)

        self.root.after = recording_after
        try:
            app._refresh()
        finally:
            self.root.after = real_after

        self.assertEqual(scheduled[-1], (500, app._refresh))

    def test_counter_advances_on_its_own_without_manual_refresh(self) -> None:
        app = self.build_meter_app(real_clock=True)
        app.taximeter.start_trip()
        app.taximeter.set_status(TaxiStatus.MOVING)
        app._show_meter()
        before = app.amount_label.cget("text")

        advanced = _pump_until(
            self.root, lambda: app.amount_label.cget("text") != before
        )

        self.assertTrue(advanced, "el contador no se actualizo solo")
        self.assertNotEqual(app.time_label.cget("text"), "0 s")
        self.assertEqual(app.status_label.cget("text"), "Estado: en movimiento")

    def test_amount_follows_the_active_status(self) -> None:
        app = self.build_meter_app()
        app.taximeter.start_trip()
        self.clock.advance(60)
        app.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(60)
        app._show_meter()
        app._refresh()

        # 60 s parado (1.20) + 60 s en movimiento (3.00)
        self.assertEqual(app.amount_label.cget("text"), "4.20 EUR")

    def test_buttons_are_large_touch_targets(self) -> None:
        app = self.build_meter_app()

        app._show_meter()
        buttons = self.meter_buttons()

        self.assertEqual(len(buttons), 5)
        for button in buttons:
            with self.subTest(boton=button.cget("text")):
                self.assertEqual(int(button.cget("height")), 3)
                self.assertGreaterEqual(button.winfo_reqwidth(), 100)


class PasswordSetupTest(GuiTestCase):
    def test_creating_a_password_opens_the_meter(self) -> None:
        app = self.build_login_app()

        app._show_setup()
        self.assertIn("Crear contraseña", self.labels_text())

        self.submit("secreto123")

        self.assertTrue(self.auth.verify("secreto123"))
        self.assertIn("Sin carrera activa", self.labels_text())

    def test_mismatched_passwords_are_reported_and_nothing_is_saved(self) -> None:
        app = self.build_login_app()

        with patch.object(gui.messagebox, "showerror") as show_error:
            app._show_setup()
            self.submit("secreto123", repeated="otro1234")

        show_error.assert_called_once_with("Error", "Las contraseñas no coinciden")
        self.assertFalse(self.credentials_path.exists())
        self.assertIn("Crear contraseña", self.labels_text())

    def test_short_passwords_are_reported_and_nothing_is_saved(self) -> None:
        app = self.build_login_app()

        with patch.object(gui.messagebox, "showerror") as show_error:
            app._show_setup()
            self.submit("abc")

        self.assertEqual(show_error.call_count, 1)
        self.assertIn("4 caracteres", show_error.call_args[0][1])
        self.assertFalse(self.credentials_path.exists())

    def test_write_failures_are_reported_without_crashing(self) -> None:
        app = self.build_login_app()
        app.auth = MagicMock()
        app.auth.create_password.side_effect = OSError("disco lleno")

        with patch.object(gui.messagebox, "showerror") as show_error:
            app._show_setup()
            with self.assertLogs(gui.logger, level="ERROR") as logs:
                self.submit("secreto123")

        self.assertIn("gui_credentials_write_error", "\n".join(logs.output))
        self.assertIn("No se pudo guardar la contraseña", show_error.call_args[0][1])
        self.assertIn("Crear contraseña", self.labels_text())


class LoginTest(GuiTestCase):
    def test_correct_password_opens_the_meter(self) -> None:
        self.auth.create_password("secreto123")
        app = self.build_login_app()

        app._show_login()
        self.assertIn("TaxiTech Taximetro", self.labels_text())

        self.submit_login("secreto123")

        self.assertIn("Sin carrera activa", self.labels_text())

    def test_wrong_password_is_reported_and_keeps_the_login_screen(self) -> None:
        self.auth.create_password("secreto123")
        app = self.build_login_app()

        with patch.object(gui.messagebox, "showerror") as show_error:
            app._show_login()
            with self.assertLogs(gui.logger, level="ERROR") as logs:
                self.submit_login("incorrecta")

        self.assertIn("gui_login_failed", "\n".join(logs.output))
        show_error.assert_called_once_with("Error", "Contraseña incorrecta")
        self.assertIn("TaxiTech Taximetro", self.labels_text())
        self.assertFalse(hasattr(app, "amount_label"))


class CorruptCredentialsRecoveryTest(GuiTestCase):
    def corrupt_credentials(self) -> None:
        self.credentials_path.write_text("{ truncado", encoding="utf-8")

    def test_startup_with_damaged_credentials_offers_a_reset(self) -> None:
        self.corrupt_credentials()

        with patch.object(gui, "load_rates", return_value=Rates(STOPPED_RATE, MOVING_RATE)), \
                patch.object(gui, "PasswordAuth", return_value=self.auth):
            gui.TaximeterApp(self.root)

        self.assertIn("Restablecer contraseña", self.labels_text())

    def test_login_on_damaged_credentials_falls_back_to_reset(self) -> None:
        self.auth.create_password("secreto123")
        app = self.build_login_app()

        with patch.object(gui.messagebox, "showerror") as show_error:
            app._show_login()
            self.corrupt_credentials()
            self.submit_login("secreto123")

        self.assertIn("dañado", show_error.call_args[0][1])
        self.assertIn("Restablecer contraseña", self.labels_text())

    def test_reset_creates_new_credentials_and_opens_the_meter(self) -> None:
        self.corrupt_credentials()
        app = self.build_login_app()

        app._show_reset()
        self.submit("nueva1234")

        self.assertTrue(self.auth.verify("nueva1234"))
        self.assertIn("Sin carrera activa", self.labels_text())

    def test_startup_without_credentials_shows_the_creation_form(self) -> None:
        with patch.object(gui, "load_rates", return_value=Rates(STOPPED_RATE, MOVING_RATE)), \
                patch.object(gui, "PasswordAuth", return_value=self.auth):
            gui.TaximeterApp(self.root)

        self.assertIn("Crear contraseña", self.labels_text())

    def test_startup_with_valid_credentials_shows_login(self) -> None:
        self.auth.create_password("secreto123")

        with patch.object(gui, "load_rates", return_value=Rates(STOPPED_RATE, MOVING_RATE)), \
                patch.object(gui, "PasswordAuth", return_value=self.auth):
            gui.TaximeterApp(self.root)

        self.assertIn("TaxiTech Taximetro", self.labels_text())


if __name__ == "__main__":
    unittest.main()
