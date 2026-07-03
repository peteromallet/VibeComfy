---
name: vibecomfy
description: 'Drive the VibeComfy package to discover ComfyUI workflows, load ready Python templates, edit and compose them in a `VibeWorkflow` IR, validate, and execute either embedded locally, against an existing ComfyUI server, or on RunPod. Use whenever the user wants to generate images/video/audio/edits from ComfyUI workflows, tweak templates, build recipes, compose graphs in Python, or run existing `ready_templates` end-to-end.'
---

# VibeComfy

VibeComfy is this package: a Python-first way to drive ComfyUI without hand-editing JSON. The center of gravity is `VibeWorkflow`: load a workflow, edit it in Python, validate it, then compile to ComfyUI API JSON and run it.

Use this umbrella skill for orientation and package rules. For real work, route to the smallest focused skill:

| User wants | Use |
|---|---|
| Configure ComfyUI paths, server URL, custom nodes, or models | `vibecomfy-setup` |
| Find a workflow, precedent, node wiring, or Hivemind evidence | `search-comfy-workflows` |
| Explain what a workflow does or answer questions about it | `explain-comfy-workflow` |
| Clean up, regroup, or align a ComfyUI workflow layout without changing runtime behavior | `reorganise-comfy-workflow` |
| Tweak or rewrite a workflow without running it | `edit-comfy-workflow` |
| Execute a ready template, recipe, scratchpad, server run, or RunPod smoke | `run-comfy-workflow` |
| Diagnose validation, conversion, node/model, or runtime failures | `debug-comfy-workflow` |
| Add a durable package ready template | `add-comfy-workflow-template` |

The operating path is:

```text
discover -> load -> edit/compose -> validate -> run -> collect outputs
```

## First Moves

Work from the repo root. Prefer the `vibecomfy ...` console entrypoint; if an editable checkout has no console script, use `python -m vibecomfy.cli ...`.

For a runnable starting point:

```bash
vibecomfy workflows list --ready
vibecomfy inspect image/z_image
vibecomfy copy-to-recipe image/z_image --out recipes/my_run.py
vibecomfy validate recipes/my_run.py
vibecomfy run recipes/my_run.py --runtime server --server-url http://127.0.0.1:8188
```

For raw JSON:

```bash
vibecomfy port check workflow.json --json
vibecomfy port convert workflow.json --out out/scratchpads/workflow.py --json
vibecomfy validate out/scratchpads/workflow.py
```

For setup trouble:

```bash
vibecomfy config show --json
vibecomfy runtime doctor
```

## Authoring Model

Use one loader by default:

```python
from vibecomfy import load_workflow_any

def build():
    wf = load_workflow_any("image/z_image")
    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)
    return wf.finalize_metadata()
```

Choose the lightest edit shape:

| Shape | Use when |
|---|---|
| `VibeWorkflow` setters/direct methods | You are changing existing prompt, seed, steps, widgets, edges, or metadata. |
| Patches | You are decorating an existing graph without changing the public handle shape. |
| Blocks | You are adding graph structure that produces new handles. |
| Recipes | You are making a user-specific composition or chaining logic. |
| Ready templates | You are adding a durable package starting point by id. |

Keep ComfyUI's terms precise: a **workflow** is any graph; a **template** is a curated starting-point workflow under `ready_templates/`.

## Rules

- Treat the worktree as shared. Do not revert, overwrite, or clean up edits you did not make.
- Keep changes scoped to the requested workflow, command, template, or doc surface.
- Do not change runtime behavior, workflow corpus files, generated snapshots, or template manifests unless the task explicitly covers them.
- Never invent node class names, sockets, widget fields, or model layouts. Use `inspect`, `analyze info`, `nodes spec`, local precedents, or `search-comfy-workflows`.
- Sync indexes only when needed: `vibecomfy sources sync`.
- Add focused tests when changing command routing, parser behavior, conversion, validation, search, runtime-facing code, or template coverage.
- Keep tests deterministic; avoid requiring ComfyUI, RunPod, network, or local model files unless the test is explicitly marked for that environment.

## Agent-Edit Policy

- Prefer normal static graph edits first.
- Use `vibecomfy.loop` only for bounded visible sweeps that cannot lower cleanly to ordinary nodes. Keep iteration counts bounded and metadata typed.
- Use `vibecomfy.code` only for inspectable typed logic when no shipped shape fits. Default to sandboxed modes. Never emit unrestricted execution from agent-authored code.
- Reject side-effecting, unbounded, runtime-only, external-I/O, or otherwise unrepresentable requests at policy level.
- Editor-only intent nodes may be valid for Canvas Apply, but they are Queue blockers until lowered to normal runtime nodes.
- When emitting an intent node programmatically, build metadata with `intent_node_properties(...)`.

## When You Need More Detail

Read [REFERENCE.md](REFERENCE.md) for the API surface, layer model, command catalog, plugin hooks, known limitations, RunPod environment, and durable-template checklist.

In-repo references:

- `docs/authoring.md` — blocks, patches, handles, opaque subgraphs, recipes
- `docs/vibeworkflow.md` — IR contract
- `docs/api/m6-public-api.md` — public imports and compatibility aliases
- `docs/custom_nodes.md` — node packs, install/lock/restore
- `docs/runtime/lifecycle.md`, `docs/runtime/surface.md` — embedded vs server runtime
- `docs/errors_and_doctor.md` — what `doctor` flags and how to fix it
- `docs/templates/adding_templates_models.md` — full ready-template addition process

When in doubt, stay in Python and descend only as far as needed:

```text
op -> Artifact -> preview_workflow -> VibeWorkflow -> compile("api") -> run
```
