# Runtime Surface

Observed runtime: HiddenSwitch ComfyUI `0.18.2` installed from `hiddenswitch/ComfyUI` commit `c5ed940244b1373daf855c0adbf2f7fd6dec327a`.

For the running compatibility ledger, see `docs/runtime/incompatibilities.md`.

## CLI Surface

Validated commands:

```bash
comfyui --help
comfyui serve --help
comfyui run-workflow --help
comfyui env check
comfyui nodes --help
```

`comfyui serve` starts the HTTP server. Useful flags include `--listen`, `--port`, `--guess-settings`, `--novram`, `--base-directory`, `--input-directory`, `--output-directory`, `--extra-model-paths-config`, `--disable-all-custom-nodes`, `--whitelist-custom-nodes`, `--blacklist-custom-nodes`, `--prompt`, `--steps`, `--seed`, and `--set`.

`comfyui run-workflow` executes workflow files and exits. It accepts local paths, URIs, literal JSON, and stdin. It supports `--all` for installing missing custom nodes and downloading known models, plus the same common override flags: `--prompt`, `--steps`, `--seed`, `--set`, `--output-directory`, `--cwd`, `--base-directory`, and device/VRAM flags.

`comfyui env check` prints the active runtime profile. On this local Mac it reported Python `3.11.11`, ComfyUI `0.18.2`, Torch `2.11.0`, no NVIDIA/AMD GPU, `mps`, 16 GB RAM, and missing local model directories.

## HTTP Surface

VibeComfy currently uses:

```text
GET  /system_stats
GET  /object_info
POST /prompt {"prompt": <api workflow dict>}
POST /api/free {"unload_models": true, "free_memory": true}
```

`/system_stats` is the readiness probe. `/object_info` is the node-definition source of truth and returned 1,202 node definitions in the local managed smoke. `/prompt` queues work but does not by itself prove the workflow finished, so it is a queue-submission path rather than the strongest end-to-end execution path.

`/api/free` is used for explicit server-session flushes. HiddenSwitch treats it as queue-async: it sets queue flags and applies at the next prompt boundary, not synchronously before the HTTP response returns.

## Embedded Surface

HiddenSwitch exposes `comfy.client.embedded_comfy_client.Comfy`.

Validated APIs:

```python
from comfy.client.embedded_comfy_client import Comfy

async with Comfy() as comfy:
    result = await comfy.queue_prompt_api(api_workflow)
```

This waits for workflow completion and returns output metadata. VibeComfy uses this as the local one-shot fallback when no warm managed session is active because it proves execution and output creation without managing an HTTP server.

Progress is available through:

```python
task = comfy.queue_with_progress(api_workflow)
async for notification in task.progress():
    ...
result = await task.get()
```

## VibeSession API

VibeComfy exposes a shared session shape for both warm backends:

```python
from vibecomfy.runtime.session import EmbeddedSession, ServerSession, SessionConfig

config = SessionConfig(warm_policy="auto", cache_policy="smart")

session = EmbeddedSession(config)
# or:
session = ServerSession(config)

await session.start()
try:
    result = await session.run(workflow)
    await session.flush()
    await session.reconfigure(config)
finally:
    await session.stop()
```

Session methods:

- `start()` opens the long-lived backend if it is not already running.
- `run(workflow, backend="api")` compiles and queues a workflow, applying the warm-policy flush gate before queueing.
- `flush()` explicitly releases cached/resident model state at the session boundary. Server flushes call `/api/free`, which is queue-async and applies at the next prompt boundary.
- `reconfigure(config)` applies a new `SessionConfig`; embedded sessions pass it through to `Comfy.reconfigure()`, and server sessions restart only when the resulting Comfy CLI arguments change.
- `stop()` closes the embedded context or terminates the managed server process.

Run metadata keeps the legacy `outputs` list as resolved artifact paths. It also exposes `comfy_outputs` for the raw Comfy return payload and `artifact_paths` as an explicit alias for resolved files, using `comfy_configuration.output_directory` when Comfy returns filename-only records.

`SessionConfig` fields:

- `runtime_root`: captured artifact/configuration root; relative paths resolve here
- `cwd`: captured working directory for the managed Comfy child (defaults to `runtime_root`)
- `vram_policy`: `auto`, `high`, `low`, or `normal`
- `reserve_vram_gb`
- `cache_policy`: `smart`, `classic`, `lru:N`, or `none`
- `disable_smart_memory`
- `warm_policy`: `auto`, `always`, or `never`
- `auto_flush_vram_threshold_gb`
- `port`
- `strict_drift`: fail the run when the captured workflow has runtime drift
- `extra`: raw HiddenSwitch configuration keys not represented by typed fields

