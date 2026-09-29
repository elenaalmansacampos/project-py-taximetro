from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from taximeter import paths
from taximeter.config import RatesConfigurationError, load_rates
from taximeter.history import TripHistory
from taximeter.taximeter import TaxiStatus, Taximeter


EXIT_OK = 0
EXIT_UNEXPECTED = 1
EXIT_PYTHON_VERSION = 10
EXIT_PERSISTENT_DIRS = 11
EXIT_RATES_MISSING = 12
EXIT_RATES_INVALID = 13
EXIT_HISTORY_WRITABLE = 14
EXIT_HISTORY_READABLE = 15
EXIT_LOG_WRITABLE = 16
EXIT_CREDENTIALS = 17
EXIT_TAXIMETER = 18
EXIT_TKINTER = 19

MINIMUM_PYTHON = (3, 10)
CREDENTIAL_KEYS = ("salt", "password_hash", "iterations")


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    exit_code: int
    detail: str


def check_python_version() -> CheckResult:
    actual = tuple(sys.version_info[:2])
    if actual < MINIMUM_PYTHON:
        return CheckResult(
            "python_version",
            False,
            EXIT_PYTHON_VERSION,
            "se requiere Python "
            f"{'.'.join(str(part) for part in MINIMUM_PYTHON)} y hay "
            f"{'.'.join(str(part) for part in actual)}",
        )
    return CheckResult(
        "python_version", True, EXIT_OK, f"Python {actual[0]}.{actual[1]}"
    )


def check_tkinter() -> CheckResult:
    try:
        import tkinter
    except ImportError as error:
        return CheckResult(
            "tkinter", False, EXIT_TKINTER, f"la GUI no puede arrancar: {error}"
        )
    return CheckResult("tkinter", True, EXIT_OK, f"tkinter {tkinter.TkVersion}")


def check_persistent_directories() -> CheckResult:
    try:
        paths.ensure_directories()
    except OSError as error:
        return CheckResult(
            "persistent_directories",
            False,
            EXIT_PERSISTENT_DIRS,
            f"no se pudieron preparar los directorios persistentes: {error}",
        )
    where = paths.persistent_home() or Path.cwd()
    return CheckResult(
        "persistent_directories", True, EXIT_OK, f"raiz persistente en {where}"
    )


def check_rates() -> CheckResult:
    path = paths.rates_path()
    if not path.is_file():
        return CheckResult(
            "rates", False, EXIT_RATES_MISSING, f"no existe el fichero de tarifas {path}"
        )
    try:
        rates = load_rates(path)
    except RatesConfigurationError as error:
        return CheckResult("rates", False, EXIT_RATES_INVALID, str(error))
    return CheckResult(
        "rates",
        True,
        EXIT_OK,
        f"parado {rates.stopped_rate_per_second} EUR/s, "
        f"movimiento {rates.moving_rate_per_second} EUR/s",
    )


def check_history_writable() -> CheckResult:
    try:
        with NamedTemporaryFile(
            "w", dir=paths.data_dir(), prefix=".healthcheck-", suffix=".csv",
            encoding="utf-8", delete=False,
        ) as handle:
            handle.write("date,duration_seconds,amount\n")
            temporary = Path(handle.name)
    except OSError as error:
        return CheckResult(
            "history_writable",
            False,
            EXIT_HISTORY_WRITABLE,
            f"el historial no se puede escribir: {error}",
        )
    temporary.unlink(missing_ok=True)
    return CheckResult(
        "history_writable", True, EXIT_OK, f"escribible en {paths.data_dir()}"
    )


def check_history_readable() -> CheckResult:
    history = TripHistory()
    if not history.path.exists():
        return CheckResult(
            "history_readable", True, EXIT_OK, "todavia no hay carreras guardadas"
        )
    try:
        entries = history.all()
    except Exception as error:
        return CheckResult(
            "history_readable",
            False,
            EXIT_HISTORY_READABLE,
            f"el historial no se puede leer: {error}",
        )
    return CheckResult(
        "history_readable", True, EXIT_OK, f"{len(entries)} carreras legibles"
    )


def check_log_writable() -> CheckResult:
    try:
        with NamedTemporaryFile(
            "w", dir=paths.logs_dir(), prefix=".healthcheck-", suffix=".log",
            encoding="utf-8", delete=False,
        ) as handle:
            handle.write("healthcheck\n")
            temporary = Path(handle.name)
    except OSError as error:
        return CheckResult(
            "log_writable",
            False,
            EXIT_LOG_WRITABLE,
            f"los logs no se pueden escribir: {error}",
        )
    temporary.unlink(missing_ok=True)
    return CheckResult(
        "log_writable", True, EXIT_OK, f"escribible en {paths.logs_dir()}"
    )


