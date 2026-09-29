from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from taximeter.application.ports import HistoryEntry
from taximeter.infrastructure.csv_history import CSV_HISTORY_PATH
from taximeter.infrastructure.database import (
    DEFAULT_DATABASE_PATH,
    TripHistory,
    record_key_for,
)


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class RejectedRecord:
    line: int
    reason: str


@dataclass(frozen=True)
class MigrationReport:
    source: Path
    database: Path
    total_rows: int
    valid_rows: int
    imported: int
    duplicates: int
    rejected: tuple[RejectedRecord, ...]
    missing: int
    verified: bool
    source_preserved: bool

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)

    @property
    def ok(self) -> bool:
        return self.verified and self.rejected_count == 0

    def render(self) -> str:
        lines = [
            "Migracion del historial",
            f"Origen: {self.source}",
            f"Base de datos: {self.database}",
            f"Filas leidas: {self.total_rows}",
            f"Filas validas: {self.valid_rows}",
            f"Importadas: {self.imported}",
            f"Ya existentes: {self.duplicates}",
            f"Rechazadas: {self.rejected_count}",
        ]
        if self.rejected:
            lines.append("Detalle de rechazos:")
            lines.extend(
                f"  linea {record.line}: {record.reason}"
                for record in self.rejected
            )
        lines.append(f"Verificacion: {'correcta' if self.verified else 'fallida'}")
        if self.missing:
            lines.append(f"Registros validos pendientes: {self.missing}")
        lines.append(
            f"CSV original conservado: {'si' if self.source_preserved else 'no'}"
        )
        return "\n".join(lines)


def migrate_csv_to_database(
    source: Path = CSV_HISTORY_PATH,
    database: Path = DEFAULT_DATABASE_PATH,
) -> MigrationReport:
    source_path = Path(source)
    database_path = Path(database)
    if not source_path.is_file():
        raise MigrationError(f"No existe el CSV de origen: {source_path}")

    try:
        valid_records, rejected, total_rows = _read_records(source_path)
    except (OSError, UnicodeError, csv.Error) as error:
        raise MigrationError(
            f"No se pudo leer el CSV de origen {source_path}: {error}"
        ) from error

    history = TripHistory(database_path)
    imported = 0
    duplicates = 0
    for record in valid_records:
        if history.add_migrated(record):
            imported += 1
        else:
            duplicates += 1

    expected_keys = {
        record_key_for(record.date, record.duration_seconds, record.amount)
        for record in valid_records
    }
    stored_keys = {
        record_key_for(record.date, record.duration_seconds, record.amount)
        for record in history.migrated_entries()
    }
    missing = len(expected_keys - stored_keys)
    source_preserved = source_path.is_file()

    return MigrationReport(
        source=source_path,
        database=database_path,
        total_rows=total_rows,
        valid_rows=len(valid_records),
        imported=imported,
        duplicates=duplicates,
        rejected=tuple(rejected),
        missing=missing,
        verified=missing == 0 and source_preserved,
        source_preserved=source_preserved,
    )


def format_migration_report(report: MigrationReport) -> str:
    return report.render()


def _read_records(
    source: Path,
) -> tuple[list[HistoryEntry], list[RejectedRecord], int]:
    valid_records: list[HistoryEntry] = []
    rejected: list[RejectedRecord] = []
    total_rows = 0

    with source.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != ["date", "duration_seconds", "amount"]:
            raise MigrationError(
                "La cabecera del CSV debe ser: date,duration_seconds,amount"
            )

        for line_number, row in enumerate(reader, start=2):
            total_rows += 1
            record, reason = _parse_row(row)
            if record is None:
                rejected.append(RejectedRecord(line=line_number, reason=reason))
            else:
                valid_records.append(record)

    return valid_records, rejected, total_rows


def _parse_row(row: dict[str, str] | None) -> tuple[HistoryEntry | None, str]:
    if row is None:
        return None, "fila vacia"
    if None in row:
        return None, "la fila contiene columnas adicionales"

    date_local = (row.get("date") or "").strip()
    if not date_local:
        return None, "la fecha esta vacia"
    try:
        datetime.fromisoformat(date_local)
    except ValueError:
        return None, f"fecha no valida: {date_local}"

    duration_seconds = _parse_number(
        row.get("duration_seconds"), "duracion", date_local
    )
    if isinstance(duration_seconds, str):
        return None, duration_seconds
    amount = _parse_number(row.get("amount"), "importe", date_local)
    if isinstance(amount, str):
        return None, amount

    return HistoryEntry(
        date=date_local,
        duration_seconds=duration_seconds,
        amount=amount,
    ), ""


def _parse_number(value: str | None, field: str, date_local: str) -> float | str:
    if value is None or not value.strip():
        return f"{field} vacio en la carrera {date_local}"
    try:
        number = float(value)
    except ValueError:
        return f"{field} no numerico en la carrera {date_local}: {value}"
    if not math.isfinite(number):
        return f"{field} no finito en la carrera {date_local}: {value}"
    if number < 0:
        return f"{field} negativo en la carrera {date_local}: {value}"
    return number
