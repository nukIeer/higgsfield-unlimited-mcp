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
    """Best-effort extraction of a job id from a submit/poll response."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
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
            url = _first(node, _URL_KEYS)
            if url and isinstance(url, str) and url.startswith("http"):
                results.append({"url": url, "type": node.get("type") or node.get("kind")})
            for v in node.values():
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

    async def aclose(self) -> None:
        await self._http.aclose()

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
    async def upload_file(self, file_path: str | Path) -> dict[str, Any]:
        """Upload a local image/video and return the hosted media descriptor.

        Higgsfield issues a presigned upload target, we PUT the bytes, then
        register the media. Endpoint shapes vary; this implements the common
        presign->PUT->confirm flow and falls back to a direct multipart upload.
        """
        path = Path(file_path).expanduser()
        if not path.is_file():
            raise HiggsfieldError(f"File not found: {path}")
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

        # 1) Ask for a presigned upload URL.
        presign = await self.post(
            "/media/upload-url",
            json={"filename": path.name, "content_type": content_type, "size": len(data)},
        )
        upload_url = _first(presign or {}, ("upload_url", "url", "put_url"))
        media_url = _first(presign or {}, ("public_url", "cdn_url", "media_url", "download_url"))
        media_id = _first(presign or {}, _ID_KEYS)

        if upload_url:
            put = await self._http.put(
                upload_url, content=data, headers={"Content-Type": content_type}
            )
            if put.status_code >= 400:
                raise HiggsfieldError(
                    f"Presigned upload PUT failed ({put.status_code})", status=put.status_code
                )
            # 2) Confirm/register if the API expects it.
            if media_id:
                try:
                    await self.post("/media/confirm", json={"id": media_id})
                except HiggsfieldError:
                    pass  # some deployments don't require a confirm step
            return {"id": media_id, "url": media_url or upload_url.split("?")[0]}

        # Fallback: direct multipart upload.
        jwt = await self.auth.get_jwt()
        resp = await self._http.post(
            f"{API_BASE}/media",
            headers={"Authorization": f"Bearer {jwt}"},
            files={"file": (path.name, data, content_type)},
        )
        result = self._handle_response(resp, expect_json=True)
        return {
            "id": extract_job_id(result),
            "url": _first(result or {}, _URL_KEYS),
            "raw": result,
        }

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
