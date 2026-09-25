from __future__ import annotations

import argparse
import logging
import sys
import time

from taximeter.auth import PasswordAuth, ensure_cli_password
from taximeter.config import RatesConfigurationError, load_rates
from taximeter.gui import run_gui
from taximeter.history import TripHistory
from taximeter.logging_config import configure_logging
from taximeter.taximeter import TaxiStatus, Taximeter


logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Taximetro digital TaxiTech Solutions")
    parser.add_argument("--gui", action="store_true", help="abre la interfaz grafica")
    args = parser.parse_args()

    configure_logging()
    logger.info("application_started")

    try:
        if args.gui:
            run_gui()
            return

        run_cli()
    except Exception:
        logger.exception("application_error")
        raise


def run_cli() -> None:
    try:
        rates = load_rates()
    except RatesConfigurationError as error:
        logger.exception("configuration_error")
        print(f"Error de configuración: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    auth = PasswordAuth()
    ensure_cli_password(auth)
    try:
        authenticated = auth.verify(_ask_password())
    except Exception:
        logger.exception("authentication_error")
        raise
    if not authenticated:
        logger.error("login_failed")
        print("Contraseña incorrecta.")
        sys.exit(1)

    taximeter = Taximeter(rates)
    history = TripHistory()

    print_welcome()
    while True:
        command = input("\nComando: ").strip().lower()
        try:
            if command in {"i", "inicio"}:
                taximeter.start_trip()
                logger.info("trip_started")
                print("Carrera iniciada. Estado inicial: parado.")
            elif command in {"p", "parado"}:
                taximeter.set_status(TaxiStatus.STOPPED)
                logger.info("status_changed stopped")
                print(f"Estado: parado. Importe actual: {taximeter.current_amount():.2f} EUR")
            elif command in {"m", "marcha"}:
                taximeter.set_status(TaxiStatus.MOVING)
                logger.info("status_changed moving")
                print(
                    f"Estado: en movimiento. Importe actual: {taximeter.current_amount():.2f} EUR"
                )
            elif command in {"f", "fin"}:
                summary = taximeter.finish_trip()
                history.add(summary)
                logger.info("trip_finished amount=%.2f", summary.amount)
                print(f"Total a cobrar: {summary.amount:.2f} EUR")
            elif command in {"h", "historial"}:
                print_history(history)
            elif command in {"v", "ver"}:
                if taximeter.active:
                    print(
                        f"Estado: {taximeter.status.value}. "
                        f"Tiempo: {taximeter.elapsed_seconds():.0f}s. "
                        f"Importe: {taximeter.current_amount():.2f} EUR"
                    )
                else:
                    print("No hay carrera activa.")
            elif command in {"s", "salir"}:
                logger.info("application_finished")
                print("Fin del turno.")
                return
            elif command == "":
                continue
            else:
                print("Comando no reconocido.")
        except Exception as error:
            logger.exception("operation_error")
            print(f"Error: {error}")


def print_welcome() -> None:
    print(
        """
TaxiTech Solutions - Taximetro Digital

Comandos:
  inicio | i      iniciar una carrera
  parado | p      cambiar a taxi parado o velocidad < 20 km/h
  marcha | m      cambiar a taxi en movimiento
  ver | v         ver estado, tiempo e importe actual
  fin | f         finalizar carrera y guardar historial
  historial | h   ver carreras guardadas
  salir | s       cerrar el programa
"""
    )


def print_history(history: TripHistory) -> None:
    entries = history.all()
    if not entries:
        print("Todavia no hay carreras guardadas.")
        return

    print("\nHistorial de carreras")
    for entry in entries:
        print(
            f"- {entry.date} | {entry.duration_seconds:.0f}s | {entry.amount:.2f} EUR"
        )


def _ask_password() -> str:
    try:
        import getpass

        return getpass.getpass("Contraseña: ")
    except (KeyboardInterrupt, EOFError):
        raise
    except Exception:
        time.sleep(0.1)
        return input("Contraseña: ")

