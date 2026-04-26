"""Generate base images carrying hidden text instructions."""
import random
from pathlib import Path

from PIL import Image, ImageDraw

from ._fonts import load_font as _load_font


CARRIERS_DIR = Path(__file__).resolve().parents[2] / "vlm-shop-chatbot" / "static" / "images"


def _wrapped_lines(draw, text, font, max_w):
    words = text.split()
    lines, line = [], ""
    for w in words:
        cand = (line + " " + w).strip()
        bbox = draw.textbbox((0, 0), cand, font=font)
        if bbox[2] - bbox[0] > max_w and line:
            lines.append(line)
            line = w
        else:
            line = cand
    if line:
        lines.append(line)
    return lines


def make_text_image(text: str, size=(640, 640), bg=(255, 255, 255),
                    fg=(0, 0, 0), font_size: int = 28) -> Image.Image:
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    margin = 24
    lines = _wrapped_lines(draw, text, font, size[0] - margin * 2)
    y = margin
    for ln in lines:
        draw.text((margin, y), ln, fill=fg, font=font)
        bbox = draw.textbbox((0, 0), ln, font=font)
        y += (bbox[3] - bbox[1]) + 6
    return img


def overlay_on_carrier(text: str, carrier_path: Path = None,
                       font_size: int = 14, position: str = "bottom-right",
                       fg=(40, 40, 40)) -> Image.Image:
    if carrier_path and Path(carrier_path).exists():
        img = Image.open(carrier_path).convert("RGB").resize((640, 640))
    else:
        img = Image.new("RGB", (640, 640), (240, 235, 230))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = 8
    if position == "bottom-right":
        x, y = img.width - tw - margin, img.height - th - margin
    elif position == "top-left":
        x, y = margin, margin
    elif position == "top-right":
        x, y = img.width - tw - margin, margin
    else:
        x, y = (img.width - tw) // 2, (img.height - th) // 2
    draw.text((x, y), text, fill=fg, font=font)
    return img


def list_carriers():
    if not CARRIERS_DIR.exists():
        return []
    return [p for p in CARRIERS_DIR.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg")]


def random_carrier():
    options = list_carriers()
    return random.choice(options) if options else None
