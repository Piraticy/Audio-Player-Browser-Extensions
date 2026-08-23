#!/usr/bin/env python3
"""Container smoke test for the desktop app and browser extension scaffold."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        ("Python compile", check_python_compile),
        ("Desktop module import", check_desktop_import),
        ("Extension JavaScript syntax", check_extension_javascript),
        ("Manifest JSON", check_manifest_json),
        ("Web app files", check_web_app_files),
        ("FFmpeg conversion", check_ffmpeg_conversion),
    ]

    for label, check in checks:
        print(f"==> {label}")
        check()
        print(f"OK: {label}\n")

    print("All Docker smoke checks passed.")
    return 0


def check_python_compile() -> None:
    run(["python3", "-m", "py_compile", "desktop/audio_player_app.py", "web/server.py"])


def check_desktop_import() -> None:
    module_path = ROOT / "desktop" / "audio_player_app.py"
    spec = importlib.util.spec_from_file_location("audio_player_app", module_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load desktop/audio_player_app.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    expected_formats = {"mp3", "m4a", "wav", "flac", "ogg"}
    actual_formats = set(module.CONVERSION_PROFILES)
    if actual_formats != expected_formats:
        raise AssertionError(f"Unexpected conversion profiles: {sorted(actual_formats)}")


def check_extension_javascript() -> None:
    for script in ("background.js", "offscreen.js", "popup.js"):
        run(["node", "--check", script])


def check_manifest_json() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        raise AssertionError("manifest.json must use Manifest V3")
    if "offscreen" not in manifest.get("permissions", []):
        raise AssertionError("manifest.json must include the offscreen permission")
    if manifest.get("name") != "Auralith Studio":
        raise AssertionError("manifest.json must use the Auralith Studio app name")
    for size in ("16", "32", "48", "128"):
        icon_path = manifest.get("icons", {}).get(size)
        if not icon_path or not (ROOT / icon_path).exists():
            raise AssertionError(f"Missing extension icon for {size}px")
        if not (ROOT / icon_path).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise AssertionError(f"Extension icon for {size}px is not a valid PNG")


def check_web_app_files() -> None:
    required_files = [
        ROOT / "web" / "server.py",
        ROOT / "web" / "static" / "index.html",
        ROOT / "web" / "static" / "styles.css",
        ROOT / "web" / "static" / "app.js",
        ROOT / "web" / "static" / "icons" / "favicon.svg",
        ROOT / "web" / "static" / "icons" / "icon-128.png",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    if missing:
        raise AssertionError(f"Missing web app files: {', '.join(missing)}")

    html = (ROOT / "web" / "static" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
    required_text = [
        "Auralith",
        "Try demo",
        "Drop audio or video files here",
        "-20s",
        "+20s",
        "Motion Studio",
        "Auto-convert",
        "Online Streaming",
        "Play stream",
        "Clone file link",
        "/app.js?v=20260823-online-streams",
    ]
    missing_text = [text for text in required_text if text not in html]
    if missing_text:
        raise AssertionError(f"Missing web app UI text: {', '.join(missing_text)}")
    required_script_text = [
        "routeHostedMusicPage",
        "resolveOnlineStream",
        "isYouTubeUrl",
        "isAudiomackUrl",
        "isPlaylistStreamUrl",
        "Removed hosted music page from the playlist.",
        "official player",
    ]
    missing_script_text = [text for text in required_script_text if text not in app_js]
    if missing_script_text:
        raise AssertionError(f"Missing web app link handling: {', '.join(missing_script_text)}")

    server_path = ROOT / "web" / "server.py"
    spec = importlib.util.spec_from_file_location("web_server", server_path)
    if not spec or not spec.loader:
        raise RuntimeError("Could not load web/server.py")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if "no-store" not in server_path.read_text(encoding="utf-8"):
        raise AssertionError("web/server.py must disable browser caching for Docker testing")
    if "resolve_stream" not in server_path.read_text(encoding="utf-8"):
        raise AssertionError("web/server.py must resolve online stream playlists")
    if module.first_playlist_stream("#EXTM3U\nhttps://example.com/live.mp3\n", "https://example.com/station.m3u") != "https://example.com/live.mp3":
        raise AssertionError("M3U stream playlist parsing failed")
    if module.first_playlist_stream("[playlist]\nFile1=/live.aac\n", "https://example.com/station.pls") != "https://example.com/live.aac":
        raise AssertionError("PLS stream playlist parsing failed")

    for blocked_url in ("file:///tmp/song.mp3", "http://127.0.0.1/song.mp3", "http://localhost/song.mp3"):
        try:
            module.validate_public_media_url(blocked_url)
        except ValueError:
            continue
        raise AssertionError(f"Unsafe link was not blocked: {blocked_url}")


def check_ffmpeg_conversion() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for Docker media conversion checks")

    with tempfile.TemporaryDirectory(prefix="auralith-") as temp_dir:
        temp_path = Path(temp_dir)
        source = temp_path / "source.wav"
        target = temp_path / "converted.mp3"

        run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=0.25",
                "-codec:a",
                "pcm_s16le",
                str(source),
            ]
        )
        run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "320k",
                str(target),
            ]
        )

        if not target.exists() or target.stat().st_size <= 0:
            raise AssertionError("FFmpeg did not create a converted MP3")


def run(command: list[str]) -> None:
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
