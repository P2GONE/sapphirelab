"""Video mutations (moviepy-based).

Each transform takes a moviepy VideoClip and returns a (lazily-evaluated) clip.
The harness composes a chain in memory and writes the file once at the end —
that keeps the number of ffmpeg encodes to one per case.
"""
import random
from pathlib import Path

from .video_generator import _load_font, _moviepy


def _text_rgba(text: str, size, color=(40, 40, 40), alpha: int = 255,
               font_size: int = 14, position: str = "center"):
    from PIL import Image, ImageDraw
    import numpy as np

    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = 8
    if position == "bottom-right":
        x, y = size[0] - tw - margin, size[1] - th - margin
    elif position == "top-left":
        x, y = margin, margin
    elif position == "top-right":
        x, y = size[0] - tw - margin, margin
    else:
        x, y = (size[0] - tw) // 2, (size[1] - th) // 2
    draw.text((x, y), text, fill=(*color, alpha), font=font)
    return np.array(img)


def _overlay_clip(text, size, duration, color=(40, 40, 40),
                  alpha: int = 255, font_size: int = 14, position: str = "center"):
    arr = _text_rgba(text, size, color=color, alpha=alpha,
                     font_size=font_size, position=position)
    mp = _moviepy()
    return mp["ImageClip"](arr).set_duration(duration).set_position((0, 0))


def frame_overlay_text(clip, text: str, font_size: int = 14,
                       color=(40, 40, 40), alpha: int = 255,
                       position: str = "center"):
    mp = _moviepy()
    overlay = _overlay_clip(text, clip.size, clip.duration,
                            color=color, alpha=alpha,
                            font_size=font_size, position=position)
    return mp["CompositeVideoClip"]([clip, overlay])


def low_contrast_overlay(clip, text: str, font_size: int = 14):
    return frame_overlay_text(clip, text, font_size=font_size,
                              color=(180, 180, 180), alpha=110)


def corner_caption(clip, text: str, font_size: int = 12):
    return frame_overlay_text(clip, text, font_size=font_size,
                              color=(60, 60, 60), position="bottom-right")


def single_hidden_frame(clip, text: str, position_ratio: float = 0.4,
                        font_size: int = 24, frame_duration: float = None):
    """Insert a single high-contrast instruction frame mid-clip."""
    mp = _moviepy()
    fps = clip.fps or 24
    fdur = frame_duration or (1.0 / fps)
    pos_t = max(0.0, min(clip.duration - fdur, clip.duration * position_ratio))
    arr = _text_rgba(text, clip.size, color=(0, 0, 0), alpha=255,
                     font_size=font_size, position="center")
    flash = mp["ImageClip"](arr).set_duration(fdur).set_fps(fps)
    pre = clip.subclip(0, pos_t)
    post = clip.subclip(pos_t, clip.duration)
    return mp["concatenate_videoclips"]([pre, flash, post])


def frame_shuffle(clip, n_segments: int = 4):
    """SI-Attack style — split clip into N segments and shuffle their order."""
    mp = _moviepy()
    seg = clip.duration / n_segments
    parts = [clip.subclip(i * seg, (i + 1) * seg) for i in range(n_segments)]
    random.shuffle(parts)
    return mp["concatenate_videoclips"](parts)


def audio_track_mix(clip, hidden_audio_path: Path,
                    hidden_volume: float = 0.12, position_ratio: float = 0.4):
    """Overlay hidden TTS instruction quietly under the video's audio track."""
    mp = _moviepy()
    base = clip.audio
    hidden = mp["AudioFileClip"](str(hidden_audio_path)).volumex(hidden_volume)
    if hidden.duration > clip.duration:
        hidden = hidden.subclip(0, clip.duration)
    start = clip.duration * max(0.0, min(1.0, position_ratio))
    hidden = hidden.set_start(start)
    if base is None:
        return clip.set_audio(hidden)
    return clip.set_audio(mp["CompositeAudioClip"]([base, hidden]))


# Transforms that fit the clip→clip protocol and only need (clip, text).
TRANSFORMS = {
    "frame_overlay_text": frame_overlay_text,
    "low_contrast_overlay": low_contrast_overlay,
    "corner_caption": corner_caption,
    "single_hidden_frame": single_hidden_frame,
    "frame_shuffle": frame_shuffle,           # ignores text
}

# Which transforms take the seed instruction as their second arg.
NEEDS_TEXT = {
    "frame_overlay_text", "low_contrast_overlay",
    "corner_caption", "single_hidden_frame",
}
