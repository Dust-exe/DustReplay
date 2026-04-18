"""Generate icon.ico next to this script (run from dev env or build)."""

from PIL import Image, ImageDraw, ImageFilter

sz = 256
img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse([0, 0, sz - 1, sz - 1], fill=(30, 0, 60, 255))
d.ellipse([14, 14, sz - 15, sz - 15], fill=(110, 30, 210, 255))
d.ellipse([32, 32, sz - 33, sz - 33], fill=(155, 60, 245, 255))
d.ellipse([82, 82, sz - 83, sz - 83], fill=(255, 255, 255, 245))
img = img.filter(ImageFilter.SMOOTH)
sizes = (16, 32, 48, 64, 128, 256)
imgs = [img.resize((s, s), Image.LANCZOS) for s in sizes]
imgs[0].save(
    "icon.ico",
    format="ICO",
    append_images=imgs[1:],
    sizes=[(s, s) for s in sizes],
)
