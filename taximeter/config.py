from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config/tarifas.json")
RATE_KEYS = ("stopped_rate_per_second", "moving_rate_per_second")


class RatesConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class Rates:
    stopped_rate_per_second: float
    moving_rate_per_second: float


def load_rates(path: Path = DEFAULT_CONFIG_PATH) -> Rates:
    config_path = Path(path)

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError as error:
        raise RatesConfigurationError(
            f"No existe el fichero de tarifas: {config_path}"
        ) from error
    except json.JSONDecodeError as error:
        raise RatesConfigurationError(
            f"El fichero de tarifas {config_path} no contiene JSON valido"
        ) from error
    except (OSError, UnicodeError) as error:
        raise RatesConfigurationError(
            f"No se pudo leer el fichero de tarifas {config_path}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise RatesConfigurationError(
            f"El fichero de tarifas {config_path} debe contener un objeto JSON"
        )

    values: dict[str, float] = {}
    for key in RATE_KEYS:
        if key not in data:
            raise RatesConfigurationError(
                f"Falta la clave '{key}' en el fichero de tarifas: {config_path}"
            )

        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RatesConfigurationError(
                f"La tarifa '{key}' debe ser un numero en {config_path}"
            )

        try:
            numeric_value = float(value)
        except (OverflowError, ValueError) as error:
            raise RatesConfigurationError(
                f"La tarifa '{key}' debe ser un numero valido en {config_path}"
            ) from error

        if not math.isfinite(numeric_value):
            raise RatesConfigurationError(
                f"La tarifa '{key}' debe ser un numero finito en {config_path}"
            )
        if numeric_value < 0:
            raise RatesConfigurationError(
                f"La tarifa '{key}' no puede ser negativa en {config_path}"
            )

        values[key] = numeric_value

    return Rates(
        stopped_rate_per_second=values["stopped_rate_per_second"],
        moving_rate_per_second=values["moving_rate_per_second"],
    )

