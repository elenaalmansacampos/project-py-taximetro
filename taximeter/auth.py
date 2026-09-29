from __future__ import annotations

import base64
import binascii
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from taximeter import paths


CREDENTIALS_PATH = paths.credentials_path()
MINIMUM_PASSWORD_LENGTH = 4
PBKDF2_ITERATIONS = 600_000
CREDENTIALS_FILE_MODE = 0o600


class CorruptCredentialsError(RuntimeError):
    """El archivo de credenciales existe pero no se puede utilizar."""


class PasswordAuth:
    def __init__(self, path: Path | None = None) -> None:
        self.path = paths.credentials_path() if path is None else Path(path)

    def credentials_exist(self) -> bool:
        return self.path.exists()

    def create_password(self, password: str) -> None:
        if len(password) < MINIMUM_PASSWORD_LENGTH:
            raise ValueError(
                f"La contraseña debe tener al menos {MINIMUM_PASSWORD_LENGTH} caracteres"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        password_hash = _hash_password(password, salt)
        self._write_payload(
            {
                "salt": base64.b64encode(salt).decode("ascii"),
                "password_hash": base64.b64encode(password_hash).decode("ascii"),
                "iterations": PBKDF2_ITERATIONS,
            }
        )

    def load(self) -> dict[str, Any] | None:
        """Devuelve el contenido almacenado, o None si falta o es ilegible."""
        if not self.path.exists():
            return None

        try:
            with self.path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None

        return payload if _is_valid_payload(payload) else None

    def verify(self, password: str) -> bool:
        salt, expected_hash, iterations = self._read_credentials()
        actual_hash = _hash_password(password, salt, iterations)
        return hmac.compare_digest(actual_hash, expected_hash)

    def _read_credentials(self) -> tuple[bytes, bytes, int]:
        message = f"El archivo de credenciales {self.path} esta dañado o no se puede leer"
        payload = self.load()
        if payload is None:
            raise CorruptCredentialsError(message)

        try:
            salt = base64.b64decode(payload["salt"], validate=True)
            expected_hash = base64.b64decode(payload["password_hash"], validate=True)
            iterations = int(payload["iterations"])
        except (binascii.Error, TypeError, ValueError) as error:
            raise CorruptCredentialsError(message) from error

        if not salt or not expected_hash or iterations < 1:
            raise CorruptCredentialsError(message)

        return salt, expected_hash, iterations

    def _write_payload(self, payload: dict[str, Any]) -> None:
        descriptor = os.open(
            self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, CREDENTIALS_FILE_MODE
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
        os.chmod(self.path, CREDENTIALS_FILE_MODE)


def ensure_cli_password(auth: PasswordAuth) -> None:
    if auth.credentials_exist():
        return

    print("Primera ejecucion: crea una contraseña para proteger el taximetro.")
    while True:
        password = getpass.getpass("Nueva contraseña: ")
        repeated = getpass.getpass("Repite la contraseña: ")
        if password != repeated:
            print("Las contraseñas no coinciden.")
            continue
        try:
            auth.create_password(password)
        except ValueError as error:
            print(str(error))
            continue
        print("Contraseña creada.")
        return


def _is_valid_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("salt"), str):
        return False
    if not isinstance(payload.get("password_hash"), str):
        return False
    iterations = payload.get("iterations")
    if isinstance(iterations, bool) or not isinstance(iterations, int):
        return False
    return iterations > 0


def _hash_password(
    password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS
) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
