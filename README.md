# Higgsfield Unlimited MCP

A complete [MCP](https://modelcontextprotocol.io) server for **Higgsfield AI** that
calls the generation API in **unlimited mode**, bypassing the credit system used by
the official Higgsfield MCP. Auth uses your existing browser session (Clerk JWT,
auto-refreshed every 4 minutes).

**What's covered:** image generation (32 models), video generation (31 models), audio
(TTS), storyboards (multi-shot continuity), workspaces, media library, assets,
favourites, generation history, account/plan info, job cancellation — everything the
official Higgsfield MCP exposes, plus video, audio, storyboard, and cancel that the
official MCP doesn't.

> Requires an active Higgsfield subscription with **unlimited mode enabled**.

---

## Quick Install

**Requirements:** Python 3.10+, Claude Code (or any MCP client)

```bash
pip install git+https://github.com/nukIeer/higgsfield-unlimited-mcp.git
```

Or with `uvx` (no install needed, runs ephemerally):

```bash
uvx --from git+https://github.com/nukIeer/higgsfield-unlimited-mcp.git higgsfield-unlimited-mcp
```

Then jump to [Setup](#setup) to wire up your credentials.

---

## Tools (31 total)

### Auth & account
| Tool | Description |
|------|-------------|
| `auth_status` | Verify Clerk credentials by fetching a fresh JWT. |
| `account_info` | Plan info, all credit balances, `has_unlim` flag. |
| `concurrent_state` | Concurrent-slot tier (4/8/12/16). |
| `queue_status` | In-process job registry snapshot. |

### Models
| Tool | Description |
|------|-------------|
| `list_models` | All 60+ generation models, optionally filtered by category (image / video / audio). |
| `get_aspect_dimensions` | Canonical pixel dims for an aspect ratio. |

### Image generation
| Tool | Description |
|------|-------------|
| `generate_image` | Single image — 32 models including nano-banana-2, flux-2, seedream-v4-5, openai-hazel, reve, z-image. Supports `input_files` for local-file auto-upload. |
| `generate_image_batch` | Queue many prompts; runs up to `max_concurrent` in parallel. |
| `generate_storyboard` | Multi-shot storyboard with character/style continuity (uses `nano-banana-2-shots`). |

### Video generation
| Tool | Description |
|------|-------------|
| `generate_video` | 31 models including seedance, kling/kling2-6, sora2-video, veo3/veo3-1, minimax-hailuo, wan2-2-video/wan2-5-video/wan2-6, image2video, infinite-talk. |

### Audio
| Tool | Description |
|------|-------------|
| `generate_audio` | Text-to-speech (`text2speech` model). |

### Generic / advanced
| Tool | Description |
|------|-------------|
| `generate_raw` | Escape hatch for any model with a custom params dict (face-swap, character-swap, upscale, inpaint, etc.). |

### Job management
| Tool | Description |
|------|-------------|
| `check_job` | Poll a single job (local + remote). |
| `wait_for_job` | Block until a job finishes; optionally download. |
| `cancel_job` | Cancel an in-progress job (`DELETE /jobs/{id}`). |
| `list_jobs` | List jobs in the local registry. |
| `download_job_result` | Re-fetch a completed job's results to disk. |
| `show_generations` | Server-side recent generation history (`/jobs/accessible`). |

### Workspaces
| Tool | Description |
|------|-------------|
| `list_workspaces` | List all your workspaces. |
| `workspace_details` | Active workspace info (id, name, type, role). |
| `workspace_wallet` | Credit balance. |
| `workspace_members` | Members of the active workspace. |
| `workspace_usage` | Credit-usage chart. |

### Media library
| Tool | Description |
|------|-------------|
| `show_medias` | Paginated media library (images + videos). |
| `media_upload` | Upload a local image/video for use as input on subsequent generations. |
| `media_status` | Check status of media items by id. |
| `media_download_batch` | Bulk download URLs by media id. |

### Assets & favourites
| Tool | Description |
|------|-------------|
| `list_assets` | List your assets. |
| `list_favourites` | List your favourited assets. |
| `like_asset` / `unlike_asset` | Add/remove asset from favourites. |

---

## Setup

### 1. Get your Higgsfield credentials (~2 min)

Open <https://higgsfield.ai> in Chrome while logged in.

**`__client` cookie:**
1. Open DevTools (`Cmd+Option+I` / `F12`)
2. Application → Cookies → `https://higgsfield.ai`
3. Copy the value of the `__client` cookie

**Session ID:**
1. DevTools → Console
2. Run: `window.Clerk.session.id`
3. Copy the result — it starts with `sess_`

### 2. Install

```bash
pip install git+https://github.com/nukIeer/higgsfield-unlimited-mcp.git
```

To update later:

```bash
pip install --upgrade git+https://github.com/nukIeer/higgsfield-unlimited-mcp.git
```

### 3. Add to Claude Code

Add this to your Claude Code MCP config (`~/.claude.json`, user-level). Paste your
credentials into the `env` block — they never leave your machine.

```json
{
  "mcpServers": {
    "higgsfield-unlimited": {
      "command": "python",
      "args": ["-m", "higgsfield_unlimited_mcp"],
      "env": {
        "HIGGSFIELD_CLERK_COOKIE": "<paste your __client cookie here>",
        "HIGGSFIELD_SESSION_ID": "sess_xxxxxxxxxxxxx",
        "HIGGSFIELD_MAX_CONCURRENT": "4",
        "HIGGSFIELD_DEFAULT_MODEL": "nano-banana-2",
        "HIGGSFIELD_DEFAULT_RESOLUTION": "2k"
      }
    }
  }
}
```

Or register via the CLI:

```bash
claude mcp add higgsfield-unlimited -s user -- python -m higgsfield_unlimited_mcp
```

Then set the env vars in `~/.claude.json` as shown above.

### 4. Verify it's working

```bash
# Full check: auth + API endpoints + 1 test image generation + download
higgsfield-unlimited-verify

# Auth + API checks only (no generation)
higgsfield-unlimited-verify --skip-generate

# Keep the test image after success
higgsfield-unlimited-verify --keep-output
```

Or from inside Claude Code:

> Use higgsfield-unlimited to check `auth_status`, then `account_info`.

---

## Multiple accounts (parallel generation)

A single account serialises jobs behind a per-account rate limit — hit it and the API
returns `429 rate_limit_reached`. Connect several accounts and the server load-balances
across them and fails a job over to another account on 429, so many generations run in
parallel.

Add numbered credentials in the `env` block — `_2`, `_3`, `_4`, `_5`, … each with its own
session id, `__client` cookie, and `datadome` cookie:

```json
"env": {
  "HIGGSFIELD_SESSION_ID": "sess_a...",
  "HIGGSFIELD_CLERK_COOKIE": "eyJ...a",
  "HIGGSFIELD_EXTRA_COOKIES": "datadome=aaaa",

  "HIGGSFIELD_SESSION_ID_2": "sess_b...",
  "HIGGSFIELD_CLERK_COOKIE_2": "eyJ...b",
  "HIGGSFIELD_EXTRA_COOKIES_2": "datadome=bbbb",

  "HIGGSFIELD_SESSION_ID_3": "sess_c...",
  "HIGGSFIELD_CLERK_COOKIE_3": "eyJ...c",
  "HIGGSFIELD_EXTRA_COOKIES_3": "datadome=cccc"
}
```

`auth_status` reports every account; `queue_status` shows per-account in-flight jobs;
each generation and every prompt in `generate_image_batch` is routed to the least-busy
account. (You can also pass all accounts as one JSON array via `HIGGSFIELD_ACCOUNTS_JSON`.)

> Image-to-image / image-to-video needs the input media uploaded **on the account that
> generates**, so the pool uploads local `input_files` per-account. Pre-uploaded media ids
> are account-specific.

## Video (viral 9:16) & resolution fallback

`generate_video` targets vertical 9:16 clips and uses the v2 API. Unlimited video is
capped per model (Seedance / Wan / Gemini render unlimited at **720p**), so it walks the
requested resolution down the ladder — `1080p → 720p → 480p` — whenever the server denies
unlimited at a tier, landing on the best resolution your plan actually allows:

```
generate_video(prompt="neon city rain at night, moody", model="seedance_2_0",
               aspect_ratio="9:16", duration=5, resolution="1080p")
# -> tries 1080p (denied unlimited) -> 720p (granted) -> returns the 720p clip
```

Unlimited-eligible video models on a 1-day-unlimited Plus plan: `seedance_2_0`,
`seedance_2_0_mini`, `wan2_7`, `gemini_omni`, `kling3_0`. A `429` (rate limit) is **not**
a resolution problem — the pool fails it over to another account instead of downgrading.

**Image-to-video:** pass `input_files=["./frame.png"]` — the file is uploaded on the
generating account (3-step presigned flow + IP/NSFW check) and attached as the
`start_image`. `kling3_0` and `seedance_2_0` both do image-to-video well. Pin a job to a
specific account with `account="account-2"` (or an index) when you want a particular
login — required if you pass a pre-uploaded media id, since ids are account-scoped.

## Configuration reference

| Variable | Default | Description |
|----------|---------|-------------|
| `HIGGSFIELD_CLERK_COOKIE` | *(required)* | The `__client` cookie from your browser. |
| `HIGGSFIELD_SESSION_ID` | *(required)* | `window.Clerk.session.id`. |
| `HIGGSFIELD_EXTRA_COOKIES` | *(often required)* | Extra browser cookies forwarded to the API, e.g. `datadome=...`. The `/jobs` create endpoint sits behind DataDome; without your browser's `datadome` cookie, `POST /jobs/{model}` returns a `403` captcha challenge. Get it from DevTools → Console: `document.cookie`. This cookie rotates, so refresh it when generation starts 403-ing. |
| `HIGGSFIELD_SESSION_ID_2..N` | *(optional)* | Additional accounts for parallel generation. Also `HIGGSFIELD_CLERK_COOKIE_2..N` and `HIGGSFIELD_EXTRA_COOKIES_2..N`. See [Multiple accounts](#multiple-accounts-parallel-generation). |
| `HIGGSFIELD_ACCOUNTS_JSON` | *(optional)* | Alternative: all accounts as a JSON array `[{"session_id","clerk_cookie","extra_cookies","label"}]`. |
| `HIGGSFIELD_MAX_CONCURRENT` | `4` | Max parallel jobs (match your plan tier: 4/8/12/16). |
| `HIGGSFIELD_DEFAULT_MODEL` | `nano-banana-2` | Image model used when not specified. |
| `HIGGSFIELD_DEFAULT_RESOLUTION` | `2k` | One of `1k`, `2k`, `4k`. |
| `HIGGSFIELD_OUTPUT_DIR` | `./higgsfield_output` | Default download directory. |
| `HIGGSFIELD_JWT_REFRESH_SECONDS` | `240` | How often to proactively refresh the JWT. |
| `HIGGSFIELD_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

---

## Usage examples

**Generate a single image:**
> Generate a 2k 16:9 image: "ancient Egyptian temple at golden hour, cinematic lighting"

**Batch storyboard (fire-and-forget):**
> Generate this 11-shot storyboard at 2k 9:16, fire-and-forget.

Calls `generate_image_batch(prompts=[...], wait=False)`, then check progress with `queue_status`.

**Single video at Veo 3:**
> Generate a 5-second 16:9 video with Veo 3: "drone shot of a desert pyramid at sunset"

**Image-to-video with auto-upload (one step):**
> Animate `./Assets/Character 1.png` with seedance for 5s, 720p, 16:9

Calls `generate_video(model="seedance", input_files=["./Assets/Character 1.png"], ...)` — the file is uploaded automatically.

**Storyboard with character continuity:**
> Use `./Assets/Character 1.png` as the reference and generate this 5-shot storyboard at 2k 9:16

**Cancel a runaway job:**
> Cancel job `<id>`

**Check plan & balances:**
> What's my Higgsfield plan?

Returns `has_unlim`, plan type, and all per-feature credit balances.

---

## How auth works

Higgsfield's web app uses a short-lived JWT (~5 min TTL) issued by Clerk. The
long-lived `__client` cookie lets us mint fresh JWTs on demand:

```http
POST https://clerk.higgsfield.ai/v1/client/sessions/{session_id}/tokens
Cookie: __client=<your cookie>
-> { "jwt": "..." }
```

The server caches the JWT and refreshes it proactively (every ~4 minutes). On a 401 it
invalidates and retries once automatically.

Unlimited mode is enabled by setting `"use_unlim": true` in both the `params` object and
the top-level request body:

```http
POST https://fnf.higgsfield.ai/jobs/{model}
Authorization: Bearer <jwt>

{ "params": { "...": "...", "use_unlim": true }, "use_unlim": true }
```

**Unlimited is granted (or denied) by Higgsfield's server, per model + account.**
Sending `use_unlim: true` is exactly what the official web app sends — the server then
decides. If a model isn't covered by your plan it returns
`403 {"error_type": "unlimited_generation_not_allowed"}`, and this MCP surfaces that as-is;
it does not (and cannot) override the decision. Check your entitlement with `account_info`
(`has_unlim` / `has_flex_unlim`). In practice unlimited is model-specific — some models
accept the flag on lower tiers, others require a true unlimited plan.

The `/jobs` create endpoint is also behind DataDome bot protection. This client forwards
your browser's own `datadome` cookie (via `HIGGSFIELD_EXTRA_COOKIES`) so your existing
session is recognised; it does not solve or bypass challenges.

See [`docs/EXTENDING.md`](docs/EXTENDING.md) for how to add new endpoints, and
[`docs/MODEL_SCHEMAS.md`](docs/MODEL_SCHEMAS.md) for the verified per-model request contract.

> **Video model note:** Each video model has different required fields. When
> `generate_video` returns a 422 error, the message tells you exactly which fields to add
> via `extra_params`. You can also use `generate_raw` to pass the full params dict directly.

---

## Security

- **Never commit your `.env` file.** It's in `.gitignore` by default.
- Your `__client` cookie + session id are equivalent to your logged-in browser session.
  Treat them like a password.
- Credentials passed via MCP env config stay local — they are never sent anywhere except
  Higgsfield's own API.
- For team use: each member should set up with their own Higgsfield account and credentials.

---

## Notes on model ids & endpoints

Higgsfield changes model ids and endpoint paths over time. This server is resilient to
that:

- The model registry in [`models.py`](higgsfield_unlimited_mcp/models.py) is for
  **discovery + hints only** — `generate_raw` works with any model id the API accepts.
- Read endpoints (account / workspace / media / assets) try a small list of candidate
  paths and report which one worked, so a moved endpoint is a one-line fix.
- Job responses are parsed tolerantly (see `docs/EXTENDING.md`).

If something 404s or 422s, the returned JSON includes the status and body so you can
adjust — see the docs.

---

## License

MIT — see [LICENSE](LICENSE).
