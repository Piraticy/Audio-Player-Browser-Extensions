from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from api._shared import method_not_allowed, send_json


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        send_json(
            self,
            {
                "ok": False,
                "error": "Hosted conversion is disabled on Vercel free hosting. Run the Docker app for FFmpeg conversion.",
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )

    def do_GET(self) -> None:
        method_not_allowed(self)
