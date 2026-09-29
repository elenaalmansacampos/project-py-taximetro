import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taximeter.infrastructure.auth import (
    CREDENTIALS_FILE_MODE,
    MINIMUM_PASSWORD_LENGTH,
    PBKDF2_ITERATIONS,
    CorruptCredentialsError,
    PasswordAuth,
    ensure_cli_password,
)


class PasswordAuthTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "credentials.json"
        self.auth = PasswordAuth(self.path)


class PasswordStorageTest(PasswordAuthTestCase):
    def test_stores_only_salt_hash_and_iterations(self) -> None:
        self.auth.create_password("secreto123")

        content = self.path.read_text(encoding="utf-8")
        payload = json.loads(content)

        self.assertNotIn("secreto123", content)
        self.assertEqual(
            set(payload), {"salt", "password_hash", "iterations"}
        )
        self.assertEqual(payload["iterations"], PBKDF2_ITERATIONS)
        self.assertNotEqual(payload["salt"], payload["password_hash"])

    def test_credentials_file_is_not_readable_by_other_users(self) -> None:
        self.auth.create_password("secreto123")

        mode = stat.S_IMODE(self.path.stat().st_mode)

        self.assertEqual(mode, CREDENTIALS_FILE_MODE)
        self.assertEqual(mode & (stat.S_IRWXG | stat.S_IRWXO), 0)

    def test_tightens_permissions_of_a_previously_wide_file(self) -> None:
        self.auth.create_password("secreto123")
        os.chmod(self.path, 0o644)

        self.auth.create_password("otro1234")

        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_creates_missing_parent_directories(self) -> None:
        auth = PasswordAuth(self.path.parent / "anidado" / "credentials.json")

        auth.create_password("secreto123")

        self.assertTrue(auth.path.exists())

    def test_rejects_short_password_without_writing_credentials(self) -> None:
        too_short = "a" * (MINIMUM_PASSWORD_LENGTH - 1)

        with self.assertRaises(ValueError):
            self.auth.create_password(too_short)

        self.assertFalse(self.path.exists())


class PasswordVerificationTest(PasswordAuthTestCase):
    def test_accepts_the_original_password(self) -> None:
        self.auth.create_password("secreto123")

        self.assertTrue(self.auth.verify("secreto123"))

    def test_rejects_a_different_password(self) -> None:
        self.auth.create_password("secreto123")

        for candidate in ("secreto124", "secreto12", "otro1234", ""):
            with self.subTest(candidate=candidate):
                self.assertFalse(self.auth.verify(candidate))

    def test_same_password_produces_different_hashes(self) -> None:
        other = PasswordAuth(self.path.with_name("otra.json"))
        self.auth.create_password("secreto123")
        other.create_password("secreto123")

        self.assertNotEqual(self.auth.load()["salt"], other.load()["salt"])
        self.assertNotEqual(
            self.auth.load()["password_hash"], other.load()["password_hash"]
        )


class CorruptCredentialsTest(PasswordAuthTestCase):
    def _write(self, content: str) -> None:
        self.path.write_text(content, encoding="utf-8")

    def test_load_returns_none_when_file_is_missing(self) -> None:
        self.assertIsNone(self.auth.load())

    def test_load_returns_none_for_unreadable_payloads(self) -> None:
        cases = {
            "json invalido": "{no es json",
            "lista en vez de objeto": "[]",
            "sin salt": json.dumps({"password_hash": "eA==", "iterations": 1}),
            "sin hash": json.dumps({"salt": "eA==", "iterations": 1}),
            "iterations como texto": json.dumps(
                {"salt": "eA==", "password_hash": "eA==", "iterations": "600000"}
            ),
            "iterations en cero": json.dumps(
                {"salt": "eA==", "password_hash": "eA==", "iterations": 0}
            ),
        }

        for name, content in cases.items():
            with self.subTest(caso=name):
                self._write(content)
                self.assertIsNone(self.auth.load())

    def test_verify_reports_corruption_instead_of_failing_silently(self) -> None:
        self._write("{no es json")

        with self.assertRaises(CorruptCredentialsError):
            self.auth.verify("secreto123")

    def test_verify_reports_corruption_for_invalid_base64(self) -> None:
        self._write(
            json.dumps({"salt": "!!!", "password_hash": "!!!", "iterations": 600_000})
        )

        with self.assertRaises(CorruptCredentialsError):
            self.auth.verify("secreto123")

    def test_verify_reports_corruption_when_file_disappears(self) -> None:
        self.auth.create_password("secreto123")
        self.path.unlink()

        with self.assertRaises(CorruptCredentialsError):
            self.auth.verify("secreto123")


class EnsureCliPasswordTest(PasswordAuthTestCase):
    def _run(self, answers: list[str]):
        output = []
        with patch("getpass.getpass", side_effect=answers) as getpass_mock:
            with patch("builtins.print", side_effect=output.append):
                ensure_cli_password(self.auth)
        return getpass_mock, output

    def test_retries_instead_of_crashing_when_password_is_too_short(self) -> None:
        getpass_mock, output = self._run(["abc", "abc", "secreto123", "secreto123"])

        self.assertEqual(getpass_mock.call_count, 4)
        self.assertTrue(self.auth.verify("secreto123"))
        self.assertIn(
            f"La contraseña debe tener al menos {MINIMUM_PASSWORD_LENGTH} caracteres",
            "\n".join(output),
        )
        self.assertIn("Contraseña creada.", output)

    def test_retries_when_passwords_do_not_match(self) -> None:
        _, output = self._run(["secreto123", "otra1234", "secreto123", "secreto123"])

        self.assertTrue(self.auth.verify("secreto123"))
        self.assertIn("Las contraseñas no coinciden.", output)

    def test_does_not_prompt_when_credentials_already_exist(self) -> None:
        self.auth.create_password("secreto123")

        getpass_mock, output = self._run([])

        getpass_mock.assert_not_called()
        self.assertEqual(output, [])


if __name__ == "__main__":
    unittest.main()
