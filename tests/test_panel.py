import re
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from taximeter.interfaces import api
from taximeter.interfaces.web import panel
from taximeter.infrastructure.database import TripHistory
from taximeter.application.ports import HistoryEntry
from taximeter.domain.taximeter import TripSummary


def request(url: str, method: str = "GET"):
    http_request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(http_request, timeout=10) as response:
            return response.status, response.headers, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.headers, error.read().decode("utf-8")


class BrokenHistory:
    def all(self) -> list[HistoryEntry]:
        raise RuntimeError("sqlite:///home/conductor/secreto.db no se puede abrir")

    def add(self, summary: TripSummary) -> None:
        raise AssertionError("el panel no debe escribir")


def data_rows(markup: str) -> list[str]:
    body = re.search(r"<tbody>(.*?)</tbody>", markup, re.DOTALL)
    if body is None:
        return []
    return re.findall(r"<tr>.*?</tr>", body.group(1), re.DOTALL)


class PanelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "taximetro.db"
        self.history = TripHistory(self.database)

    def serve(self, history=None) -> str:
        repository = self.history if history is None else history
        server = api.create_server(repository, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def stop() -> None:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

        self.addCleanup(stop)
        return server.base_url


class PanelListingTest(PanelTestCase):
    def test_shows_date_duration_and_amount_in_readable_format(self) -> None:
        self.history.add_migrated(
            HistoryEntry(
                date="2026-09-25T13:17:38",
                duration_seconds=1303.91,
                amount=64.7512,
            )
        )
        self.history.add_migrated(
            HistoryEntry(
                date="2026-09-25T14:35:10", duration_seconds=47.58, amount=2.18
            )
        )
        base_url = self.serve()

        status, headers, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("<!DOCTYPE html>", markup)
        self.assertIn('lang="es"', markup)
        self.assertIn(panel.PANEL_HEADING, markup)
        self.assertIn('<th scope="col">Fecha</th>', markup)
        self.assertIn("25/09/2026 13:17", markup)
        self.assertIn("21 min 44 s", markup)
        self.assertIn("64.75 EUR", markup)
        self.assertIn("25/09/2026 14:35", markup)
        self.assertIn("48 s", markup)
        self.assertIn("2.18 EUR", markup)
        self.assertEqual(len(data_rows(markup)), 2)

    def test_does_not_expose_internal_columns(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        _, _, markup = request(f"{base_url}{api.PANEL_PATH}")

        for leaked in ("record_key", "imported_at", "source", "sqlite", "id="):
            self.assertNotIn(leaked, markup)

    def test_renders_without_javascript_or_external_resources(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        _, _, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertNotIn("<script", markup.lower())
        self.assertNotIn("http://", markup)
        self.assertNotIn("https://", markup)

    def test_panel_is_read_only(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        status, _, _ = request(f"{base_url}{api.PANEL_PATH}", method="POST")
        status_delete, _, _ = request(f"{base_url}{api.PANEL_PATH}", method="DELETE")

        self.assertEqual(status, 405)
        self.assertEqual(status_delete, 405)
        self.assertEqual(len(TripHistory(self.database).all()), 1)


class PanelEmptyStateTest(PanelTestCase):
    def test_shows_a_clear_empty_state_without_inventing_data(self) -> None:
        base_url = self.serve()

        status, _, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertEqual(status, 200)
        self.assertIn(panel.PANEL_HEADING, markup)
        self.assertIn(panel.EMPTY_MESSAGE, markup)
        self.assertNotIn("<table>", markup)
        self.assertEqual(data_rows(markup), [])
        self.assertNotIn("EUR", markup)

    def test_stops_showing_the_empty_state_after_a_trip_is_added(self) -> None:
        base_url = self.serve()
        _, _, before = request(f"{base_url}{api.PANEL_PATH}")
        self.assertIn(panel.EMPTY_MESSAGE, before)

        self.history.add(TripSummary(duration_seconds=42, amount=1.5))
        _, _, after = request(f"{base_url}{api.PANEL_PATH}")

        self.assertNotIn(panel.EMPTY_MESSAGE, after)
        self.assertIn("42 s", after)


class PanelLiveReloadTest(PanelTestCase):
    def test_reload_shows_a_new_trip_without_restarting_the_service(self) -> None:
        base_url = self.serve()
        _, _, before = request(f"{base_url}{api.PANEL_PATH}")
        self.assertEqual(len(data_rows(before)), 0)

        # Otra escritura del mismo repositorio, como la haria la CLI o la GUI.
        TripHistory(self.database).add(
            TripSummary(duration_seconds=75, amount=3.25)
        )

        status, _, after = request(f"{base_url}{api.PANEL_PATH}")

        self.assertEqual(status, 200)
        self.assertEqual(len(data_rows(after)), 1)
        self.assertIn("1 min 15 s", after)
        self.assertIn("3.25 EUR", after)

    def test_panel_and_api_agree_on_the_number_of_trips(self) -> None:
        base_url = self.serve()
        TripHistory(self.database).add(TripSummary(duration_seconds=10, amount=0.5))
        TripHistory(self.database).add(TripSummary(duration_seconds=20, amount=1.0))

        _, _, markup = request(f"{base_url}{api.PANEL_PATH}")
        import json

        _, _, body = request(f"{base_url}{api.TRIPS_PATH}")

        self.assertEqual(len(data_rows(markup)), len(json.loads(body)))


class PanelErrorTest(PanelTestCase):
    def test_reports_the_error_without_sensitive_information(self) -> None:
        base_url = self.serve(BrokenHistory())

        with self.assertLogs(api.logger, level="ERROR") as logs:
            status, headers, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertEqual(status, 500)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn(panel.ERROR_HEADING, markup)
        self.assertIn(panel.ERROR_MESSAGE, markup)
        self.assertIn("panel_render_error", "\n".join(logs.output))
        for leaked in ("secreto", "conductor", "Traceback", "RuntimeError", "sqlite"):
            self.assertNotIn(leaked, markup)

    def test_keeps_serving_after_a_transient_failure(self) -> None:
        class FlakyHistory:
            def __init__(self) -> None:
                self.calls = 0

            def all(self) -> list[HistoryEntry]:
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("fallo transitorio")
                return [
                    HistoryEntry(
                        date="2026-09-25T10:30:00", duration_seconds=60, amount=2.0
                    )
                ]

        base_url = self.serve(FlakyHistory())

        with self.assertLogs(api.logger, level="ERROR"):
            first_status, _, _ = request(f"{base_url}{api.PANEL_PATH}")
        second_status, _, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertEqual(first_status, 500)
        self.assertEqual(second_status, 200)
        self.assertIn("1 min 0 s", markup)


class PanelEscapingTest(PanelTestCase):
    def test_escapes_values_that_look_like_markup(self) -> None:
        hostile = "<script>alert('x')</script>"
        self.history.add_migrated(
            HistoryEntry(date=hostile, duration_seconds=30, amount=1.0)
        )
        base_url = self.serve()

        _, _, markup = request(f"{base_url}{api.PANEL_PATH}")

        self.assertNotIn(hostile, markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>alert", markup)


class FormatterTest(unittest.TestCase):
    def test_formats_dates_in_readable_form(self) -> None:
        self.assertEqual(panel.format_date("2026-09-25T13:17:38"), "25/09/2026 13:17")
        self.assertEqual(panel.format_date("2026-01-05T00:00:00"), "05/01/2026 00:00")

    def test_keeps_unparseable_dates_visible(self) -> None:
        self.assertEqual(panel.format_date("sin fecha"), "sin fecha")
        self.assertEqual(panel.format_date(""), "")

    def test_formats_durations_in_human_units(self) -> None:
        cases = {
            0: "0 s",
            1: "1 s",
            47.58: "48 s",
            59.4: "59 s",
            60: "1 min 0 s",
            90: "1 min 30 s",
            1303.91: "21 min 44 s",
            3600: "1 h 0 min",
            3900: "1 h 5 min",
        }
        for seconds, expected in cases.items():
            with self.subTest(segundos=seconds):
                self.assertEqual(panel.format_duration(seconds), expected)

    def test_formats_amounts_with_two_decimals_and_currency(self) -> None:
        self.assertEqual(panel.format_amount(64.7512), "64.75 EUR")
        self.assertEqual(panel.format_amount(2), "2.00 EUR")
        self.assertEqual(panel.format_amount(0), "0.00 EUR")


if __name__ == "__main__":
    unittest.main()
