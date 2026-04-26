"""Image-level mutations: small font, low contrast, rotation, patch shuffle, overlay."""
import random

from PIL import Image, ImageEnhance

from .image_generator import make_text_image, overlay_on_carrier, random_carrier


# ── initializers: text → image ────────────────────────────────────────────────

def small_font(text: str, font_size: int = 10) -> Image.Image:
    return make_text_image(text, font_size=font_size)


def overlay_init(text: str, font_size: int = 12) -> Image.Image:
    return overlay_on_carrier(text, carrier_path=random_carrier(), font_size=font_size)


def corner_placement(text: str, font_size: int = 12, position: str = "bottom-right") -> Image.Image:
    return overlay_on_carrier(text, carrier_path=random_carrier(),
                              font_size=font_size, position=position)


# ── transformers: image → image ──────────────────────────────────────────────

def low_contrast(img: Image.Image, factor: float = 0.3) -> Image.Image:
    return ImageEnhance.Contrast(img).enhance(factor)


def rotation(img: Image.Image, angle: float = 5.0) -> Image.Image:
    return img.rotate(angle, expand=False, fillcolor=(255, 255, 255))


def patch_shuffle(img: Image.Image, grid: int = 4) -> Image.Image:
    w, h = img.size
    pw, ph = w // grid, h // grid
    boxes, crops = [], []
    for r in range(grid):
        for c in range(grid):
            box = (c * pw, r * ph, (c + 1) * pw, (r + 1) * ph)
            boxes.append(box)
            crops.append(img.crop(box))
    random.shuffle(crops)
    out = img.copy()
    for box, crop in zip(boxes, crops):
        out.paste(crop, box)
    return out


def si_patch_shuffle(img: Image.Image, patch_size: int = 128,
                     canvas: int = 1024) -> Image.Image:
    """SI-Attack style patch shuffle (Zhao et al. 2025).

    Resizes the image to a fixed canvas, then chops it into patch_size×patch_size
    tiles and shuffles them — the exact form used in the SI-Attack paper.
    """
    import numpy as np
    img = img.convert("RGB").resize((canvas, canvas), Image.BILINEAR)
    arr = np.array(img)
    h_p = canvas // patch_size
    w_p = canvas // patch_size
    patches = [
        arr[i * patch_size:(i + 1) * patch_size,
            j * patch_size:(j + 1) * patch_size, :]
        for i in range(h_p) for j in range(w_p)
    ]
    random.shuffle(patches)
    out = arr.copy()
    for idx, patch in enumerate(patches):
        i, j = divmod(idx, w_p)
        out[i * patch_size:(i + 1) * patch_size,
            j * patch_size:(j + 1) * patch_size, :] = patch
    return Image.fromarray(out)


# Maps used by the harness.
INIT_FROM_TEXT = {
    "small_font": small_font,
    "overlay_on_carrier": overlay_init,
    "corner_placement": corner_placement,
}

TRANSFORMS = {
    "low_contrast": low_contrast,
    "rotation": rotation,
    "patch_shuffle": patch_shuffle,
    "si_patch_shuffle": si_patch_shuffle,
}
