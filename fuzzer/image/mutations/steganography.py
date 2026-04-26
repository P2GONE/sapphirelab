"""
LSB(Least Significant Bit) 스테가노그래피.
픽셀 최하위 비트에 텍스트를 인코딩 — 육안으로 완전히 불가시.
멀티모달 모델이 이미지를 직접 읽는 경우엔 탐지되지 않지만,
모델이 이미지를 세밀하게 분석할 경우 패턴을 감지할 가능성 테스트.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class StegoResult:
    strategy: str
    image: Image.Image
    encoded_text: str
    description: str


def encode_lsb(image: Image.Image, text: str) -> StegoResult:
    """
    RGB 각 채널의 LSB에 UTF-8 텍스트를 인코딩.
    텍스트는 NULL 종료자(b'\\x00')로 구분.
    """
    img = image.copy().convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    payload = text.encode("utf-8") + b"\x00"
    bits = _bytes_to_bits(payload)

    capacity = arr.size  # R,G,B 각 픽셀당 1비트
    if len(bits) > capacity:
        raise ValueError(
            f"Image too small for payload: needs {len(bits)} bits, has {capacity}"
        )

    flat = arr.flatten()
    for i, bit in enumerate(bits):
        flat[i] = (flat[i] & 0xFE) | bit  # LSB 교체

    encoded_arr = flat.reshape(arr.shape)
    encoded_img = Image.fromarray(encoded_arr, "RGB")

    return StegoResult(
        strategy="steganography_lsb",
        image=encoded_img,
        encoded_text=text,
        description="LSB steganography — text hidden in pixel LSBs, visually identical",
    )


def decode_lsb(image: Image.Image) -> str:
    """LSB 인코딩된 이미지에서 텍스트 복원 (검증용)."""
    arr = np.array(image.convert("RGB"), dtype=np.uint8)
    bits = [int(px & 1) for px in arr.flatten()]
    return _bits_to_text(bits)


def encode_lsb_channel(image: Image.Image, text: str, channel: int = 2) -> StegoResult:
    """
    특정 단일 채널(기본: Blue=2)의 LSB에만 인코딩.
    변조 픽셀 수가 줄어 통계적 탐지가 더 어려움.
    """
    img = image.copy().convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    payload = text.encode("utf-8") + b"\x00"
    bits = _bytes_to_bits(payload)

    channel_flat = arr[:, :, channel].flatten()
    if len(bits) > len(channel_flat):
        raise ValueError(
            f"Channel too small: needs {len(bits)} bits, channel has {len(channel_flat)}"
        )

    for i, bit in enumerate(bits):
        channel_flat[i] = (channel_flat[i] & 0xFE) | bit

    arr[:, :, channel] = channel_flat.reshape(arr[:, :, channel].shape)
    encoded_img = Image.fromarray(arr, "RGB")

    channel_name = {0: "Red", 1: "Green", 2: "Blue"}.get(channel, str(channel))
    return StegoResult(
        strategy=f"steganography_lsb_{channel_name.lower()}",
        image=encoded_img,
        encoded_text=text,
        description=f"LSB steganography in {channel_name} channel only",
    )


# ── helpers ───────────────────────────────────────────────────────────────

def _bytes_to_bits(data: bytes) -> list[int]:
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_text(bits: list[int]) -> str:
    chars = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        if byte == 0:
            break
        chars.append(byte)
    return bytes(chars).decode("utf-8", errors="replace")
