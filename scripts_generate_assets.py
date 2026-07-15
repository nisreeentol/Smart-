"""
One-off utility script used during project setup to GENERATE the default
sticker assets (glasses, hat, mask) as transparent RGBA PNGs, and a sample
background image, using only PIL drawing primitives (no external downloads
needed). Run this once: `python scripts_generate_assets.py`

Students are encouraged to replace these placeholder stickers with their
own higher-quality artwork in /assets/stickers/ for extra creativity points.
"""

from PIL import Image, ImageDraw
import os

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
STICKERS_DIR = os.path.join(ASSETS_DIR, "stickers")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
os.makedirs(STICKERS_DIR, exist_ok=True)
os.makedirs(BACKGROUNDS_DIR, exist_ok=True)


def make_glasses(path, size=(600, 220)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lens_w, lens_h = 220, 180
    gap = 60
    cx = size[0] // 2
    cy = size[1] // 2
    left_box = (cx - gap // 2 - lens_w, cy - lens_h // 2, cx - gap // 2, cy + lens_h // 2)
    right_box = (cx + gap // 2, cy - lens_h // 2, cx + gap // 2 + lens_w, cy + lens_h // 2)

    outline_color = (20, 20, 20, 255)
    lens_color = (120, 200, 255, 90)
    d.ellipse(left_box, fill=lens_color, outline=outline_color, width=14)
    d.ellipse(right_box, fill=lens_color, outline=outline_color, width=14)
    # bridge
    d.line([(left_box[2] - 10, cy), (right_box[0] + 10, cy)], fill=outline_color, width=14)
    # temple arms
    d.line([(left_box[0], cy), (left_box[0] - 60, cy - 10)], fill=outline_color, width=14)
    d.line([(right_box[2], cy), (right_box[2] + 60, cy - 10)], fill=outline_color, width=14)

    img.save(path)


def make_hat(path, size=(600, 420)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    brim_color = (30, 30, 40, 255)
    top_color = (55, 55, 75, 255)
    band_color = (170, 30, 40, 255)

    # brim (wide ellipse at the bottom)
    d.ellipse((20, 300, 580, 400), fill=brim_color)
    # crown (rounded rectangle-ish top hat body)
    d.rounded_rectangle((150, 40, 450, 330), radius=40, fill=top_color)
    # band
    d.rectangle((150, 270, 450, 320), fill=band_color)

    img.save(path)


def make_mask(path, size=(500, 260)):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fabric_color = (40, 110, 180, 235)
    d.rounded_rectangle((20, 40, 480, 240), radius=90, fill=fabric_color)
    # pleats (simple lines to suggest fabric folds)
    for yy in (100, 140, 180):
        d.line([(60, yy), (440, yy)], fill=(20, 70, 130, 180), width=6)
    # ear loops
    d.line([(20, 90), (-40, 60)], fill=(255, 255, 255, 180), width=8)
    d.line([(480, 90), (540, 60)], fill=(255, 255, 255, 180), width=8)

    img.save(path)


def make_sample_background(path, size=(1280, 720)):
    """A simple gradient 'studio' backdrop as a default chroma-key replacement."""
    img = Image.new("RGB", size)
    top = (25, 35, 70)
    bottom = (140, 180, 230)
    for yy in range(size[1]):
        t = yy / size[1]
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for xx in range(size[0]):
            img.putpixel((xx, yy), (r, g, b))
    img.save(path)


if __name__ == "__main__":
    make_glasses(os.path.join(STICKERS_DIR, "glasses.png"))
    make_hat(os.path.join(STICKERS_DIR, "hat.png"))
    make_mask(os.path.join(STICKERS_DIR, "mask.png"))
    make_sample_background(os.path.join(BACKGROUNDS_DIR, "sample_studio_bg.jpg"))
    print("Assets generated successfully in /assets/")
