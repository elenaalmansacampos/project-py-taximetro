from __future__ import annotations

import logging
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from taximeter.infrastructure.auth import CorruptCredentialsError, PasswordAuth
from taximeter.infrastructure.config import RatesConfigurationError, load_rates
from taximeter.infrastructure.database import TripHistory
from taximeter.domain.taximeter import TaxiStatus, Taximeter


logger = logging.getLogger(__name__)

BG = "#0F1115"
CARD = "#1A1D24"
SURFACE = "#2A2F3A"
BORDER = "#2E3340"
INPUT = "#12141A"
TEXT = "#E5E7EB"
MUTED = "#9CA3AF"
INK = "#0F1115"
WHITE = "#FFFFFF"
ACCENT = "#22D3EE"
ACCENT_HOVER = "#06B6D4"
SUCCESS = "#10B981"
SUCCESS_HOVER = "#059669"
WARNING = "#F5B301"
WARNING_HOVER = "#D69E2E"
DANGER = "#EF4444"
DANGER_HOVER = "#DC2626"
NEUTRAL_HOVER = "#374151"


class TaximeterApp:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("TaxiTech Taximetro")
        self.root.geometry("560x620")
        self.root.minsize(460, 560)
        self.root.configure(fg_color=BG)

        self.auth = PasswordAuth()
        self.taximeter = Taximeter(load_rates())
        self.history = TripHistory()

        if not self.auth.credentials_exist():
            self._show_setup()
        elif self.auth.load() is None:
            self._show_reset()
        else:
            self._show_login()

    def _clear(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()

    def _center_card(self) -> ctk.CTkFrame:
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        card = ctk.CTkFrame(
            self.root,
            fg_color=CARD,
            corner_radius=20,
            border_width=1,
            border_color=BORDER,
        )
        card.grid(row=0, column=0, padx=48, pady=48, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        return card

    def _entry(self, parent: ctk.CTkFrame, **placeholder: object) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            height=44,
            corner_radius=10,
            fg_color=INPUT,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=("Arial", 16),
            show=placeholder.pop("show", ""),
            **placeholder,  # type: ignore[arg-type]
        )

    def _show_setup(self) -> None:
        self._show_password_form("Crear contraseña")

    def _show_reset(self) -> None:
        self._show_password_form(
            "Restablecer contraseña",
            "El archivo de credenciales esta dañado. "
            "Crea una contraseña nueva para continuar.",
        )

    def _show_password_form(self, title: str, message: str | None = None) -> None:
        self._clear()
        card = self._center_card()

        row = 0
        ctk.CTkLabel(
            card, text=title, font=("Arial", 24, "bold"), text_color=TEXT
        ).grid(row=row, column=0, pady=(56, 4))
        row += 1
        if message is not None:
            ctk.CTkLabel(
                card,
                text=message,
                font=("Arial", 14),
                text_color=MUTED,
                wraplength=380,
                justify="center",
            ).grid(row=row, column=0, padx=32, pady=(0, 24))
            row += 1

        password = self._entry(card, show="*", placeholder_text="Contraseña")
        password.grid(row=row, column=0, padx=32, pady=(0, 8), sticky="ew")
        row += 1
        repeated = self._entry(
            card, show="*", placeholder_text="Repite la contraseña"
        )
        repeated.grid(row=row, column=0, padx=32, pady=(0, 8), sticky="ew")
        row += 1

        def save() -> None:
            if password.get() != repeated.get():
                messagebox.showerror("Error", "Las contraseñas no coinciden")
                return
            try:
                self.auth.create_password(password.get())
            except ValueError as error:
                messagebox.showerror("Error", str(error))
                return
            except OSError as error:
                logger.exception("gui_credentials_write_error")
                messagebox.showerror(
                    "Error", f"No se pudo guardar la contraseña: {error}"
                )
                return
            self._show_meter()

        ctk.CTkButton(
            card,
            text="Guardar",
            command=save,
            font=("Arial", 18),
            height=48,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=INK,
        ).grid(row=row, column=0, padx=32, pady=(8, 56), sticky="ew")

        password.bind("<Return>", lambda event: save())
        repeated.bind("<Return>", lambda event: save())
        password.focus()

    def _show_login(self) -> None:
        self._clear()
        card = self._center_card()

        ctk.CTkLabel(
            card, text="TaxiTech Taximetro", font=("Arial", 26, "bold"), text_color=TEXT
        ).grid(row=0, column=0, pady=(56, 4))
        ctk.CTkLabel(
            card, text="Acceso restringido", font=("Arial", 14), text_color=ACCENT
        ).grid(row=1, column=0, pady=(0, 28))

        password = self._entry(card, show="*", placeholder_text="Contraseña")
        password.grid(row=2, column=0, padx=32, sticky="ew", pady=(0, 8))

        def login() -> None:
            try:
                authenticated = self.auth.verify(password.get())
            except CorruptCredentialsError as error:
                logger.exception("gui_credentials_corrupted")
                messagebox.showerror("Error", str(error))
                self._show_reset()
                return
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

        ctk.CTkButton(
            card,
            text="Entrar",
            command=login,
            font=("Arial", 18),
            height=48,
            corner_radius=12,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color=INK,
        ).grid(row=3, column=0, padx=32, pady=(8, 56), sticky="ew")

        password.bind("<Return>", lambda event: login())
        password.focus()

    def _show_meter(self) -> None:
        self._clear()
        self.root.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.root, text="TaxiTech Taximetro", font=("Arial", 20, "bold"), text_color=MUTED
        ).grid(row=0, column=0, pady=(28, 0))

        self.amount_label = ctk.CTkLabel(
            self.root, text="0.00 EUR", font=("Arial", 52, "bold"), text_color=TEXT
        )
        self.amount_label.grid(row=1, column=0, pady=(12, 0))

        self.time_label = ctk.CTkLabel(
            self.root, text="0 s", font=("Arial", 18), text_color=MUTED
        )
        self.time_label.grid(row=2, column=0, pady=(4, 0))

        self.status_label = ctk.CTkLabel(
            self.root,
            text="Sin carrera activa",
            font=("Arial", 16, "bold"),
            fg_color=SURFACE,
            corner_radius=14,
            text_color=MUTED,
            padx=16,
            pady=6,
        )
        self.status_label.grid(row=3, column=0, pady=(18, 0))

        buttons = ctk.CTkFrame(self.root, fg_color="transparent")
        buttons.grid(row=4, column=0, padx=24, pady=24, sticky="nsew")
        self.root.grid_rowconfigure(4, weight=1)
        for index in range(2):
            buttons.columnconfigure(index, weight=1)
        for index in range(3):
            buttons.rowconfigure(index, weight=1)

        self._button(
            buttons, "Iniciar", self._start, 0, 0, SUCCESS, SUCCESS_HOVER, INK
        )
        self._button(
            buttons,
            "Parado",
            lambda: self._set_status(TaxiStatus.STOPPED),
            0,
            1,
            WARNING,
            WARNING_HOVER,
            INK,
        )
        self._button(
            buttons,
            "Marcha",
            lambda: self._set_status(TaxiStatus.MOVING),
            1,
            0,
            ACCENT,
            ACCENT_HOVER,
            INK,
        )
        self._button(
            buttons, "Finalizar", self._finish, 1, 1, DANGER, DANGER_HOVER, WHITE
        )
        self._button(
            buttons,
            "Historial",
            self._show_history,
            2,
            0,
            SURFACE,
            NEUTRAL_HOVER,
            TEXT,
            columnspan=2,
        )
        self._refresh()

    def _button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        command: Callable[[], None],
        row: int,
        column: int,
        fg_color: str,
        hover_color: str,
        text_color: str,
        columnspan: int = 1,
    ) -> None:
        ctk.CTkButton(
            parent,
            text=text,
            command=command,
            font=("Arial", 18),
            height=48,
            corner_radius=12,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
        ).grid(
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
            moving = self.taximeter.status == TaxiStatus.MOVING
            self.status_label.configure(
                text=f"Estado: {self.taximeter.status.value}",
                fg_color=SUCCESS if moving else WARNING,
                text_color=INK,
            )
            self.amount_label.configure(
                text=f"{self.taximeter.current_amount():.2f} EUR"
            )
            self.time_label.configure(text=f"{self.taximeter.elapsed_seconds():.0f} s")
        else:
            self.status_label.configure(
                text="Sin carrera activa", fg_color=SURFACE, text_color=MUTED
            )
            self.amount_label.configure(text="0.00 EUR")
            self.time_label.configure(text="0 s")
        self.root.after(500, self._refresh)


def run_gui() -> None:
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    try:
        TaximeterApp(root)
    except RatesConfigurationError as error:
        logger.exception("gui_configuration_error")
        messagebox.showerror("Error de configuración", str(error))
        root.destroy()
        raise SystemExit(1) from error
    root.mainloop()
