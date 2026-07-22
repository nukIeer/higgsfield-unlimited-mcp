"""Multi-account pool.

A single Higgsfield account serialises jobs behind a per-account concurrency /
rate limit (HTTP 429 ``rate_limit_reached``). The pool spreads work across several
accounts so many generations run in parallel, and fails a job over to another
account when one hits its limit.

Each account gets its own :class:`Service` (own HTTP client, JWT, cookies, job
registry, concurrency semaphore). Generation tools submit through the pool, which
picks the least-busy account not currently cooling down.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from .client import HiggsfieldError
from .config import Account, Config, enumerate_accounts, get_config
from .jobs import JobRecord
from .service import Service

log = logging.getLogger("higgsfield.pool")

# How long to rest an account after a 429 before routing to it again.
_COOLDOWN_SECONDS = 20.0


def _is_rate_limited(exc: HiggsfieldError) -> bool:
    if exc.status == 429:
        return True
    body = exc.body
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, dict) and detail.get("error_type") == "rate_limit_reached":
            return True
    return False


class Pool:
    def __init__(self, base: Config, accounts: list[Account]) -> None:
        self.base = base
        self.accounts = accounts
        self.services: list[Service] = []
        self.labels: list[str] = []
        for acc in accounts:
            cfg = dataclasses.replace(
                base,
                session_id=acc.session_id,
                clerk_cookie=acc.clerk_cookie,
                extra_cookies=acc.extra_cookies,
            )
            self.services.append(Service(cfg))
            self.labels.append(acc.label)
        self._cooldown_until: list[float] = [0.0] * len(self.services)
        # Jobs picked-but-not-yet-submitted per account, so simultaneous fan-out
        # (a batch) spreads across accounts instead of piling on account-1.
        self._pending: list[int] = [0] * len(self.services)
        self._pick_lock = asyncio.Lock()

    async def aclose(self) -> None:
        for svc in self.services:
            await svc.aclose()

    # ------------------------------------------------------------------ #
    def primary(self) -> Service:
        return self.services[0]

    def _load(self, idx: int) -> int:
        # In-flight jobs (running) + picked-but-not-yet-submitted.
        return self.services[idx].registry.snapshot()["active_count"] + self._pending[idx]

    def _cooldown(self, idx: int) -> None:
        self._cooldown_until[idx] = time.monotonic() + _COOLDOWN_SECONDS

    # ------------------------------------------------------------------ #
    def _allowed_indices(self, account: str | int | None) -> list[int] | None:
        """Which account indices this job may use (None = any)."""
        if account is None:
            return list(range(len(self.services)))
        if isinstance(account, int):
            return [account] if 0 <= account < len(self.services) else []
        return [i for i, label in enumerate(self.labels) if label == account or account in label]

    async def _pick(self, allowed: list[int], exclude: set[int]) -> int | None:
        """Atomically choose the least-loaded, non-cooling account and reserve it."""
        async with self._pick_lock:
            now = time.monotonic()
            ready = [i for i in allowed if i not in exclude and self._cooldown_until[i] <= now]
            pool = ready or [i for i in allowed if i not in exclude]  # all cooling? still try
            if not pool:
                return None
            idx = min(pool, key=lambda i: (self._load(i), self._cooldown_until[i]))
            self._pending[idx] += 1
            return idx

    async def run_job(
        self,
        submit: Callable[[Service], Awaitable[JobRecord]],
        *,
        wait: bool,
        download: bool,
        timeout: float,
        out_dir: Path | None = None,
        account: str | int | None = None,
    ) -> dict[str, Any]:
        """Submit one job with cross-account failover, then optionally wait + download.

        ``submit`` is a coroutine factory that performs the actual submit on a given
        service (so image=v1, video=v2, etc. all reuse this). ``account`` pins to a
        specific account (label or index) and disables failover — use it when the job
        references media that only one account owns.
        """
        attempts: list[dict[str, Any]] = []
        last_exc: HiggsfieldError | None = None

        allowed = self._allowed_indices(account)
        if not allowed:
            return {"error": f"Unknown account selector: {account!r}",
                    "available": self.labels}

        exclude: set[int] = set()
        while True:
            idx = await self._pick(allowed, exclude)
            if idx is None:
                break  # every allowed account tried / rate-limited
            svc = self.services[idx]
            label = self.labels[idx]
            try:
                rec = await submit(svc)
            except HiggsfieldError as exc:
                last_exc = exc
                rate = _is_rate_limited(exc)
                attempts.append({"account": label, "status": exc.status, "rate_limited": rate})
                if rate:
                    self._cooldown(idx)
                    exclude.add(idx)
                    continue  # try the next account
                raise  # a non-rate-limit error won't be fixed by another account
            finally:
                self._pending[idx] -= 1  # picked -> submitted (or failed); registry covers it now

            summary = self._summary(rec, label)
            if wait and not rec.is_terminal:
                rec = await svc.wait(rec.id, timeout=timeout)
                summary = self._summary(rec, label)
            if download and rec.status == "completed" and rec.results:
                summary["downloaded"] = await svc.download_results(rec, out_dir)
            if attempts:
                summary["account_attempts"] = attempts
            return summary

        return {
            "error": "All accounts are rate-limited (429). Add more accounts via "
            "HIGGSFIELD_SESSION_ID_2/_3... or retry shortly.",
            "account_attempts": attempts,
            "last_body": last_exc.body if last_exc else None,
        }

    @staticmethod
    def _summary(rec: JobRecord, account: str) -> dict[str, Any]:
        d: dict[str, Any] = {
            "job_id": rec.id,
            "account": account,
            "model": rec.model,
            "kind": rec.kind,
            "status": rec.status,
            "results": rec.results,
        }
        if rec.error:
            d["error"] = rec.error
        return d

    # ------------------------------------------------------------------ #
    def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        return {
            "accounts": len(self.services),
            "per_account": [
                {
                    "account": self.labels[i],
                    "cooling_down": self._cooldown_until[i] > now,
                    **self.services[i].registry.snapshot(),
                }
                for i in range(len(self.services))
            ],
        }


_pool: Pool | None = None


def get_pool() -> Pool:
    global _pool
    if _pool is None:
        base = get_config()
        accounts = enumerate_accounts()
        if not accounts:
            # Fall back to an (invalid) single account so validation reports nicely.
            accounts = [Account("account-1", base.session_id, base.clerk_cookie, base.extra_cookies)]
        _pool = Pool(base, accounts)
    return _pool
