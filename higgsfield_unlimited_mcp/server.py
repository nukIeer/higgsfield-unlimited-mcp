"""Higgsfield Unlimited MCP server.

Exposes the full Higgsfield generation surface (image / video / audio / storyboard
+ account, workspace, media, asset management) as MCP tools, all running in
unlimited mode. Auth uses your existing browser session (Clerk JWT, auto-refreshed).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import HiggsfieldError
from .config import get_config
from . import dimensions as dims
from . import models as model_registry
from .service import Service

log = logging.getLogger("higgsfield.server")

mcp = FastMCP("higgsfield-unlimited")

_service: Service | None = None


def _svc() -> Service:
    global _service
    if _service is None:
        _service = Service(get_config())
    return _service


def _jdump(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _err(exc: Exception) -> str:
    if isinstance(exc, HiggsfieldError):
        return _jdump(
            {"error": str(exc), "status": exc.status, "body": exc.body}
        )
    return _jdump({"error": f"{type(exc).__name__}: {exc}"})


def _job_summary(rec: Any, saved: list[str] | None = None) -> dict[str, Any]:
    d = {
        "job_id": rec.id,
        "model": rec.model,
        "kind": rec.kind,
        "status": rec.status,
        "results": rec.results,
    }
    if rec.error:
        d["error"] = rec.error
    if saved:
        d["downloaded"] = saved
    return d


# ======================================================================= #
# Auth & account
# ======================================================================= #
@mcp.tool()
async def auth_status() -> str:
    """Verify Clerk credentials by fetching a fresh JWT."""
    cfg = get_config()
    problems = cfg.validate()
    if problems:
        return _jdump({"ok": False, "problems": problems})
    try:
        jwt = await _svc().client.auth.get_jwt(force=True)
        return _jdump(
            {
                "ok": True,
                "session_id": cfg.session_id,
                "jwt_prefix": jwt[:16] + "...",
                "jwt_length": len(jwt),
                "message": "Clerk JWT minted successfully.",
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def account_info() -> str:
    """Plan info, all credit balances, and the has_unlim flag."""
    try:
        res = await _svc().try_get(["/user", "/account", "/me"])
        return _jdump(res)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def concurrent_state() -> str:
    """Concurrent-slot tier (how many jobs can run at once: 4/8/12/16)."""
    try:
        res = await _svc().try_get(
            ["/concurrent-boost-credits/state", "/concurrent-boost-credits/products"]
        )
        return _jdump(res)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def queue_status() -> str:
    """Snapshot of the in-process job registry (jobs submitted this session)."""
    return _jdump(_svc().registry.snapshot())


# ======================================================================= #
# Models
# ======================================================================= #
@mcp.tool()
async def list_models(category: str | None = None) -> str:
    """List generation models. Optionally filter by category: image / video / audio."""
    specs = model_registry.models_by_category(category)
    out = [
        {
            "id": m.id,
            "category": m.category,
            "note": m.note,
            "needs_input": m.needs_input,
            "required_extra": list(m.required_extra),
        }
        for m in specs
    ]
    return _jdump(
        {"count": len(out), "counts_by_category": model_registry.category_counts(), "models": out}
    )


@mcp.tool()
async def get_aspect_dimensions(aspect_ratio: str, resolution: str = "2k") -> str:
    """Canonical (width, height) in pixels for an aspect ratio + resolution (1k/2k/4k)."""
    try:
        w, h = dims.get_dimensions(aspect_ratio, resolution)
        return _jdump({"aspect_ratio": aspect_ratio, "resolution": resolution, "width": w, "height": h})
    except ValueError as exc:
        return _jdump({"error": str(exc), "aspect_ratios": list(dims.ASPECT_RATIOS)})


# ======================================================================= #
# Image generation
# ======================================================================= #
async def _build_image_params(
    prompt: str,
    aspect_ratio: str,
    resolution: str,
    seed: int | None,
    negative_prompt: str | None,
    batch_size: int,
    input_files: list[str] | None,
    input_images: list[str] | None,
    extra_params: dict[str, Any] | None,
) -> dict[str, Any]:
    width, height = dims.get_dimensions(aspect_ratio, resolution)
    params: dict[str, Any] = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "batch_size": batch_size,
    }
    if seed is not None:
        params["seed"] = seed
    if negative_prompt:
        params["negative_prompt"] = negative_prompt
    urls = await _svc().resolve_inputs(input_files, input_images)
    if urls:
        params["input_images"] = urls
    if extra_params:
        params.update(extra_params)
    return params


@mcp.tool()
async def generate_image(
    prompt: str,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    resolution: str | None = None,
    seed: int | None = None,
    negative_prompt: str | None = None,
    batch_size: int = 1,
    input_files: list[str] | None = None,
    input_images: list[str] | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 300.0,
) -> str:
    """Generate a single image (or a small batch of the same prompt).

    32 image models are available (nano-banana-2, flux-2, seedream-v4-5,
    openai-hazel, reve, z-image, ...). Local files in ``input_files`` are
    auto-uploaded and passed as input images. Set ``wait=False`` to fire-and-forget.
    """
    cfg = get_config()
    model = model or cfg.default_model
    resolution = resolution or cfg.default_resolution
    try:
        params = await _build_image_params(
            prompt, aspect_ratio, resolution, seed, negative_prompt,
            batch_size, input_files, input_images, extra_params,
        )
        rec = await _svc().submit(model=model, params=params, kind="image", prompt=prompt)
        if wait and not rec.is_terminal:
            rec = await _svc().wait(rec.id, timeout=timeout)
        saved = None
        if download and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def generate_image_batch(
    prompts: list[str],
    model: str | None = None,
    aspect_ratio: str = "16:9",
    resolution: str | None = None,
    max_concurrent: int | None = None,
    input_files: list[str] | None = None,
    input_images: list[str] | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = False,
    download: bool = False,
    timeout: float = 600.0,
) -> str:
    """Queue many prompts, running up to ``max_concurrent`` in parallel.

    With ``wait=False`` (default) this fires all jobs and returns their ids —
    poll progress with ``queue_status`` / ``list_jobs``. With ``wait=True`` it
    blocks until every job finishes.
    """
    cfg = get_config()
    model = model or cfg.default_model
    resolution = resolution or cfg.default_resolution
    limit = max_concurrent or cfg.max_concurrent
    sema = asyncio.Semaphore(max(1, limit))

    async def _one(p: str) -> dict[str, Any]:
        async with sema:
            try:
                params = await _build_image_params(
                    p, aspect_ratio, resolution, None, None, 1,
                    input_files, input_images, extra_params,
                )
                rec = await _svc().submit(model=model, params=params, kind="image", prompt=p)
                if wait and not rec.is_terminal:
                    rec = await _svc().wait(rec.id, timeout=timeout)
                saved = None
                if download and rec.status == "completed" and rec.results:
                    saved = await _svc().download_results(rec)
                return _job_summary(rec, saved)
            except Exception as exc:  # noqa: BLE001
                return {"prompt": p, "error": str(exc)}

    results = await asyncio.gather(*[_one(p) for p in prompts])
    return _jdump({"submitted": len(results), "jobs": results})


@mcp.tool()
async def generate_storyboard(
    shots: list[str],
    model: str = "nano-banana-2-shots",
    aspect_ratio: str = "9:16",
    resolution: str | None = None,
    reference_files: list[str] | None = None,
    reference_images: list[str] | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 600.0,
) -> str:
    """Multi-shot storyboard with character/style continuity.

    Uses Higgsfield's dedicated multi-shot endpoint (nano-banana-2-shots). Each
    entry in ``shots`` is one shot's prompt; an optional reference image is shared
    across every shot for continuity.
    """
    cfg = get_config()
    resolution = resolution or cfg.default_resolution
    try:
        width, height = dims.get_dimensions(aspect_ratio, resolution)
        refs = await _svc().resolve_inputs(reference_files, reference_images)
        params: dict[str, Any] = {
            "prompt": shots[0] if shots else "",
            "shots": [{"prompt": s} for s in shots],
            "width": width,
            "height": height,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        if refs:
            params["input_images"] = refs
        if extra_params:
            params.update(extra_params)
        rec = await _svc().submit(
            model=model, params=params, kind="storyboard", prompt=f"{len(shots)}-shot storyboard"
        )
        if wait and not rec.is_terminal:
            rec = await _svc().wait(rec.id, timeout=timeout)
        saved = None
        if download and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Video generation
# ======================================================================= #
@mcp.tool()
async def generate_video(
    prompt: str,
    model: str = "seedance",
    aspect_ratio: str = "16:9",
    duration: int | None = None,
    resolution: str | None = None,
    input_files: list[str] | None = None,
    input_images: list[str] | None = None,
    seed: int | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 600.0,
) -> str:
    """Generate a video (31 models: seedance, kling/kling2-6, sora2-video, veo3/veo3-1,
    minimax-hailuo, wan2-*, image2video, infinite-talk, ...).

    Each video model needs different fields. On a 422 the error tells you exactly
    which fields to add via ``extra_params`` (or use ``generate_raw``). Local files
    in ``input_files`` are auto-uploaded for image-to-video.
    """
    try:
        params: dict[str, Any] = {"prompt": prompt, "aspect_ratio": aspect_ratio}
        if duration is not None:
            params["duration"] = duration
        if resolution:
            params["resolution"] = resolution
            # For video the platform commonly wants a quality/height hint too.
            params.setdefault("quality", resolution)
        if seed is not None:
            params["seed"] = seed
        urls = await _svc().resolve_inputs(input_files, input_images)
        if urls:
            params["input_images"] = urls
            params.setdefault("image_url", urls[0].get("url"))
        if extra_params:
            params.update(extra_params)
        rec = await _svc().submit(model=model, params=params, kind="video", prompt=prompt)
        if wait and not rec.is_terminal:
            rec = await _svc().wait(rec.id, timeout=timeout)
        saved = None
        if download and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Audio generation
# ======================================================================= #
@mcp.tool()
async def generate_audio(
    text: str,
    model: str = "text2speech",
    voice: str | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 300.0,
) -> str:
    """Text-to-speech via the text2speech model."""
    try:
        params: dict[str, Any] = {"text": text}
        if voice:
            params["voice"] = voice
        if extra_params:
            params.update(extra_params)
        rec = await _svc().submit(model=model, params=params, kind="audio", prompt=text[:80])
        if wait and not rec.is_terminal:
            rec = await _svc().wait(rec.id, timeout=timeout)
        saved = None
        if download and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Generic / advanced escape hatch
# ======================================================================= #
@mcp.tool()
async def generate_raw(
    model: str,
    params: dict[str, Any],
    kind: str = "raw",
    input_files: list[str] | None = None,
    wait: bool = True,
    download: bool = False,
    timeout: float = 600.0,
) -> str:
    """Escape hatch: call any model with a custom params dict.

    Use for face-swap, character-swap, upscale, inpaint, or any model whose exact
    schema you already know (see docs/MODEL_SCHEMAS.md). ``params`` is passed
    through verbatim (with use_unlim added). Local ``input_files`` are uploaded and
    merged into ``params['input_images']``.
    """
    try:
        params = dict(params)
        if input_files:
            urls = await _svc().resolve_inputs(input_files, params.get("input_images"))
            params["input_images"] = urls
        rec = await _svc().submit(
            model=model, params=params, kind=kind, prompt=str(params.get("prompt", ""))[:80]
        )
        if wait and not rec.is_terminal:
            rec = await _svc().wait(rec.id, timeout=timeout)
        saved = None
        if download and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Job management
# ======================================================================= #
@mcp.tool()
async def check_job(job_id: str) -> str:
    """Poll a single job (checks the local registry, then the remote API)."""
    try:
        rec = await _svc().refresh(job_id)
        if rec is None:
            return _jdump({"error": f"Job {job_id} not found."})
        return _jdump(_job_summary(rec))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def wait_for_job(
    job_id: str, timeout: float = 600.0, interval: float = 5.0, download: bool = False
) -> str:
    """Block until a job finishes; optionally download its results."""
    try:
        rec = await _svc().wait(job_id, timeout=timeout, interval=interval)
        saved = None
        if download and rec and rec.status == "completed" and rec.results:
            saved = await _svc().download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def cancel_job(job_id: str) -> str:
    """Cancel an in-progress job (DELETE /jobs/{id})."""
    try:
        rec = await _svc().cancel(job_id)
        return _jdump(_job_summary(rec))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def list_jobs() -> str:
    """List all jobs in the local (this-session) registry."""
    return _jdump({"jobs": [r.to_dict() for r in _svc().registry.all()]})


@mcp.tool()
async def download_job_result(job_id: str, output_dir: str | None = None) -> str:
    """Re-fetch a completed job's results and save them to disk."""
    try:
        rec = await _svc().refresh(job_id)
        if rec is None:
            return _jdump({"error": f"Job {job_id} not found."})
        if not rec.results:
            return _jdump({"error": f"Job {job_id} has no downloadable results.", "status": rec.status})
        out = Path(output_dir) if output_dir else None
        saved = await _svc().download_results(rec, out)
        return _jdump({"job_id": job_id, "downloaded": saved})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def show_generations(limit: int = 20, offset: int = 0) -> str:
    """Server-side recent generation history (your account's /jobs/accessible)."""
    try:
        data = await _svc().client.accessible_jobs(limit=limit, offset=offset)
        return _jdump(data)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Workspaces
