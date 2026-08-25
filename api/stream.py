from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from api._shared import method_not_allowed, send_error_json, web_server


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        try:
            parsed = urllib.parse.urlparse(self.path)
            url = urllib.parse.parse_qs(parsed.query).get("url", [""])[0].strip()
            web_server.validate_public_media_url(url)
            response, content_type = web_server.open_stream_response(url)
        except ValueError as error:
            send_error_json(self, error, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            send_error_json(self, error, HTTPStatus.BAD_GATEWAY)
            return

        with response:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

            while True:
                try:
                    chunk = response.read(1024 * 64)
                    if not chunk:
                        return
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return

    def do_POST(self) -> None:
        method_not_allowed(self)
