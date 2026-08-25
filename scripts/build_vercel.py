#!/usr/bin/env python3
"""Prepare static assets for Vercel deployment."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web" / "static"
TARGET = ROOT / "public"


def main() -> int:
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)
    print(f"Copied {SOURCE.relative_to(ROOT)} to {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
