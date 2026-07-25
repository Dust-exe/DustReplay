"""Write icon.ico next to this script from branding/logo.png (portal mark + palette)."""

import os

from PIL import Image

from branding_paths import logo_png_path

_SIZES = (16, 32, 48, 64, 128, 256)


def _render_icon(sz: int) -> Image.Image:
    path = logo_png_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Missing logo for icon build: {path}")
    out = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    src = Image.open(path).convert("RGBA")

    # Strip black/dark background to leave clean transparent portal mark
    datas = src.getdata()
    new_data = []
    for item in datas:
        if item[0] < 22 and item[1] < 22 and item[2] < 28:
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append(item)
    src.putdata(new_data)

    # Use thumbnail (preserves aspect ratio) then CENTER on square canvas
    margin = max(1, int(sz * 0.06))
    inner = sz - 2 * margin
    src.thumbnail((inner, inner), Image.Resampling.LANCZOS)
    x = margin + (inner - src.width) // 2
    y = margin + (inner - src.height) // 2
    out.paste(src, (x, y), src)
    return out


def make_square_logo(size: int = 256) -> Image.Image:
    """Create a square transparent logo from the rectangular source, preserving aspect ratio."""
    path = logo_png_path()
    if not os.path.isfile(path):
        return Image.new("RGBA", (size, size), (0, 0, 0, 0))
    src = Image.open(path).convert("RGBA")

    # Strip dark background pixels
    datas = src.getdata()
    new_data = []
    for item in datas:
        if item[0] < 22 and item[1] < 22 and item[2] < 28:
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append(item)
    src.putdata(new_data)

    # Create square canvas and center the logo
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    src.thumbnail((size, size), Image.Resampling.LANCZOS)
    x = (size - src.width) // 2
    y = (size - src.height) // 2
    out.paste(src, (x, y), src)
    return out


if __name__ == "__main__":
    imgs = [_render_icon(s) for s in _SIZES]
    imgs[0].save(
        "icon.ico",
        format="ICO",
        append_images=imgs[1:],
        sizes=[(s, s) for s in _SIZES],
    )
    print(f"icon.ico created with sizes: {_SIZES}")
