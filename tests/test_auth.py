import base64
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from taximeter.auth import (
    MIN_PASSWORD_LENGTH,
    PBKDF2_ITERATIONS,
    PasswordAuth,
    ensure_cli_password,
)


class PasswordAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "data" / "credentials.json"
        self.auth = PasswordAuth(self.path)

    def test_rejects_short_password_without_creating_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "al menos 4 caracteres"):
            self.auth.create_password("abc")

        self.assertFalse(self.path.exists())

    def test_uses_pbkdf2_sha256_with_configured_iterations(self) -> None:
        salt = b"0123456789abcdef"
        password = "secreta"
        with patch("taximeter.auth.os.urandom", return_value=salt):
            self.auth.create_password(password)

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        expected_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
        )

        self.assertEqual(payload["iterations"], PBKDF2_ITERATIONS)
        self.assertEqual(base64.b64decode(payload["salt"]), salt)
        self.assertEqual(base64.b64decode(payload["password_hash"]), expected_hash)
        self.assertNotIn(password, self.path.read_text(encoding="utf-8"))

    def test_correct_password_is_accepted_and_incorrect_password_is_rejected(self) -> None:
        self.auth.create_password("secreta")

        self.assertTrue(self.auth.verify("secreta"))
        self.assertFalse(self.auth.verify("incorrecta"))

    def test_salt_is_random_for_each_credential(self) -> None:
        salts = [b"salt-one!", b"salt-two!"]

        for index, salt in enumerate(salts):
            path = self.path.with_name(f"credentials-{index}.json")
            with patch("taximeter.auth.os.urandom", return_value=salt):
                PasswordAuth(path).create_password("secreta")
            self.assertEqual(base64.b64decode(json.loads(path.read_text())["salt"]), salt)

    def test_cli_setup_retries_short_password_and_creates_it_after_confirmation(self) -> None:
        with (
            patch(
                "taximeter.auth.getpass.getpass",
                side_effect=["abc", "abc", "abcd", "abcd"],
            ) as prompt,
            redirect_stdout(io.StringIO()),
        ):
            ensure_cli_password(self.auth)

        self.assertTrue(self.auth.credentials_exist())
        self.assertTrue(self.auth.verify("abcd"))
        self.assertEqual(prompt.call_args_list[0].args, ("Nueva contraseña: ",))
        self.assertEqual(prompt.call_args_list[1].args, ("Repite la contraseña: ",))
        self.assertEqual(prompt.call_count, 4)

    def test_cli_setup_rejects_mismatched_confirmation(self) -> None:
        with (
            patch(
                "taximeter.auth.getpass.getpass",
                side_effect=["abcd", "otro", "abcd", "abcd"],
            ) as prompt,
            redirect_stdout(io.StringIO()),
        ):
            ensure_cli_password(self.auth)

        self.assertTrue(self.auth.credentials_exist())
        self.assertTrue(self.auth.verify("abcd"))
        self.assertEqual(prompt.call_count, 4)

    def test_minimum_password_length_is_four(self) -> None:
        self.assertEqual(MIN_PASSWORD_LENGTH, 4)


if __name__ == "__main__":
    unittest.main()
