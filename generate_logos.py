"""Generate all logo/favicon/icon assets from the White 1.png folder.
Uses colorful 3D versions for in-app logos (visible on both light and dark backgrounds).
Uses App 1 (neon on dark bg) for favicon and web icons.
"""
import os
from PIL import Image

SRC = r"C:\Users\maani\Downloads\White 1.png"
FRONTEND = r"C:\Users\maani\github-instantrisk\repo\frontend"

def autocrop_content(img, padding=20, bg_threshold=245):
    """Crop image to content area (skip near-white and transparent pixels)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 20:
                continue
            if r > bg_threshold and g > bg_threshold and b > bg_threshold:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x <= min_x or max_y <= min_y:
        bbox = img.getbbox()
        if bbox:
            return img.crop(bbox)
        return img
    x1 = max(0, min_x - padding)
    y1 = max(0, min_y - padding)
    x2 = min(w, max_x + padding)
    y2 = min(h, max_y + padding)
    return img.crop((x1, y1, x2, y2))

def autocrop_dark(img, padding=20, bg_threshold=25):
    """Crop image to content area on DARK background (skip near-black pixels)."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 20:
                continue
            if r < bg_threshold and g < bg_threshold and b < bg_threshold:
                continue
            min_x = min(min_x, x)
            min_y = min(min_y, y)
            max_x = max(max_x, x)
            max_y = max(max_y, y)
    if max_x <= min_x or max_y <= min_y:
        bbox = img.getbbox()
        if bbox:
            return img.crop(bbox)
        return img
    x1 = max(0, min_x - padding)
    y1 = max(0, min_y - padding)
    x2 = min(w, max_x + padding)
    y2 = min(h, max_y + padding)
    return img.crop((x1, y1, x2, y2))

def make_square(img, bg_color=(0, 0, 0, 0)):
    """Pad image to square."""
    w, h = img.size
    size = max(w, h)
    new = Image.new("RGBA", (size, size), bg_color)
    new.paste(img, ((size - w) // 2, (size - h) // 2), img if img.mode == "RGBA" else None)
    return new

def resize_to(img, size):
    return img.resize((size, size), Image.LANCZOS)

print("=" * 60)
print("GENERATING LOGO ASSETS (v2 - colorful)")
print("=" * 60)

# ── 1. logo-full.png → IR 3D.png (colorful shield + "InstantRisk" text) ──
print("\n1. logo-full.png (colorful 3D logo + text)")
ir3d = Image.open(os.path.join(SRC, "IR 3D.png")).convert("RGBA")
cropped = autocrop_content(ir3d, padding=15, bg_threshold=248)
# Resize to max 800px wide, keep aspect ratio
aspect = cropped.height / cropped.width
logo_full = cropped.resize((800, int(800 * aspect)), Image.LANCZOS)
out = os.path.join(FRONTEND, "assets", "images", "logo-full.png")
logo_full.save(out, "PNG", optimize=True)
print(f"   Saved: {out} ({logo_full.width}x{logo_full.height})")

# ── 2. logo-icon.png → 48x48 V2.png (colorful shield icon, no text) ──
print("\n2. logo-icon.png (colorful shield icon)")
color_icon = Image.open(os.path.join(SRC, "48x48 V2.png")).convert("RGBA")
cropped = autocrop_content(color_icon, padding=10, bg_threshold=248)
sq = make_square(cropped)
logo_icon = resize_to(sq, 256)
out = os.path.join(FRONTEND, "assets", "images", "logo-icon.png")
logo_icon.save(out, "PNG", optimize=True)
print(f"   Saved: {out} (256x256)")

# ── 3. logo-app.png → App 1.png (neon icon on dark bg, app store style) ──
print("\n3. logo-app.png (app icon, dark bg)")
app1 = Image.open(os.path.join(SRC, "App 1.png")).convert("RGBA")
app_cropped = autocrop_dark(app1, padding=5, bg_threshold=25)
app_sq = make_square(app_cropped, bg_color=(10, 6, 24, 255))
logo_app = resize_to(app_sq, 512)
out = os.path.join(FRONTEND, "assets", "images", "logo-app.png")
logo_app.save(out, "PNG", optimize=True)
print(f"   Saved: {out} (512x512)")

# ── 4. favicon.png (32x32, from App 1) ──
print("\n4. favicon.png (32x32)")
favicon = resize_to(app_sq, 32)
out = os.path.join(FRONTEND, "web", "favicon.png")
favicon.save(out, "PNG", optimize=True)
print(f"   Saved: {out} (32x32)")

# ── 5. Web Icons ──
print("\n5. Web icons")
for name, size in [
    ("Icon-192.png", 192),
    ("Icon-512.png", 512),
    ("Icon-maskable-192.png", 192),
    ("Icon-maskable-512.png", 512),
]:
    if "maskable" in name:
        padded = int(size * 0.8)
        inner = resize_to(app_sq, padded)
        outer = Image.new("RGBA", (size, size), (10, 6, 24, 255))
        outer.paste(inner, ((size - padded) // 2, (size - padded) // 2), inner)
        icon = outer
    else:
        icon = resize_to(app_sq, size)
    out = os.path.join(FRONTEND, "web", "icons", name)
    icon.save(out, "PNG", optimize=True)
    print(f"   Saved: {out} ({size}x{size})")

# ── 6. Website logos ──
print("\n6. Website logos")
web_images = os.path.join(os.path.dirname(FRONTEND), "website", "assets", "images")
if os.path.exists(web_images):
    logo_full.save(os.path.join(web_images, "logo-full.png"), "PNG", optimize=True)
    logo_full.save(os.path.join(web_images, "logo-color.png"), "PNG", optimize=True)
    logo_icon.save(os.path.join(web_images, "logo-icon.png"), "PNG", optimize=True)
    # White version for dark sections
    white_full = Image.open(os.path.join(SRC, "White 1.png")).convert("RGBA")
    bbox = white_full.getbbox()
    if bbox:
        white_cropped = white_full.crop(bbox)
        aspect_w = white_cropped.height / white_cropped.width
        white_resized = white_cropped.resize((800, int(800 * aspect_w)), Image.LANCZOS)
        white_resized.save(os.path.join(web_images, "logo-white.png"), "PNG", optimize=True)
    print("   Saved all website logos")
else:
    print(f"   SKIP: website dir not found")

print("\n" + "=" * 60)
print("ALL LOGO ASSETS GENERATED (v2)")
print("=" * 60)
