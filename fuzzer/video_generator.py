"""Generate carrier videos for the video modality (moviepy + PIL)."""
from pathlib import Path

from ._fonts import load_font as _load_font


def _moviepy():
    try:
        from moviepy.editor import (
            ImageClip, AudioFileClip, VideoFileClip,
            CompositeVideoClip, CompositeAudioClip, concatenate_videoclips,
        )
        return dict(ImageClip=ImageClip, AudioFileClip=AudioFileClip,
                    VideoFileClip=VideoFileClip,
                    CompositeVideoClip=CompositeVideoClip,
                    CompositeAudioClip=CompositeAudioClip,
                    concatenate_videoclips=concatenate_videoclips)
    except ImportError:
        from moviepy import (
            ImageClip, AudioFileClip, VideoFileClip,
            CompositeVideoClip, CompositeAudioClip, concatenate_videoclips,
        )
        return dict(ImageClip=ImageClip, AudioFileClip=AudioFileClip,
                    VideoFileClip=VideoFileClip,
                    CompositeVideoClip=CompositeVideoClip,
                    CompositeAudioClip=CompositeAudioClip,
                    concatenate_videoclips=concatenate_videoclips)


def make_carrier_video(out_path: Path, audio_path: Path = None,
                       duration: float = 4.0, size=(640, 480),
                       caption: str = "STYLE MARKET — Product Showcase") -> Path:
    """Synthesize a short product showcase clip used as the benign carrier."""
    from PIL import Image, ImageDraw
    import numpy as np

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", size, (240, 235, 230))
    draw = ImageDraw.Draw(img)
    font = _load_font(32)
    bbox = draw.textbbox((0, 0), caption, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size[0] - tw) // 2, (size[1] - th) // 2),
              caption, fill=(60, 60, 60), font=font)

    mp = _moviepy()
    bg = mp["ImageClip"](np.array(img)).set_duration(duration).set_fps(24)
    if audio_path and Path(audio_path).exists():
        a = mp["AudioFileClip"](str(audio_path))
        if a.duration > duration:
            a = a.subclip(0, duration)
        bg = bg.set_audio(a)

    write_kwargs = dict(fps=24, codec="libx264", audio_codec="aac",
                        logger=None)
    try:
        bg.write_videofile(str(out_path), verbose=False, **write_kwargs)
    except TypeError:  # moviepy v2 dropped `verbose`
        bg.write_videofile(str(out_path), **write_kwargs)
    bg.close()
    return out_path
