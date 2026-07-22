"""HTTP client for the Higgsfield generation API (unlimited mode).

All generation goes through ``POST /jobs/{model}`` with unlimited mode enabled by
setting ``use_unlim: true`` in both the ``params`` object and the top-level body.
The client injects a fresh Clerk JWT, retries once on a 401, and normalises the
various job response shapes into a small common structure.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import random
import time
from pathlib import Path
from typing import Any

import httpx

from .auth import AuthError, ClerkAuth
from .config import API_BASE, Config

log = logging.getLogger("higgsfield.client")


class HiggsfieldError(RuntimeError):
    """API-level error with the HTTP status and (parsed) body attached."""

    def __init__(self, message: str, status: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


# Candidate keys that carry a job id in various responses.
_ID_KEYS = ("id", "job_id", "jobId", "uuid")
# Candidate keys that carry a status string.
_STATUS_KEYS = ("status", "state", "job_status")
# Candidate keys carrying a result URL.
_URL_KEYS = ("url", "result_url", "output_url", "min_url", "raw_url", "cdn_url", "video_url",
             "image_url", "audio_url", "signed_url")


def _first(d: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for k in keys:
        if k in d and d[k]:
            return d[k]
    return None


def extract_job_id(payload: Any) -> str | None:
    """Best-effort extraction of a *pollable* job id from a submit/poll response.

    Higgsfield's create response nests the real job id under
    ``job_sets[].jobs[].id`` — the top-level ``id`` is the project id and is NOT
    pollable via ``GET /jobs/{id}``. Prefer the nested job id.
    """
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        job_sets = payload.get("job_sets")
        if isinstance(job_sets, list) and job_sets:
            jobs = job_sets[0].get("jobs") if isinstance(job_sets[0], dict) else None
            if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
                jid = _first(jobs[0], _ID_KEYS)
                if jid:
                    return str(jid)
        jid = _first(payload, _ID_KEYS)
        if jid:
            return str(jid)
        # Sometimes wrapped: {"job": {...}} or {"data": {...}}
        for wrap in ("job", "data", "result"):
            inner = payload.get(wrap)
            if isinstance(inner, dict):
                jid = _first(inner, _ID_KEYS)
                if jid:
                    return str(jid)
    return None


def normalize_status(payload: Any) -> str:
    """Map a raw status string to one of our canonical statuses."""
    raw = None
    if isinstance(payload, dict):
        raw = _first(payload, _STATUS_KEYS)
        if raw is None:
            for wrap in ("job", "data", "result"):
                inner = payload.get(wrap)
                if isinstance(inner, dict):
                    raw = _first(inner, _STATUS_KEYS)
                    if raw:
                        break
    if not raw:
        return "unknown"
    raw = str(raw).lower()
    if raw in ("completed", "succeeded", "success", "done", "finished", "ready"):
        return "completed"
    if raw in ("failed", "error", "errored", "rejected"):
        return "failed"
    if raw in ("cancelled", "canceled", "aborted"):
        return "cancelled"
    if raw in ("queued", "pending", "created", "accepted", "nsfw_check"):
        return "queued"
    if raw in ("running", "in_progress", "processing", "started", "generating"):
        return "running"
    return raw


def extract_result_urls(payload: Any) -> list[dict[str, Any]]:
    """Collect result media descriptors from a completed job payload."""
    results: list[dict[str, Any]] = []

    def _scan(node: Any) -> None:
        if isinstance(node, dict):
            # Skip source/input media — those are not generation outputs.
            if node.get("type") == "media_input":
                return
            url = _first(node, _URL_KEYS)
            if url and isinstance(url, str) and url.startswith("http"):
                results.append({"url": url, "type": node.get("type") or node.get("kind")})
            for k, v in node.items():
                if k in ("input_images", "input_image", "medias", "reference_elements"):
                    continue  # these carry input media, not results
                _scan(v)
        elif isinstance(node, list):
            for item in node:
                _scan(item)

    _scan(payload)
    # de-dup by url, preserve order
    seen: set[str] = set()
    deduped = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            deduped.append(r)
    return deduped


class HiggsfieldClient:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._http = httpx.AsyncClient(
            timeout=config.request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://higgsfield.ai",
                "Referer": "https://higgsfield.ai/",
                "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
            },
        )
        self.auth = ClerkAuth(config, self._http)
        # Per-account request pacing (anti-DataDome).
        self._throttle_lock = asyncio.Lock()
        self._next_allowed_ts = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _throttle(self) -> None:
        """Space out API calls on this account so we look human to DataDome."""
        interval = self._config.min_request_interval
        if interval <= 0:
            return
        async with self._throttle_lock:
            now = time.monotonic()
            wait = self._next_allowed_ts - now
            if wait > 0:
                await asyncio.sleep(wait)
            # Schedule the next slot with a random jitter (+0–50%).
            gap = interval + random.uniform(0, interval * 0.5)
            self._next_allowed_ts = time.monotonic() + gap

    # --------------------------------------------------------------------- #
    # Core request with auth + 401 retry
    # --------------------------------------------------------------------- #
    async def request(
        self,
        method: str,
        url: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        expect_json: bool = True,
    ) -> Any:
        for attempt in (1, 2):
            await self._throttle()
            jwt = await self.auth.get_jwt(force=(attempt == 2))
            headers = {"Authorization": f"Bearer {jwt}"}
            if self._config.extra_cookies:
                # Forward the browser's existing session cookies (e.g. datadome)
                # so the account's own session is recognised.
                headers["Cookie"] = self._config.extra_cookies
            resp = await self._http.request(
                method, url, json=json, params=params, headers=headers
            )
            if resp.status_code == 401 and attempt == 1:
                log.debug("401 on %s %s — refreshing JWT and retrying once", method, url)
                self.auth.invalidate()
                continue
            return self._handle_response(resp, expect_json)
        raise HiggsfieldError("Unreachable retry state")  # pragma: no cover

    @staticmethod
    def _handle_response(resp: httpx.Response, expect_json: bool) -> Any:
        if resp.status_code >= 400:
            body: Any
            try:
                body = resp.json()
            except ValueError:
                body = resp.text[:500]
            msg = f"Higgsfield API {resp.request.method} {resp.request.url} -> {resp.status_code}"
            if resp.status_code == 422:
                msg += (
                    " (Unprocessable Entity). The model rejected the params — the "
                    "body below lists the required/invalid fields. Add them via "
                    "extra_params or use generate_raw."
                )
            raise HiggsfieldError(msg, status=resp.status_code, body=body)
        if not expect_json:
            return resp
        if not resp.content:
            return {}
        try:
            return resp.json()
        except ValueError:
            return {"_raw_text": resp.text}

    # --------------------------------------------------------------------- #
    # Generation
    # --------------------------------------------------------------------- #
    async def submit_job(self, model: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST /jobs/{model} with unlimited mode enabled."""
        params = dict(params)
        params["use_unlim"] = True
        body = {"params": params, "use_unlim": True}
        url = f"{API_BASE}/jobs/{model}"
        return await self.request("POST", url, json=body)

    async def submit_job_v2(self, model: str, params: dict[str, Any]) -> dict[str, Any]:
        """POST /jobs/v2/{model} — the newer API generation (video + newer image models).

        v2 differs from v1: the path is ``/jobs/v2/{underscore_id}``, ``params`` carries
        a ``model`` field, and input media go under ``medias`` as
        ``[{"role": ..., "data": {id, type, url}}]`` (see docs/MODEL_SCHEMAS.md).
        """
        params = dict(params)
        params["use_unlim"] = True
        params["model"] = model
        body = {"params": params, "use_unlim": True}
        url = f"{API_BASE}/jobs/v2/{model}"
        return await self.request("POST", url, json=body)

    async def poll_job(self, job_id: str) -> dict[str, Any]:
        """GET /jobs/{id}."""
        url = f"{API_BASE}/jobs/{job_id}"
        return await self.request("GET", url)

    async def cancel_job(self, job_id: str) -> dict[str, Any]:
        """DELETE /jobs/{id}."""
        url = f"{API_BASE}/jobs/{job_id}"
        return await self.request("DELETE", url)

    async def accessible_jobs(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """GET /jobs/accessible — recent generation history for the account."""
        url = f"{API_BASE}/jobs/accessible"
        return await self.request("GET", url, params={"limit": limit, "offset": offset})

    # --------------------------------------------------------------------- #
    # Account / workspaces / media / assets — generic passthroughs
    # --------------------------------------------------------------------- #
    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        return await self.request("GET", url, params=params)

    async def post(self, path: str, json: Any = None) -> Any:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        return await self.request("POST", url, json=json)

    async def delete(self, path: str) -> Any:
        url = path if path.startswith("http") else f"{API_BASE}{path}"
        return await self.request("DELETE", url)

    # --------------------------------------------------------------------- #
    # Media upload (local file -> hosted URL usable as input_images)
    # --------------------------------------------------------------------- #
    async def upload_file(
        self, file_path: str | Path, wait_ip_check: bool = True
    ) -> dict[str, Any]:
        """Upload a local image/video and return its media descriptor {id, url, ...}.

        Implements Higgsfield's real 3-step flow (captured from traffic):
          1. POST /media/batch  -> [{id, url, upload_url}] (presigned S3 target)
          2. PUT  <upload_url>  with the raw bytes + Content-Type
          3. POST /media/{id}/upload  -> finalises + starts NSFW/IP checks

        The returned ``url`` is the public CDN URL to use in
        ``input_images``/``medias`` as ``{id, type: "media_input", url}``.
        """
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise HiggsfieldError(f"File not found: {path}")
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"

        # 1) Reserve a media slot + presigned upload URL.
        batch = await self.post(
            "/media/batch",
            json={"mimetypes": [content_type], "source": "user_upload", "force_ip_check": False},
        )
        if not isinstance(batch, list) or not batch:
            raise HiggsfieldError(f"/media/batch returned no slot: {batch}")
        slot = batch[0]
        media_id = slot.get("id")
        public_url = slot.get("url")
        upload_url = slot.get("upload_url")
        if not (media_id and public_url and upload_url):
            raise HiggsfieldError(f"/media/batch slot missing fields: {slot}")

        # 2) PUT the bytes to S3. The presigned URL signs content-type + host.
        put = await self._http.put(
            upload_url, content=data, headers={"Content-Type": content_type}
        )
        if put.status_code >= 400:
            raise HiggsfieldError(
                f"Presigned S3 upload failed ({put.status_code}): {put.text[:200]}",
                status=put.status_code,
            )

        # 3) Finalise — triggers NSFW/IP checks.
        await self.post(
            f"/media/{media_id}/upload",
            json={"filename": path.name, "force_nsfw_check": True, "force_ip_check": False},
        )

        if wait_ip_check:
            await self._await_media_ready(media_id)

        return {"id": media_id, "url": public_url, "type": "media_input"}

    async def _await_media_ready(self, media_id: str, timeout: float = 60.0) -> None:
        """Poll until the media's IP/NSFW check finishes (best-effort)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                info = await self.get(f"/media/{media_id}")
            except HiggsfieldError:
                return
            if isinstance(info, dict):
                done = info.get("ip_check_finished")
                status = str(info.get("status", "")).lower()
                if done or status in ("ready", "processed", "completed"):
                    return
            await asyncio.sleep(3)

    # --------------------------------------------------------------------- #
    # File download
    # --------------------------------------------------------------------- #
    async def download(self, url: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        async with self._http.stream("GET", url) as resp:
            if resp.status_code >= 400:
                raise HiggsfieldError(
                    f"Download failed ({resp.status_code}) for {url}", status=resp.status_code
                )
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes():
                    fh.write(chunk)
        return dest
