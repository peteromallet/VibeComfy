---
name: run-comfy-workflow
description: Execute an existing VibeComfy/ComfyUI workflow, ready template, recipe, or scratchpad and collect outputs. Use when the user asks to run, queue, execute, generate, render, smoke test, use a local/remote ComfyUI runtime, or run on RunPod.
---

# Run Comfy Workflow

Use this for execution. If the graph must change first, use `edit-comfy-workflow`. If ComfyUI or paths are not configured, use `vibecomfy-setup`. If a run fails, use `debug-comfy-workflow`.

## Preflight

```bash
vibecomfy inspect <workflow>
vibecomfy validate <workflow>
vibecomfy doctor <workflow> --json
```

For raw JSON or a selected Hivemind revision, use the one importer first; run
the resulting local bundle:

```bash
vibecomfy import <workflow.json-or-hivemind-reference>
vibecomfy validate workflows/<name> --json
vibecomfy run workflows/<name> --runtime embedded
```

## Embedded Runtime

`@python_node` and source capsules execute through the existing ordinary
`vibecomfy.exec` node. They run in process with the selected ComfyUI worker's
files, imports, network, credentials, and GPU privileges; there is no reliable
timeout or sandbox. Snapshot capsules are materialized in a digest-qualified
cache, while installed entrypoints use their normal package namespace. A
worker dependency check happens before source import.

Use embedded when local ComfyUI is discoverable in the active environment:

```bash
vibecomfy run <workflow.py> --runtime embedded
vibecomfy run image/z_image --ready --runtime embedded
```

Prompt/seed/steps CLI overrides only work when the workflow exposes matching public inputs:

```bash
vibecomfy run image/z_image --ready --runtime embedded --prompt "..." --seed 7 --steps 20
```

Use dependency helpers only when the user wants VibeComfy to prepare local runtime assets:

```bash
vibecomfy run <workflow.py> --runtime embedded --ensure-packs --ensure-models
```

`--ensure-packs` is embedded-only.

## Canonical dependency repair loop

For a local Python workflow, `run` reads the authored `MODELS` /
`ModelAsset` and `READY_METADATA.requirements.custom_node_refs` surfaces before
compilation. Missing model URLs, repository URLs, unsafe destinations,
unsupported dynamic metadata, and root or nested node classes that are not
core, explicitly listed in a ref's `classes`/`class_set`, or covered by one
unambiguous local pack catalog are reported together. The run stops with:
"Run blocked: dependencies unresolved. Nothing downloaded, installed,
restarted, compiled, or queued." Common literal placeholders are written back
to the same `workflow.py`; rerunning is idempotent.

```python
from vibecomfy.templates import ModelAsset, ReadyMetadata

MODELS = {
    "denoiser": ModelAsset(
        filename="denoiser.safetensors",
        url="https://host.example/models/denoiser.safetensors",
        subdir="diffusion_models",
        hf_revision="<revision>",       # optional
        sha256="<64-hex-digest>",        # optional
    ),
}
READY_METADATA = ReadyMetadata.build(
    capability="image",
    requirements={"custom_node_refs": [{
        "slug": "example-pack", "source": "git",
        "url": "https://host.example/example-pack.git",
        "version": "<tag-or-branch>",  # optional; commit is also supported
        "classes": ["ExampleNode"],
    }]},
)
```

A model URL resolves the current bytes at that URL by default and records the
effective URL, observed SHA-256, size, and file-stat evidence in the local
verification receipt. A supplied checksum/revision is honored. A node URL
resolves the repository's default branch by default; a supplied version/tag/
branch is checked out, and a supplied commit is verified exactly. The existing
`custom_nodes.lock` is reused when its URL and optional selectors match, so a
repeat does not silently move a workflow to a new revision. Change the URL or
request an explicit refresh to start a new resolution.

After the report is clear, the existing preparation and runtime path performs
the download/install, preserves bounded download concurrency, and keeps the
normal warm-session behavior. Inspect preparation receipts under
`out/preparations/` when troubleshooting; do not infer a provider from a model
filename or node class. Remote `--server-url` runs remain non-mutating, and
RunPod/GPU validation plus Astrid project integration are separate follow-on
routes.

## Existing ComfyUI Server

Use this when the user already has ComfyUI running locally or remotely:

```bash
vibecomfy run <workflow.py> --runtime server --server-url http://127.0.0.1:8188
vibecomfy run image/z_image --ready --runtime server --server-url http://127.0.0.1:8188
```

Python-format workflows work against an existing server. VibeComfy imports the workflow's `build()`, compiles the `VibeWorkflow` to API JSON, and queues that JSON to the server.

The external server must already have the required custom nodes and models unless the user separately stages them into that server's environment. Do not use `--ensure-packs` with server runtime. `--ensure-models` can only prepare the local/shared model path VibeComfy can see.

For a VibeComfy-managed local HTTP server, omit `--server-url`:

```bash
vibecomfy run <workflow.py> --runtime server
```

`--runtime auto` attaches to an active default session when one exists; otherwise it falls back to embedded execution.

## RunPod

Use RunPod when requested or when local execution is unavailable and a GPU run is necessary. The acceptance script is a retired fail-closed placeholder; it exits before provisioning and cannot establish an end-to-end result. The validation and matrix commands are live remote operations:

```bash
python scripts/runpod_acceptance.py  # refusal only; no live acceptance
python scripts/runpod_validate.py   # one remote smoke
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py  # remote matrix
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
```

Use `runpod_validate.py` for the cheapest live launch/runtime sanity check. Use `runpod_corpus_matrix.py` only for model-family or corpus coverage after the smoke is green, starting with the smallest scope that answers the question. These are GPU/network checks and do not replace the no-GPU structural gates. Use `vibecomfy import` followed by `validate` and `doctor` for source onboarding; use the offline approved-record transport to check record bytes and queue payloads.

## Report Outputs

Runs return a `RunResult` with `run_id`, `prompt_id`, `outputs`, `metadata_path`, and `log_path`. The same fields are persisted under `out/runs/<run_id>/`.

Report:

- generated files under the run directory
- `out/runs/<run_id>/metadata.json`
- `prompt_id` when available
- relevant `vibecomfy logs tail` lines if execution failed

Do not report an edit candidate as a run result. A candidate graph from the Comfy app or agentic edit harness becomes a run result only after it is applied or executed through `vibecomfy run` / runtime APIs.
