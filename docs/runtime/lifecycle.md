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

When the runtime must use a pinned ComfyUI source checkout rather than an
installed `comfyui` package, pass its root explicitly:

```bash
vibecomfy session start --id pinned --port 8189 \
  --comfyui-root /workspace/runtime/ComfyUI
```

This launches `<root>/main.py` with the current Python interpreter (without
the `serve` subcommand) and uses the checkout as the process working directory.
The option is validated before launch and is persisted in the session config.

`session start` writes `pid`, `url`, and `config.json` under `out/sessions/<id>/`. `vibecomfy run --runtime auto` checks the default session before loading schemas or queueing work; if the session is alive it passes the same URL to schema discovery and execution. If no warm session is alive, `auto` uses embedded one-shot execution. `--runtime server` also reuses the active session when present, and otherwise keeps the existing one-shot managed-server behavior.

Warm policy is controlled by `SessionConfig.warm_policy` and can be overridden with `VIBECOMFY_WARM`:

- `auto` keeps models warm by default, but flushes before the next prompt when the workflow's model fingerprint changes and free VRAM is below the configured threshold.
- `always` keeps the resident models and disables the automatic pre-run flush.
- `never` flushes before every run.

The auto-flush fingerprint is pattern-based. Any node whose `class_type` contains `Loader` contributes its non-edge string-valued input slots to the fingerprint, except for future explicit exclusions. Edge references such as `["12", 0]`, seeds, prompts, and other non-loader inputs do not contribute, so seed or prompt changes do not trigger a flush.

`session flush` and `ServerSession.flush()` call `POST /api/free` with `{"unload_models": true, "free_memory": true}`. In HiddenSwitch this endpoint sets queue flags; it is asynchronous and takes effect at the next prompt boundary rather than synchronously unloading models before the HTTP response returns. Embedded sessions call `Comfy.clear_cache()`.

Model reconciliation stores a per-file verification receipt under
`.vibecomfy/model-verification/` below the models root. A receipt is accepted
only when the expected SHA-256, canonical path, and `(dev, inode, size,
mtime_ns)` fingerprint still match, so unchanged large assets do not get
rehashed. Use `vibecomfy models ensure WORKFLOW --force-verify` to bypass the
receipt and stream-hash present files; `--force` retains its existing meaning
of downloading again.

Session configuration covers the model-memory and cache flags that Comfy already exposes:

- `vram_policy`: `auto`, `high`, `low`, or `normal`
- `reserve_vram_gb`
- `cache_policy`: `smart`, `classic`, `lru:N`, or `none`
- `disable_smart_memory`
- `port`
- `warm_policy`

`SessionConfig.extra` is an escape hatch for raw HiddenSwitch configuration keys that VibeComfy does not type yet. Mixed dictionaries may include both typed field names and raw HiddenSwitch keys; raw keys are translated first, then typed field names win on conflicts.

## Memory Profiles

VibeComfy exposes the Wan2GP-compatible memory profile numbers as integer profiles 1-5. The profile mapping is centralized in `vibecomfy.memory_profile.MemoryProfile`; runtime, CLI, templates, and worker integrations should consume the resolved `SessionConfig` fields or numeric protocol value rather than duplicating the mapping.

| Profile | Public label | `SessionConfig` fields |
| --- | --- | --- |
| `1` | `Low RAM` | `vram_policy="high"`, `cache_policy="smart"` |
| `2` | `High RAM` | `vram_policy="high"`, `cache_policy="lru:32"` |
| `3` | `Low VRAM` | `vram_policy="normal"`, `cache_policy="smart"` |
| `4` | `Very Low VRAM` | `vram_policy="low"`, `cache_policy="classic"`, `reserve_vram_gb=2.0` |
| `5` | `Minimum` | `vram_policy="low"`, `cache_policy="lru:1"`, `reserve_vram_gb=4.0`, `disable_smart_memory=true` |

Normal config resolution and explicit CLI override have different precedence:

- Workflow metadata and session config dictionaries apply `memory_profile` first, then explicit low-level fields such as `cache_policy` or `reserve_vram_gb` may override the profile-controlled fields.
- `vibecomfy run --memory-profile N` is an explicit per-run override. It is applied after workflow/default config resolution and overwrites profile-controlled fields for that run.
- When `memory_profile` is unset, VibeComfy leaves existing Comfy and WGP defaults unchanged.

Run-mode behavior:

- `vibecomfy run --runtime embedded --memory-profile N` applies the profile to the one-shot embedded runtime.
- `vibecomfy run --runtime server --memory-profile N` applies the profile only when VibeComfy is starting a new local managed server for that run.
- `vibecomfy run --runtime server --server-url ... --memory-profile N` is rejected with exit code 2 because VibeComfy cannot safely reconfigure an external process.
- `vibecomfy run --runtime auto --memory-profile N` is rejected with exit code 2 when it discovers an already-running warm session. Stop and restart the session with the desired process default.
- `vibecomfy session start --memory-profile N` persists the process default in `out/sessions/<id>/config.json`. Changing this process-level profile requires a session restart.

The reigh-worker boundary is numeric-only. The worker-side helper validates the process default and per-task `override_profile`, treats `override_profile=-1` as "use the process default", emits only one-run `--memory-profile N` CLI protocol data, and imports no VibeComfy modules. If neither a process default nor concrete override is present, the worker emits no VibeComfy memory-profile flag and leaves WGP flags/defaults untouched.

## Profile Smoke Artifacts

The profile 1 and profile 3 VRAM/wall-clock evidence artifacts are JSON reports written under `out/profile_smokes/`. They summarize an existing run directory containing `metadata.json` and `watchdog.json`.

Collect a real profile 1 artifact on a GPU-capable worker:

```bash
vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile 1
python tools/profile_smoke_report.py \
  --profile 1 \
  --run-dir out/runs/<run-id> \
  --output out/profile_smokes/profile-1.json \
  --template-id video/wan_t2v \
  --command "vibecomfy run video/wan_t2v --ready --runtime embedded --memory-profile 1" \
  --gpu-label "<gpu name>"
```

Collect profile 3 with the representative WanVideoWrapper template:

```bash
vibecomfy run video/wanvideo_wrapper_22_5b_i2v --ready --runtime embedded --memory-profile 3
python tools/profile_smoke_report.py \
  --profile 3 \
  --run-dir out/runs/<run-id> \
  --output out/profile_smokes/profile-3.json \
  --template-id video/wanvideo_wrapper_22_5b_i2v \
  --command "vibecomfy run video/wanvideo_wrapper_22_5b_i2v --ready --runtime embedded --memory-profile 3" \
  --gpu-label "<gpu name>"
```

The report schema requires `schema_version=1`, the numeric profile and public label, run id, runtime, workflow/template id, command, wall-clock seconds from `watchdog.elapsed_seconds`, at least one numeric VRAM sample from `watchdog.vram_samples`, and the watchdog diagnosis. Committed schema fixtures live in `tests/fixtures/profile_smokes/profile-1.json` and `tests/fixtures/profile_smokes/profile-3.json`; `tests/test_profile_smoke_report.py` validates the schema without GPU access.
