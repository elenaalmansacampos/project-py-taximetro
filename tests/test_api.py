import io
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from taximeter import api, cli
from taximeter.database import TripHistory
from taximeter.history import HistoryEntry
from taximeter.taximeter import TripSummary


def request(url: str, method: str = "GET"):
    http_request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(http_request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        with error:
            return error.code, error.headers, error.read()


class BrokenHistory:
    def all(self) -> list[HistoryEntry]:
        raise RuntimeError("sqlite:///home/conductor/secreto.db no se puede abrir")

    def add(self, summary: TripSummary) -> None:
        raise AssertionError("la API no debe escribir")


class ApiTestCase(unittest.TestCase):
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


class TripsEndpointTest(ApiTestCase):
    def test_returns_200_with_date_duration_and_amount(self) -> None:
        self.history.add(TripSummary(duration_seconds=1303.91, amount=64.7512))
        self.history.add(TripSummary(duration_seconds=47.58, amount=2.18))
        base_url = self.serve()

        status, headers, body = request(f"{base_url}{api.TRIPS_PATH}")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertEqual(len(payload), 2)
        self.assertEqual(
            set(payload[0]), {"date", "duration_seconds", "amount"}
        )
        self.assertEqual(payload[0]["duration_seconds"], 1303.91)
        self.assertEqual(payload[0]["amount"], 64.75)
        self.assertEqual(payload[1]["duration_seconds"], 47.58)
        self.assertEqual(payload[1]["amount"], 2.18)
        for trip in payload:
            self.assertRegex(trip["date"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_returns_empty_collection_with_success_when_there_are_no_trips(
        self,
    ) -> None:
        base_url = self.serve()

        status, _, body = request(f"{base_url}{api.TRIPS_PATH}")

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), [])

    def test_ignores_the_query_string(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        status, _, body = request(f"{base_url}{api.TRIPS_PATH}?limite=5&pagina=2")

        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)), 1)

    def test_never_exposes_extra_internal_columns(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        _, _, body = request(f"{base_url}{api.TRIPS_PATH}")

        for trip in json.loads(body):
            self.assertEqual(set(trip), {"date", "duration_seconds", "amount"})


class InvalidRequestTest(ApiTestCase):
    def test_unknown_paths_return_404(self) -> None:
        base_url = self.serve()

        for path in ("/", "/api", "/api/v1", "/api/v1/trip", "/api/v2/trips"):
            with self.subTest(ruta=path):
                status, _, body = request(f"{base_url}{path}")

                self.assertEqual(status, 404)
                payload = json.loads(body)
                self.assertEqual(payload["error"], "not_found")
                self.assertIn(api.TRIPS_PATH, payload["message"])

    def test_trailing_slash_is_not_accepted(self) -> None:
        base_url = self.serve()

        status, _, _ = request(f"{base_url}{api.TRIPS_PATH}/")

        self.assertEqual(status, 404)

    def test_write_and_unsupported_methods_return_405_with_allow_header(self) -> None:
        base_url = self.serve()

        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            with self.subTest(metodo=method):
                status, headers, body = request(
                    f"{base_url}{api.TRIPS_PATH}", method=method
                )

                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET")
                if method != "HEAD":
                    self.assertEqual(
                        json.loads(body)["error"], "method_not_allowed"
                    )

    def test_write_attempts_do_not_modify_the_history(self) -> None:
        self.history.add(TripSummary(duration_seconds=10, amount=0.5))
        base_url = self.serve()

        request(f"{base_url}{api.TRIPS_PATH}", method="POST")
        request(f"{base_url}{api.TRIPS_PATH}", method="DELETE")

        self.assertEqual(len(TripHistory(self.database).all()), 1)

    def test_head_response_has_no_body(self) -> None:
        base_url = self.serve()

        status, _, body = request(f"{base_url}{api.TRIPS_PATH}", method="HEAD")

        self.assertEqual(status, 405)
        self.assertEqual(body, b"")


class InternalFailureTest(ApiTestCase):
    def test_returns_500_without_leaking_internal_details(self) -> None:
        base_url = self.serve(BrokenHistory())

        with self.assertLogs(api.logger, level="ERROR") as logs:
            status, headers, body = request(f"{base_url}{api.TRIPS_PATH}")

        self.assertEqual(status, 500)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        payload = json.loads(body)
        self.assertEqual(payload["error"], "internal_error")
        self.assertEqual(payload["message"], "No se pudo consultar el historial.")
        self.assertIn("api_trips_error", "\n".join(logs.output))

        body_text = body.decode("utf-8")
        self.assertNotIn("secreto", body_text)
        self.assertNotIn("conductor", body_text)
        self.assertNotIn("Traceback", body_text)
        self.assertNotIn("RuntimeError", body_text)


class SerializeTripTest(unittest.TestCase):
    def test_rounds_amounts_to_two_decimals(self) -> None:
        payload = api.serialize_trip(
            HistoryEntry(
                date="2026-09-25T10:30:00", duration_seconds=3.456, amount=1.005
            )
        )

        self.assertEqual(payload, {
            "date": "2026-09-25T10:30:00",
            "duration_seconds": 3.46,
            "amount": 1.0,
        })


class ApiCliTest(unittest.TestCase):
    def test_api_flag_routes_to_the_api(self) -> None:
        with (
            patch.object(sys, "argv", ["main.py", "--api"]),
            patch.object(cli, "configure_logging"),
            patch.object(cli, "run_api") as run_api,
            patch.object(cli, "run_cli") as run_cli,
            patch.object(cli, "run_gui") as run_gui,
        ):
            cli.main()

        run_api.assert_called_once_with(
            host=api.DEFAULT_API_HOST, port=api.DEFAULT_API_PORT
        )
        run_cli.assert_not_called()
        run_gui.assert_not_called()

    def test_host_and_port_are_forwarded(self) -> None:
        argv = ["main.py", "--api", "--api-host", "0.0.0.0", "--api-port", "9000"]
        with (
            patch.object(sys, "argv", argv),
            patch.object(cli, "configure_logging"),
            patch.object(cli, "run_api") as run_api,
        ):
            cli.main()

        run_api.assert_called_once_with(host="0.0.0.0", port=9000)

    def test_api_is_mutually_exclusive_with_gui_and_migration(self) -> None:
        for argv in (
            ["main.py", "--api", "--gui"],
            ["main.py", "--api", "--migrate-history"],
        ):
            with self.subTest(argv=argv):
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(cli, "configure_logging"),
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as exit_info,
                ):
                    cli.main()

                self.assertEqual(exit_info.exception.code, 2)

    def test_host_and_port_require_the_api_flag(self) -> None:
        argv_options = (
            ["main.py", "--api-port", "9000"],
            ["main.py", "--api-host", "0.0.0.0"],
        )
        for argv in argv_options:
            with self.subTest(argv=argv):
                with (
                    patch.object(sys, "argv", argv),
                    patch.object(cli, "configure_logging"),
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as exit_info,
                ):
                    cli.main()

                self.assertEqual(exit_info.exception.code, 2)

    def test_run_api_serves_the_database_history(self) -> None:
        server = MagicMock()
        server.base_url = "http://127.0.0.1:8000"
        server.server_address = ("127.0.0.1", 8000)

        with (
            patch.object(
                cli, "create_server", return_value=server
            ) as create_server_mock,
            patch.object(cli, "TripHistory") as history_class,
            patch("builtins.print") as print_mock,
        ):
            cli.run_api(host="127.0.0.1", port=8000)

        history_class.assert_called_once_with()
        create_server_mock.assert_called_once_with(
            history_class.return_value, "127.0.0.1", 8000
        )
        server.serve_forever.assert_called_once_with()
        server.server_close.assert_called_once_with()
        printed = "\n".join(str(call) for call in print_mock.call_args_list)
        self.assertIn("http://127.0.0.1:8000/api/v1/trips", printed)

    def test_run_api_closes_the_server_on_interrupt(self) -> None:
        server = MagicMock()
        server.base_url = "http://127.0.0.1:8000"
        server.server_address = ("127.0.0.1", 8000)
        server.serve_forever.side_effect = KeyboardInterrupt

        with (
            patch.object(cli, "create_server", return_value=server),
            patch.object(cli, "TripHistory"),
            patch("builtins.print"),
        ):
            cli.run_api()

        server.server_close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
