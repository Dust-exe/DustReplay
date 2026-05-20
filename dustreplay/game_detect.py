"""Detect fullscreen games on Windows to reduce capture load (e.g. CS2)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Common competitive / fullscreen titles (lowercase exe names).
_GAME_EXE_NAMES = frozenset(
    {
        "cs2.exe",
        "csgo.exe",
        "dota2.exe",
        "valorant.exe",
        "valorant-win64-shipping.exe",
        "r5apex.exe",
        "fortniteclient-win64-shipping.exe",
        "overwatch.exe",
        "pubg.exe",
        "tslgame.exe",
        "gta5.exe",
        "eldenring.exe",
        "rocketleague.exe",
    }
)


def _foreground_hwnd() -> int:
    try:
        import ctypes

        return int(ctypes.windll.user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def _hwnd_process_name(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        import psutil

        return (psutil.Process(pid.value).name() or "").lower()
    except Exception as e:
        logger.debug("hwnd process name: %s", e)
        return ""


def _hwnd_is_fullscreen(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        rect = wintypes.RECT()
        if not ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        w = rect.right - rect.left
        h = rect.bottom - rect.top
        if w < 800 or h < 600:
            return False
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        return w >= int(sw * 0.92) and h >= int(sh * 0.92)
    except Exception:
        return False


def is_fullscreen_game_active() -> bool:
    """True when a known game exe owns a near-fullscreen foreground window."""
    hwnd = _foreground_hwnd()
    if not _hwnd_is_fullscreen(hwnd):
        return False
    name = _hwnd_process_name(hwnd)
    if name in _GAME_EXE_NAMES:
        return True
    # Heuristic: Steam common layout — large window + game-like exe suffix.
    if name.endswith(".exe") and any(
        k in name for k in ("game", "shipping", "win64", "client")
    ):
        return _hwnd_is_fullscreen(hwnd)
    return False
