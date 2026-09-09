# Workflow onboarding

Use this path when you have a workflow from ComfyUI or an upstream repository and want a local, editable VibeComfy surface.

## 1. Save the source and provenance

Keep the upstream file unchanged under a stable source path, and record its URL, upstream commit or release, local path, and SHA-256. For example, the MiniMax H3 AV inpainting source used by the Matrix experiment is:

- upstream: [LanPaint `MiniMax_H3_AV_EncodeDecode_Inpaint.json`](https://github.com/scraed/LanPaint/blob/32cf848e93971da380d868936e007f5611218bee/example_workflows/MiniMax_H3_AV_EncodeDecode_Inpaint.json)
- local: `planning/comfy-inspection/MiniMax_H3_AV_EncodeDecode_Inpaint.json`
- SHA-256: `2dd64fe26c42281962e434841c458cc935b1d1858e83093b882bbaeb02dc3121`

Keep source JSON as evidence. Put hand edits in a recipe or scratchpad so the upstream graph can still be compared with the candidate.

## 2. Preflight, then understand the graph

From the VibeComfy repository root, use the console entrypoint (or replace `vibecomfy` with `python -m vibecomfy.cli` in an editable checkout):

```bash
vibecomfy port check path/to/workflow.json --json
vibecomfy inspect path/to/workflow.json --json
vibecomfy analyze info path/to/workflow.json
```

For a ready template, discovery and inspection use its id:

```bash
vibecomfy workflows list --ready
vibecomfy inspect image/z_image --json
```

`inspect` and `analyze info` describe the graph and public inputs; they do not prove that models, custom nodes, a ComfyUI checkout, or a server are available. If a class schema is missing, `doctor` identifies the gap and the supported recovery command is `vibecomfy schemas ensure <workflow>`; provisioning is an environment change and should be treated separately.

## 3. Materialize the editable Python candidate

For a supported source workflow, convert it to a scratchpad and keep the emitted path as the canonical edit surface:

```bash
vibecomfy port convert path/to/workflow.json \
  --out out/scratchpads/my_workflow.py --json
vibecomfy inspect out/scratchpads/my_workflow.py --json
```

For a curated ready template, copy a user-specific recipe instead:

```bash
vibecomfy copy-to-recipe image/z_image --out recipes/my_run.py
```

Load the candidate through `load_bundle()` before editing or running. A minimal recipe looks like this:

```python
from vibecomfy.cli_loader import load_bundle


def build():
    wf = load_bundle("image/z_image").workflow
    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)
    return wf.finalize_metadata()
```

Use `vibecomfy inspect <candidate> --field <PUBLIC_INPUTS field>` when you need to resolve one public handle. Use `vibecomfy nodes spec <ClassType>` before relying on a custom node's sockets or widgets.

## 4. Edit, validate, and inspect readiness

Make the smallest change in the Python candidate, then run structural and dependency checks:

```bash
vibecomfy validate out/scratchpads/my_workflow.py --json
vibecomfy doctor out/scratchpads/my_workflow.py --json
vibecomfy runtime doctor --json
```

`validate`/`doctor` describe the candidate. `runtime doctor` reports local runtime findings; configured `models` or `custom_nodes` directories alone do not make embedded execution ready, and an external server remains unverified until a URL is supplied to a run.

Only after the candidate and runtime are ready should execution be attempted, for example:

```bash
vibecomfy run out/scratchpads/my_workflow.py \
  --runtime server --server-url http://127.0.0.1:8188
```

## Evidence and blockers

There are three distinct claims:

1. **Source evidence:** the saved JSON, provenance, and inspection output show what the upstream graph contains.
2. **Executable candidate:** conversion produced Python, and `validate`/`doctor` passed for the candidate and its available schemas.
3. **Runtime readiness:** the selected ComfyUI runtime, custom nodes, models, and server or embedded environment were checked.

Do not promote one claim into another. In particular, the H3 example currently contains a native recursive subgraph boundary (`inputNode`/`outputNode`). VibeComfy reports `unsupported_boundary_encoding` and does not create a runnable Python candidate until the source has an explicit Python-owned boundary mapping. That is an import representation blocker, not proof that the upstream graph or models are invalid. Retain the source provenance and reopen with a resolved export or an explicit boundary contract, then rerun `port check`, `port convert`, `validate`, and `doctor`.
