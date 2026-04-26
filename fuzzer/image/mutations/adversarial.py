"""
적대적 시각 패턴 뮤테이션.
- Typography noise: 텍스트처럼 보이는 픽셀 패턴
- Grid-encoded text: 픽셀 그리드에 ASCII 인코딩
- Gaussian noise with embedded signal
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class AdversarialResult:
    strategy: str
    image: Image.Image
    description: str


def add_gaussian_noise(image: Image.Image, std: float = 8.0) -> AdversarialResult:
    """
    가우시안 노이즈 추가.
    페이로드를 노이즈에 직접 인코딩하는 것이 아니라
    모델의 이미지 인식을 교란하는 기본 노이즈 베이스라인.
    """
    img = image.copy().convert("RGB")
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, std, arr.shape)
    noisy = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return AdversarialResult(
        strategy="adversarial_gaussian_noise",
        image=Image.fromarray(noisy, "RGB"),
        description=f"Gaussian noise (std={std}) added — baseline perceptual disruption",
    )


def pixel_grid_encode(image: Image.Image, text: str) -> AdversarialResult:
    """
    이미지 우하단 코너의 픽셀 그리드에 ASCII 바이너리 인코딩.
    각 비트 = 1픽셀 (흰색=1, 검은색=0).
    사람 눈에는 작은 흑백 패턴으로 보이지만 이진 데이터를 담음.
    """
    img = image.copy().convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    payload_bits = []
    for char in text.encode("utf-8") + b"\x00":
        for i in range(7, -1, -1):
            payload_bits.append((char >> i) & 1)

    n_bits = len(payload_bits)
    grid_side = int(np.ceil(np.sqrt(n_bits)))
    grid_w = grid_h = grid_side
    pixel_size = max(2, min(4, (img.width // 4) // grid_w))

    total_w = grid_w * pixel_size
    total_h = grid_h * pixel_size

    if total_w > img.width or total_h > img.height:
        return AdversarialResult(
            strategy="adversarial_pixel_grid",
            image=img,
            description="Image too small for pixel grid encoding — skipped",
        )

    x_offset = img.width - total_w - 2
    y_offset = img.height - total_h - 2

    for idx, bit in enumerate(payload_bits):
        row = idx // grid_w
        col = idx % grid_w
        px = x_offset + col * pixel_size
        py = y_offset + row * pixel_size
        color = 255 if bit else 0
        arr[py:py+pixel_size, px:px+pixel_size] = color

    return AdversarialResult(
        strategy="adversarial_pixel_grid",
        image=Image.fromarray(arr, "RGB"),
        description=f"Binary payload encoded as {grid_w}x{grid_h} pixel grid in bottom-right corner",
    )


def color_channel_signal(image: Image.Image, text: str, channel: int = 2) -> AdversarialResult:
    """
    특정 색상 채널(기본 Blue)의 규칙적인 픽셀에 신호 패턴 삽입.
    채널 값을 짝수(0)/홀수(1)로 조정해 비트 인코딩.
    """
    img = image.copy().convert("RGB")
    arr = np.array(img, dtype=np.uint8)

    payload_bits = []
    for byte in text.encode("utf-8") + b"\x00":
        for i in range(7, -1, -1):
            payload_bits.append((byte >> i) & 1)

    h, w = arr.shape[:2]
    positions = [(r, c) for r in range(0, h, 4) for c in range(0, w, 4)]

    if len(payload_bits) > len(positions):
        return AdversarialResult(
            strategy="adversarial_channel_signal",
            image=img,
            description="Image too small for channel signal encoding — skipped",
        )

    for idx, bit in enumerate(payload_bits):
        r, c = positions[idx]
        val = int(arr[r, c, channel])
        if bit == 1:
            arr[r, c, channel] = np.uint8(val | 1)
        else:
            arr[r, c, channel] = np.uint8(val & 0xFE)

    channel_name = {0: "Red", 1: "Green", 2: "Blue"}.get(channel, str(channel))
    return AdversarialResult(
        strategy="adversarial_channel_signal",
        image=Image.fromarray(arr, "RGB"),
        description=f"Payload encoded as LSB signal in every 4th pixel of {channel_name} channel",
    )
