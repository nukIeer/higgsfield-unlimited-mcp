# Higgsfield Unlimited MCP

An [MCP](https://modelcontextprotocol.io) server for **Higgsfield AI** that drives the
generation API in **unlimited mode** (`use_unlim: true`) — the same call the official web
app makes. It authenticates with your existing browser session (Clerk JWT, auto-refreshed),
runs **multiple accounts in parallel**, and covers image, video, audio, upload, cost
preview and job management.

> Unlimited is granted per model + account by Higgsfield's server. This client sends the
> unlimited flag exactly like the web app; the server decides. Check `unlimited_status`
> before generating — if a model isn't unlimited-active for you it costs credits
> (`estimate_cost`).

**Covered (34 tools):** image (v1 + v2 models), video (text-to-video & image-to-video,
9:16, resolution fallback), audio (TTS + voice list), local-file upload, multi-account
pool, cost/unlimited status, workspaces, media library, assets, job management.

---

## Requirements

- Python 3.10+
- Claude Code (CLI, or the VS Code / JetBrains extension) — or any MCP client
- An active Higgsfield login in your browser

## 1. Install

```bash
pip install git+https://github.com/nukIeer/higgsfield-unlimited-mcp.git
```

Or from a local clone (what you have now):

```bash
pip install -e .
```

## 2. Get your credentials (~2 min)

Open <https://higgsfield.ai> in your browser, logged in. Then in DevTools (`F12`):

1. **Session id** — Console tab, run:
   ```js
   window.Clerk.session.id        // → sess_xxxxxxxx
   ```
2. **`__client` cookie** — Application → Cookies → `https://higgsfield.ai` → copy the
   `__client` value (it's `httpOnly`, so it won't show in `document.cookie`).
3. **`datadome` cookie** — Console tab, run:
   ```js
   document.cookie    // copy the datadome=... part
   ```
   The `/jobs` endpoint sits behind DataDome bot protection; without this cookie
   generation returns a `403` captcha. **This cookie rotates** — refresh it if you start
   getting 403s.

Put them in a `.env` file in the project root (copy `.env.example`):

```ini
HIGGSFIELD_SESSION_ID=sess_xxxx
HIGGSFIELD_CLERK_COOKIE=eyJ...
HIGGSFIELD_EXTRA_COOKIES=datadome=xxxx
HIGGSFIELD_DEFAULT_MODEL=nano-banana-2
HIGGSFIELD_DEFAULT_RESOLUTION=2k
```

`.env` is gitignored — your credentials never leave your machine.

## 3. Connect it to Claude Code (VS Code)

The server reads credentials from your `.env` via `HIGGSFIELD_DOTENV` (an absolute path),
so no secrets go into the MCP config file.

**Project-scoped** — create `.mcp.json` in the project root:

```json
{
  "mcpServers": {
    "higgsfield-unlimited": {
      "command": "python",
      "args": ["-m", "higgsfield_unlimited_mcp"],
      "env": {
        "HIGGSFIELD_DOTENV": "C:\\Users\\TESST\\Desktop\\higgsfield-unlimited-mcp\\.env"
      }
    }
  }
}
```

**Or user-scoped** (works in every project) — add the same `mcpServers` block to
`~/.claude.json`.

**Or via the CLI:**

```bash
claude mcp add higgsfield-unlimited -s user -- python -m higgsfield_unlimited_mcp
```

Then reload the window / restart Claude Code. Verify the tools are live by asking:

> Use higgsfield-unlimited to run `auth_status`, then `unlimited_status`.

## 4. Verify (optional, CLI)

```bash
higgsfield-unlimited-verify --skip-generate    # auth + endpoints only, no credits
```

---

## Multiple accounts (parallel generation)

One account serialises behind a per-account rate limit (`429 rate_limit_reached`). Add more
accounts and the pool load-balances and fails a job over to another account on 429. Numbered
credentials, each with its own session id, `__client`, and `datadome`:

```ini
HIGGSFIELD_SESSION_ID_2=sess_bbbb
HIGGSFIELD_CLERK_COOKIE_2=eyJ...
HIGGSFIELD_EXTRA_COOKIES_2=datadome=bbbb
HIGGSFIELD_SESSION_ID_3=sess_cccc
HIGGSFIELD_CLERK_COOKIE_3=eyJ...
HIGGSFIELD_EXTRA_COOKIES_3=datadome=cccc
```

`auth_status` lists every account; `queue_status` shows per-account load; jobs and every
prompt in `generate_image_batch` route to the least-busy account. Pin a job to one account
with `account="account-2"` (needed when you pass a pre-uploaded media id — ids are
account-scoped).

---

## Tools

### Auth, account & cost
`auth_status` · `account_info` · `unlimited_status` (what's unlimited-active) ·
`estimate_cost` (credit table, no spend) · `concurrent_state` · `queue_status`

### Models
`list_models` (with `unlimited` + `api_version` per model) · `get_aspect_dimensions`

### Image
`generate_image` (v1 dash ids like `nano-banana-2`; v2 underscore ids like `seedream_v5_pro`,
`flux_2`, `gpt_image_2` with `api_version="v2"`) · `generate_image_batch` · `generate_storyboard`

### Video
`generate_video` — v2, defaults to viral **9:16**, image-to-video via `input_files`,
resolution fallback `1080p → 720p → 480p`. Unlimited video models: `seedance_2_0`,
`seedance_2_0_mini`, `wan2_7`, `gemini_omni`, `kling3_0`.

### Audio
`generate_audio` (TTS, `text2speech_v2`, multilingual incl. Turkish) · `list_voices`

### Upload & media
`media_upload` (local file → IP-checked media id) · `show_medias` · `media_status` ·
`media_download_batch`

### Jobs
`check_job` · `wait_for_job` · `cancel_job` · `list_jobs` · `download_job_result` ·
`show_generations`

### Workspaces & assets
`list_workspaces` · `workspace_details` · `workspace_wallet` · `workspace_members` ·
`workspace_usage` · `list_assets` · `list_favourites` · `like_asset` · `unlike_asset`

### Advanced
`generate_raw` (any model + `api_version`, custom params — face-swap, upscale, inpaint,
outpaint, explainer, …)

---

## Usage examples (ask Claude in plain language)

**Check what's free before spending:**
> Run `unlimited_status`, then `estimate_cost`.

**Image — first frame for a video:**
> Generate a 9:16 image with `nano-banana-2`: "messy salon appointment notebook, warm evening light, cinematic".

**Video — viral 9:16 (text-to-video):**
> Generate a 5s 9:16 video with `seedance_2_0`: "neon city rain at night, moody" (let it fall back to 720p).

**Image-to-video (animate a local frame):**
> Animate `./frame.jpg` into a 9:16 video with `kling3_0`, `input_files=["./frame.jpg"]`.

**Turkish voiceover:**
> `list_voices`, pick a female voice, then `generate_audio` that voice: "Randevularınızı tek yerden yönetin."

**Batch across accounts:**
> `generate_image_batch` these 8 prompts at 9:16, fire-and-forget — then `queue_status`.

---

## How it works

- **Auth** — the long-lived `__client` cookie mints short-lived Clerk JWTs
  (`POST clerk.higgsfield.ai/v1/client/sessions/{id}/tokens`), cached and refreshed
  proactively; a 401 forces a re-mint + one retry.
- **Unlimited** — every job sets `use_unlim: true` in `params` and the top-level body.
  The server enforces entitlement per model/account and returns
  `403 unlimited_generation_not_allowed` when not covered.
- **Two API generations** — v1 `POST /jobs/{dash-id}` (`input_images`), v2
  `POST /jobs/v2/{underscore_id}` (`medias:[{role,data}]`, `model` field). Video and newer
  models are v2.
- **DataDome** — the create endpoint is bot-protected; the client forwards your browser's
  `datadome` cookie so your session is recognised. It does not solve challenges.

See [`docs/EXTENDING.md`](docs/EXTENDING.md) and
[`docs/MODEL_SCHEMAS.md`](docs/MODEL_SCHEMAS.md) for the full verified request contracts
(upload flow, video params, TTS, IP-check, endpoints).

## Security

- Never commit `.env` — it's gitignored. Cookies equal your logged-in session; treat them
  like passwords.
- Credentials stay local — sent only to Higgsfield's own API.
- Rapid automated requests can trip DataDome (a browser verification / temporary IP flag).
  Generate at a human pace; refresh the `datadome` cookie if you see 403s.

## License

MIT — see [LICENSE](LICENSE).
