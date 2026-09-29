from __future__ import annotations

import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from taximeter.history import HistoryEntry, HistoryRepository


logger = logging.getLogger(__name__)

TRIPS_PATH = "/api/v1/trips"
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8000
ALLOWED_METHOD = "GET"


class ApiServer(ThreadingHTTPServer):
    """Servidor HTTP que expone el historial mediante TripRequestHandler."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        history: HistoryRepository,
        handler_class: type[BaseHTTPRequestHandler] | None = None,
    ) -> None:
        super().__init__(server_address, handler_class or TripRequestHandler)
        self.history = history

    @property
    def base_url(self) -> str:
        host, port = self.server_address[0], self.server_address[1]
        if ":" in host:  # IPv6
            host = f"[{host}]"
        return f"http://{host}:{port}"


class TripRequestHandler(BaseHTTPRequestHandler):
    """Sirve unicamente la consulta del historial; no expone escritura."""

    server_version = "TaximeterAPI/1.0"
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if urlsplit(self.path).path != TRIPS_PATH:
            self._send_error(
                HTTPStatus.NOT_FOUND,
                "not_found",
                f"Recurso no encontrado. El historial se consulta en {TRIPS_PATH}.",
            )
            return

        try:
            entries = self.server.history.all()
        except Exception:
            logger.exception("api_trips_error")
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal_error",
                "No se pudo consultar el historial.",
            )
            return

        logger.info("api_trips_served count=%s", len(entries))
        self._send_json(HTTPStatus.OK, [serialize_trip(entry) for entry in entries])

    def do_HEAD(self) -> None:
        self._send_method_not_allowed(include_body=False)

    def do_POST(self) -> None:
        self._send_method_not_allowed()

    def do_PUT(self) -> None:
        self._send_method_not_allowed()

    def do_PATCH(self) -> None:
        self._send_method_not_allowed()

    def do_DELETE(self) -> None:
        self._send_method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._send_method_not_allowed()

    def log_message(self, format: str, *args: Any) -> None:
        logger.debug("api_access %s", format % args)

    def _send_method_not_allowed(self, include_body: bool = True) -> None:
        message = (
            f"Solo se admite {ALLOWED_METHOD} sobre {TRIPS_PATH}. "
            "La API es de solo lectura."
        )
        body = json.dumps(
            {"error": "method_not_allowed", "message": message}, ensure_ascii=False
        ).encode("utf-8")
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", ALLOWED_METHOD)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_body(body, include_body=include_body)

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        self._send_json(status, {"error": code, "message": message})

    def _send_json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_body(body, include_body=True)

    def _send_body(self, body: bytes | str, include_body: bool = True) -> None:
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)


def serialize_trip(entry: HistoryEntry) -> dict[str, Any]:
    return {
        "date": entry.date,
        "duration_seconds": round(float(entry.duration_seconds), 2),
        "amount": round(float(entry.amount), 2),
    }


def create_server(
    history: HistoryRepository,
    host: str = DEFAULT_API_HOST,
    port: int = DEFAULT_API_PORT,
) -> ApiServer:
    return ApiServer((host, port), history)
