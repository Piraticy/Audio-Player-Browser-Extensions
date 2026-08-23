#!/usr/bin/env python3
"""Small Docker-friendly web app for local media playback and conversion."""

from __future__ import annotations

import argparse
import ipaddress
import json
import shutil
import socket
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import warnings
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


warnings.filterwarnings("ignore", category=DeprecationWarning, module="cgi")
import cgi

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "web" / "static"
MAX_LINK_BYTES = 100 * 1024 * 1024
CONVERSION_PROFILES = {
    "mp3": ["-vn", "-codec:a", "libmp3lame", "-b:a", "320k"],
    "m4a": ["-vn", "-codec:a", "aac", "-b:a", "192k"],
    "wav": ["-vn", "-codec:a", "pcm_s16le"],
    "flac": ["-vn", "-codec:a", "flac"],
    "ogg": ["-vn", "-codec:a", "libvorbis", "-q:a", "5"],
}


class AudioPlayerHandler(SimpleHTTPRequestHandler):
    server_version = "AudioPlayerHTTP/0.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(
                {
                    "ok": True,
                    "app": "Auralith Studio",
                    "ffmpeg": bool(shutil.which("ffmpeg")),
                    "formats": sorted(CONVERSION_PROFILES),
                }
            )
            return

        if self.path.startswith("/api/youtube-suggestions"):
            self._send_json(fetch_youtube_suggestions(self.path))
            return

        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path == "/api/clone-link":
            self.clone_link()
            return

        if self.path != "/api/convert":
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")
            return

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self._send_json({"ok": False, "error": "FFmpeg is not installed."}, HTTPStatus.SERVICE_UNAVAILABLE)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )
        upload = form["file"] if "file" in form else None
        output_format = form.getfirst("format", "mp3")

        if output_format not in CONVERSION_PROFILES:
            self._send_json({"ok": False, "error": "Unsupported output format."}, HTTPStatus.BAD_REQUEST)
            return

        if upload is None or not getattr(upload, "filename", ""):
            self._send_json({"ok": False, "error": "Upload a media file first."}, HTTPStatus.BAD_REQUEST)
            return

        source_name = Path(upload.filename).name
        output_name = f"{Path(source_name).stem or 'converted'}.{output_format}"

        with tempfile.TemporaryDirectory(prefix="auralith-web-") as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / source_name
            target = temp_path / output_name
            source.write_bytes(upload.file.read())

            result = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(source),
                    *CONVERSION_PROFILES[output_format],
                    "-map_metadata",
                    "0",
                    str(target),
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self._send_json(
                    {"ok": False, "error": compact_error(result.stderr)},
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return

            data = target.read_bytes()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type_for(output_format))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{output_name}"')
        self.end_headers()
        self.wfile.write(data)

    def clone_link(self) -> None:
        try:
            payload = self.read_json_payload()
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            url = str(payload.get("url", "")).strip()
            validate_public_media_url(url)
            data, filename, content_type = fetch_link_media(url)
        except ValueError as error:
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_REQUEST)
            return
        except OSError as error:
            self._send_json({"ok": False, "error": str(error)}, HTTPStatus.BAD_GATEWAY)
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def read_json_payload(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if content_length <= 0:
            raise ValueError("Missing request body.")
        if content_length > 4096:
            raise ValueError("Request body is too large.")

        try:
            return json.loads(self.rfile.read(content_length).decode("utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be JSON.") from error

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def content_type_for(output_format: str) -> str:
    return {
        "flac": "audio/flac",
        "m4a": "audio/mp4",
        "mp3": "audio/mpeg",
        "ogg": "audio/ogg",
        "wav": "audio/wav",
    }[output_format]


def compact_error(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    return lines[-1] if lines else "Conversion failed."


def validate_public_media_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Use an http or https media link.")
    if not parsed.hostname:
        raise ValueError("The media link needs a valid host.")

    try:
        address_infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as error:
        raise ValueError("Could not resolve the media link host.") from error

    for address_info in address_infos:
        ip_address = ipaddress.ip_address(address_info[4][0])
        if (
            ip_address.is_private
            or ip_address.is_loopback
            or ip_address.is_link_local
            or ip_address.is_multicast
            or ip_address.is_reserved
            or ip_address.is_unspecified
        ):
            raise ValueError("Private, local, or reserved network links are not allowed.")


def fetch_link_media(url: str) -> tuple[bytes, str, str]:
    current_url = url
    opener = urllib.request.build_opener(NoRedirectHandler)

    for _ in range(5):
        validate_public_media_url(current_url)
        request = urllib.request.Request(current_url, headers={"User-Agent": "AuralithStudio/0.1"})

        try:
            response = opener.open(request, timeout=15)
        except urllib.error.HTTPError as error:
            if error.code not in {301, 302, 303, 307, 308}:
                raise OSError(f"Could not fetch link: HTTP {error.code}") from error

            location = error.headers.get("Location")
            if not location:
                raise ValueError("Linked media redirected without a destination.") from error
            current_url = urllib.parse.urljoin(current_url, location)
            continue

        with response:
            content_type = response.headers.get("Content-Type", "application/octet-stream").split(";")[0].strip().lower()
            content_length = response.headers.get("Content-Length")

            if content_type in {"text/html", "text/plain", "application/json"}:
                raise ValueError("This does not look like a direct audio or video file link.")
            if content_length and int(content_length) > MAX_LINK_BYTES:
                raise ValueError("Linked media is larger than the 100 MB clone limit.")

            data = read_limited(response, MAX_LINK_BYTES)
            filename = filename_from_response(current_url, response.headers.get("Content-Disposition", ""))
            return data, filename, content_type or "application/octet-stream"

    raise ValueError("Linked media has too many redirects.")


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_limited(response, max_bytes: int) -> bytes:
    chunks = []
    total = 0

    while True:
        chunk = response.read(1024 * 256)
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("Linked media is larger than the 100 MB clone limit.")
        chunks.append(chunk)


def filename_from_response(url: str, content_disposition: str) -> str:
    if "filename=" in content_disposition:
        raw_name = content_disposition.split("filename=", 1)[1].strip().strip('"')
    else:
        raw_name = Path(urllib.parse.urlparse(url).path).name

    name = "".join(character for character in urllib.parse.unquote(raw_name) if character.isalnum() or character in " ._-").strip()
    return name or "linked-media"


def fetch_youtube_suggestions(path: str) -> dict:
    parsed = urllib.parse.urlparse(path)
    query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()

    if not query:
        return {"ok": True, "suggestions": []}

    url = "https://suggestqueries.google.com/complete/search?" + urllib.parse.urlencode(
        {
            "client": "firefox",
            "ds": "yt",
            "q": query,
        }
    )
    request = urllib.request.Request(url, headers={"User-Agent": "AudioPlayer/0.1"})

    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"ok": False, "error": str(error), "suggestions": []}

    suggestions = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
    return {"ok": True, "suggestions": suggestions[:8]}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), AudioPlayerHandler)
    print(f"Auralith Studio web app running on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
