"""
이미지 메타데이터(EXIF) 주입.
일부 멀티모달 모델이 EXIF를 컨텍스트로 읽는 경우를 테스트.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

import piexif
from PIL import Image


@dataclass
class MetadataResult:
    strategy: str
    image_bytes: bytes
    injected_fields: dict
    description: str


_EXIF_FIELD_MAP = {
    "ImageDescription": (piexif.ImageIFD.ImageDescription, "0th"),
    "Artist":           (piexif.ImageIFD.Artist,           "0th"),
    "Copyright":        (piexif.ImageIFD.Copyright,        "0th"),
    "Make":             (piexif.ImageIFD.Make,             "0th"),
    "Model":            (piexif.ImageIFD.Model,            "0th"),
    "Software":         (piexif.ImageIFD.Software,         "0th"),
    "UserComment":      (piexif.ExifIFD.UserComment,       "Exif"),
}


def inject_exif(image: Image.Image, payload: str) -> MetadataResult:
    """
    EXIF의 주요 텍스트 필드 전체에 페이로드 삽입.
    모델이 메타데이터를 컨텍스트로 참조하는 경우 탐지.
    """
    img = image.copy().convert("RGB")
    encoded = payload.encode("utf-8")

    exif_dict: dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    injected_fields = {}
    for field_name, (tag, ifd) in _EXIF_FIELD_MAP.items():
        if field_name == "UserComment":
            # UserComment 는 앞에 8바이트 charset 헤더 필요
            value = b"UNICODE\x00" + payload.encode("utf-16-be")
        else:
            value = encoded
        exif_dict[ifd][tag] = value
        injected_fields[field_name] = payload

    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes, quality=95)
    buf.seek(0)

    return MetadataResult(
        strategy="metadata_exif_injection",
        image_bytes=buf.read(),
        injected_fields=injected_fields,
        description="Payload injected into EXIF ImageDescription, Artist, Copyright, UserComment, etc.",
    )


def inject_exif_description_only(image: Image.Image, payload: str) -> MetadataResult:
    """ImageDescription 필드에만 삽입 — 가장 기본적인 메타데이터 주입."""
    img = image.copy().convert("RGB")
    exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}
    exif_dict["0th"][piexif.ImageIFD.ImageDescription] = payload.encode("utf-8")

    exif_bytes = piexif.dump(exif_dict)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif_bytes, quality=95)
    buf.seek(0)

    return MetadataResult(
        strategy="metadata_exif_description",
        image_bytes=buf.read(),
        injected_fields={"ImageDescription": payload},
        description="Payload injected into EXIF ImageDescription field only",
    )
