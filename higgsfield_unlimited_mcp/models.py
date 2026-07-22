"""Model registry for Higgsfield Unlimited MCP.

Each entry maps a model id (the ``{model}`` path segment in
``POST /jobs/{model}``) to metadata: its category and, where known, the extra
fields that model requires beyond the common ones.

Model ids evolve on Higgsfield's side. Treat this as a convenient default list —
you can always call ``generate_raw`` with any model id and a custom params dict,
and the API's 422 error will tell you exactly which fields a model needs. See
``docs/MODEL_SCHEMAS.md``.
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
    # Human note on what the model is / needs.
    note: str = ""
    # Fields the model needs in addition to the common ones (prompt, dims, ...).
    required_extra: tuple[str, ...] = field(default_factory=tuple)
    # Whether this model consumes an input image/video (i2i, i2v, edit, ...).
    needs_input: bool = False


# --------------------------------------------------------------------------- #
# Image models (text-to-image + image editing)
# --------------------------------------------------------------------------- #
_IMAGE_MODELS = [
    ModelSpec("nano-banana-2", CATEGORY_IMAGE, "Google Nano Banana 2 (default)."),
    ModelSpec("nano-banana", CATEGORY_IMAGE, "Google Nano Banana."),
    ModelSpec("nano-banana-2-shots", CATEGORY_IMAGE, "Multi-shot storyboard endpoint.",
              required_extra=("shots",)),
    ModelSpec("flux-2", CATEGORY_IMAGE, "Black Forest Labs FLUX.2."),
    ModelSpec("flux-1-1-pro", CATEGORY_IMAGE, "FLUX 1.1 Pro."),
    ModelSpec("flux-kontext", CATEGORY_IMAGE, "FLUX Kontext (image editing).", needs_input=True),
    ModelSpec("seedream-v4-5", CATEGORY_IMAGE, "ByteDance Seedream v4.5."),
    ModelSpec("seedream-v4", CATEGORY_IMAGE, "ByteDance Seedream v4."),
    ModelSpec("openai-hazel", CATEGORY_IMAGE, "OpenAI image model (Hazel)."),
    ModelSpec("gpt-image", CATEGORY_IMAGE, "OpenAI GPT image."),
    ModelSpec("reve", CATEGORY_IMAGE, "Reve image model."),
    ModelSpec("z-image", CATEGORY_IMAGE, "Z-Image."),
    ModelSpec("recraft-v3", CATEGORY_IMAGE, "Recraft V3."),
    ModelSpec("ideogram-v3", CATEGORY_IMAGE, "Ideogram v3."),
    ModelSpec("imagen-4", CATEGORY_IMAGE, "Google Imagen 4."),
    ModelSpec("qwen-image", CATEGORY_IMAGE, "Qwen Image."),
    ModelSpec("hunyuan-image", CATEGORY_IMAGE, "Tencent Hunyuan Image."),
    ModelSpec("higgsfield-soul", CATEGORY_IMAGE, "Higgsfield Soul (photoreal)."),
    ModelSpec("higgsfield-soul-id", CATEGORY_IMAGE, "Higgsfield Soul with character id.",
              needs_input=True),
    ModelSpec("face-swap", CATEGORY_IMAGE, "Face swap.", needs_input=True),
    ModelSpec("character-swap", CATEGORY_IMAGE, "Character swap.", needs_input=True),
    ModelSpec("upscale", CATEGORY_IMAGE, "Image upscaler.", needs_input=True),
    ModelSpec("inpaint", CATEGORY_IMAGE, "Inpainting / edit region.", needs_input=True),
    ModelSpec("outpaint", CATEGORY_IMAGE, "Outpainting / extend canvas.", needs_input=True),
    ModelSpec("remove-background", CATEGORY_IMAGE, "Background removal.", needs_input=True),
    ModelSpec("relight", CATEGORY_IMAGE, "Relighting.", needs_input=True),
    ModelSpec("style-transfer", CATEGORY_IMAGE, "Style transfer.", needs_input=True),
    ModelSpec("product-placement", CATEGORY_IMAGE, "Product placement.", needs_input=True),
    ModelSpec("sketch-to-image", CATEGORY_IMAGE, "Sketch to image.", needs_input=True),
    ModelSpec("hunyuan-3d", CATEGORY_IMAGE, "Image to 3D preview.", needs_input=True),
    ModelSpec("seededit", CATEGORY_IMAGE, "Seedream edit.", needs_input=True),
    ModelSpec("photo-restore", CATEGORY_IMAGE, "Photo restoration.", needs_input=True),
]

# --------------------------------------------------------------------------- #
# Video models (text-to-video + image-to-video)
# --------------------------------------------------------------------------- #
_VIDEO_MODELS = [
    ModelSpec("seedance", CATEGORY_VIDEO, "ByteDance Seedance."),
    ModelSpec("seedance-pro", CATEGORY_VIDEO, "Seedance Pro."),
    ModelSpec("kling", CATEGORY_VIDEO, "Kuaishou Kling."),
    ModelSpec("kling2-6", CATEGORY_VIDEO, "Kling 2.6."),
    ModelSpec("kling2-5", CATEGORY_VIDEO, "Kling 2.5."),
    ModelSpec("kling2-1", CATEGORY_VIDEO, "Kling 2.1."),
    ModelSpec("sora2-video", CATEGORY_VIDEO, "OpenAI Sora 2."),
    ModelSpec("sora2-pro", CATEGORY_VIDEO, "OpenAI Sora 2 Pro."),
    ModelSpec("veo3", CATEGORY_VIDEO, "Google Veo 3.", required_extra=("duration",)),
    ModelSpec("veo3-1", CATEGORY_VIDEO, "Google Veo 3.1.", required_extra=("duration",)),
    ModelSpec("veo3-fast", CATEGORY_VIDEO, "Google Veo 3 Fast."),
    ModelSpec("minimax-hailuo", CATEGORY_VIDEO, "MiniMax Hailuo."),
    ModelSpec("minimax-hailuo-02", CATEGORY_VIDEO, "MiniMax Hailuo 02."),
    ModelSpec("wan2-2-video", CATEGORY_VIDEO, "Alibaba WAN 2.2."),
    ModelSpec("wan2-5-video", CATEGORY_VIDEO, "Alibaba WAN 2.5."),
    ModelSpec("wan2-6", CATEGORY_VIDEO, "Alibaba WAN 2.6."),
    ModelSpec("image2video", CATEGORY_VIDEO, "Generic image-to-video.", needs_input=True),
    ModelSpec("infinite-talk", CATEGORY_VIDEO, "Talking-avatar / lip-sync.", needs_input=True,
              required_extra=("audio_url",)),
    ModelSpec("higgsfield-dop", CATEGORY_VIDEO, "Higgsfield DoP (motion presets)."),
    ModelSpec("higgsfield-dop-turbo", CATEGORY_VIDEO, "Higgsfield DoP Turbo."),
    ModelSpec("runway-gen4", CATEGORY_VIDEO, "Runway Gen-4."),
    ModelSpec("luma-ray", CATEGORY_VIDEO, "Luma Dream Machine (Ray)."),
    ModelSpec("luma-ray2", CATEGORY_VIDEO, "Luma Ray 2."),
    ModelSpec("pika", CATEGORY_VIDEO, "Pika."),
    ModelSpec("pixverse", CATEGORY_VIDEO, "PixVerse."),
    ModelSpec("hunyuan-video", CATEGORY_VIDEO, "Tencent Hunyuan Video."),
    ModelSpec("ltx-video", CATEGORY_VIDEO, "Lightricks LTX Video."),
    ModelSpec("wan-animate", CATEGORY_VIDEO, "WAN animate (image drive).", needs_input=True),
    ModelSpec("act-two", CATEGORY_VIDEO, "Runway Act-Two performance capture.", needs_input=True),
    ModelSpec("video-upscale", CATEGORY_VIDEO, "Video upscaler.", needs_input=True),
    ModelSpec("lipsync", CATEGORY_VIDEO, "Lip-sync.", needs_input=True,
              required_extra=("audio_url",)),
]

# --------------------------------------------------------------------------- #
# Audio models
# --------------------------------------------------------------------------- #
_AUDIO_MODELS = [
    ModelSpec("text2speech", CATEGORY_AUDIO, "Text-to-speech.", required_extra=("text",)),
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


def get_model(model_id: str) -> ModelSpec | None:
    return REGISTRY.get(model_id)


def is_known(model_id: str) -> bool:
    return model_id in REGISTRY


def category_counts() -> dict[str, int]:
    counts = {CATEGORY_IMAGE: 0, CATEGORY_VIDEO: 0, CATEGORY_AUDIO: 0}
    for m in REGISTRY.values():
        counts[m.category] = counts.get(m.category, 0) + 1
    return counts
