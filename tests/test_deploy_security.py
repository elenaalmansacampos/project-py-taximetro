import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from taximeter.infrastructure.auth import PasswordAuth


class CredentialsPermissionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "credentials.json"
        self.auth = PasswordAuth(self.path)

    def test_new_credentials_are_only_readable_by_their_owner(self) -> None:
        self.auth.create_password("secreto123")

        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_permissions_are_tightened_even_if_the_file_existed_before(self) -> None:
        self.path.write_text("{}", encoding="utf-8")
        self.path.chmod(0o644)

        self.auth.create_password("secreto123")

        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_rewriting_credentials_keeps_them_private(self) -> None:
        self.auth.create_password("secreto123")
        self.path.chmod(0o644)

        self.auth.create_password("otro1234")

        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_no_temporary_file_is_left_behind(self) -> None:
        self.auth.create_password("secreto123")

        self.assertEqual(
            [path.name for path in self.path.parent.iterdir()], ["credentials.json"]
        )

    def test_the_password_still_round_trips(self) -> None:
        self.auth.create_password("secreto123")

        self.assertTrue(self.auth.verify("secreto123"))
        self.assertFalse(self.auth.verify("secreto124"))

    def test_no_plaintext_password_reaches_the_disk(self) -> None:
        self.auth.create_password("secreto123")

        self.assertNotIn("secreto123", self.path.read_text(encoding="utf-8"))

    def test_the_file_only_holds_the_expected_keys(self) -> None:
        self.auth.create_password("secreto123")

        payload = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(
            sorted(payload), ["iterations", "password_hash", "salt"]
        )
        self.assertGreaterEqual(payload["iterations"], 100_000)

    def test_permissions_hold_even_with_a_permissive_umask(self) -> None:
        previous = os.umask(0o000)
        self.addCleanup(os.umask, previous)

        self.auth.create_password("secreto123")

        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
