# Model schemas (per-model required fields)

Every generation is `POST /jobs/{model}` with:

```json
{ "params": { "...": "...", "use_unlim": true }, "use_unlim": true }
```

## Verified request/response contract

`{model}` in the path is the **dash form** of the model id (`nano-banana-2`,
`z-image`, `seedream-v4-5`), even though the catalog lists ids in underscore form
(`nano_banana_2`). The underscore form on the path returns `405 Method Not Allowed`.

**`input_images` must be a list of media objects, each with an `id`:**

```json
"input_images": [
  { "id": "b6af2228-...", "type": "media_input", "url": "https://.../file.jpg" }
]
```

A bare URL string (no `id`) is rejected with `422 input_images.0.id Field required`.
So an input image must first be uploaded (via `media_upload` / `input_files`) to obtain
an `id`. The server ignores the `width`/`height` you send and recomputes them.

**The create response nests the pollable job id** — the top-level `id` is the
*project* id, not pollable:

```json
{ "id": "<project_id>",
  "job_sets": [ { "type": "nano_banana_2",
    "jobs": [ { "id": "<POLL THIS>", "status": "waiting" } ] } ] }
```

Poll with `GET /jobs/{job_id}` (or `POST /jobs/status-batch`). Results arrive under
`results.raw` / `results.min` as `{type, url}`; **exclude `type: "media_input"`** —
those are your input images echoed back, not outputs.

## Two API generations: v1 and v2

There are two create endpoints:

- **v1** — `POST /jobs/{dash-id}` (e.g. `nano-banana-2`). Input media go under
  `input_images: [{id, type: "media_input", url}]`.
- **v2** — `POST /jobs/v2/{underscore_id}` (e.g. `seedream_v5_lite`, and most video
  models). `params` carries a `model` field, and input media go under
  `medias: [{"role": "start_image"|"image"|..., "data": {id, type, url}}]`.

The underscore id on a v1 path (or vice-versa) returns `405 Method Not Allowed`. The MCP
picks the endpoint from `api_version` (`generate_image(api_version=...)`,
`generate_raw(api_version=...)`); video is always v2.

### Video params (v2)

`params` needs `prompt`, `aspect_ratio`, `batch_size`, `duration`, `resolution`
(`480p/720p/1080p/4k`), `width`, `height` (short side from the tier, long side from the
aspect ratio — the server recomputes), and usually `generate_audio` + `mode` (`std`/`fast`
for Seedance). Image-to-video attaches a start frame via
`medias: [{role: "start_image", data: {...}}]`. **Input media must pass an IP check first**
or the job fails `400 {"error_type":"other","text":"IP check not finished for input media"}` —
text-to-video has no such dependency.

## Uploading input media (for image-to-image / image-to-video)

Local files become usable input media via a 3-step flow (`media_upload` /
`input_files` do this automatically, per generating account):

1. `POST /media/batch` — `{"mimetypes":["image/jpeg"],"source":"user_upload","force_ip_check":false}`
   → `[{id, url, upload_url}]` (`upload_url` is a presigned S3 PUT target).
2. `PUT <upload_url>` — the raw bytes with `Content-Type: image/jpeg` (the signature
   covers `content-type;host`).
3. `POST /media/{id}/upload` — `{"filename":..., "force_nsfw_check":true, "force_ip_check":false}`
   → `{id, status:"uploaded", ip_check_finished:null}`; poll `GET /media/{id}` until
   `ip_check_finished`.

Then reference it as `{id, type:"media_input", url}` (v1 `input_images`) or
`{role:"start_image", data:{...}}` (v2 `medias`). Media ids are **account-scoped** —
uploaded on one account, they only work on that account, so the pool uploads local
`input_files` on whichever account runs the job. To reuse a pre-uploaded id, pin the
job with `account=` on `generate_image` / `generate_video`.

### Text-to-speech (v2)

`POST /jobs/v2/text2speech_v2` (verified):

```json
{ "params": { "prompt": "metin", "model": "elevenlabs",
              "voice_id": "b0f766b7-...", "voice_type": "preset", "use_unlim": true },
  "use_unlim": true }
```

Voice ids come from `GET /reference-elements/voices` → `{items:[{id, name, gender,
source(preview mp3), type:"preset"}]}`. ElevenLabs is multilingual, so a Turkish prompt
works with any voice. The result mp3 is at `.../hf_..._{jobid}.mp3` (the `voice.source`
in params is the preview, not the output — result extraction ignores `source`).

## `use_unlim` is enforced server-side, per model + account

Setting `use_unlim: true` does **not** guarantee unlimited generation. The server
checks entitlement and may return `403 {"error_type": "unlimited_generation_not_allowed"}`.
Observed: `nano-banana-2` accepts it on a `plus` account (has a free/promo allowance);
`z-image` rejects it. Whether a model is unlimited-eligible depends on your plan
(`has_unlim` / `has_flex_unlim` in `GET /user`) and Higgsfield's per-model rules. When
denied, either the model isn't covered or your account isn't entitled — this MCP does
not and cannot override that decision.

## Real account / workspace endpoints (from traffic capture)

| Tool | Path |
|------|------|
| `account_info` | `GET /user` (has `plan_type`, `has_unlim`, all `*_credits`) |
| `concurrent_state` | `GET /concurrent-boost-credits/state` |
| `workspace_details` | `GET /workspaces/details` |
| `workspace_wallet` | `GET /workspaces/wallet` |
| free generations | `GET /user/free-gens/v2` |
| history | `GET /jobs/accessible` |

The **common** fields the server always sends for image jobs are `prompt`, `width`,
`height`, `aspect_ratio`, `resolution`, `batch_size`. Video jobs send `prompt`,
`aspect_ratio`, and (when provided) `duration`, `resolution`/`quality`, `image_url`,
`input_images`.

Beyond that, each model has its own required fields. **The authoritative source is the
API itself**: when a model rejects your params it returns **HTTP 422** with a body that
names the missing/invalid fields. Add them via `extra_params` (on `generate_image` /
`generate_video`) or pass the whole dict through `generate_raw`.

## Discovering a model's schema

```
generate_raw(model="veo3-1", params={"prompt": "a cat"}, wait=false)
```

If it 422s, read `body` in the returned JSON — it lists the required fields. Re-issue
with them filled in.

## Known extras (from observation — verify against live 422s)

| Model | Category | Extra fields commonly required |
|-------|----------|-------------------------------|
| `nano-banana-2-shots` | image | `shots` (list of `{prompt}`) |
| `veo3`, `veo3-1` | video | `duration` (e.g. 4 / 6 / 8) |
| `infinite-talk`, `lipsync` | video | `audio_url`, an input image |
| `text2speech` | audio | `text`, optionally `voice` |
| `face-swap`, `character-swap` | image | source + target `input_images` |
| `upscale`, `video-upscale` | image/video | one `input_images` entry, `scale` |
| `inpaint` | image | `input_images`, `mask` |

> These are hints, not guarantees. Model ids and required fields change on Higgsfield's
> side. Always trust a live 422 over this table.

## Resolutions & dimensions

`get_aspect_dimensions(aspect_ratio, resolution)` returns the exact pixel dims the
server sends. Supported aspect ratios: `1:1, 16:9, 9:16, 4:3, 3:4, 3:2, 2:3, 21:9,
9:21, 5:4, 4:5, 2:1, 1:2`. Resolutions: `1k, 2k, 4k`.
