from __future__ import annotations

import logging
from pathlib import Path


LOG_PATH = Path("logs/taximetro.log")


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

