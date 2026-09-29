from __future__ import annotations

import os
from pathlib import Path


ENV_HOME = "TAXIMETER_HOME"
DATA_DIRNAME = "data"
LOGS_DIRNAME = "logs"
CONFIG_DIRNAME = "config"
RATES_FILENAME = "tarifas.json"
HISTORY_FILENAME = "historial_carreras.csv"
CREDENTIALS_FILENAME = "credentials.json"
LOG_FILENAME = "taximetro.log"


def persistent_home() -> Path | None:
    raw = os.environ.get(ENV_HOME, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def is_persistent() -> bool:
    return persistent_home() is not None


def data_dir() -> Path:
    home = persistent_home()
    return home / DATA_DIRNAME if home is not None else Path(DATA_DIRNAME)


def logs_dir() -> Path:
    home = persistent_home()
    return home / LOGS_DIRNAME if home is not None else Path(LOGS_DIRNAME)


def config_dir() -> Path:
    home = persistent_home()
    return home / CONFIG_DIRNAME if home is not None else Path(CONFIG_DIRNAME)


def history_path() -> Path:
    return data_dir() / HISTORY_FILENAME


def credentials_path() -> Path:
    return data_dir() / CREDENTIALS_FILENAME


def log_path() -> Path:
    return logs_dir() / LOG_FILENAME


def rates_path() -> Path:
    return config_dir() / RATES_FILENAME


def ensure_directories() -> None:
    for directory in (data_dir(), logs_dir(), config_dir()):
        directory.mkdir(parents=True, exist_ok=True)
