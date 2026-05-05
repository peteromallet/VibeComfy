# Runtime Lifecycle

CLI `vibecomfy run` defaults to `auto`: it reuses an active warm managed session when one is running, otherwise it falls back to embedded one-shot execution.

Managed server mode starts `comfyui serve`, waits for readiness, queries `/object_info` or queues the workflow, captures logs under `out/runs/<run-id>/`, then stops the server.

`--runtime server --server-url ...` switches to an external server. External mode never stops the user's server.

Python callers use the async API:

```python
await run(workflow)
```

The CLI bridges sync commands to async execution with `asyncio.run`.

Validated local checks:

```bash
vibecomfy runtime smoke --mode managed
vibecomfy run smoke/empty_image_red --ready --runtime embedded --backend graphbuilder
```

The managed smoke started Comfy, read node definitions from `/object_info`, and terminated. The embedded smoke runs the Python ready template `ready_templates/smoke/empty_image_red.py` and writes a PNG under `output/`.

## Warm Sessions

VibeComfy has two warm-session backends:

- `EmbeddedSession` keeps one HiddenSwitch `Comfy()` context open inside the current Python process. This is the backend for in-process callers that own the lifecycle, such as tests, tight local loops, and future worker integrations.
- `ServerSession` keeps one `comfyui serve` subprocess alive and talks to it over HTTP. This is the CLI-friendly backend because separate `vibecomfy run` invocations can share the same server process through files under `out/sessions/<id>/`.

The session CLI manages daemon-style server sessions:

```bash
vibecomfy session start --id default --port 8188
vibecomfy session status default
vibecomfy session list
vibecomfy session flush default
vibecomfy session stop default
```

`session start` writes `pid`, `url`, and `config.json` under `out/sessions/<id>/`. `vibecomfy run --runtime auto` checks the default session before loading schemas or queueing work; if the session is alive it passes the same URL to schema discovery and execution. If no warm session is alive, `auto` uses embedded one-shot execution. `--runtime server` also reuses the active session when present, and otherwise keeps the existing one-shot managed-server behavior.

Warm policy is controlled by `SessionConfig.warm_policy` and can be overridden with `VIBECOMFY_WARM`:

- `auto` keeps models warm by default, but flushes before the next prompt when the workflow's model fingerprint changes and free VRAM is below the configured threshold.
- `always` keeps the resident models and disables the automatic pre-run flush.
- `never` flushes before every run.

The auto-flush fingerprint is pattern-based. Any node whose `class_type` contains `Loader` contributes its non-edge string-valued input slots to the fingerprint, except for future explicit exclusions. Edge references such as `["12", 0]`, seeds, prompts, and other non-loader inputs do not contribute, so seed or prompt changes do not trigger a flush.

`session flush` and `ServerSession.flush()` call `POST /api/free` with `{"unload_models": true, "free_memory": true}`. In HiddenSwitch this endpoint sets queue flags; it is asynchronous and takes effect at the next prompt boundary rather than synchronously unloading models before the HTTP response returns. Embedded sessions call `Comfy.clear_cache()`.

Session configuration covers the model-memory and cache flags that Comfy already exposes:

- `vram_policy`: `auto`, `high`, `low`, or `normal`
- `reserve_vram_gb`
- `cache_policy`: `smart`, `classic`, `lru:N`, or `none`
- `disable_smart_memory`
- `port`
- `warm_policy`

`SessionConfig.extra` is an escape hatch for raw HiddenSwitch configuration keys that VibeComfy does not type yet. Mixed dictionaries may include both typed field names and raw HiddenSwitch keys; raw keys are translated first, then typed field names win on conflicts.
