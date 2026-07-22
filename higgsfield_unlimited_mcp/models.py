"""Model registry for Higgsfield Unlimited MCP.

``id`` is the API path form used for ``POST /jobs/{id}`` (v1) or
``POST /jobs/v2/{id}`` (v2). v1 ids use dashes (``nano-banana-2``); v2 ids use
underscores (``seedream_v5_pro``). ``unlimited=True`` marks models that a typical
Plus + 1-day-unlimited plan can run with ``use_unlim: true`` — the server is the
final authority (see ``account_info``). Model ids and entitlements change on
Higgsfield's side; ``generate_raw`` works with any id + ``api_version``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CATEGORY_IMAGE = "image"
CATEGORY_VIDEO = "video"
CATEGORY_AUDIO = "audio"


@dataclass(frozen=True)
class ModelSpec:
    id: str
    category: str
    api_version: str = "v2"
    unlimited: bool = False
    note: str = ""
    # Resolution options the model supports (empty = model has no resolution knob).
    resolutions: tuple[str, ...] = field(default_factory=tuple)
    # For unlimited: the highest resolution unlimited actually grants (else None).
    unlimited_max: str | None = None
    needs_input: bool = False


# --------------------------------------------------------------------------- #
# Image models
# --------------------------------------------------------------------------- #
_IMAGE_MODELS = [
    ModelSpec("nano-banana-2", CATEGORY_IMAGE, "v1", True, "Google Nano Banana 2.",
              ("1k", "2k", "4k"), "2k"),
    ModelSpec("nano-banana-pro", CATEGORY_IMAGE, "v1", True, "Google Nano Banana Pro.",
              ("1k", "2k", "4k"), "2k"),
    ModelSpec("nano-banana", CATEGORY_IMAGE, "v1", True, "Google Nano Banana."),
    ModelSpec("gpt_image_2", CATEGORY_IMAGE, "v2", True, "OpenAI GPT Image 2.",
              ("1k", "2k", "4k"), "2k"),
    ModelSpec("gpt_image", CATEGORY_IMAGE, "v2", True, "OpenAI GPT Image."),
    ModelSpec("seedream_v5_pro", CATEGORY_IMAGE, "v2", True, "ByteDance Seedream 5.0 Pro.",
              ("1k", "1.5k", "2k"), "2k"),
    ModelSpec("seedream_v5_lite", CATEGORY_IMAGE, "v2", True, "ByteDance Seedream 5.0 Lite."),
    ModelSpec("seedream_v4_5", CATEGORY_IMAGE, "v2", True, "ByteDance Seedream 4.5."),
    ModelSpec("soul_2", CATEGORY_IMAGE, "v2", True, "Higgsfield Soul 2.0 (realistic/UGC)."),
    ModelSpec("flux_2", CATEGORY_IMAGE, "v2", True, "Black Forest Labs FLUX.2 Pro.",
              ("1k", "2k"), "2k"),
    ModelSpec("kling_omni_image", CATEGORY_IMAGE, "v2", True, "Kling O1 Image.", ("1k", "2k"), "2k"),
    # Available but not part of the sample unlimited set:
    ModelSpec("openai_hazel", CATEGORY_IMAGE, "v2", False, "OpenAI Hazel (best text)."),
    ModelSpec("z_image", CATEGORY_IMAGE, "v2", False, "Z-Image (fast, not unlimited-eligible)."),
    ModelSpec("recraft_v4_1", CATEGORY_IMAGE, "v2", False, "Recraft V4.1 (logos/vector)."),
    ModelSpec("grok_image", CATEGORY_IMAGE, "v2", False, "xAI Grok Image."),
    ModelSpec("hunyuan_image", CATEGORY_IMAGE, "v2", False, "Tencent Hunyuan Image."),
    ModelSpec("outpaint", CATEGORY_IMAGE, "v2", False, "Outpaint / extend.", needs_input=True),
    ModelSpec("image_background_remover", CATEGORY_IMAGE, "v2", False, "Background removal.",
              needs_input=True),
    ModelSpec("bytedance_image_upscale", CATEGORY_IMAGE, "v2", False, "Image upscale.",
              ("2k", "4k"), needs_input=True),
]

# --------------------------------------------------------------------------- #
# Video models (v2). Unlimited caps are 720p for Seedance/Wan/Gemini.
# --------------------------------------------------------------------------- #
_VIDEO_MODELS = [
    ModelSpec("seedance_2_0", CATEGORY_VIDEO, "v2", True, "Seedance 2.0 (ref-driven, audio).",
              ("480p", "720p", "1080p", "4k"), "720p"),
    ModelSpec("seedance_2_0_mini", CATEGORY_VIDEO, "v2", True, "Seedance 2.0 Mini (fast).",
              ("480p", "720p"), "720p"),
    ModelSpec("wan2_7", CATEGORY_VIDEO, "v2", True, "Wan 2.7 (synced audio, character).",
              ("720p", "1080p"), "720p"),
    ModelSpec("gemini_omni", CATEGORY_VIDEO, "v2", True, "Gemini Omni Flash (native audio).",
              ("720p",), "720p"),
    ModelSpec("kling3_0", CATEGORY_VIDEO, "v2", True, "Kling v3.0 (multi-shot, audio sync)."),
    # Available but not part of the sample unlimited set:
    ModelSpec("kling3_0_turbo", CATEGORY_VIDEO, "v2", False, "Kling 3.0 Turbo (fast).",
              ("720p", "1080p")),
    ModelSpec("kling2_6", CATEGORY_VIDEO, "v2", False, "Kling 2.6."),
    ModelSpec("seedance1_5", CATEGORY_VIDEO, "v2", False, "Seedance 1.5 Pro.",
              ("480p", "720p", "1080p")),
    ModelSpec("minimax_hailuo", CATEGORY_VIDEO, "v2", False, "Minimax Hailuo.",
              ("512", "768", "1080")),
    ModelSpec("wan2_6", CATEGORY_VIDEO, "v2", False, "Wan 2.6 (stylized).", ("720p", "1080p")),
    ModelSpec("veo3", CATEGORY_VIDEO, "v2", False, "Google Veo 3.", needs_input=True),
    ModelSpec("veo3_1", CATEGORY_VIDEO, "v2", False, "Google Veo 3.1.", needs_input=True),
    ModelSpec("grok_video", CATEGORY_VIDEO, "v2", False, "xAI Grok Video."),
    ModelSpec("cinematic_studio_3_0", CATEGORY_VIDEO, "v2", False, "Cinema Studio Video 3.0.",
              ("480p", "720p", "1080p", "4k")),
    ModelSpec("video_upscale", CATEGORY_VIDEO, "v2", False, "Video upscale.", needs_input=True),
]

# --------------------------------------------------------------------------- #
# Audio models (unlimited on the sample plan). Exact ids may vary; verify with a
# capture or generate_raw.
# --------------------------------------------------------------------------- #
_AUDIO_MODELS = [
    ModelSpec("text2speech", CATEGORY_AUDIO, "v2", True, "Text to Speech V2."),
    ModelSpec("mirelo_text2audio", CATEGORY_AUDIO, "v2", True, "Mirelo Text to Audio."),
    ModelSpec("inworld_tts", CATEGORY_AUDIO, "v2", True, "Inworld Text to Speech."),
    ModelSpec("seed_audio", CATEGORY_AUDIO, "v2", True, "Seed Audio 1.0."),
]


REGISTRY: dict[str, ModelSpec] = {
    m.id: m for m in (_IMAGE_MODELS + _VIDEO_MODELS + _AUDIO_MODELS)
}


def all_models() -> list[ModelSpec]:
    return list(REGISTRY.values())


def models_by_category(category: str | None) -> list[ModelSpec]:
    if category is None:
        return all_models()
    category = category.lower()
    return [m for m in REGISTRY.values() if m.category == category]


def unlimited_models(category: str | None = None) -> list[ModelSpec]:
    return [m for m in models_by_category(category) if m.unlimited]


def get_model(model_id: str) -> ModelSpec | None:
    return REGISTRY.get(model_id)


def is_known(model_id: str) -> bool:
    return model_id in REGISTRY


def category_counts() -> dict[str, int]:
    counts = {CATEGORY_IMAGE: 0, CATEGORY_VIDEO: 0, CATEGORY_AUDIO: 0}
    for m in REGISTRY.values():
        counts[m.category] = counts.get(m.category, 0) + 1
    return counts
