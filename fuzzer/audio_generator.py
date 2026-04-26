"""Generate audio payloads via TTS + carrier review preparation."""
import struct
import wave
from pathlib import Path


CARRIER_REVIEW_TEXT = (
    "Hello, I bought the white sneakers last week. The fit is great, "
    "shipping was fast, and the quality looks solid. Highly recommend."
)


def _silence_wav(out_path: Path, seconds: float = 1.0, rate: int = 22050) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = int(rate * seconds)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack("<" + "h" * n, *([0] * n)))
    return out_path


def tts(text: str, out_path: Path) -> Path:
    """Synthesize speech via gTTS. Falls back to silence wav so the pipeline still runs."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from gtts import gTTS
        gTTS(text=text, lang="en").save(str(out_path))
        return out_path
    except Exception as e:
        fallback = out_path.with_suffix(".wav")
        print(f"[audio] gTTS failed ({e}); writing silence -> {fallback}")
        return _silence_wav(fallback, seconds=2)


def make_carrier(out_path: Path, text: str = CARRIER_REVIEW_TEXT) -> Path:
    return tts(text, out_path)


def make_seed_audio(seed_text: str, out_path: Path) -> Path:
    return tts(seed_text, out_path)