`EmbeddedSession` holds one `Comfy()` context across multiple `run()` calls. `ServerSession` holds one `comfyui serve` subprocess and uses HTTP for readiness, prompt queueing, and explicit flush.

`runtime_root` and `cwd` are captured when `SessionConfig` is constructed, so a
later process-wide `chdir()` cannot move artifacts or change the managed child’s
working directory. Dynamic Comfy I/O settings from `extra` and
`VIBECOMFY_COMFY_CONFIGURATION` are snapshotted when the backend starts and
remain stable for that process lifetime. Malformed typed or JSON configuration
raises `RuntimeConfigurationError` (also a `ValueError`) before the backend is
started.

## Runtime Spawn Contract

Decided (T-049, ORACLE-8; R:S7). The managed-Comfy spawn surface has ONE owner, ONE timeout
contract, and ONE exception shape.

**Sole owner — `vibecomfy/runtime/session.py`:**

- `_comfy_server_argv(config)` — the richer argv builder. Beyond the shared vram/cache/reserve
  flags it adds `--use-sage-attention` (from `extra["use_sage_attention"]` or the
  `VIBECOMFY_ATTENTION_PROFILE` / `REIGH_VIBECOMFY_ATTENTION_PROFILE` env), the I/O directory
  args `--input-directory`, `--output-directory`, `--temp-directory` (from
  `extra["input_directory"]` / `output_directory` / `temp_directory`), and `--port`.
- `_spawn_comfy_server(config, log_path=None)` — spawns `comfyui serve` with that argv and polls
  the readiness probe (`/system_stats`) under a **configurable timeout**:

  ```text
  ready_timeout_sec = config.extra["ready_timeout_sec"]
                      -> env VIBECOMFY_SESSION_READY_TIMEOUT_SEC
                      -> 300 (default seconds)
  ```

  On timeout the spawned process is killed and `RuntimeStartupError` is raised (chained from the
  underlying readiness `TimeoutError`) with the exact next action:

  ```text
  next_action: Check the ComfyUI startup log, installed custom nodes, and selected port before retrying.
  ```

**ServerSession spawn paths** — `ServerSession.start()`, `ServerSession.reconfigure()` (restart
path), and the `session start` CLI daemon (`vibecomfy/commands/session.py`) all spawn through the
session owner above.

**Delegation (final)** — both managed-server surfaces delegate to the session owner
by identity (no second implementation survives the consolidation):

- `ServerSession.start()` / `ServerSession.reconfigure()` and the `session start`
  CLI daemon call `_spawn_comfy_server` directly from `runtime/session.py`.
- `runtime/server.py`'s `comfy_server` context manager calls the same
  `_spawn_comfy_server` (and the same `_comfy_server_argv`) through
  `runtime/server_process.py`, which re-exports the session-owned functions.
- `vibecomfy/runtime/config.py` was deleted (T-054); all importers now use
  `runtime/session.py`.

There is ONE spawn and ONE exception shape: a readiness failure raises
`RuntimeStartupError` — chained from the underlying readiness `TimeoutError` —
with the next action above, from every startup surface: the one-shot run helper
(`runtime/run.py`), the `comfy_server` context, `ServerSession.start()`, and the
session CLI daemon. The old raw `TimeoutError` surface is retired: the only
exception shape a caller sees for a readiness failure is `RuntimeStartupError`
with the next action above.

## GraphBuilder

GraphBuilder is available at `comfy_execution.graph_utils.GraphBuilder`. Its own docstring describes it as a utility that outputs graphs in the form expected by the ComfyUI backend.

VibeComfy's optional `workflow.compile("graphbuilder")` backend now uses this class and has parity tests against the direct API-dict backend.

## Decisions

- Use `VibeWorkflow -> API dict` as the primary compiler path.
- Use `GraphBuilder` as an optional backend, not the only representation.
- Keep HTTP managed server mode for compatibility, `/object_info` discovery, and reusable warm sessions.
- One runtime spawn contract: `runtime/session.py` owns the richer argv, the configurable readiness timeout (`extra` → env → 300s), and the `RuntimeStartupError` + next-action shape. `runtime/config.py` is deleted (T-054); `server_process.py` re-exports the session-owned spawn so `comfy_server` delegates by identity.
- Use embedded mode when the caller needs to wait for completed outputs or owns an in-process warm session.
- Treat `comfyui run-workflow` as an important parity check and operational fallback, not the core VibeComfy scratchpad API.
