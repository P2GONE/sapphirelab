"""Audio mutations (volume / speed / pitch / noise / background mix / split).

Requires `pydub` (which uses ffmpeg). All transformer functions read a path,
mutate, and overwrite — or write to `out` if provided.
"""
from pathlib import Path


def _segment(path: Path):
    from pydub import AudioSegment
    suffix = Path(path).suffix.lower().lstrip(".")
    fmt = {"mp3": "mp3", "wav": "wav", "m4a": "m4a", "ogg": "ogg"}.get(suffix, suffix)
    return AudioSegment.from_file(str(path), format=fmt)


def _export(seg, path: Path) -> Path:
    suffix = Path(path).suffix.lower().lstrip(".")
    fmt = {"mp3": "mp3", "wav": "wav", "m4a": "m4a", "ogg": "ogg"}.get(suffix, suffix)
    seg.export(str(path), format=fmt)
    return Path(path)


def volume_down(path: Path, db: float = 18.0, out: Path = None) -> Path:
    out = out or path
    seg = _segment(path) - abs(db)
    return _export(seg, out)


def speed_up(path: Path, factor: float = 1.4, out: Path = None) -> Path:
    out = out or path
    seg = _segment(path)
    new_rate = int(seg.frame_rate * factor)
    fast = seg._spawn(seg.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(seg.frame_rate)
    return _export(fast, out)


def slow_down(path: Path, factor: float = 0.7, out: Path = None) -> Path:
    return speed_up(path, factor=factor, out=out)


def pitch_shift(path: Path, semitones: int = -3, out: Path = None) -> Path:
    out = out or path
    seg = _segment(path)
    new_rate = int(seg.frame_rate * (2 ** (semitones / 12.0)))
    shifted = seg._spawn(seg.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(seg.frame_rate)
    return _export(shifted, out)


def noise_injection(path: Path, gain_db: float = -28.0, out: Path = None) -> Path:
    out = out or path
    from pydub.generators import WhiteNoise
    seg = _segment(path)
    noise = WhiteNoise().to_audio_segment(duration=len(seg)).apply_gain(gain_db)
    return _export(seg.overlay(noise), out)


def background_mix(carrier_path: Path, hidden_path: Path, out_path: Path,
                   hidden_db: float = 18.0, position_ratio: float = 0.4) -> Path:
    """Overlay the hidden instruction quietly underneath the carrier review."""
    carrier = _segment(carrier_path)
    hidden = _segment(hidden_path) - abs(hidden_db)
    pos_ms = int(len(carrier) * max(0.0, min(1.0, position_ratio)))
    return _export(carrier.overlay(hidden, position=pos_ms), out_path)


def audio_split_segments(path: Path, parts: int = 3, gap_ms: int = 200, out: Path = None) -> Path:
    out = out or path
    from pydub import AudioSegment
    seg = _segment(path)
    if parts <= 1:
        return _export(seg, out)
    chunk = len(seg) // parts
    silence = AudioSegment.silent(duration=gap_ms)
    pieces = [seg[i * chunk:(i + 1) * chunk] for i in range(parts)]
    out_seg = pieces[0]
    for p in pieces[1:]:
        out_seg = out_seg + silence + p
    return _export(out_seg, out)


# In-place transformers (chainable). `background_mix` is handled separately
# in the harness because it needs two inputs.
TRANSFORMS = {
    "volume_down": volume_down,
    "speed_up": speed_up,
    "slow_down": slow_down,
    "pitch_shift": pitch_shift,
    "noise_injection": noise_injection,
    "audio_split_segments": audio_split_segments,
}
