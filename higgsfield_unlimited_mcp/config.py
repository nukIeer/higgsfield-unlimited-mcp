"""Environment-driven configuration for the Higgsfield Unlimited MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# API endpoints
# --------------------------------------------------------------------------- #
CLERK_BASE = "https://clerk.higgsfield.ai"
API_BASE = "https://fnf.higgsfield.ai"
PLATFORM_BASE = "https://higgsfield.ai"


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


_config: Config | None = None


def get_config() -> Config:
    """Return the process-wide config singleton."""
    global _config
    if _config is None:
        _config = Config()
    return _config
