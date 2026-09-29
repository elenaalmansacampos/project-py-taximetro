from __future__ import annotations

import logging

from taximeter import paths


LOG_PATH = paths.log_path()


def configure_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

