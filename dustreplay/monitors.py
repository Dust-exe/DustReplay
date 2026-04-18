import ctypes
import ctypes.wintypes


def list_monitors():
    """Return list of dicts: index (1-based), x, y, w, h, name."""
    monitors = []
    idx = [0]

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.c_double,
    )

    def _cb(hMon, hdcMon, lprcMon, _):
        rc = lprcMon.contents
        idx[0] += 1
        w = rc.right - rc.left
        h = rc.bottom - rc.top
        monitors.append(
            {
                "index": idx[0],
                "x": rc.left,
                "y": rc.top,
                "w": w,
                "h": h,
                "name": f"Display {idx[0]} ({w}×{h})",
            }
        )
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(_cb), 0)
    return monitors


def get_monitor(index: int):
    """index: 1-based. Returns dict or None."""
    mons = list_monitors()
    if 1 <= index <= len(mons):
        return mons[index - 1]
    return None
