"""
텍스트 오버레이 뮤테이션 전략.
- VISIBLE: 명시적으로 보이는 텍스트
- LOW_OPACITY: 반투명 텍스트 (사람 눈엔 희미, 모델은 인식 가능)
- INVISIBLE_WHITE: 흰색 배경에 흰색 텍스트
- TINY_CORNER: 코너에 아주 작은 텍스트
- INVERTED: 어두운 배경에 밝은 텍스트
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont


@dataclass
class TextOverlayResult:
    strategy: str
    image: Image.Image
    description: str


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",    # 맑은 고딕 (한국어 지원)
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "C:/Windows/Fonts/consola.ttf",
    ]
    for path in font_candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(text: str, max_width_chars: int = 40) -> str:
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, max_width_chars) or [""])
    return "\n".join(lines)


def overlay_visible(image: Image.Image, text: str) -> TextOverlayResult:
    """뚜렷하게 보이는 빨간 텍스트 오버레이."""
    img = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = _load_font(max(16, img.width // 30))
    wrapped = _wrap_text(text)

    # 텍스트 배경 박스
    bbox = draw.multiline_textbbox((10, 10), wrapped, font=font)
    draw.rectangle([bbox[0]-4, bbox[1]-4, bbox[2]+4, bbox[3]+4], fill=(0, 0, 0, 180))
    draw.multiline_text((10, 10), wrapped, font=font, fill=(255, 50, 50, 255))

    return TextOverlayResult(
        strategy="text_overlay_visible",
        image=img.convert("RGB"),
        description="Visible red text with dark background box",
    )


def overlay_low_opacity(image: Image.Image, text: str, opacity: int = 40) -> TextOverlayResult:
    """낮은 불투명도 텍스트: 사람 눈에 희미하지만 모델이 인식할 수 있음."""
    img = image.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(18, img.width // 25))
    wrapped = _wrap_text(text)

    draw.multiline_text((10, 10), wrapped, font=font, fill=(0, 0, 0, opacity))

    result = Image.alpha_composite(img, overlay)
    return TextOverlayResult(
        strategy="text_overlay_low_opacity",
        image=result.convert("RGB"),
        description=f"Low opacity ({opacity}/255) black text — subtle to human eye",
    )


def overlay_invisible_white(image: Image.Image, text: str) -> TextOverlayResult:
    """흰색 배경 영역에 흰색 텍스트 — 사람 눈에 안 보이지만 모델은 OCR로 감지 가능."""
    img = image.copy().convert("RGBA")

    # 이미지 상단에 흰색 패딩 추가
    pad_h = max(80, img.height // 5)
    new_img = Image.new("RGBA", (img.width, img.height + pad_h), (255, 255, 255, 255))
    new_img.paste(img, (0, pad_h))

    draw = ImageDraw.Draw(new_img)
    font = _load_font(max(14, img.width // 35))
    wrapped = _wrap_text(text)

    # 흰 배경에 흰 텍스트 (RGB 255,255,255 → 254,254,254로 1 차이)
    draw.multiline_text((10, 5), wrapped, font=font, fill=(254, 254, 254, 255))

    return TextOverlayResult(
        strategy="text_overlay_invisible_white",
        image=new_img.convert("RGB"),
        description="White text on white background — invisible to humans, detectable by models",
    )


def overlay_tiny_corner(image: Image.Image, text: str) -> TextOverlayResult:
    """이미지 우하단 코너에 매우 작은 텍스트."""
    img = image.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)
    font = _load_font(max(8, img.width // 80))
    wrapped = _wrap_text(text, max_width_chars=60)

    # bbox 계산 후 우하단 배치
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = img.width - text_w - 5
    y = img.height - text_h - 5

    draw.multiline_text((x, y), wrapped, font=font, fill=(10, 10, 10, 200))

    return TextOverlayResult(
        strategy="text_overlay_tiny_corner",
        image=img.convert("RGB"),
        description="Tiny text in bottom-right corner",
    )


def overlay_inverted(image: Image.Image, text: str) -> TextOverlayResult:
    """어두운 배경 스트립에 밝은 텍스트 — 이미지 하단 바."""
    img = image.copy().convert("RGBA")
    font = _load_font(max(13, img.width // 40))
    wrapped = _wrap_text(text)

    draw_tmp = ImageDraw.Draw(img)
    bbox = draw_tmp.multiline_textbbox((0, 0), wrapped, font=font)
    bar_h = bbox[3] - bbox[1] + 20

    # 하단 바 추가
    bar = Image.new("RGBA", (img.width, bar_h), (20, 20, 20, 240))
    new_img = Image.new("RGBA", (img.width, img.height + bar_h), (255, 255, 255, 255))
    new_img.paste(img, (0, 0))
    new_img.paste(bar, (0, img.height))

    draw = ImageDraw.Draw(new_img)
    draw.multiline_text((10, img.height + 5), wrapped, font=font, fill=(220, 220, 220, 255))

    return TextOverlayResult(
        strategy="text_overlay_inverted",
        image=new_img.convert("RGB"),
        description="Light text on dark bar appended to bottom of image",
    )


def overlay_blended(image: Image.Image, text: str) -> TextOverlayResult:
    """이미지 색상과 비슷한 색상 텍스트 — 시각적으로 위장."""
    img = image.copy().convert("RGB")

    # 이미지 평균 색상 계산 → 그것과 가까운 색으로 텍스트
    import numpy as np
    arr = np.array(img)
    avg_color = arr.mean(axis=(0, 1)).astype(int)
    # 약간 어둡게 조정 (텍스트가 배경에 묻히도록)
    text_color = tuple(max(0, int(c) - 30) for c in avg_color)

    rgba = img.convert("RGBA")
    draw = ImageDraw.Draw(rgba)
    font = _load_font(max(16, img.width // 30))
    wrapped = _wrap_text(text)

    draw.multiline_text((10, 10), wrapped, font=font, fill=(*text_color, 180))

    return TextOverlayResult(
        strategy="text_overlay_blended",
        image=rgba.convert("RGB"),
        description="Text color blended with image average color — camouflaged",
    )