def check_credentials() -> CheckResult:
    path = paths.credentials_path()
    if not path.is_file():
        return CheckResult(
            "credentials",
            True,
            EXIT_OK,
            "sin contrasena todavia, se creara en el primer uso",
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return CheckResult(
            "credentials",
            False,
            EXIT_CREDENTIALS,
            f"el fichero de credenciales no se puede leer: {error}",
        )
    missing = [key for key in CREDENTIAL_KEYS if key not in payload]
    if missing:
        return CheckResult(
            "credentials",
            False,
            EXIT_CREDENTIALS,
            f"faltan claves en el fichero de credenciales: {', '.join(missing)}",
        )
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        return CheckResult(
            "credentials",
            False,
            EXIT_CREDENTIALS,
            f"el fichero de credenciales es accesible para otros usuarios ({mode:o})",
        )
    return CheckResult(
        "credentials", True, EXIT_OK, f"credenciales validas con permisos {mode:o}"
    )


def check_taximeter() -> CheckResult:
    try:
        rates = load_rates(paths.rates_path())
    except RatesConfigurationError as error:
        return CheckResult("taximeter", False, EXIT_TAXIMETER, str(error))
    now = [1000.0]
    try:
        taximeter = Taximeter(rates, clock=lambda: now[0])
        taximeter.start_trip()
        now[0] += 60
        taximeter.set_status(TaxiStatus.MOVING)
        now[0] += 60
        summary = taximeter.finish_trip()
    except Exception as error:
        return CheckResult(
            "taximeter", False, EXIT_TAXIMETER, f"la calculadora no responde: {error}"
        )
    expected = round(
        60 * rates.stopped_rate_per_second + 60 * rates.moving_rate_per_second, 2
    )
    if summary.duration_seconds != 120 or summary.amount != expected:
        return CheckResult(
            "taximeter",
            False,
            EXIT_TAXIMETER,
            f"resultado incoherente: 120.0 s por {expected:.2f} EUR "
            f"pero devolvio {summary.duration_seconds:.0f} s por "
            f"{summary.amount:.2f} EUR",
        )
    return CheckResult(
        "taximeter",
        True,
        EXIT_OK,
        f"carrera de prueba 120 s por {summary.amount:.2f} EUR",
    )


CHECKS = (
    check_python_version,
    check_tkinter,
    check_persistent_directories,
    check_rates,
    check_history_writable,
    check_history_readable,
    check_log_writable,
    check_credentials,
    check_taximeter,
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for check in CHECKS:
        try:
            results.append(check())
        except Exception as error:
            results.append(
                CheckResult(
                    check.__name__.removeprefix("check_"),
                    False,
                    EXIT_UNEXPECTED,
                    f"fallo inesperado: {error!r}",
                )
            )
    return results


def report(results: list[CheckResult], as_json: bool) -> int:
    failures = [result for result in results if not result.ok]
    if as_json:
        print(
            json.dumps(
                {
                    "status": "ok" if not failures else "error",
                    "checked_at": datetime.now(timezone.utc).isoformat(
                        timespec="seconds"
                    ),
                    "persistent_home": str(paths.persistent_home() or Path.cwd()),
                    "checks": [
                        {
                            "name": result.name,
                            "ok": result.ok,
                            "exit_code": result.exit_code,
                            "detail": result.detail,
                        }
                        for result in results
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for result in results:
            prefix = "OK   " if result.ok else "FALLO"
            print(f"[{prefix}] {result.name}: {result.detail}")
        if failures:
            print()
            print(f"Aplicacion NO operativa: {len(failures)} comprobacion(es) fallida(s).")
        else:
            print()
            print("Aplicacion operativa: todas las comprobaciones han pasado.")
    if not failures:
        return EXIT_OK
    return failures[0].exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m taximeter.healthcheck",
        description="Comprueba que la aplicacion esta operativa, sin abrir ventana.",
    )
    parser.add_argument(
        "--json", action="store_true", help="devuelve el resultado en formato JSON"
    )
    args = parser.parse_args(argv)
    return report(run_checks(), args.json)


if __name__ == "__main__":
    raise SystemExit(main())
