"""Font discovery for image/video text overlays.

Resolution order:
  1. $MMFUZZ_FONT  — explicit override
  2. OS-specific candidate paths (macOS / Linux / Windows)
  3. matplotlib.font_manager (if installed) — system-wide search
  4. PIL ImageFont.load_default(size)   (PIL >= 10)
  5. PIL ImageFont.load_default()       (legacy bitmap fallback — small)

The discovered path is memoized; pass `--font /path/to.ttf` style overrides
through the env var if needed.
"""
import functools
import os


_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    # Linux (Debian/Ubuntu, Fedora, Arch)
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    # Windows
    "C:\\Windows\\Fonts\\arial.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
]


@functools.lru_cache(maxsize=1)
def _discover_path():
    env = os.environ.get("MMFUZZ_FONT")
    if env and os.path.isfile(env):
        return env
    for p in _CANDIDATES:
        if os.path.isfile(p):
            return p
    try:
        from matplotlib import font_manager
        return font_manager.findfont(
            font_manager.FontProperties(family="sans-serif"),
            fallback_to_default=True,
        )
    except Exception:
        return None


def load_font(size: int):
    """Return a PIL ImageFont sized to `size`, with graceful fallbacks."""
    from PIL import ImageFont
    path = _discover_path()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # PIL >= 10 supports a size argument on the default bundled font.
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()
