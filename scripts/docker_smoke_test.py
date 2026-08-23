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
    run(["python3", "-m", "py_compile", "desktop/audio_player_app.py"])


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


def check_web_app_files() -> None:
    required_files = [
        ROOT / "web" / "server.py",
        ROOT / "web" / "static" / "index.html",
        ROOT / "web" / "static" / "styles.css",
        ROOT / "web" / "static" / "app.js",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    if missing:
        raise AssertionError(f"Missing web app files: {', '.join(missing)}")

    run(["python3", "-m", "py_compile", "web/server.py"])


def check_ffmpeg_conversion() -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for Docker media conversion checks")

    with tempfile.TemporaryDirectory(prefix="audio-player-") as temp_dir:
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
