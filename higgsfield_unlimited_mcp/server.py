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
from .pool import get_pool
from .service import Service

log = logging.getLogger("higgsfield.server")

mcp = FastMCP("higgsfield-unlimited")


def _pool():
    return get_pool()


def _svc() -> Service:
    """Primary account's service — for per-account read/job tools."""
    return get_pool().primary()


def _find_service(job_id: str) -> Service:
    """Return the account whose registry owns this job (else primary)."""
    for svc in get_pool().services:
        if svc.registry.get(job_id) is not None:
            return svc
    return get_pool().primary()


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
    """Verify credentials for every configured account by minting a fresh JWT each."""
    pool = _pool()
    results = []
    ok_count = 0
    for svc, label in zip(pool.services, pool.labels):
        entry: dict[str, Any] = {"account": label, "session_id": svc.config.session_id[:16] + "..."}
        if not svc.config.session_id or not svc.config.clerk_cookie:
            entry["ok"] = False
            entry["problem"] = "missing session_id or clerk_cookie"
        else:
            try:
                jwt = await svc.client.auth.get_jwt(force=True)
                entry["ok"] = True
                entry["jwt_length"] = len(jwt)
                entry["has_datadome"] = "datadome=" in svc.config.extra_cookies
                ok_count += 1
            except Exception as exc:  # noqa: BLE001
                entry["ok"] = False
                entry["problem"] = str(exc)
        results.append(entry)
    return _jdump({"accounts": len(results), "authenticated": ok_count, "results": results})


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
    """Snapshot of in-flight jobs across all accounts in the pool."""
    return _jdump(_pool().snapshot())


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
            "api_version": m.api_version,
            "unlimited": m.unlimited,
            "unlimited_max_resolution": m.unlimited_max,
            "resolutions": list(m.resolutions),
            "needs_input": m.needs_input,
            "note": m.note,
        }
        for m in specs
    ]
    return _jdump({
        "count": len(out),
        "counts_by_category": model_registry.category_counts(),
        "unlimited_ids": [m.id for m in model_registry.unlimited_models(category)],
        "models": out,
    })


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
    svc: Service,
    prompt: str,
    aspect_ratio: str,
    resolution: str,
    seed: int | None,
    negative_prompt: str | None,
    batch_size: int,
    input_files: list[str] | None,
    input_images: list | None,
    extra_params: dict[str, Any] | None,
    api_version: str = "v1",
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
    media = await svc.resolve_inputs(input_files, input_images)
    if media:
        if api_version == "v2":
            params["medias"] = svc.to_v2_medias(media, role="image")
        else:
            params["input_images"] = media
    if extra_params:
        params.update(extra_params)
    return params


@mcp.tool()
async def generate_image(
    prompt: str,
    model: str | None = None,
    aspect_ratio: str = "16:9",
    resolution: str | None = None,
    api_version: str = "v1",
    seed: int | None = None,
    negative_prompt: str | None = None,
    batch_size: int = 1,
    input_files: list[str] | None = None,
    input_images: list[str] | None = None,
    account: str | int | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 300.0,
) -> str:
    """Generate a single image, unlimited, across the account pool.

    ``model`` uses the API path form: v1 models use dashes (``nano-banana-2``,
    ``nano-banana-pro``); v2 models use underscores + ``api_version="v2"``
    (``seedream_v5_pro``, ``seedream_v5_lite``, ``flux_2``, ``gpt_image_2``, ``soul_2``,
    ``kling_omni_image``). Unlimited-eligible on a typical plan: nano_banana_2,
    nano_banana_pro, gpt_image_2, seedream_v5_pro, seedream_v4_5, soul_2,
    seedream_v5_lite, flux_2, kling_omni_image. Local ``input_files`` are auto-uploaded.
    See ``list_models`` and ``account_info`` for what's unlimited on your plan.
    """
    cfg = get_config()
    model = model or cfg.default_model
    resolution = resolution or cfg.default_resolution
    try:
        async def _submit(svc: Service):
            params = await _build_image_params(
                svc, prompt, aspect_ratio, resolution, seed, negative_prompt,
                batch_size, input_files, input_images, extra_params, api_version,
            )
            submit = svc.submit_v2 if api_version == "v2" else svc.submit
            return await submit(model=model, params=params, kind="image", prompt=prompt)

        result = await _pool().run_job(
            _submit, wait=wait, download=download, timeout=timeout, account=account
        )
        return _jdump(result)
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
    # Cap total in-flight across the whole pool; the pool spreads them over accounts
    # and fails over on 429.
    pool = _pool()
    limit = max_concurrent or (cfg.max_concurrent * len(pool.services))
    sema = asyncio.Semaphore(max(1, limit))

    async def _one(p: str) -> dict[str, Any]:
        async with sema:
            async def _submit(svc: Service):
                params = await _build_image_params(
                    svc, p, aspect_ratio, resolution, None, None, 1,
                    input_files, input_images, extra_params,
                )
                return await svc.submit(model=model, params=params, kind="image", prompt=p)
            try:
                return await pool.run_job(_submit, wait=wait, download=download, timeout=timeout)
            except Exception as exc:  # noqa: BLE001
                return {"prompt": p, "error": str(exc)}

    results = await asyncio.gather(*[_one(p) for p in prompts])
    return _jdump({"submitted": len(results), "accounts": len(pool.services), "jobs": results})


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

        async def _submit(svc: Service):
            refs = await svc.resolve_inputs(reference_files, reference_images)
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
            return await svc.submit(
                model=model, params=params, kind="storyboard",
                prompt=f"{len(shots)}-shot storyboard",
            )

        result = await _pool().run_job(_submit, wait=wait, download=download, timeout=timeout)
        return _jdump(result)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Video generation
