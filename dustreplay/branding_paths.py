"""Resolve bundled branding files (dev tree vs PyInstaller one-file)."""

import os
import sys


def resource_root() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return str(sys._MEIPASS)
    return os.path.dirname(os.path.abspath(__file__))


def logo_png_path() -> str:
    bundled = os.path.join(resource_root(), "branding", "logo.png")
    if os.path.isfile(bundled):
        return bundled
    for extra in (
        os.path.join(os.path.expanduser("~"), "Desktop", "dasasd", "dust logo.png"),
        r"C:\Users\kaan3\Desktop\dasasd\dust logo.png",
    ):
        if os.path.isfile(extra):
            return extra
    return bundled
