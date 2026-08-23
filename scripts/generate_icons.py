#!/usr/bin/env python3
"""Generate Auralith Studio icon assets with only the Python standard library."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB_ICON_DIR = ROOT / "web" / "static" / "icons"
EXTENSION_ICON_DIR = ROOT / "assets" / "icons"
SIZES = (16, 32, 48, 128)


def main() -> int:
    WEB_ICON_DIR.mkdir(parents=True, exist_ok=True)
    EXTENSION_ICON_DIR.mkdir(parents=True, exist_ok=True)

    svg = build_svg()
    (WEB_ICON_DIR / "favicon.svg").write_text(svg, encoding="utf-8")
    (WEB_ICON_DIR / "app-icon.svg").write_text(svg, encoding="utf-8")

    for size in SIZES:
        png = build_png(size)
        (WEB_ICON_DIR / f"icon-{size}.png").write_bytes(png)
        (EXTENSION_ICON_DIR / f"icon-{size}.png").write_bytes(png)

    return 0


def build_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bg" x1="18" y1="10" x2="110" y2="118" gradientUnits="userSpaceOnUse">
      <stop stop-color="#2fe6c8"/>
      <stop offset="0.48" stop-color="#5d8cff"/>
      <stop offset="1" stop-color="#f2c14d"/>
    </linearGradient>
    <radialGradient id="glow" cx="64" cy="62" r="56" gradientUnits="userSpaceOnUse">
      <stop stop-color="#f5f2ec" stop-opacity="0.92"/>
      <stop offset="0.3" stop-color="#2fe6c8" stop-opacity="0.44"/>
      <stop offset="1" stop-color="#111314" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="128" height="128" rx="28" fill="#111314"/>
  <circle cx="64" cy="64" r="51" fill="url(#bg)" opacity="0.94"/>
  <circle cx="64" cy="64" r="36" fill="#111314" opacity="0.34"/>
  <circle cx="64" cy="64" r="25" fill="url(#glow)"/>
  <circle cx="64" cy="64" r="13" fill="#111314"/>
  <path d="M88 28c8 7 13 17 15 29" fill="none" stroke="#f5f2ec" stroke-opacity="0.72" stroke-width="7" stroke-linecap="round"/>
  <path d="M31 89c-8-8-12-17-14-29" fill="none" stroke="#2fe6c8" stroke-opacity="0.55" stroke-width="7" stroke-linecap="round"/>
</svg>
"""


def build_png(size: int) -> bytes:
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            row.extend(pixel_at(x, y, size))
        rows.append(bytes(row))

    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def pixel_at(x: int, y: int, size: int) -> tuple[int, int, int, int]:
    cx = cy = (size - 1) / 2
    dx = (x - cx) / size
    dy = (y - cy) / size
    distance = math.sqrt(dx * dx + dy * dy)
    angle = (math.atan2(dy, dx) + math.pi) / (math.pi * 2)
    corner_alpha = rounded_square_alpha(x, y, size)

    bg = mix((17, 19, 20), (30, 39, 42), 1 - min(1, distance * 1.8))

    if distance < 0.41:
        color = gradient(angle)
        color = mix(color, (245, 242, 236), max(0, 0.12 - distance) * 2.3)
    elif distance < 0.5:
        color = mix((17, 19, 20), (47, 230, 200), 0.18)
    else:
        color = bg

    if distance < 0.2:
        color = mix(color, (245, 242, 236), 0.78)
    if distance < 0.105:
        color = (17, 19, 20)

    return (*color, int(255 * corner_alpha))


def gradient(position: float) -> tuple[int, int, int]:
    stops = [
        (0.0, (47, 230, 200)),
        (0.38, (93, 140, 255)),
        (0.72, (242, 193, 77)),
        (1.0, (47, 230, 200)),
    ]
    for index, (stop, color) in enumerate(stops[1:], start=1):
        previous_stop, previous_color = stops[index - 1]
        if position <= stop:
            local = (position - previous_stop) / (stop - previous_stop)
            return mix(previous_color, color, local)
    return stops[-1][1]


def rounded_square_alpha(x: int, y: int, size: int) -> float:
    radius = size * 0.22
    inset = size * 0.03
    px = min(x - inset, size - inset - x)
    py = min(y - inset, size - inset - y)
    if px >= radius or py >= radius:
        return 1

    distance = math.sqrt((radius - px) ** 2 + (radius - py) ** 2)
    return max(0, min(1, radius + 0.75 - distance))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = max(0, min(1, amount))
    return tuple(round(a[index] * (1 - amount) + b[index] * amount) for index in range(3))


def png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)


if __name__ == "__main__":
    raise SystemExit(main())