# ======================================================================= #
# Resolution ladder, highest -> lowest. Fallback walks down from the request.
_RES_LADDER = ["4k", "1080p", "720p", "480p"]


def _resolution_chain(preferred: str) -> list[str]:
    """Return resolutions to try, starting at `preferred` and descending."""
    preferred = preferred.lower()
    if preferred not in _RES_LADDER:
        return [preferred, "720p", "480p"]
    return _RES_LADDER[_RES_LADDER.index(preferred):]


def _is_unlim_denied(exc: HiggsfieldError) -> bool:
    body = exc.body
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict) and detail.get("error_type") == "unlimited_generation_not_allowed":
            return True
    return False


@mcp.tool()
async def generate_video(
    prompt: str,
    model: str = "seedance_2_0",
    aspect_ratio: str = "9:16",
    duration: int = 5,
    resolution: str = "1080p",
    resolution_fallback: bool = True,
    input_files: list[str] | None = None,
    input_images: list | None = None,
    media_role: str = "start_image",
    generate_audio: bool = True,
    mode: str | None = "std",
    seed: int | None = None,
    account: str | int | None = None,
    extra_params: dict[str, Any] | None = None,
    wait: bool = True,
    download: bool = True,
    timeout: float = 900.0,
) -> str:
    """Generate a video via the v2 API, with automatic resolution fallback.

    Defaults target viral 9:16 clips. Because unlimited access is capped per model
    (e.g. Seedance/Wan/Gemini unlimited render at 720p), ``resolution_fallback`` walks
    the requested resolution down the ladder (1080p -> 720p -> 480p) whenever the server
    returns ``unlimited_generation_not_allowed`` or rejects the resolution — so you get
    the highest resolution your unlimited plan actually allows.

    Unlimited-eligible video models on a typical plan: ``seedance_2_0``,
    ``seedance_2_0_mini``, ``wan2_7``, ``gemini_omni``, ``kling3_0``. Local
    ``input_files`` are uploaded and attached as ``medias`` (role ``start_image`` for
    image-to-video). Use ``extra_params`` for model-specific fields.
    """
    try:
        chain = _resolution_chain(resolution) if resolution_fallback else [resolution]
        res_attempts: list[dict[str, Any]] = []

        for res in chain:
            try:
                vw, vh = dims.video_dimensions(aspect_ratio, res)
            except ValueError:
                vw, vh = dims.video_dimensions("9:16", res)

            async def _submit(svc: Service, _res=res, _vw=vw, _vh=vh):
                media_objs = await svc.resolve_inputs(input_files, input_images)
                params: dict[str, Any] = {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "batch_size": 1,
                    "duration": duration,
                    "resolution": _res,
                    "generate_audio": generate_audio,
                    "width": _vw,
                    "height": _vh,
                }
                if mode:
                    params["mode"] = mode
                if seed is not None:
                    params["seed"] = seed
                if media_objs:
                    params["medias"] = svc.to_v2_medias(media_objs, role=media_role)
                if extra_params:
                    params.update(extra_params)
                return await svc.submit_v2(model=model, params=params, kind="video", prompt=prompt)

            try:
                result = await _pool().run_job(
                    _submit, wait=wait, download=download, timeout=timeout, account=account
                )
            except HiggsfieldError as exc:
                res_attempts.append({"resolution": res, "status": exc.status,
                                     "denied_unlim": _is_unlim_denied(exc)})
                # Unlimited denied at this resolution -> step down. Other hard errors stop.
                if _is_unlim_denied(exc) or exc.status in (400, 422):
                    continue
                return _err(exc)

            # run_job returned: either a job summary, or an all-accounts-rate-limited dict.
            if result.get("error") and "rate-limited" in str(result.get("error", "")):
                # Lower resolution won't fix a rate limit; surface it (add more accounts).
                result["resolution_tried"] = res
                if res_attempts:
                    result["resolution_attempts"] = res_attempts
                return _jdump(result)

            result["resolution_used"] = res
            if res_attempts:
                result["resolution_attempts"] = res_attempts
            return _jdump(result)

        return _jdump({
            "error": "Every resolution in the fallback chain was denied for unlimited.",
            "model": model,
            "resolution_attempts": res_attempts,
            "hint": "This model may not be unlimited-eligible on your plan. Check account_info.",
        })
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
        async def _submit(svc: Service):
            params: dict[str, Any] = {"text": text}
            if voice:
                params["voice"] = voice
            if extra_params:
                params.update(extra_params)
            return await svc.submit(model=model, params=params, kind="audio", prompt=text[:80])

        result = await _pool().run_job(_submit, wait=wait, download=download, timeout=timeout)
        return _jdump(result)
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
    api_version: str = "v1",
    input_files: list[str] | None = None,
    wait: bool = True,
    download: bool = False,
    timeout: float = 600.0,
) -> str:
    """Escape hatch: call any model with a custom params dict, across the account pool.

    Use for face-swap, character-swap, upscale, inpaint, or any model whose exact
    schema you already know (see docs/MODEL_SCHEMAS.md). ``params`` is passed through
    verbatim (with use_unlim added). ``api_version`` selects the endpoint: ``v1``
    (`/jobs/{model}`) or ``v2`` (`/jobs/v2/{model}`, newer models incl. most video).
    Local ``input_files`` are uploaded and merged into ``params['input_images']``.
    """
    try:
        async def _submit(svc: Service):
            p = dict(params)
            if input_files:
                p["input_images"] = await svc.resolve_inputs(input_files, p.get("input_images"))
            submit = svc.submit_v2 if api_version == "v2" else svc.submit
            return await submit(
                model=model, params=p, kind=kind, prompt=str(p.get("prompt", ""))[:80]
            )

        result = await _pool().run_job(_submit, wait=wait, download=download, timeout=timeout)
        return _jdump(result)
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


