import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from taximeter import paths


class PersistentHomeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)

    def test_without_the_variable_paths_stay_relative_to_the_working_directory(
        self,
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(paths.persistent_home())
            self.assertFalse(paths.is_persistent())
            self.assertEqual(paths.data_dir(), Path("data"))
            self.assertEqual(paths.logs_dir(), Path("logs"))
            self.assertEqual(paths.config_dir(), Path("config"))
            self.assertEqual(paths.history_path(), Path("data/historial_carreras.csv"))
            self.assertEqual(paths.log_path(), Path("logs/taximetro.log"))
            self.assertEqual(paths.rates_path(), Path("config/tarifas.json"))

    def test_the_variable_moves_every_persistent_path_under_the_same_root(self) -> None:
        with patch.dict(os.environ, {"TAXIMETER_HOME": str(self.home)}):
            self.assertTrue(paths.is_persistent())
            self.assertEqual(paths.persistent_home(), self.home)
            self.assertEqual(paths.data_dir(), self.home / "data")
            self.assertEqual(paths.logs_dir(), self.home / "logs")
            self.assertEqual(paths.config_dir(), self.home / "config")
            self.assertEqual(
                paths.history_path(), self.home / "data" / "historial_carreras.csv"
            )
            self.assertEqual(
                paths.credentials_path(), self.home / "data" / "credentials.json"
            )
            self.assertEqual(paths.log_path(), self.home / "logs" / "taximetro.log")
            self.assertEqual(paths.rates_path(), self.home / "config" / "tarifas.json")

    def test_a_blank_value_is_treated_as_unset(self) -> None:
        with patch.dict(os.environ, {"TAXIMETER_HOME": "   "}):
            self.assertIsNone(paths.persistent_home())
            self.assertEqual(paths.data_dir(), Path("data"))

    def test_ensure_directories_creates_the_three_directories(self) -> None:
        target = self.home / "fresh"
        with patch.dict(os.environ, {"TAXIMETER_HOME": str(target)}):
            paths.ensure_directories()

            self.assertTrue((target / "data").is_dir())
            self.assertTrue((target / "logs").is_dir())
            self.assertTrue((target / "config").is_dir())

    def test_ensure_directories_is_idempotent(self) -> None:
        target = self.home / "fresh"
        with patch.dict(os.environ, {"TAXIMETER_HOME": str(target)}):
            paths.ensure_directories()
            paths.ensure_directories()

        self.assertTrue((target / "data").is_dir())


if __name__ == "__main__":
    unittest.main()
