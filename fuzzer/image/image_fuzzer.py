"""
Image Fuzzer — 뮤테이션 전략별 변형 이미지를 생성하는 메인 클래스.

지원 전략:
  text_overlay_visible        — 뚜렷하게 보이는 텍스트
  text_overlay_low_opacity    — 반투명 텍스트 (시각적으로 희미)
  text_overlay_invisible_white — 흰 배경에 흰 텍스트
  text_overlay_tiny_corner    — 코너 초소형 텍스트
  text_overlay_inverted       — 어두운 바에 밝은 텍스트
  text_overlay_blended        — 이미지 배경색과 유사한 텍스트
  steganography_lsb           — LSB 스테가노그래피 (전체 채널)
  steganography_lsb_blue      — LSB 스테가노그래피 (Blue 채널)
  metadata_exif               — EXIF 전체 필드 주입
  metadata_exif_description   — EXIF ImageDescription만 주입
  adversarial_gaussian_noise  — 가우시안 노이즈
  adversarial_pixel_grid      — 픽셀 그리드 이진 인코딩
  adversarial_channel_signal  — 채널 LSB 신호 인코딩
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from PIL import Image

from fuzzer.image.mutations import text_overlay, steganography, adversarial, metadata
from payloads.injection_payloads import InjectionPayload


class MutationStrategy(str, Enum):
    TEXT_OVERLAY_VISIBLE         = "text_overlay_visible"
    TEXT_OVERLAY_LOW_OPACITY     = "text_overlay_low_opacity"
    TEXT_OVERLAY_INVISIBLE_WHITE = "text_overlay_invisible_white"
    TEXT_OVERLAY_TINY_CORNER     = "text_overlay_tiny_corner"
    TEXT_OVERLAY_INVERTED        = "text_overlay_inverted"
    TEXT_OVERLAY_BLENDED         = "text_overlay_blended"
    STEGANOGRAPHY_LSB            = "steganography_lsb"
    STEGANOGRAPHY_LSB_BLUE       = "steganography_lsb_blue"
    METADATA_EXIF                = "metadata_exif"
    METADATA_EXIF_DESCRIPTION    = "metadata_exif_description"
    ADVERSARIAL_GAUSSIAN_NOISE   = "adversarial_gaussian_noise"
    ADVERSARIAL_PIXEL_GRID       = "adversarial_pixel_grid"
    ADVERSARIAL_CHANNEL_SIGNAL   = "adversarial_channel_signal"


ALL_STRATEGIES = list(MutationStrategy)


@dataclass
class MutatedImage:
    payload_id:   str
    payload_text: str
    strategy:     MutationStrategy
    image_bytes:  bytes
    description:  str
    save_path:    Optional[Path] = None
    error:        Optional[str]  = None


class ImageFuzzer:
    """
    베이스 이미지 + 페이로드 → 뮤테이션된 이미지 생성.

    사용법:
        fuzzer  = ImageFuzzer(base_image_path="samples/product.jpg")
        results = fuzzer.fuzz(payload, strategies=[MutationStrategy.TEXT_OVERLAY_VISIBLE])
    """

    def __init__(
        self,
        base_image_path: Optional[str | Path] = None,
        base_image: Optional[Image.Image] = None,
        output_dir: Optional[Path] = None,
        save_images: bool = True,
    ):
        if base_image is not None:
            self._base = base_image.copy()
        elif base_image_path is not None:
            self._base = Image.open(base_image_path).convert("RGB")
        else:
            self._base = self._create_default_base()

        self.output_dir  = output_dir or Path("output")
        self.save_images = save_images

    # ── Public API ──────────────────────────────────────────────────────────

    def fuzz(
        self,
        payload: InjectionPayload,
        strategies: Optional[list[MutationStrategy]] = None,
    ) -> list[MutatedImage]:
        target_strategies = strategies or ALL_STRATEGIES
        results: list[MutatedImage] = []
        for strategy in target_strategies:
            result = self._apply(payload, strategy)
            if self.save_images and result.error is None:
                result.save_path = self._save(result, payload.id)
            results.append(result)
        return results

    def fuzz_all_payloads(
        self,
        payloads: list[InjectionPayload],
        strategies: Optional[list[MutationStrategy]] = None,
    ) -> list[MutatedImage]:
        all_results: list[MutatedImage] = []
        for payload in payloads:
            all_results.extend(self.fuzz(payload, strategies))
        return all_results

    # ── Strategy dispatch ───────────────────────────────────────────────────

    def _apply(self, payload: InjectionPayload, strategy: MutationStrategy) -> MutatedImage:
        text = payload.text
        try:
            img_bytes, description = self._dispatch(strategy, text)
            return MutatedImage(
                payload_id=payload.id,
                payload_text=text,
                strategy=strategy,
                image_bytes=img_bytes,
                description=description,
            )
        except Exception as exc:
            return MutatedImage(
                payload_id=payload.id,
                payload_text=text,
                strategy=strategy,
                image_bytes=b"",
                description="",
                error=str(exc),
            )

    def _dispatch(self, strategy: MutationStrategy, text: str) -> tuple[bytes, str]:
        base = self._base.copy()

        if strategy == MutationStrategy.TEXT_OVERLAY_VISIBLE:
            r = text_overlay.overlay_visible(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.TEXT_OVERLAY_LOW_OPACITY:
            r = text_overlay.overlay_low_opacity(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.TEXT_OVERLAY_INVISIBLE_WHITE:
            r = text_overlay.overlay_invisible_white(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.TEXT_OVERLAY_TINY_CORNER:
            r = text_overlay.overlay_tiny_corner(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.TEXT_OVERLAY_INVERTED:
            r = text_overlay.overlay_inverted(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.TEXT_OVERLAY_BLENDED:
            r = text_overlay.overlay_blended(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.STEGANOGRAPHY_LSB:
            r = steganography.encode_lsb(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.STEGANOGRAPHY_LSB_BLUE:
            r = steganography.encode_lsb_channel(base, text, channel=2)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.METADATA_EXIF:
            r = metadata.inject_exif(base, text)
            return r.image_bytes, r.description

        if strategy == MutationStrategy.METADATA_EXIF_DESCRIPTION:
            r = metadata.inject_exif_description_only(base, text)
            return r.image_bytes, r.description

        if strategy == MutationStrategy.ADVERSARIAL_GAUSSIAN_NOISE:
            r = adversarial.add_gaussian_noise(base)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.ADVERSARIAL_PIXEL_GRID:
            r = adversarial.pixel_grid_encode(base, text)
            return _pil_to_bytes(r.image), r.description

        if strategy == MutationStrategy.ADVERSARIAL_CHANNEL_SIGNAL:
            r = adversarial.color_channel_signal(base, text)
            return _pil_to_bytes(r.image), r.description

        raise ValueError(f"Unknown strategy: {strategy}")

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _save(self, result: MutatedImage, payload_id: str) -> Path:
        subdir = self.output_dir / payload_id
        subdir.mkdir(parents=True, exist_ok=True)
        ext  = "jpg" if not result.strategy.value.startswith("steganography") else "png"
        path = subdir / f"{result.strategy.value}.{ext}"
        path.write_bytes(result.image_bytes)
        return path

    @staticmethod
    def _create_default_base(width: int = 512, height: int = 512) -> Image.Image:
        from PIL import ImageDraw
        img  = Image.new("RGB", (width, height), (245, 245, 245))
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 462, 462], outline=(200, 200, 200), width=2)
        draw.text((width // 2 - 60, height // 2 - 10), "[Product Image]", fill=(180, 180, 180))
        return img


def _pil_to_bytes(img: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=95)
    return buf.getvalue()
