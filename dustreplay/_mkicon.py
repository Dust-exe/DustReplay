"""Write icon.ico next to this script from branding/logo.png (portal mark + palette)."""

import os

from PIL import Image

from branding_paths import logo_png_path

_BG = (20, 16, 24)  # theme.BG #141018
_SIZES = (16, 32, 48, 64, 128, 256)


def _render_icon(sz: int) -> Image.Image:
    path = logo_png_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Missing logo for icon build: {path}")
    out = Image.new("RGBA", (sz, sz), (*_BG, 255))
    src = Image.open(path).convert("RGBA")
    margin = max(1, int(sz * 0.06))
    inner = sz - 2 * margin
    src.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = margin + (inner - src.width) // 2
    y = margin + (inner - src.height) // 2
    out.paste(src, (x, y), src)
    return out


sz = 256
img = _render_icon(sz)
imgs = [_render_icon(s) for s in _SIZES]
imgs[0].save(
    "icon.ico",
    format="ICO",
    append_images=imgs[1:],
    sizes=[(s, s) for s in _SIZES],
)