# ======================================================================= #
# Job management
# ======================================================================= #
@mcp.tool()
async def check_job(job_id: str) -> str:
    """Poll a single job across the account pool (local registry, then remote API)."""
    try:
        rec = await _find_service(job_id).refresh(job_id)
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
        svc = _find_service(job_id)
        rec = await svc.wait(job_id, timeout=timeout, interval=interval)
        saved = None
        if download and rec and rec.status == "completed" and rec.results:
            saved = await svc.download_results(rec)
        return _jdump(_job_summary(rec, saved))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def cancel_job(job_id: str) -> str:
    """Cancel an in-progress job (DELETE /jobs/{id})."""
    try:
        rec = await _find_service(job_id).cancel(job_id)
        return _jdump(_job_summary(rec))
    except Exception as exc:  # noqa: BLE001
        return _err(exc)


@mcp.tool()
async def list_jobs() -> str:
    """List all jobs across every account in the pool (this session)."""
    jobs: list[dict[str, Any]] = []
    for svc, label in zip(_pool().services, _pool().labels):
        for r in svc.registry.all():
            d = r.to_dict()
            d["account"] = label
            jobs.append(d)
    jobs.sort(key=lambda d: d.get("created_at", 0), reverse=True)
    return _jdump({"jobs": jobs})


@mcp.tool()
async def download_job_result(job_id: str, output_dir: str | None = None) -> str:
    """Re-fetch a completed job's results and save them to disk."""
    try:
        svc = _find_service(job_id)
        rec = await svc.refresh(job_id)
        if rec is None:
            return _jdump({"error": f"Job {job_id} not found."})
        if not rec.results:
            return _jdump({"error": f"Job {job_id} has no downloadable results.", "status": rec.status})
        out = Path(output_dir) if output_dir else None
        saved = await svc.download_results(rec, out)
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
