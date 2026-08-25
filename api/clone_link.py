from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from api._shared import method_not_allowed, read_json, send_error_json, web_server


class handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        try:
            payload = read_json(self)
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            url = str(payload.get("url", "")).strip()
            web_server.validate_public_media_url(url)
            data, filename, content_type = web_server.fetch_link_media(url)
        except ValueError as error:
            send_error_json(self, error, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            send_error_json(self, error, HTTPStatus.BAD_GATEWAY)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        method_not_allowed(self)
