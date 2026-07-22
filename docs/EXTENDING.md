# Extending the server

## Adding a model

Model ids are just the `{model}` path segment in `POST /jobs/{model}`. To surface
a new one in `list_models`, add a `ModelSpec` to the relevant list in
[`models.py`](../higgsfield_unlimited_mcp/models.py):

```python
ModelSpec("my-new-model", CATEGORY_IMAGE, "What it does.", required_extra=("foo",))
```

You do **not** need to register a model to use it — `generate_raw(model="my-new-model", params={...})`
works with any id the API accepts. The registry is only for discovery and hints.

## Adding an endpoint / tool

1. Add a client method to [`client.py`](../higgsfield_unlimited_mcp/client.py) (or
   just use the generic `client.get/post/delete`).
2. Add a `@mcp.tool()` function in [`server.py`](../higgsfield_unlimited_mcp/server.py)
   that calls it and returns `_jdump(...)`.

For read endpoints whose path you're unsure of, use `service.try_get([...])` with a
list of candidate paths — it returns the first one that responds and reports which
path won under `_endpoint`.

## How responses are normalised

Higgsfield job payloads vary by model. [`client.py`](../higgsfield_unlimited_mcp/client.py)
provides three tolerant helpers used everywhere:

- `extract_job_id(payload)` — finds an id under `id/job_id/jobId/uuid`, including when
  wrapped in `job`/`data`/`result`.
- `normalize_status(payload)` — maps many raw status strings to `queued/running/completed/failed/cancelled`.
- `extract_result_urls(payload)` — recursively collects any `http(s)` URLs under
  common url keys, de-duplicated.

If a model returns results under an unusual key, add it to `_URL_KEYS` / `_STATUS_KEYS`
/ `_ID_KEYS` at the top of `client.py`.

## Auth

`ClerkAuth` mints a JWT from the `__client` cookie and caches it, refreshing when it
is older than `HIGGSFIELD_JWT_REFRESH_SECONDS` (default 240s). Any request that hits a
401 forces a re-mint and retries once (`HiggsfieldClient.request`).
