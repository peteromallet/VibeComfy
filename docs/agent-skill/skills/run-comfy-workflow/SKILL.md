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

For raw JSON, treat the file as import evidence and convert the positional source before running:

```bash
vibecomfy port check <workflow.json> --json
vibecomfy nodes reconcile --workflow <workflow.json> --json
vibecomfy port convert <workflow.json> --out out/scratchpads/<name>.py --json
```

## Embedded Runtime

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

Use RunPod when requested or when local execution is unavailable and a GPU run is necessary:

```bash
python scripts/runpod_acceptance.py
python scripts/runpod_validate.py
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
```

Use `runpod_acceptance.py` when the user asks whether the package works end to end in practice. It proves setup inspection, dependency dry-runs, direct API JSON queueing, raw JSON conversion, Python ready-template execution, converted-JSON Python execution, embedded runtime, existing ComfyUI server runtime, and artifact collection. Add `--model-template <ready_id> --model-phase <phase>` when the live proof must include a real model-backed template.

Use `runpod_validate.py` only for the cheapest launch/runtime sanity check. Use `runpod_corpus_matrix.py` after acceptance is green and the question is model-family or corpus coverage. Start with the smallest family/smoke scope that answers the question.

## Report Outputs

Runs return a `RunResult` with `run_id`, `prompt_id`, `outputs`, `metadata_path`, and `log_path`. The same fields are persisted under `out/runs/<run_id>/`.

Report:

- generated files under the run directory
- `out/runs/<run_id>/metadata.json`
- `prompt_id` when available
- relevant `vibecomfy logs tail` lines if execution failed

Do not report an edit candidate as a run result. A candidate graph from the Comfy app or agentic edit harness becomes a run result only after it is applied or executed through `vibecomfy run` / runtime APIs.
