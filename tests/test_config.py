import json
import tempfile
import unittest
from pathlib import Path

from taximeter.config import Rates, RatesConfigurationError, load_rates
from taximeter.taximeter import TaxiStatus, Taximeter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class RatesConfigurationTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "tarifas.json"

    def test_loads_alternative_rates(self) -> None:
        self._write({"stopped_rate_per_second": 0.10, "moving_rate_per_second": 0.20})

        self.assertEqual(
            load_rates(self.path),
            Rates(stopped_rate_per_second=0.10, moving_rate_per_second=0.20),
        )

    def test_changes_are_loaded_on_the_next_execution(self) -> None:
        self._write({"stopped_rate_per_second": 0.10, "moving_rate_per_second": 0.20})
        first_rates = load_rates(self.path)

        self._write({"stopped_rate_per_second": 0.30, "moving_rate_per_second": 0.40})
        second_rates = load_rates(self.path)

        self.assertEqual(first_rates.stopped_rate_per_second, 0.10)
        self.assertEqual(second_rates.stopped_rate_per_second, 0.30)
        self.assertEqual(second_rates.moving_rate_per_second, 0.40)

    def test_alternative_rates_drive_taximeter_calculation(self) -> None:
        self._write({"stopped_rate_per_second": 0.10, "moving_rate_per_second": 0.20})
        rates = load_rates(self.path)
        clock = FakeClock()
        taximeter = Taximeter(rates, clock=clock)

        taximeter.start_trip()
        clock.advance(10)
        taximeter.set_status(TaxiStatus.MOVING)
        clock.advance(20)
        summary = taximeter.finish_trip()

        self.assertEqual(summary.amount, 5.00)

    def test_zero_rates_are_valid(self) -> None:
        self._write({"stopped_rate_per_second": 0, "moving_rate_per_second": 0})

        rates = load_rates(self.path)

        self.assertEqual(rates.stopped_rate_per_second, 0.0)
        self.assertEqual(rates.moving_rate_per_second, 0.0)

    def test_missing_file_is_rejected(self) -> None:
        with self.assertRaises(RatesConfigurationError) as context:
            load_rates(self.path)

        self.assertIn("No existe el fichero de tarifas", str(context.exception))
        self.assertIn(str(self.path), str(context.exception))

    def test_missing_keys_are_rejected(self) -> None:
        for key in ("stopped_rate_per_second", "moving_rate_per_second"):
            with self.subTest(key=key):
                payload = {
                    "stopped_rate_per_second": 0.02,
                    "moving_rate_per_second": 0.05,
                }
                del payload[key]
                self._write(payload)

                with self.assertRaises(RatesConfigurationError) as context:
                    load_rates(self.path)

                self.assertIn(f"Falta la clave '{key}'", str(context.exception))

    def test_non_numeric_values_are_rejected(self) -> None:
        for value in ("0.05", True, None, [0.05]):
            with self.subTest(value=value):
                self._write(
                    {"stopped_rate_per_second": value, "moving_rate_per_second": 0.05}
                )

                with self.assertRaises(RatesConfigurationError) as context:
                    load_rates(self.path)

                self.assertIn("debe ser un numero", str(context.exception))

    def test_negative_rates_are_rejected(self) -> None:
        for key in ("stopped_rate_per_second", "moving_rate_per_second"):
            with self.subTest(key=key):
                payload = {
                    "stopped_rate_per_second": 0.02,
                    "moving_rate_per_second": 0.05,
                }
                payload[key] = -0.01
                self._write(payload)

                with self.assertRaises(RatesConfigurationError) as context:
                    load_rates(self.path)

                self.assertIn(f"La tarifa '{key}' no puede ser negativa", str(context.exception))

    def test_malformed_json_is_rejected(self) -> None:
        self.path.write_text("{", encoding="utf-8")

        with self.assertRaises(RatesConfigurationError) as context:
            load_rates(self.path)

        self.assertIn("no contiene JSON valido", str(context.exception))

    def test_non_object_json_is_rejected(self) -> None:
        self._write([0.02, 0.05])

        with self.assertRaises(RatesConfigurationError) as context:
            load_rates(self.path)

        self.assertIn("debe contener un objeto JSON", str(context.exception))

    def test_non_finite_rates_are_rejected(self) -> None:
        self.path.write_text(
            '{"stopped_rate_per_second": NaN, "moving_rate_per_second": 0.05}',
            encoding="utf-8",
        )

        with self.assertRaises(RatesConfigurationError) as context:
            load_rates(self.path)

        self.assertIn("debe ser un numero finito", str(context.exception))

    def _write(self, payload: object) -> None:
        self.path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
