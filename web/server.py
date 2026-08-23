#!/usr/bin/env python3
"""Small Docker-friendly web app for local media playback and conversion."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
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

        with tempfile.TemporaryDirectory(prefix="audio-player-web-") as temp_dir:
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

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} - {format % args}")

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
    print(f"Audio Player web app running on http://{args.host}:{args.port}")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
