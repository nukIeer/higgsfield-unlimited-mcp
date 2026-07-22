"""Canonical pixel dimensions for aspect ratios and resolutions."""

from __future__ import annotations

# Base dimensions at "1k" tier. Values are multiples of 32 to satisfy most
# diffusion backends.
_BASE_1K: dict[str, tuple[int, int]] = {
    "1:1": (1024, 1024),
    "16:9": (1344, 768),
    "9:16": (768, 1344),
    "4:3": (1152, 896),
    "3:4": (896, 1152),
    "3:2": (1216, 832),
    "2:3": (832, 1216),
    "21:9": (1536, 640),
    "9:21": (640, 1536),
    "5:4": (1152, 928),
    "4:5": (928, 1152),
    "2:1": (1408, 704),
    "1:2": (704, 1408),
}

_RESOLUTION_SCALE: dict[str, float] = {
    "1k": 1.0,
    "2k": 1.5,
    "4k": 3.0,
}

ASPECT_RATIOS = tuple(_BASE_1K.keys())
RESOLUTIONS = tuple(_RESOLUTION_SCALE.keys())


def _round32(x: float) -> int:
    return max(32, int(round(x / 32.0)) * 32)


# Video resolution tiers -> short-side pixel length.
_VIDEO_SHORT_SIDE: dict[str, int] = {
    "480p": 480,
    "720p": 720,
    "1080p": 1080,
    "4k": 2160,
    "2160p": 2160,
}


def _round_even(x: float) -> int:
    return max(2, int(round(x / 2.0)) * 2)


def video_dimensions(aspect_ratio: str, resolution: str = "720p") -> tuple[int, int]:
    """Return (width, height) for a video aspect ratio + resolution tier.

    The short side is fixed by the tier (720p -> 720px short side); the long side
    follows the aspect ratio. Values are rounded to even numbers (codec-friendly).
    The server recomputes exact dims, so this only needs to be valid and consistent.
    """
    res = resolution.strip().lower()
    short = _VIDEO_SHORT_SIDE.get(res)
    if short is None:
        raise ValueError(
            f"Unknown video resolution {resolution!r}. Supported: {', '.join(_VIDEO_SHORT_SIDE)}"
        )
    try:
        w_ratio, h_ratio = (float(p) for p in aspect_ratio.split(":"))
    except ValueError as exc:
        raise ValueError(f"Bad aspect ratio {aspect_ratio!r}, expected 'W:H'.") from exc
    ratio = w_ratio / h_ratio
    if ratio <= 1:  # portrait / square: short side is the width
        return _round_even(short), _round_even(short / ratio)
    return _round_even(short * ratio), _round_even(short)  # landscape: short side is height


def get_dimensions(aspect_ratio: str, resolution: str = "2k") -> tuple[int, int]:
    """Return (width, height) for an aspect ratio + resolution tier.

    Raises ValueError for unknown aspect ratios or resolutions.
    """
    ar = aspect_ratio.strip()
    if ar not in _BASE_1K:
        raise ValueError(
            f"Unknown aspect ratio {aspect_ratio!r}. Supported: {', '.join(ASPECT_RATIOS)}"
        )
    res = resolution.strip().lower()
    if res not in _RESOLUTION_SCALE:
        raise ValueError(
            f"Unknown resolution {resolution!r}. Supported: {', '.join(RESOLUTIONS)}"
        )
    w, h = _BASE_1K[ar]
    scale = _RESOLUTION_SCALE[res]
    return _round32(w * scale), _round32(h * scale)
