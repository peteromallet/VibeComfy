---
name: vibecomfy-setup
description: Set up VibeComfy for local or remote ComfyUI use. Use when the user asks to install, configure, initialize, connect VibeComfy to ComfyUI, choose between pip-installed ComfyUI and their own ComfyUI checkout, configure custom_nodes/models paths, reuse existing nodes/models, create isolated libraries, or make `vibecomfy run` stop warning about missing ComfyUI/config.
---

# VibeComfy Setup

Use this when the environment is the problem: VibeComfy cannot find ComfyUI, the user wants to reuse or isolate their `custom_nodes` / `models`, or a run needs to target an existing ComfyUI server.

The good setup is explicit. Pick a runtime, pick node/model libraries only when they matter, dry-run dependency changes, then verify.

## First Conversation

Before mutating the user's machine, ask for three choices:

1. **Runtime**
   - installed/importable `comfy` package
   - the user's own ComfyUI checkout path
   - an already-running ComfyUI server URL

2. **Custom nodes**
   - reuse an existing `custom_nodes`
   - create/use an isolated `custom_nodes`
   - skip local custom-node setup for now

3. **Models**
   - reuse an existing `models`
   - create/use an isolated `models`
   - skip local model setup for now

Also ask whether the config should be global (`~/.vibecomfy/config.toml`) or repo-local (`./vibecomfy.toml`). Use global for a personal workstation unless the user wants this checkout to carry the setup.

If they choose an existing server URL, do not force local ComfyUI setup. External server runs only need local node/model paths when VibeComfy is staging files or preparing dependencies on a shared filesystem.

## Inspect

Run from the repo root:

```bash
vibecomfy config show --json
vibecomfy runtime doctor
```

If the console script is unavailable in an editable checkout, use `python -m vibecomfy.cli ...`.

Know the two resolution paths:

- `vibecomfy config init` detects ComfyUI from `COMFYUI_PATH`, an importable `comfy` package, `~/ComfyUI`, then the current directory if it has `custom_nodes` or `models`.
- Library paths used by config/model/node helpers prefer env vars first (`VIBECOMFY_CUSTOM_NODES_DIR`, `VIBECOMFY_MODELS_ROOT`, `COMFY_MODELS_ROOT`), then repo config, then global config.

## Runtime Setup

For an importable/pip ComfyUI:

```bash
python - <<'PY'
import comfy
from pathlib import Path
root = Path(comfy.__file__).resolve().parent.parent
print(root)
print(root / "custom_nodes")
print(root / "models")
PY
vibecomfy config init --yes
```

For the user's own checkout:

```bash
export COMFYUI_PATH=/absolute/path/to/ComfyUI
test -d "$COMFYUI_PATH/custom_nodes"
test -d "$COMFYUI_PATH/models"
vibecomfy config set-library \
  --custom-nodes "$COMFYUI_PATH/custom_nodes" \
  --models "$COMFYUI_PATH/models"
```

Add `--repo` to `config init` or `config set-library` only when the user wants repo-local config.

For an existing server:

```bash
vibecomfy run <workflow.py> --runtime server --server-url http://host:8188
vibecomfy run image/z_image --ready --runtime server --server-url http://host:8188
```

Python workflows work here: VibeComfy imports `build()`, compiles the returned `VibeWorkflow` to ComfyUI API JSON, and queues it to the server.

## Custom Nodes

Reuse an existing library:

```bash
vibecomfy config set-library --custom-nodes /absolute/path/to/custom_nodes
vibecomfy nodes restore
```

Use an isolated library:

```bash
mkdir -p /absolute/path/to/new-custom_nodes
vibecomfy config set-library --custom-nodes /absolute/path/to/new-custom_nodes --force
vibecomfy nodes restore
```

Plan before installing:

```bash
vibecomfy nodes install-plan <workflow>
vibecomfy nodes ensure --workflow <workflow>
vibecomfy nodes ensure --template <ready_id>
```

Caveat: `nodes restore` and single-pack `nodes install` honor the configured custom-node root. `nodes ensure` currently installs through the package default `custom_nodes` path, so verify the install destination before claiming an isolated library was populated.

Skip local nodes:

```bash
vibecomfy config set-library --no-custom-nodes
```

## Models

Reuse an existing library:

```bash
vibecomfy config set-library --models /absolute/path/to/models
```

Use an isolated library:

```bash
mkdir -p /absolute/path/to/new-models
vibecomfy config set-library --models /absolute/path/to/new-models --force
```

Plan before downloading:

```bash
vibecomfy models stage --select-phase core --dry-run
vibecomfy fetch <workflow> --dry-run
```

Then install only after the user agrees:

```bash
vibecomfy models stage --select-phase core
vibecomfy fetch <workflow>
```

Skip local models:

```bash
vibecomfy config set-library --no-models
```

## Verify

Finish every setup with the canonical candidate still represented by Python; use API JSON only at the runtime boundary:


```bash
vibecomfy config show --json
vibecomfy runtime doctor
vibecomfy inspect <workflow>
vibecomfy doctor <workflow> --json
```

If embedded runtime still cannot find a ComfyUI root or `comfy` module, local embedded execution is not ready. Either set `COMFYUI_PATH`, install/import `comfy` in the active environment, or run with `--runtime server --server-url ...`.

## Default Path

When the user has no strong preference:

1. Run `vibecomfy config init --yes`.
2. If ComfyUI is not detected, ask for a ComfyUI path or server URL.
3. Reuse real existing `custom_nodes` and `models`.
4. Use isolated dirs only when they want to protect their current ComfyUI setup.
5. Dry-run dependency changes before installs/downloads.
6. Run `runtime doctor`, `inspect`, and `doctor` before handing off to `run-comfy-workflow`.
