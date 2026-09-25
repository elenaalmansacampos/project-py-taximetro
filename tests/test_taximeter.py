import unittest

from taximeter.config import Rates
from taximeter.taximeter import TaxiStatus, Taximeter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TaximeterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = FakeClock()
        self.taximeter = Taximeter(
            Rates(stopped_rate_per_second=0.02, moving_rate_per_second=0.05),
            clock=self.clock,
        )

    def test_starts_trip_in_stopped_state_with_zero_amount(self) -> None:
        self.taximeter.start_trip()

        self.assertTrue(self.taximeter.active)
        self.assertEqual(self.taximeter.status, TaxiStatus.STOPPED)
        self.assertEqual(self.taximeter.current_amount(), 0.0)

    def test_cannot_start_a_second_trip(self) -> None:
        self.taximeter.start_trip()

        with self.assertRaisesRegex(RuntimeError, "Ya hay una carrera activa"):
            self.taximeter.start_trip()

    def test_can_start_a_new_trip_after_finishing(self) -> None:
        self.taximeter.start_trip()
        self.taximeter.finish_trip()
        self.taximeter.start_trip()

        self.assertTrue(self.taximeter.active)
        self.assertEqual(self.taximeter.status, TaxiStatus.STOPPED)
        self.assertEqual(self.taximeter.current_amount(), 0.0)

    def test_chains_multiple_trips_with_independent_summaries(self) -> None:
        self.taximeter.start_trip()
        self.clock.advance(10)
        self.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(20)
        first_summary = self.taximeter.finish_trip()

        self.clock.advance(10)
        self.taximeter.start_trip()

        self.assertTrue(self.taximeter.active)
        self.assertEqual(self.taximeter.status, TaxiStatus.STOPPED)
        self.assertEqual(self.taximeter.current_amount(), 0.0)
        self.assertEqual(first_summary.duration_seconds, 30)
        self.assertEqual(first_summary.amount, 1.20)

        self.clock.advance(5)
        self.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(20)
        second_summary = self.taximeter.finish_trip()

        self.assertEqual(first_summary.duration_seconds, 30)
        self.assertEqual(first_summary.amount, 1.20)
        self.assertEqual(second_summary.duration_seconds, 25)
        self.assertEqual(second_summary.amount, 1.10)

    def test_charges_stopped_time(self) -> None:
        self.taximeter.start_trip()
        self.clock.advance(10)

        self.assertEqual(self.taximeter.current_amount(), 0.20)

    def test_charges_moving_time(self) -> None:
        self.taximeter.start_trip()
        self.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(10)

        self.assertEqual(self.taximeter.current_amount(), 0.50)

    def test_charges_mixed_trip(self) -> None:
        self.taximeter.start_trip()
        self.clock.advance(10)
        self.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(20)
        summary = self.taximeter.finish_trip()

        self.assertEqual(summary.amount, 1.20)
        self.assertEqual(summary.duration_seconds, 30)

    def test_charges_after_switching_back_to_stopped(self) -> None:
        self.taximeter.start_trip()
        self.clock.advance(10)
        self.taximeter.set_status(TaxiStatus.MOVING)
        self.clock.advance(20)
        self.taximeter.set_status(TaxiStatus.STOPPED)
        self.clock.advance(10)
        summary = self.taximeter.finish_trip()

        self.assertEqual(summary.amount, 1.40)
        self.assertEqual(summary.duration_seconds, 40)

    def test_cannot_change_status_without_active_trip(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No hay ninguna carrera activa"):
            self.taximeter.set_status(TaxiStatus.MOVING)

        self.assertFalse(self.taximeter.active)
        self.assertEqual(self.taximeter.status, TaxiStatus.STOPPED)

    def test_cannot_finish_without_active_trip(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "No hay ninguna carrera activa"):
            self.taximeter.finish_trip()

    def test_does_not_charge_time_after_finishing(self) -> None:
        self.taximeter.start_trip()
        self.clock.advance(10)
        summary = self.taximeter.finish_trip()
        self.clock.advance(20)

        self.assertEqual(summary.duration_seconds, 10)
        self.assertEqual(summary.amount, 0.20)
        self.assertFalse(self.taximeter.active)
        with self.assertRaisesRegex(RuntimeError, "No hay ninguna carrera activa"):
            self.taximeter.current_amount()
        with self.assertRaisesRegex(RuntimeError, "No hay ninguna carrera activa"):
            self.taximeter.finish_trip()


if __name__ == "__main__":
    unittest.main()

