"""Clerk JWT authentication for Higgsfield.

Higgsfield's web app authenticates with a short-lived JWT (~5 min TTL) issued by
Clerk. The long-lived ``__client`` cookie lets us mint fresh JWTs on demand:

    POST https://clerk.higgsfield.ai/v1/client/sessions/{session_id}/tokens
    Cookie: __client=<cookie>
    -> { "jwt": "..." }

This module caches the JWT and proactively refreshes it before expiry. On a 401,
callers should invalidate and retry once (see ``client.py``).
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .config import CLERK_BASE, Config

log = logging.getLogger("higgsfield.auth")


class AuthError(RuntimeError):
    """Raised when a fresh JWT cannot be minted from the Clerk cookie."""


class ClerkAuth:
    """Mints and caches Clerk JWTs from a ``__client`` cookie + session id."""

    def __init__(self, config: Config, http: httpx.AsyncClient) -> None:
        self._config = config
        self._http = http
        self._jwt: str | None = None
        self._minted_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def _token_url(self) -> str:
        return f"{CLERK_BASE}/v1/client/sessions/{self._config.session_id}/tokens"

    def _is_fresh(self) -> bool:
        if self._jwt is None:
            return False
        age = time.monotonic() - self._minted_at
        return age < self._config.jwt_refresh_seconds

    async def _mint(self) -> str:
        """Force-mint a new JWT from Clerk."""
        headers = {
            "Cookie": f"__client={self._config.clerk_cookie}",
            "Origin": "https://higgsfield.ai",
            "Referer": "https://higgsfield.ai/",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        # Clerk requires the API version query param used by the JS SDK.
        params = {"__clerk_api_version": "2025-04-10"}
        try:
            resp = await self._http.post(
                self._token_url, headers=headers, params=params, content=b""
            )
        except httpx.HTTPError as exc:  # network-level failure
            raise AuthError(f"Failed to reach Clerk token endpoint: {exc}") from exc

        if resp.status_code == 404:
            raise AuthError(
                "Clerk returned 404 for the session token request. Your "
                "HIGGSFIELD_SESSION_ID may be wrong or the session expired. "
                "Re-run window.Clerk.session.id in the browser console."
            )
        if resp.status_code in (401, 403):
            raise AuthError(
                "Clerk rejected the __client cookie (unauthorized). The cookie "
                "likely expired. Copy a fresh __client cookie from DevTools > "
                "Application > Cookies > https://higgsfield.ai."
            )
        if resp.status_code >= 400:
            raise AuthError(
                f"Clerk token request failed ({resp.status_code}): {resp.text[:300]}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise AuthError(f"Clerk token response was not JSON: {resp.text[:200]}") from exc

        jwt = data.get("jwt")
        if not jwt:
            raise AuthError(f"Clerk token response had no 'jwt' field: {data}")

        self._jwt = jwt
        self._minted_at = time.monotonic()
        log.debug("Minted fresh Clerk JWT")
        return jwt

    async def get_jwt(self, force: bool = False) -> str:
        """Return a valid JWT, minting a fresh one if needed.

        Args:
            force: If True, invalidate the cache and mint a new token. Used by
                callers after a 401 response.
        """
        async with self._lock:
            if force or not self._is_fresh():
                return await self._mint()
            assert self._jwt is not None
            return self._jwt

    def invalidate(self) -> None:
        self._jwt = None
        self._minted_at = 0.0