# ======================================================================= #
@mcp.tool()
async def list_workspaces() -> str:
    """List all your workspaces."""
    try:
        return _jdump(await _svc().try_get(["/workspaces", "/workspace/list", "/account/workspaces"]))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def workspace_details() -> str:
    """Active workspace info (id, name, type, role)."""
    try:
        return _jdump(
            await _svc().try_get(["/workspaces/details", "/workspaces/active", "/workspace"])
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def workspace_wallet() -> str:
    """Workspace credit balance."""
    try:
        return _jdump(await _svc().try_get(["/workspaces/wallet", "/wallet"]))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def workspace_members() -> str:
    """Members of the active workspace."""
    try:
        return _jdump(
            await _svc().try_get(["/workspaces/members", "/workspaces/active/members", "/members"])
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def workspace_usage() -> str:
    """Credit-usage chart for the active workspace."""
    try:
        return _jdump(
            await _svc().try_get(["/workspaces/usage", "/workspaces/active/usage", "/usage"])
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Media library
# ======================================================================= #
@mcp.tool()
async def show_medias(limit: int = 30, offset: int = 0, kind: str | None = None) -> str:
    """Paginated media library (images + videos). Optional kind filter: image/video."""
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if kind:
        params["type"] = kind
    try:
        return _jdump(await _svc().try_get(["/medias", "/media", "/media/library"], params=params))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def media_upload(file_path: str) -> str:
    """Upload a local image/video for use as input on subsequent generations."""
    try:
        result = await _svc().client.upload_file(file_path)
        return _jdump({"uploaded": result})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def media_status(media_ids: list[str]) -> str:
    """Check status of media items by id."""
    try:
        return _jdump(
            await _svc().try_get(["/media/status"], params={"ids": ",".join(media_ids)})
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def media_download_batch(media_ids: list[str], output_dir: str | None = None) -> str:
    """Bulk-download media by id. Resolves each id to a URL and saves it to disk."""
    try:
        svc = _svc()
        res = await svc.try_get(["/media/batch", "/media/urls"], params={"ids": ",".join(media_ids)})
        from .client import extract_result_urls  # local import to avoid cycle at top

        urls = extract_result_urls(res.get("data"))
        out = Path(output_dir) if output_dir else svc.config.ensure_output_dir()
        out.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for i, u in enumerate(urls):
            url = u["url"]
            ext = Path(url.split("?")[0]).suffix or ".bin"
            dest = out / f"media_{i}{ext}"
            await svc.client.download(url, dest)
            saved.append(str(dest))
        return _jdump({"downloaded": saved, "resolved_urls": [u["url"] for u in urls]})
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Assets & favourites
# ======================================================================= #
@mcp.tool()
async def list_assets(limit: int = 30, offset: int = 0) -> str:
    """List your assets."""
    try:
        return _jdump(
            await _svc().try_get(["/assets", "/asset/list"], params={"limit": limit, "offset": offset})
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def list_favourites(limit: int = 30, offset: int = 0) -> str:
    """List your favourited assets."""
    try:
        return _jdump(
            await _svc().try_get(
                ["/favourites", "/favorites", "/assets/favourites"],
                params={"limit": limit, "offset": offset},
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def like_asset(asset_id: str) -> str:
    """Add an asset to your favourites."""
    try:
        return _jdump(await _svc().client.post(f"/assets/{asset_id}/like"))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def unlike_asset(asset_id: str) -> str:
    """Remove an asset from your favourites."""
    try:
        return _jdump(await _svc().client.delete(f"/assets/{asset_id}/like"))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


def run() -> None:
    cfg = get_config()
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    mcp.run()


if __name__ == "__main__":
    run()
