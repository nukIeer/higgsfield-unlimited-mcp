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
