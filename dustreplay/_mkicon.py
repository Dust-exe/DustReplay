"""Write icon.ico next to this script (black hole mark, Omni palette)."""

import math

from PIL import Image, ImageDraw

DEEP = (49, 10, 93)
MID = (65, 30, 143)
SURFACE = (53, 47, 68)
STAR = (207, 148, 80)


def _draw_blackhole(sz: int) -> Image.Image:
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = sz / 2, sz / 2
    r0 = sz * 0.42
    for i, (r, col, w) in enumerate(
        [
            (r0 + 10, (*SURFACE, 200), 10),
            (r0, (*MID, 230), 12),
            (r0 - 14, (*DEEP, 240), 8),
        ]
    ):
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=col,
            width=w,
        )
    for k in range(3):
        a0 = -math.pi * 0.35 + k * math.pi * 0.45
        pts = []
        steps = 24
        for s in range(steps + 1):
            t = s / steps
            ang = a0 + t * math.pi * 1.1
            rr = r0 * 0.55 + t * r0 * 0.5
            pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
        if len(pts) > 2:
            d.line(pts, fill=(*SURFACE, 220), width=max(3, sz // 32))
    rh = sz * 0.14
    d.ellipse([cx - rh, cy - rh, cx + rh, cy + rh], fill=(*DEEP, 255))
    d.ellipse([cx - rh * 0.45, cy - rh * 0.45, cx + rh * 0.45, cy + rh * 0.45], fill=(12, 6, 24, 255))
    rng = [(0.22, 0.18), (0.78, 0.22), (0.72, 0.78), (0.2, 0.75)]
    for ux, uy in rng:
        x, y = cx - sz / 2 + sz * ux, cy - sz / 2 + sz * uy
        rr = max(2, sz // 28)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(*STAR, 255))
    return img


sz = 256
img = _draw_blackhole(sz)
sizes = (16, 32, 48, 64, 128, 256)
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]
imgs[0].save(
    "icon.ico",
    format="ICO",
    append_images=imgs[1:],
    sizes=[(s, s) for s in sizes],
)
