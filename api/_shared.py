"""Shared helpers for Vercel Python functions."""

from __future__ import annotations

import json
import sys
from http import HTTPStatus
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web import server as web_server  # noqa: E402


def read_json(handler, max_bytes: int = 4096) -> dict:
    try:
        content_length = int(handler.headers.get("Content-Length", "0") or 0)
    except ValueError as error:
        raise ValueError("Invalid request length.") from error

    if content_length <= 0:
        raise ValueError("Missing request body.")
    if content_length > max_bytes:
        raise ValueError("Request body is too large.")

    try:
        return json.loads(handler.rfile.read(content_length).decode("utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError("Request body must be JSON.") from error


def send_json(handler, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
    data = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def send_error_json(handler, error: Exception, status: HTTPStatus) -> None:
    send_json(handler, {"ok": False, "error": str(error)}, status)


def method_not_allowed(handler) -> None:
    send_json(handler, {"ok": False, "error": "Method not allowed."}, HTTPStatus.METHOD_NOT_ALLOWED)
