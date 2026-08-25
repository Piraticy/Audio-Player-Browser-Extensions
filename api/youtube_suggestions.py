from __future__ import annotations

from http.server import BaseHTTPRequestHandler

from api._shared import method_not_allowed, send_json, web_server


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        send_json(self, web_server.fetch_youtube_suggestions(self.path))

    def do_POST(self) -> None:
        method_not_allowed(self)
