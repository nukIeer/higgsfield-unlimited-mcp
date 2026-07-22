"""Smoke test CLI: ``higgsfield-unlimited-verify``.

Checks, in order:
  1. Config is present and well-formed.
  2. A fresh Clerk JWT can be minted from the cookie.
  3. Read-only API endpoints respond (account / generation history).
  4. (optional) One test image generation + download.

Flags:
  --skip-generate   Auth + API checks only (no generation, no credits used).
  --keep-output     Keep the test image after a successful generation.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import get_config
from .service import Service

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def _ok(msg: str) -> None:
    print(f"{GREEN}[PASS]{RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"{RED}[FAIL]{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET} {msg}")


async def _run(skip_generate: bool, keep_output: bool) -> int:
    cfg = get_config()
    print("Higgsfield Unlimited MCP — verification\n" + "=" * 40)

    problems = cfg.validate()
    if problems:
        _fail("Configuration problems:")
        for p in problems:
            print(f"       - {p}")
        return 1
    _ok("Configuration present (cookie + session id set).")

    svc = Service(cfg)
    exit_code = 0
    try:
        # 2. Auth
        try:
            jwt = await svc.client.auth.get_jwt(force=True)
            _ok(f"Clerk JWT minted ({len(jwt)} chars).")
        except Exception as exc:  # noqa: BLE001
            _fail(f"Could not mint JWT: {exc}")
            return 1

        # 3. Read-only endpoints (best-effort; warn rather than hard-fail).
        try:
            hist = await svc.client.accessible_jobs(limit=1)
            _ok(f"Generation history endpoint OK ({type(hist).__name__}).")
        except Exception as exc:  # noqa: BLE001
            _warn(f"Generation history endpoint did not respond: {exc}")

        try:
            acct = await svc.try_get(["/account", "/account/info", "/me"])
            _ok(f"Account endpoint OK via {acct['_endpoint']}.")
        except Exception as exc:  # noqa: BLE001
            _warn(f"Account endpoint not reachable (paths may differ): {exc}")

        # 4. Generation
        if skip_generate:
            _warn("Skipping test generation (--skip-generate).")
        else:
            print("\nRunning a test image generation (this uses unlimited mode)...")
            try:
                from . import dimensions as dims

                w, h = dims.get_dimensions("1:1", "1k")
                params = {
                    "prompt": "a simple red circle on a white background, test image",
                    "width": w,
                    "height": h,
                    "aspect_ratio": "1:1",
                    "resolution": "1k",
                    "batch_size": 1,
                }
                rec = await svc.submit(
                    model=cfg.default_model, params=params, kind="image", prompt="verify test"
                )
                if not rec.is_terminal:
                    rec = await svc.wait(rec.id, timeout=180)
                if rec.status == "completed" and rec.results:
                    _ok(f"Test generation completed: {len(rec.results)} result(s).")
                    saved = await svc.download_results(rec)
                    _ok(f"Downloaded: {saved}")
                    if not keep_output:
                        for s in saved:
                            try:
                                Path(s).unlink()
                            except OSError:
                                pass
                        print("       (test file removed; use --keep-output to keep it)")
                else:
                    _fail(f"Test generation ended with status={rec.status} error={rec.error}")
                    exit_code = 1
            except Exception as exc:  # noqa: BLE001
                _fail(f"Test generation failed: {exc}")
                exit_code = 1

        print("\n" + "=" * 40)
        if exit_code == 0:
            print(f"{GREEN}All checks passed.{RESET}")
        else:
            print(f"{RED}Some checks failed.{RESET}")
        return exit_code
    finally:
        await svc.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Higgsfield Unlimited MCP setup.")
    parser.add_argument("--skip-generate", action="store_true", help="Auth + API checks only.")
    parser.add_argument("--keep-output", action="store_true", help="Keep the test image on success.")
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args.skip_generate, args.keep_output)))


if __name__ == "__main__":
    main()
