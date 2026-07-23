"""Resolve bundled branding files (dev tree vs PyInstaller one-file)."""

import os
import sys


def resource_root() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def logo_png_path() -> str:
    return os.path.join(resource_root(), "branding", "logo.png")
