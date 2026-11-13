"""Сборка иконки macOS (.icns) из векторной снежинки приложения."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image
from PySide6.QtWidgets import QApplication

from flakemac.app import make_snowflake_image

SIZE = 1024


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    out_dir = os.path.dirname(os.path.abspath(__file__))
    tmp = os.path.join(out_dir, "_icon_1024.png")
    make_snowflake_image(SIZE).save(tmp, "PNG")
    icns_path = os.path.join(out_dir, "flake.icns")
    Image.open(tmp).convert("RGBA").save(icns_path, format="ICNS")
    os.remove(tmp)
    print("icon:", icns_path, os.path.getsize(icns_path), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
