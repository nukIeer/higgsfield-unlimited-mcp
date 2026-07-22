"""High-level orchestration: submit -> track -> (wait) -> (download).

Sits between the thin MCP tool layer (``server.py``) and the HTTP client
(``client.py``). Owns the job registry and the concurrency semaphore.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any

from .client import (
    HiggsfieldClient,
    HiggsfieldError,
    extract_job_id,
    extract_result_urls,
    normalize_status,
)
from .config import Config
from .jobs import (
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    JobRecord,
    JobRegistry,
)

log = logging.getLogger("higgsfield.service")

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class Service:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.client = HiggsfieldClient(config)
        self.registry = JobRegistry()
        self._sema = asyncio.Semaphore(max(1, config.max_concurrent))

    async def aclose(self) -> None:
        await self.client.aclose()

    # ------------------------------------------------------------------ #
    # Input resolution: upload local files, return usable URLs
    # ------------------------------------------------------------------ #
    async def resolve_inputs(
        self, input_files: list[str] | None, input_images: list | None
    ) -> list[dict[str, Any]]:
        """Return input media as Higgsfield media-objects.

        Higgsfield expects ``input_images`` as a list of
        ``{"id": ..., "type": "media_input", "url": ...}`` objects (see the HAR
        capture / docs/MODEL_SCHEMAS.md). Accepts raw URL strings or already-formed
        objects in ``input_images`` and uploads any local ``input_files``.
        """
        media: list[dict[str, Any]] = []
        for item in input_images or []:
            if isinstance(item, dict):
                item.setdefault("type", "media_input")
                media.append(item)
            elif isinstance(item, str):
                media.append({"type": "media_input", "url": item})
        for f in input_files or []:
            uploaded = await self.client.upload_file(f)
            url = uploaded.get("url")
            if not url:
                raise HiggsfieldError(f"Upload of {f} did not return a URL: {uploaded}")
            obj = {"type": "media_input", "url": url}
            if uploaded.get("id"):
                obj["id"] = uploaded["id"]
            media.append(obj)
        return media

    # ------------------------------------------------------------------ #
    # Core: submit + track
    # ------------------------------------------------------------------ #
    async def submit(
        self,
        *,
        model: str,
        params: dict[str, Any],
        kind: str,
        prompt: str | None = None,
    ) -> JobRecord:
        async with self._sema:
            response = await self.client.submit_job(model, params)
        job_id = extract_job_id(response) or f"local-{int(time.time() * 1000)}"
        status = normalize_status(response)
        rec = JobRecord(
            id=job_id,
            model=model,
            kind=kind,
            status=status if status != "unknown" else STATUS_RUNNING,
            prompt=prompt,
            raw=response if isinstance(response, dict) else {"response": response},
        )
        # Some endpoints return results synchronously.
        results = extract_result_urls(response)
        if results:
            rec.results = results
            rec.status = STATUS_COMPLETED
        self.registry.add(rec)
        return rec

    async def submit_v2(
        self,
        *,
        model: str,
        params: dict[str, Any],
        kind: str,
        prompt: str | None = None,
    ) -> JobRecord:
        """Submit via the v2 endpoint (/jobs/v2/{model})."""
        async with self._sema:
            response = await self.client.submit_job_v2(model, params)
        job_id = extract_job_id(response) or f"local-{int(time.time() * 1000)}"
        status = normalize_status(response)
        rec = JobRecord(
            id=job_id,
            model=model,
            kind=kind,
            status=status if status != "unknown" else STATUS_RUNNING,
            prompt=prompt,
            raw=response if isinstance(response, dict) else {"response": response},
        )
        results = extract_result_urls(response)
        if results:
            rec.results = results
            rec.status = STATUS_COMPLETED
        self.registry.add(rec)
        return rec

    @staticmethod
    def to_v2_medias(media_objs: list[dict[str, Any]], role: str = "image") -> list[dict[str, Any]]:
        """Wrap resolved media objects into v2 ``medias`` entries: {role, data}."""
        return [{"role": role, "data": obj} for obj in media_objs]

    # ------------------------------------------------------------------ #
    # Poll a single job (refresh registry from remote)
    # ------------------------------------------------------------------ #
    async def refresh(self, job_id: str) -> JobRecord | None:
        rec = self.registry.get(job_id)
        if rec is not None and rec.is_terminal:
            return rec
        try:
            payload = await self.client.poll_job(job_id)
        except HiggsfieldError as exc:
            if rec is not None:
                return rec
            raise exc
        status = normalize_status(payload)
        results = extract_result_urls(payload)
        if rec is None:
            rec = JobRecord(
                id=job_id,
                model=(payload.get("model") if isinstance(payload, dict) else "") or "",
                kind="remote",
                status=status,
                raw=payload if isinstance(payload, dict) else {},
            )
            self.registry.add(rec)
        rec.raw = payload if isinstance(payload, dict) else rec.raw
        if status != "unknown":
            rec.status = status
        if results:
            rec.results = results
            if not rec.is_terminal:
                rec.status = STATUS_COMPLETED
        if isinstance(payload, dict):
            err = payload.get("error") or payload.get("failure_reason") or payload.get("message")
            if err and rec.status == STATUS_FAILED:
                rec.error = str(err)
        rec.touch()
        return rec

    # ------------------------------------------------------------------ #
    # Block until terminal
    # ------------------------------------------------------------------ #
    async def wait(
        self,
        job_id: str,
        *,
        timeout: float = 600.0,
        interval: float = 5.0,
    ) -> JobRecord:
        deadline = time.monotonic() + timeout
        while True:
            rec = await self.refresh(job_id)
            if rec is not None and rec.is_terminal:
                return rec
            if time.monotonic() >= deadline:
                if rec is not None:
                    rec.error = rec.error or f"wait_for_job timed out after {timeout}s"
                return rec  # type: ignore[return-value]
            await asyncio.sleep(interval)

    # ------------------------------------------------------------------ #
    # Resilient GET: try candidate paths, return the first that works.
    # Endpoint paths for account/workspace/media differ across deployments;
    # this keeps the tools working and makes the surviving path obvious.
    # ------------------------------------------------------------------ #
    async def try_get(
        self, candidates: list[str], params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: list[str] = []
        for path in candidates:
            try:
                data = await self.client.get(path, params=params)
                return {"_endpoint": path, "data": data}
            except HiggsfieldError as exc:
                errors.append(f"{path} -> {exc.status}")
                # A 401/403 won't be fixed by trying another path.
                if exc.status in (401, 403):
                    raise
        raise HiggsfieldError(
            "None of the candidate endpoints responded successfully. Tried: "
            + "; ".join(errors)
            + ". Update the path list in server.py if Higgsfield moved it."
        )

    async def cancel(self, job_id: str) -> JobRecord | None:
        try:
            await self.client.cancel_job(job_id)
        except HiggsfieldError as exc:
            # 404 => already gone; treat as cancelled.
            if exc.status not in (404,):
                raise
        rec = self.registry.update(job_id, status=STATUS_CANCELLED)
        if rec is None:
            rec = JobRecord(id=job_id, model="", kind="remote", status=STATUS_CANCELLED)
            self.registry.add(rec)
        return rec

    # ------------------------------------------------------------------ #
    # Download a completed job's results to disk
    # ------------------------------------------------------------------ #
    async def download_results(
        self, rec: JobRecord, out_dir: Path | None = None
    ) -> list[str]:
        out_dir = out_dir or self.config.ensure_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        saved: list[str] = []
        for i, res in enumerate(rec.results):
            url = res.get("url")
            if not url:
                continue
            ext = _guess_ext(url, rec.kind)
            base = _SAFE_NAME.sub("_", (rec.prompt or rec.model or "result"))[:40].strip("_")
            name = f"{base or 'result'}_{rec.id[:8]}_{i}{ext}"
            dest = out_dir / name
            await self.client.download(url, dest)
            saved.append(str(dest))
        return saved


def _guess_ext(url: str, kind: str) -> str:
    path = url.split("?")[0].lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm", ".mp3", ".wav", ".m4a"):
        if path.endswith(ext):
            return ext
    if kind == "video":
        return ".mp4"
    if kind == "audio":
        return ".mp3"
    return ".png"
