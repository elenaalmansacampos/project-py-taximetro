from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
from pathlib import Path


CREDENTIALS_PATH = Path("data/credentials.json")
MIN_PASSWORD_LENGTH = 4
PBKDF2_ITERATIONS = 600_000


class PasswordAuth:
    def __init__(self, path: Path = CREDENTIALS_PATH) -> None:
        self.path = path

    def credentials_exist(self) -> bool:
        return self.path.exists()

    def create_password(self, password: str) -> None:
        if len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres"
            )

        self.path.parent.mkdir(parents=True, exist_ok=True)
        salt = os.urandom(16)
        password_hash = _hash_password(password, salt)
        payload = {
            "salt": base64.b64encode(salt).decode("ascii"),
            "password_hash": base64.b64encode(password_hash).decode("ascii"),
            "iterations": PBKDF2_ITERATIONS,
        }

        with self.path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)

    def verify(self, password: str) -> bool:
        with self.path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        salt = base64.b64decode(payload["salt"])
        expected_hash = base64.b64decode(payload["password_hash"])
        actual_hash = _hash_password(password, salt, int(payload["iterations"]))
        return hmac.compare_digest(actual_hash, expected_hash)


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
            print(error)
            continue
        print("Contraseña creada.")
        return


def _hash_password(
    password: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS
) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

