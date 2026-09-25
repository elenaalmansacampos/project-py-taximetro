from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

from taximeter.auth import PasswordAuth
from taximeter.config import RatesConfigurationError, load_rates
from taximeter.history import TripHistory
from taximeter.taximeter import TaxiStatus, Taximeter


logger = logging.getLogger(__name__)


class TaximeterApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("TaxiTech Taximetro")
        self.root.geometry("520x560")
        self.root.minsize(420, 500)

        self.auth = PasswordAuth()
        self.taximeter = Taximeter(load_rates())
        self.history = TripHistory()

        if not self.auth.credentials_exist():
            self._show_setup()
        else:
            self._show_login()

    def _clear(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def _show_setup(self) -> None:
        self._clear()
        tk.Label(self.root, text="Crear contraseña", font=("Arial", 24, "bold")).pack(pady=32)
        password = tk.Entry(self.root, show="*", font=("Arial", 18))
        password.pack(padx=40, fill="x")
        repeated = tk.Entry(self.root, show="*", font=("Arial", 18))
        repeated.pack(padx=40, pady=16, fill="x")

        def save() -> None:
            if password.get() != repeated.get():
                messagebox.showerror("Error", "Las contraseñas no coinciden")
                return
            try:
                self.auth.create_password(password.get())
            except ValueError as error:
                messagebox.showerror("Error", str(error))
                return
            self._show_meter()

        tk.Button(
            self.root,
            text="Guardar",
            command=save,
            font=("Arial", 18),
            height=3,
        ).pack(pady=24)

    def _show_login(self) -> None:
        self._clear()
        tk.Label(self.root, text="TaxiTech Taximetro", font=("Arial", 26, "bold")).pack(pady=44)
        password = tk.Entry(self.root, show="*", font=("Arial", 20))
        password.pack(padx=40, fill="x")

        def login() -> None:
            try:
                authenticated = self.auth.verify(password.get())
            except Exception:
                logger.exception("gui_authentication_error")
                messagebox.showerror("Error", "No se pudo verificar la contraseña")
                return
            if authenticated:
                logger.info("gui_login_success")
                self._show_meter()
            else:
                logger.error("gui_login_failed")
                messagebox.showerror("Error", "Contraseña incorrecta")

        tk.Button(
            self.root,
            text="Entrar",
            command=login,
            font=("Arial", 18),
            height=3,
        ).pack(pady=28)

    def _show_meter(self) -> None:
        self._clear()
        self.status_label = tk.Label(self.root, text="Sin carrera activa", font=("Arial", 22))
        self.status_label.pack(pady=22)
        self.amount_label = tk.Label(self.root, text="0.00 EUR", font=("Arial", 44, "bold"))
        self.amount_label.pack(pady=12)
        self.time_label = tk.Label(self.root, text="0 s", font=("Arial", 18))
        self.time_label.pack(pady=8)

        buttons = tk.Frame(self.root)
        buttons.pack(padx=24, pady=24, fill="both", expand=True)
        for index in range(2):
            buttons.columnconfigure(index, weight=1)

        self._button(buttons, "Iniciar", self._start, 0, 0)
        self._button(buttons, "Parado", lambda: self._set_status(TaxiStatus.STOPPED), 0, 1)
        self._button(buttons, "Marcha", lambda: self._set_status(TaxiStatus.MOVING), 1, 0)
        self._button(buttons, "Finalizar", self._finish, 1, 1)
        self._button(buttons, "Historial", self._show_history, 2, 0, columnspan=2)
        self._refresh()

    def _button(
        self,
        parent: tk.Frame,
        text: str,
        command: object,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> None:
        tk.Button(parent, text=text, command=command, font=("Arial", 18), height=3).grid(
            row=row,
            column=column,
            columnspan=columnspan,
            padx=8,
            pady=8,
            sticky="nsew",
        )

    def _start(self) -> None:
        try:
            self.taximeter.start_trip()
            logger.info("gui_trip_started")
        except RuntimeError as error:
            logger.exception("gui_operation_error")
            messagebox.showinfo("Taximetro", str(error))

    def _set_status(self, status: TaxiStatus) -> None:
        try:
            self.taximeter.set_status(status)
            logger.info("gui_status_changed %s", status.value)
        except RuntimeError as error:
            logger.exception("gui_operation_error")
            messagebox.showinfo("Taximetro", str(error))

    def _finish(self) -> None:
        try:
            summary = self.taximeter.finish_trip()
        except RuntimeError as error:
            logger.exception("gui_operation_error")
            messagebox.showinfo("Taximetro", str(error))
            return

        try:
            self.history.add(summary)
        except Exception:
            logger.exception("gui_history_write_error")
            messagebox.showerror("Error", "No se pudo guardar la carrera")
        logger.info("gui_trip_finished amount=%.2f", summary.amount)
        messagebox.showinfo("Total", f"Total a cobrar: {summary.amount:.2f} EUR")

    def _show_history(self) -> None:
        try:
            entries = self.history.all()
        except Exception:
            logger.exception("gui_history_read_error")
            messagebox.showerror("Error", "No se pudo consultar el historial")
            return
        if not entries:
            messagebox.showinfo("Historial", "Todavia no hay carreras guardadas.")
            return
        text = "\n".join(
            f"{entry.date} | {entry.duration_seconds:.0f}s | {entry.amount:.2f} EUR"
            for entry in entries[-10:]
        )
        messagebox.showinfo("Ultimas carreras", text)

    def _refresh(self) -> None:
        if self.taximeter.active:
            self.status_label.config(text=f"Estado: {self.taximeter.status.value}")
            self.amount_label.config(text=f"{self.taximeter.current_amount():.2f} EUR")
            self.time_label.config(text=f"{self.taximeter.elapsed_seconds():.0f} s")
        else:
            self.status_label.config(text="Sin carrera activa")
            self.amount_label.config(text="0.00 EUR")
            self.time_label.config(text="0 s")
        self.root.after(500, self._refresh)


def run_gui() -> None:
    root = tk.Tk()
    try:
        TaximeterApp(root)
    except RatesConfigurationError as error:
        logger.exception("gui_configuration_error")
        messagebox.showerror("Error de configuración", str(error))
        root.destroy()
        raise SystemExit(1) from error
    root.mainloop()

