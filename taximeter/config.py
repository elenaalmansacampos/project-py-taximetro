from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONFIG_PATH = Path("config/tarifas.json")


@dataclass(frozen=True)
class Rates:
    stopped_rate_per_second: float
    moving_rate_per_second: float


def load_rates(path: Path = DEFAULT_CONFIG_PATH) -> Rates:
    if not path.exists():
        raise FileNotFoundError(f"No existe el fichero de tarifas: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    try:
        stopped = float(data["stopped_rate_per_second"])
        moving = float(data["moving_rate_per_second"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("El fichero de tarifas no tiene un formato valido") from error

    if stopped < 0 or moving < 0:
        raise ValueError("Las tarifas no pueden ser negativas")

    return Rates(stopped_rate_per_second=stopped, moving_rate_per_second=moving)

