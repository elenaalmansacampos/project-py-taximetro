import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from taximeter.domain.taximeter import TripSummary
from taximeter.infrastructure.config import RatesConfigurationError
from taximeter.infrastructure.database import TripHistory
from taximeter.interfaces import healthcheck


RATES = {"stopped_rate_per_second": 0.02, "moving_rate_per_second": 0.05}


class HealthCheckTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.write_rates(self.home / "config" / "tarifas.json")
        self.environment = patch.dict(os.environ, {"TAXIMETER_HOME": str(self.home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def write_rates(self, path: Path, payload: dict | None = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(RATES if payload is None else payload), encoding="utf-8")

    def run_check(self) -> tuple[int, str]:
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = healthcheck.main([])
        return code, output.getvalue()

    def failing(self, code: int) -> list:
        return [result for result in healthcheck.run_checks() if result.exit_code == code]


class HealthyDeploymentTest(HealthCheckTestCase):
    def test_a_prepared_deployment_passes_every_check(self) -> None:
        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_OK)
        self.assertIn("Aplicacion operativa", output)

    def test_no_check_leaves_temporary_files_behind(self) -> None:
        self.run_check()

        leftovers = [
            path.name
            for directory in ("data", "logs")
            for path in (self.home / directory).iterdir()
        ]
        self.assertEqual(leftovers, [])

    def test_json_output_is_machine_readable(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            code = healthcheck.main(["--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(code, healthcheck.EXIT_OK)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(str(self.home), payload["persistent_home"])
        self.assertTrue(all(check["ok"] for check in payload["checks"]))


class PersistentDataTest(HealthCheckTestCase):
    def write_history(self, entries: int) -> Path:
        path = self.home / "data" / "taximetro.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        history = TripHistory(path)
        for index in range(entries):
            history.add(
                TripSummary(duration_seconds=30.0 + index, amount=1.20 + index)
            )
        return path

    def test_the_history_is_read_from_the_persistent_root(self) -> None:
        self.write_history(1)

        results = {result.name: result for result in healthcheck.run_checks()}

        self.assertIn("1 carreras legibles", results["history_readable"].detail)

    def test_an_unreadable_history_fails_with_its_own_code(self) -> None:
        self.write_history(1)
        # SQLite no admite esto: el fichero existe pero no se puede abrir.
        (self.home / "data" / "taximetro.db").write_bytes(b"esto no es una base de datos")

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_HISTORY_READABLE)
        self.assertIn("history_readable", output)

    def test_an_unwritable_data_root_fails_with_its_own_code(self) -> None:
        (self.home / "data").mkdir()
        (self.home / "data").chmod(0o500)

        self.addCleanup((self.home / "data").chmod, 0o700)
        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_HISTORY_WRITABLE)
        self.assertIn("history_writable", output)

    def test_an_unwritable_log_root_fails_with_its_own_code(self) -> None:
        (self.home / "logs").mkdir()
        (self.home / "logs").chmod(0o500)

        self.addCleanup((self.home / "logs").chmod, 0o700)
        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_LOG_WRITABLE)
        self.assertIn("log_writable", output)


class ConfigurationTest(HealthCheckTestCase):
    def test_missing_rates_fail_with_its_own_code(self) -> None:
        (self.home / "config" / "tarifas.json").unlink()

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_RATES_MISSING)
        self.assertIn("rates", output)

    def test_invalid_rates_fail_with_its_own_code(self) -> None:
        self.write_rates(self.home / "config" / "tarifas.json", {"stopped_rate_per_second": "gratis"})

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_RATES_INVALID)
        self.assertIn("rates", output)

    def test_a_broken_calculator_fails_with_its_own_code(self) -> None:
        with patch.object(healthcheck, "Taximeter", side_effect=RuntimeError("roto")):
            code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_TAXIMETER)
        self.assertIn("taximeter", output)

    def test_a_wrong_calculation_fails_with_its_own_code(self) -> None:
        from taximeter.domain.taximeter import TripSummary

        broken = lambda rates, clock=None: type(
            "Roto",
            (),
            {
                "start_trip": lambda self: None,
                "set_status": lambda self, status: None,
                "finish_trip": lambda self: TripSummary(120.0, 99.99),
            },
        )()

        with patch.object(healthcheck, "Taximeter", side_effect=broken):
            code, _ = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_TAXIMETER)

    def test_a_missing_tkinter_fails_with_its_own_code(self) -> None:
        with patch.dict("sys.modules", {"tkinter": None}):
            code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_TKINTER)
        self.assertIn("tkinter", output)


class CredentialsTest(HealthCheckTestCase):
    def write_credentials(self, payload: dict, mode: int = 0o600) -> Path:
        path = self.home / "data" / "credentials.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        path.chmod(mode)
        return path

    def test_no_credentials_yet_is_not_a_failure(self) -> None:
        results = {result.name: result for result in healthcheck.run_checks()}

        self.assertTrue(results["credentials"].ok)
        self.assertIn("primer uso", results["credentials"].detail)

    def test_valid_credentials_pass(self) -> None:
        self.write_credentials({"salt": "c2FsdA==", "password_hash": "aGFzaA==", "iterations": 600000})

        results = {result.name: result for result in healthcheck.run_checks()}

        self.assertTrue(results["credentials"].ok)
        self.assertIn("600", results["credentials"].detail)

    def test_world_readable_credentials_fail(self) -> None:
        self.write_credentials(
            {"salt": "c2FsdA==", "password_hash": "aGFzaA==", "iterations": 600000},
            mode=0o644,
        )

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_CREDENTIALS)
        self.assertIn("otros usuarios", output)

    def test_incomplete_credentials_fail(self) -> None:
        self.write_credentials({"salt": "c2FsdA=="})

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_CREDENTIALS)
        self.assertIn("password_hash", output)

    def test_corrupted_credentials_fail(self) -> None:
        (self.home / "data").mkdir(parents=True, exist_ok=True)
        (self.home / "data" / "credentials.json").write_text("{ roto", encoding="utf-8")

        code, output = self.run_check()

        self.assertEqual(code, healthcheck.EXIT_CREDENTIALS)
        self.assertIn("credentials", output)

    def test_no_secret_is_ever_printed(self) -> None:
        secret = "clave-ultrasecreta"
        self.write_credentials(
            {"salt": "c2FsdA==", "password_hash": secret, "iterations": 600000}
        )

        _, output = self.run_check()

        self.assertNotIn(secret, output)


class UnpredictableCheckTest(HealthCheckTestCase):
    def test_an_unexpected_crash_becomes_a_named_failure(self) -> None:
        def check_explosive() -> None:
            raise RuntimeError("boom")

        with patch.object(healthcheck, "CHECKS", (check_explosive,)):
            results = healthcheck.run_checks()

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].ok)
        self.assertEqual(results[0].name, "explosive")
        self.assertEqual(results[0].exit_code, healthcheck.EXIT_UNEXPECTED)
        self.assertIn("boom", results[0].detail)


class RatesIntegrationTest(HealthCheckTestCase):
    def test_rates_configuration_errors_are_reported_as_text(self) -> None:
        with patch.object(
            healthcheck, "load_rates", side_effect=RatesConfigurationError("sin tarifas")
        ):
            result = healthcheck.check_rates()

        self.assertFalse(result.ok)
        self.assertIn("sin tarifas", result.detail)


if __name__ == "__main__":
    unittest.main()
