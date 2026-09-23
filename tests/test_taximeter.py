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

    def test_cannot_finish_without_active_trip(self) -> None:
        with self.assertRaises(RuntimeError):
            self.taximeter.finish_trip()


if __name__ == "__main__":
    unittest.main()

