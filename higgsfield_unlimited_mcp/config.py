"""Environment-driven configuration for the Higgsfield Unlimited MCP server."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# API endpoints
# --------------------------------------------------------------------------- #
CLERK_BASE = "https://clerk.higgsfield.ai"
API_BASE = "https://fnf.higgsfield.ai"
PLATFORM_BASE = "https://higgsfield.ai"


def _load_dotenv() -> None:
    """Minimal, dependency-free .env loader.

    Looks for a .env file in the current directory (or HIGGSFIELD_DOTENV) and
    sets any keys not already present in the environment. Existing env vars win,
    so MCP-config `env` blocks always take precedence.
    """
    path = Path(os.environ.get("HIGGSFIELD_DOTENV", ".env"))
    if not path.is_file():
        return
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Config:
    """Runtime configuration, populated from environment variables."""

    clerk_cookie: str = field(default_factory=lambda: os.environ.get("HIGGSFIELD_CLERK_COOKIE", ""))
    session_id: str = field(default_factory=lambda: os.environ.get("HIGGSFIELD_SESSION_ID", ""))
    # Extra cookies to forward to the API (e.g. a `datadome` session cookie your
    # browser already holds). Raw cookie string form: "datadome=xxx; foo=bar".
    # This reuses your existing browser session; it does not solve challenges.
    extra_cookies: str = field(
        default_factory=lambda: os.environ.get("HIGGSFIELD_EXTRA_COOKIES", "")
    )
    max_concurrent: int = field(default_factory=lambda: _get_int("HIGGSFIELD_MAX_CONCURRENT", 4))
    default_model: str = field(
        default_factory=lambda: os.environ.get("HIGGSFIELD_DEFAULT_MODEL", "nano-banana-2")
    )
    default_resolution: str = field(
        default_factory=lambda: os.environ.get("HIGGSFIELD_DEFAULT_RESOLUTION", "2k")
    )
    output_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("HIGGSFIELD_OUTPUT_DIR", "./higgsfield_output")
        )
    )
    log_level: str = field(default_factory=lambda: os.environ.get("HIGGSFIELD_LOG_LEVEL", "INFO"))
    # How often (seconds) to proactively refresh the Clerk JWT. Clerk tokens have
    # a ~5 min TTL, so we refresh a little before that.
    jwt_refresh_seconds: int = field(
        default_factory=lambda: _get_int("HIGGSFIELD_JWT_REFRESH_SECONDS", 240)
    )
    request_timeout: float = field(
        default_factory=lambda: float(os.environ.get("HIGGSFIELD_REQUEST_TIMEOUT", "120"))
    )

    def validate(self) -> list[str]:
        """Return a list of human-readable problems, empty if config is usable."""
        problems: list[str] = []
        if not self.clerk_cookie:
            problems.append("HIGGSFIELD_CLERK_COOKIE is not set (the __client cookie).")
        if not self.session_id:
            problems.append("HIGGSFIELD_SESSION_ID is not set (window.Clerk.session.id).")
        elif not self.session_id.startswith("sess_"):
            problems.append("HIGGSFIELD_SESSION_ID should start with 'sess_'.")
        if self.default_resolution not in ("1k", "2k", "4k"):
            problems.append("HIGGSFIELD_DEFAULT_RESOLUTION must be one of 1k, 2k, 4k.")
        return problems

    def ensure_output_dir(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


@dataclass
class Account:
    """One Higgsfield login. Multiple accounts run in parallel to sidestep the
    per-account concurrency / rate limit (429 rate_limit_reached)."""

    label: str
    session_id: str
    clerk_cookie: str
    extra_cookies: str = ""

    def is_valid(self) -> bool:
        return bool(self.session_id and self.clerk_cookie)


def enumerate_accounts() -> list[Account]:
    """Discover all configured accounts.

    Sources (all merged, de-duplicated by session_id):
      1. Primary: ``HIGGSFIELD_SESSION_ID`` / ``HIGGSFIELD_CLERK_COOKIE`` /
         ``HIGGSFIELD_EXTRA_COOKIES``.
      2. Numbered: ``HIGGSFIELD_SESSION_ID_2`` / ``..._CLERK_COOKIE_2`` / ``..._EXTRA_COOKIES_2``
         for 2..N (contiguous; stops at the first missing index).
      3. JSON: ``HIGGSFIELD_ACCOUNTS_JSON`` = a JSON array of
         ``{"session_id","clerk_cookie","extra_cookies","label"}`` objects.
    """
    accounts: list[Account] = []
    seen: set[str] = set()

    def _add(label: str, sid: str, cookie: str, extra: str) -> None:
        sid = (sid or "").strip()
        if not sid or sid in seen:
            return
        seen.add(sid)
        accounts.append(Account(label=label, session_id=sid, clerk_cookie=(cookie or "").strip(),
                                extra_cookies=(extra or "").strip()))

    _add("account-1", os.environ.get("HIGGSFIELD_SESSION_ID", ""),
         os.environ.get("HIGGSFIELD_CLERK_COOKIE", ""),
         os.environ.get("HIGGSFIELD_EXTRA_COOKIES", ""))

    for i in range(2, 33):
        sid = os.environ.get(f"HIGGSFIELD_SESSION_ID_{i}")
        if not sid:
            break
        _add(f"account-{i}", sid,
             os.environ.get(f"HIGGSFIELD_CLERK_COOKIE_{i}", ""),
             os.environ.get(f"HIGGSFIELD_EXTRA_COOKIES_{i}", ""))

    raw = os.environ.get("HIGGSFIELD_ACCOUNTS_JSON")
    if raw:
        try:
            for j, item in enumerate(json.loads(raw), start=1):
                _add(item.get("label") or f"json-{j}", item.get("session_id", ""),
                     item.get("clerk_cookie", ""), item.get("extra_cookies", ""))
        except (ValueError, TypeError, AttributeError):
            pass

    return accounts


_config: Config | None = None


def get_config() -> Config:
    """Return the process-wide config singleton."""
    global _config
    if _config is None:
        _load_dotenv()
        _config = Config()
    return _config
