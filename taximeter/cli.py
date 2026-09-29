from __future__ import annotations

import argparse
import logging
import sys
import time

from taximeter.api import (
    DEFAULT_API_HOST,
    DEFAULT_API_PORT,
    TRIPS_PATH,
    create_server,
)
from taximeter.auth import PasswordAuth, ensure_cli_password
from taximeter.config import RatesConfigurationError, load_rates
from taximeter.database import TripHistory
from taximeter.gui import run_gui
from taximeter.history import HistoryRepository
from taximeter.logging_config import configure_logging
from taximeter.migration import (
    MigrationError,
    format_migration_report,
    migrate_csv_to_database,
)
from taximeter.taximeter import TaxiStatus, Taximeter


logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Taximetro digital TaxiTech Solutions")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--gui", action="store_true", help="abre la interfaz grafica")
    modes.add_argument(
        "--migrate-history",
        action="store_true",
        help="migra el historial CSV a SQLite",
    )
    modes.add_argument(
        "--api",
        action="store_true",
        help="inicia la API REST de consulta del historial",
    )
    parser.add_argument(
        "--api-host",
        default=None,
        help=f"direccion de escucha de la API (por defecto {DEFAULT_API_HOST})",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=None,
        help=f"puerto de escucha de la API (por defecto {DEFAULT_API_PORT})",
    )
    args = parser.parse_args()

    if (args.api_host is not None or args.api_port is not None) and not args.api:
        parser.error("--api-host y --api-port solo son validos junto a --api")

    configure_logging()
    logger.info("application_started")

    try:
        if args.migrate_history:
            run_history_migration()
            return

        if args.api:
            run_api(
                host=args.api_host or DEFAULT_API_HOST,
                port=args.api_port or DEFAULT_API_PORT,
            )
            return

        if args.gui:
            run_gui()
            return

        run_cli()
    except Exception:
        logger.exception("application_error")
        raise


def run_history_migration() -> None:
    try:
        report = migrate_csv_to_database()
    except MigrationError as error:
        logger.exception("history_migration_error")
        print(f"Error de migracion: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    output = format_migration_report(report)
    print(output)
    logger.info(
        "history_migration_finished imported=%s duplicates=%s rejected=%s",
        report.imported,
        report.duplicates,
        report.rejected_count,
    )
    if not report.ok:
        raise SystemExit(1)


def run_api(host: str = DEFAULT_API_HOST, port: int = DEFAULT_API_PORT) -> None:
    history = TripHistory()
    server = create_server(history, host, port)
    logger.info(
        "api_started host=%s port=%s",
        server.server_address[0],
        server.server_address[1],
    )
    print(f"API REST del historial en {server.base_url}{TRIPS_PATH}")
    print("La API es de solo lectura. Pulsa Ctrl+C para detenerla.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nAPI detenida.")
        logger.info("api_stopped")
    finally:
        server.server_close()


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


def print_history(history: HistoryRepository) -> None:
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

