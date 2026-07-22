# Model schemas (per-model required fields)

Every generation is `POST /jobs/{model}` with:

```json
{ "params": { "...": "...", "use_unlim": true }, "use_unlim": true }
```

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
