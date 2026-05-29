---
name: vibecomfy
description: 'Drive the VibeComfy package to discover ComfyUI workflows, load ready Python templates, edit and compose them in a `VibeWorkflow` IR, validate, and execute either embedded locally or on a RunPod GPU. Use whenever the user wants to generate images / video / audio / edits via ComfyUI from Python, swap params on a template, splice templates together, write logic on top of a graph, or run one of the existing `ready_templates` end-to-end. Triggers: "run a workflow", "tweak this template", "combine wan and z_image", "generate an image / video / song", "compose a custom pipeline", "execute on RunPod", "build a recipe".'
---

# VibeComfy

VibeComfy is a Python package at `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/` for driving ComfyUI from real Python instead of JSON. Everything funnels through one editable IR — `VibeWorkflow` — and one execution path — `wf.compile("api") -> queue_prompt(dict)` against an embedded or remote ComfyUI runtime.

This skill teaches an agent how to use it. The user wants to: **grab a template, write code on top, combine it with other templates / patches / custom Python, then execute** (locally or on RunPod).

This file is the **core / basic usage**. For loops, batching, parameter sweeps,
arbitrary non-Comfy Python in a template, and data-dependent iteration ("keep
generating until the result is good enough"), read the advanced companion:
[`advanced_usage.md`](advanced_usage.md). It explains the build-time vs. run-time
boundary that answers almost every "can VibeComfy do X?" question, with runnable
examples in [`examples/`](examples/). Reach for it whenever a task needs logic
*around* a graph rather than just editing one graph.

## Repository rules

- Work from the repository root: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.
- Treat the worktree as shared. Do not revert, overwrite, or clean up edits you did not make.
- Keep changes scoped to the requested task. Avoid unrelated refactors, generated-output churn, and broad formatting changes.
- Prefer explicit, local registries and small modules over implicit discovery unless a task specifically asks for discovery.
- Do not change runtime behavior, templates, workflow corpus files, or generated snapshots unless the task explicitly covers those areas.
- If a change needs coordination with another interface or parallel task, document the integration note instead of guessing across ownership boundaries.
- Run the full test suite with `pytest`; run focused tests with `pytest tests/test_cli.py` or the relevant test file.
- Exercise the CLI locally with `python -m vibecomfy.cli ...`.
- Sync indexes only when a task or test requires it: `python -m vibecomfy.cli sources sync`.
- Before manually editing an imported workflow, converting raw JSON into a template, or launching RunPod validation, run `python -m vibecomfy.cli port check <workflow> --json` and use the report to resolve helper nodes, custom-node packs, schema issues, widget aliases, and model assets.
- `vibecomfy run` reconciles model assets by default for embedded runs: it inspects the final built workflow, resolves model-picker values through `vibecomfy/registry/models.yaml`, downloads/stages what it can, and fails before queueing when a referenced asset is unresolved. Use `--no-ensure-models` only for compile-only/local work where downloads are intentionally disabled.
- If a custom node expects a model under its own package directory, declare a `model_assets` entry with `target_path` relative to the VibeComfy checkout, such as `custom_nodes/comfyui_controlnet_aux/ckpts/...`. Do not leave these to ad hoc runtime Hugging Face downloads.
- Before replacing a node class or hand-authoring node kwargs, run `python -m vibecomfy.cli nodes spec <ClassType>`. It reads the generated index when available and falls back to installed custom-node source with `INPUT_TYPES`, which avoids guessing accepted inputs.

## CLI implementation guidance

- The console entrypoint is `vibecomfy = "vibecomfy.cli:main"`.
- Top-level command registration belongs in `vibecomfy/commands/__init__.py`.
- Individual command modules should expose `register(subparsers)` and keep command execution in private `_cmd_*` helpers.
- Keep command registration explicit. Do not add plugin discovery or dynamic filesystem scanning unless the task asks for it.
- `workflows list`, `nodes list`, `inspect`, `port check`, `port convert`, `doctor`, `sources sync`, `analyze info`, and `analyze diff` support `--json`; keep existing text output stable.

## Testing expectations

- Add or update focused tests when changing command routing, parser behavior, workflow conversion, validation, search, or runtime-facing code.
- Prefer subprocess CLI smoke tests only when behavior depends on process-level invocation or current working directory.
- Keep tests deterministic and avoid requiring ComfyUI, RunPod, network access, or local model files unless the test is explicitly marked or scoped for that environment.

## Vocabulary

VibeComfy uses ComfyUI's two-word distinction precisely:

- **Workflow** = any graph. The thing in your editor right now is a workflow. The 47 JSON files under `workflow_corpus/` are workflows. A `VibeWorkflow` is the editable IR for one workflow.
- **Template** = a workflow specifically curated as a **starting point you clone-and-edit**. ComfyUI itself has a "Browse Templates" feature for exactly this concept. In VibeComfy these live in `ready_templates/` and are addressable by id (`image/z_image`, `video/wan_t2v`).

Use "workflow" when referring to any graph; use "template" only when you mean a starting-point workflow from `ready_templates/`.

**Public API names that follow this rule:**

| Loader | What it loads |
|---|---|
| `load_workflow_any(path_or_id)` | The universal entry point — accepts a ready id, scratchpad path, or JSON file |
| `workflow_from_ready(id)` | Loads a *template* by id (e.g. `image/z_image`) |
| `workflow_from_id(id)` | Loads any workflow by id — checks ready templates first, then the indexed corpus |
| `workflow_from_file(path)` | Loads a JSON workflow from a path |
| `load_workflow_json(path)` | Low-level: read+validate JSON only, no normalization |

`workflow_from_template` is kept as a back-compat alias for `workflow_from_id`. `load_template` is kept as a back-compat alias for `load_workflow_json`. New code should use the new names.

## Mental model — two layers

VibeComfy has two distinct authoring layers. Pick the right one before doing anything.

**Layer 1 — workflow IR (`VibeWorkflow`):** the raw graph. Nodes, edges, widgets, handles. This is what compiles to the dict ComfyUI accepts. Everything else is sugar on top.

**Layer 2 — five flows that operate on workflows.** A user always *starts from a workflow* (a ready one, or a converted JSON one, or one they author from scratch) and then reaches for one of these five flows on top.

| # | Flow | Lives in | What it does | Returns |
|---|---|---|---|---|
| 1 | **Direct IR edits / setters** | `VibeWorkflow` methods | Raw graph editing: `set_prompt`, `set_seed`, `set_steps`, `add_node`, `connect`, `disconnect`, `replace_edge`, `register_input`, `finalize_metadata`. The lowest-level lever. | `VibeWorkflow` |
| 2 | **Patches** (decorate) | `vibecomfy/patches/*.py` (`seed`, `resolution`, `save_prefix`, `gguf_unet`, `controlnet`, `ltx_lowvram`) | A `Patch(name, applies_to, apply, rationale)` that **decorates** an existing graph: tweaks a widget, splices a node into an edge, swaps a class. | `VibeWorkflow` (mutated) |
| 3 | **Blocks** (extend) | `vibecomfy/blocks/*.py` (`encoding`, `sampling`, `decode`, `save`, `latent`, `loaders`, `subgraph`, `video`) | A function that mutates a workflow and returns typed `Handles`. Use when the call **changes** what handles are available (loader → `model/clip/vae`; sampler → `samples`; decode → `images`). | `Handles({"image": Handle(...)})` |
| 4 | **Ops (verb-native)** | `vibecomfy/ops/{image,video}.py` | Lazy one-call entries: `image.t2i(prompt)`, `video.t2v(prompt)`, `video.i2v(image, prompt)`. Internally call `router.pick(...)` to choose a workflow + patches. Audio and image-edit verbs are not yet wired up — for those, `load_workflow_any("audio/...")` or `load_workflow_any("edit/...")` and edit the IR directly. | `Artifact` (`Image` / `Video`) |
| 5 | **Recipes** (compose) | `recipes/*.py` | Runnable Python that combines workflows + patches + blocks + ops + custom logic for one concrete result. The natural place to write user logic that spans multiple workflows. | usually a `VibeWorkflow` |

Layer 1 rule: *changes-handles → block; decorates-handles → patch.*
Layer 2 rule: *changes-handles → new ready workflow; decorates-handles → recipe.*

## The flow you should follow

```
discover → load → edit/compose → validate → run → outputs
```

Every step has one or two canonical entry points. Use them rather than improvising.

### 1. Discover

Run from the repo root: `cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

```bash
python -m vibecomfy.cli sources sync                  # build/refresh indexes
python -m vibecomfy.cli workflows list --ready        # ready Python templates
python -m vibecomfy.cli workflows list --ready --include-dynamic  # explicit plugin/user ready rows
python -m vibecomfy.cli workflows list                # indexed JSON corpus
python -m vibecomfy.cli search wan --task i2v         # weighted search; tasks: i2v, t2v, t2i, controlnet, audio_reactive, ...
python -m vibecomfy.cli nodes list                    # node classes (Comfy core + installed packs)
python -m vibecomfy.cli nodes spec KSampler           # input/output schema for a node
python -m vibecomfy.cli nodes spec ImageResizeKJv2    # fallback-inspect installed custom-node INPUT_TYPES
python -m vibecomfy.cli inspect image/z_image         # metadata, requirements, runnable status
python -m vibecomfy.cli analyze info <wf>             # full graph dump (also: trace, path, values, diff, subgraph, unconnected)
python -m vibecomfy.cli analyze corpus --json         # aggregate stats across all ready templates
python -m vibecomfy.cli analyze tracefield <wf> <field>  # source-of-truth trace for a public input field
python -m vibecomfy.cli analyze names <wf>            # preview variable naming on a workflow
python -m vibecomfy.cli nodes coverage <wf>           # schema completeness: typed wrappers vs raw_call vs missing
python -m vibecomfy.cli nodes drift <pack>            # schema drift detector for a custom-node pack
python -m vibecomfy.cli port rules --explain          # what rules does the codemod emitter follow
python -m vibecomfy.cli port lint <wf>                # convention enforcer over generated templates
python -m vibecomfy.cli port simulate --rule X --all  # try an experimental emitter rule corpus-wide
python -m vibecomfy.cli copy-to-recipe <id> --out <path>  # take a template to recipes/ for hand-editing
```

Indexes that back these: `workflow_index.json`, `node_index.json`, `external_workflow_index.json`, `custom_nodes.lock` (all generated by `sources sync`), plus the repo-owned `template_index.json` for ready templates. Default `workflows list --ready --json` is repo-indexed and side-effect-light when `template_index.json` exists; it does not import plugin, cwd-extra, or user-global ready roots. Use `--include-dynamic` only when dynamic plugin/user rows are explicitly needed. Dynamic rows are marked `source_scope: dynamic` and `indexed: false` and are excluded from strict-ready gates.

### 1b. Port Check

When a workflow comes from raw Comfy JSON, an indexed corpus entry, a scratchpad from another agent, or a failing ready template, run the porting preflight before manual editing or RunPod:

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port check <workflow> --strict-ready-template --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
```

Use `port check` to surface helper/UI nodes (`Note`, `MarkdownNote`, `SetNode`, `GetNode`), unresolved helper broadcasts, missing real runtime classes, custom-node pack suggestions, model asset warnings, missing required inputs, schema mismatches, invalid link shapes, and unresolved positional `widget_N` aliases. Helper/UI classes should produce helper diagnostics, not missing-pack work.

Use `port convert` to produce Python. Scratchpad mode is the default while investigating. Ready-template mode requires `--ready-id <kind>/<name>` because it creates a curated candidate.

Use `--strict-ready-template` before promoting or RunPod-testing a production/app-parity template. It escalates schema-backed unresolved positional widgets, missing or broken public input targets, missing or unnamed public outputs, hidden model filenames, and opaque UUID subgraphs to hard errors while leaving unknown community-node widgets as porting warnings until object_info or committed widget schema is available.

Use `--head-check-models` only when you intentionally want model URL HEAD checks. It checks status, redirects, timeouts, and likely gated/404 URLs without downloading bodies. Normal `port check`, `doctor`, `validate`, `fetch`, and `run` should stay offline by default.

### 1c. Port Inventory

```bash
python -m vibecomfy.cli port inventory --ready --json
python -m vibecomfy.cli port inventory --ready
```

`port inventory` scans the checked-in `ready_templates/**/*.py` glob and reports
readability issues (positional `.out(<int>)`, `widget_N` fields, UUID class types,
local `_node` copies, missing output contracts), marker classification (`# vibecomfy:
manual`, `# vibecomfy: generated`), coverage-tier joins, and source-provenance flags.
The JSON output is deterministic and versioned. It never consults plugin/cwd/user-global
template paths.

Decision map:

| Situation | Start with |
|---|---|
| Raw JSON import, indexed workflow, or inherited scratchpad | `port check <workflow> --json` |
| Need editable Python from source material | `port convert <workflow> --out out/scratchpads/<name>.py --json` |
| Curating a checked-in template | `port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json` |
| Unknown runtime classes | `port check`, then `nodes install-plan` |
| Missing model files or asset URLs | `port check`, then `fetch`; add `--head-check-models` only for URL reachability |
| RunPod validation | `port check --strict-ready-template` first, then focused matrix only after hard porting errors are handled |

### 1d. Working with the codemod

When iterating on the codemod itself or debugging why a conversion
produced unexpected output:

```bash
python -m vibecomfy.cli port rules --explain      # what rules does the emitter follow
python -m vibecomfy.cli port lint <wf>            # gate output against conventions
python -m vibecomfy.cli port simulate --rule X    # try an experimental rule corpus-wide
python -m vibecomfy.cli port convert <wf> --dry-run --diff   # preview rendered output
python -m vibecomfy.cli analyze names <wf>        # preview variable naming
python -m vibecomfy.cli nodes coverage <wf>       # what'll fall through to raw_call
python -m vibecomfy.cli nodes drift <pack>        # schema diff between commits
```

The pattern for iterating safely on emitter rules:

  rules → simulate → lint

### 2. Load

There is **one loader** to remember: `load_workflow_any`. It accepts ready ids, scratchpad paths, JSON files, and indexed references.

```python
from vibecomfy import load_workflow_any
wf = load_workflow_any("image/z_image")              # ready id (preferred starting point)
wf = load_workflow_any("video/wan_t2v")
wf = load_workflow_any("workflow_corpus/official/image/z_image.json")  # raw JSON
wf = load_workflow_any("out/scratchpads/my_thing.py")                  # scratchpad
```

Pure functions also exist: `workflow_from_ready(id)`, `workflow_from_id(id)`, `workflow_from_file(path)`.

To **convert** an arbitrary JSON workflow into editable Python, use the canonical porting commands:

```bash
python -m vibecomfy.cli port convert <workflow_id_or_path> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <workflow_id_or_path> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
```

`port convert` uses atomic writes (temp file + validate/parity check + `Path.replace()`),
refuses to overwrite `# vibecomfy: manual` templates, supports `--dry-run` and `--diff`
modes, and includes parity evidence in its JSON output.

If you just want to **run** a raw Comfy workflow without converting, `python -m vibecomfy.cli run path/to/workflow.json --runtime embedded` (or `load_workflow_any("path/to/workflow.json")` in Python) is the cheapest path — no scratchpad, no checked-in template.

### 3. Edit / compose

This is where the user wants flexibility — **start from a template, then layer code on top**. There are five idioms; pick the lightest one that fits.

**(a) Tweak knobs on a single template.** Use the convenience setters on `VibeWorkflow`.
```python
wf = load_workflow_any("image/z_image")
wf.set_prompt("a glass teapot on basalt")
wf.set_seed(42)
wf.set_steps(20)
```

**(b) Apply a patch (decorate handles).** Patches are policy.
```python
from vibecomfy.patches.resolution import resolution
from vibecomfy.patches.seed import seed
from vibecomfy.patches.save_prefix import save_prefix
from vibecomfy.patches.controlnet import controlnet         # topological splice
from vibecomfy.patches.ltx_lowvram import patch as ltx_lowvram

resolution(832, 480, 81).apply(wf)
seed(20260428).apply(wf)
save_prefix("my_run/").apply(wf)
```

**(c) Add a block (change handles).** Blocks return typed `Handles` you wire into the next node.
```python
from vibecomfy.blocks.save import image as save_image
from vibecomfy.blocks.subgraph import opaque, ref

handles = opaque(wf, class_type="vibecomfy.placeholder.upscale",
                 links={"image": ref(wf.outputs[0].node_id)},
                 outputs=("image",))
save_image(wf, images=handles.image, filename_prefix="dual_pass/upscaled")
wf.finalize_metadata()
```

**(d) Edit the graph directly.** All `VibeWorkflow` methods are public:
- `wf.add_node(class_type, **inputs)` / `wf.node(class_type, **kwargs)` (chainable, with `.out(slot)` handles)
- `wf.connect(from_ref, to_ref)` / `wf.disconnect(to_ref)` / `wf.replace_edge(to_ref, new_from_ref)`
- `wf.register_input(name, node_id, field, value=None)` for inputs metadata can't infer
- `wf.finalize_metadata()` — call after structural edits to rebuild `inputs`, `outputs`, `requirements`.

**(e) Combine multiple templates / verbs (the higher-abstraction case).** This is the recipe pattern. Each call returns a `VibeWorkflow` (or an `Artifact` you can preview) and you stitch them with blocks or with plain Python control flow:

```python
# Example: dual-pass — z_image then a placeholder upscaler, both saved.
from vibecomfy.blocks.save import image as save_image
from vibecomfy.blocks.subgraph import opaque, ref
from vibecomfy import load_workflow_any

def build():
    wf = load_workflow_any("image/z_image")
    first = wf.outputs[0]
    upscaled = opaque(wf, class_type="vibecomfy.placeholder.upscale",
                     links={"image": ref(first.node_id)}, outputs=("image",))
    save_image(wf, images=upscaled.image, filename_prefix="dual_pass/upscaled")
    return wf.finalize_metadata()
```

For **completely independent** workflows (e.g. generate image with `image.t2i`, then feed it to `video.i2v`), run them sequentially and pass output paths between them — there is no single graph that spans both. The verb-native ops make this clean:

```python
from vibecomfy import image, video
img = image.t2i("a glass teapot").run(runtime="embedded")
clip = video.i2v(img.outputs[0], "the teapot rotates").run(runtime="embedded")
```

The escape-hatch chain — every level is intentionally public:
```
op() -> Artifact -> preview_workflow() -> VibeWorkflow -> compile("api") -> API JSON -> run()
```

**Custom nodes / packs.** When a graph needs nodes that aren't installed:
```bash
python -m vibecomfy.cli nodes install-plan <wf>         # what's missing + which packs satisfy it
python -m vibecomfy.cli nodes ensure <wf>               # install missing packs
python -m vibecomfy.cli nodes lock                      # write/refresh custom_nodes.lock
python -m vibecomfy.cli nodes restore                   # match the lockfile
```

**Models.** Stage models declared in `vibecomfy/registry/models.yaml`:
```bash
python -m vibecomfy.cli run <wf> --runtime embedded     # reconciles/downloads model assets by default
python -m vibecomfy.cli run <wf> --runtime embedded --no-ensure-models  # opt out only for compile-only work
python -m vibecomfy.cli fetch <wf>                      # fetch this workflow's declared authored assets
python -m vibecomfy.cli models stage --select-phase core
```

### 4. Validate

Cheap; run it before queuing. For imported or failing workflows, run `port check <workflow> --json` before `validate`, `doctor`, or RunPod so missing custom nodes, helper issues, model assets, and schema errors are reported in one port report.

```bash
python -m vibecomfy.cli validate path/to/scratchpad.py
python -m vibecomfy.cli doctor   path/to/scratchpad.py   # requirements + readiness + suggested patches
python -m vibecomfy.cli runtime doctor                   # runtime deps
```

In Python: `wf.validate(schema_provider=...)` returns a `ValidationReport`.

### 5. Run

**Local embedded** (default; needs HiddenSwitch ComfyUI installed):
```bash
python -m vibecomfy.cli run out/scratchpads/<name>.py --runtime embedded
python -m vibecomfy.cli run image/z_image --ready                 # run a ready template by id
python -m vibecomfy.cli run image/z_image --ready --prompt "..." --seed 7 --steps 20
```

Embedded runs reconcile model assets by default. If the final workflow contains a model-picker value such as `ckpt_name`, `vae_name`, `unet_name`, or `lora_name`, the runner resolves it against authored `model_assets` and `vibecomfy/registry/models.yaml` before queueing. Missing registry/authored coverage is a pre-run failure, not a Comfy queue failure. Use `--no-ensure-models` only when deliberately avoiding downloads.

Loader folders are part of the runtime contract. If an LTX audio VAE is loaded through `LTXVAudioVAELoader`, stage it as a `checkpoints` asset. Do not load `LTX*_audio_vae*.safetensors` with `VAELoaderKJ`; `validate` rejects that pairing because current KJNodes can misclassify the file and crash at runtime.

```python
from vibecomfy.runtime import run_embedded_sync
result = run_embedded_sync(wf)            # blocking
# or async: from vibecomfy.runtime.run import run_embedded; await run_embedded(wf)
```

**Remote server:**
```bash
python -m vibecomfy.cli run <wf> --runtime server --server-url http://host:8188
```

**RunPod (ephemeral GPU pod).** This is a separate harness — it provisions a pod, uploads the repo, runs validation, tears the pod down. See the `runpod-lifecycle` skill for pod management; the VibeComfy entry points are:
```bash
python -m vibecomfy.cli port check <workflow> --json     # cheap preflight before GPU spend
python scripts/runpod_validate.py                       # cheap smoke (~$0.05–$1)
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
pytest --runpod-full -m runpod_full tests/smoke/test_layer2_runpod_matrix.py
python -m vibecomfy.cli runpod list|status|terminate|gpu-types|corpus-matrix
```

The corpus matrix writes offline port reports and port-convert preview artifacts beside existing logs. Inspect those before debugging pod-only symptoms; they often identify missing packs, model declarations, helper-node problems, or schema issues without another GPU run.

API keys / env vars — set in shell or `.env`:

| Var | Purpose | Default |
|---|---|---|
| `RUNPOD_API_KEY` | RunPod creds (loaded from `runpod-lifecycle/.env` by `scripts/runpod_validate.py`) | required |
| `RUNPOD_GPU_TYPE` / `RUNPOD_GPU_TYPE_<FAMILY>` | GPU class override | RTX 4090 |
| `VIBECOMFY_RUNPOD_STORAGE` | RunPod network volume name | `Peter` |
| `VIBECOMFY_RUNPOD_GPU` | GPU class for `runpod_validate.py` | `NVIDIA GeForce RTX 4090` |
| `VIBECOMFY_RUNPOD_MAX_RUNTIME_SECONDS` | Watchdog timeout | 7200 (smoke) / 21600 (matrix) |
| `VIBECOMFY_RUNPOD_LIFECYCLE_ROOT` | Path to sibling `runpod-lifecycle` checkout | `../runpod-lifecycle` |
| `VIBECOMFY_RUNPOD_REPO_URL` / `VIBECOMFY_RUNPOD_GIT_REF` | What the pod checks out | local origin / current branch |
| `VIBECOMFY_WATCHDOG=1` | Verbose watchdog log capture on the pod | unset |

### 6. Outputs

Everything writes under `out/`:

- `out/scratchpads/<name>.py` — generated by `port convert`
- `out/runs/<run_id>/comfy.log` — server log for that run
- `out/runs/<run_id>/metadata.json` — `RunResult` snapshot (prompt id, api dict, run timestamps)
- `out/runs/<run_id>/...` — saved images / videos / audio (also accessible via `RunResult.outputs`)
- `out/sessions/<id>/` — embedded session state

`python -m vibecomfy.cli logs tail` shows the latest.

## Plugin / extension surface

- `./vibecomfy_extras/{blocks,patches,ops,recipes,ready_templates}/*.py` — project-local plugins
- `~/.vibecomfy/{...}` — user-global plugins
- pip entry points in the `vibecomfy.plugins` group

`ensure_plugins_loaded()` discovers them lazily. The `PluginAPI` exposes `register_block`, `register_patch`, `register_op`, `register_route`, `register_ready_root`. Built-in ready ids win on collision; plugin collisions warn.

## Verb-native router (`router.pick`)

`image.t2i(prompt, model="z_image")` internally calls `router.pick("image", "t2i", model=...)` to choose a template id and a list of patches. Use `router.pick(...)` directly to inspect a route before loading. Rules live in `vibecomfy/router_rules.py`.

```python
from vibecomfy import router
result = router.pick("video", "i2v", model="ltx")    # RouterResult(template_id, explicit_patches, applicable_patches)
```

## v2.7 guidance

### ContextVar template authoring

Templates now use a **context-manager pattern** with `new_workflow()` instead of passing `wf` explicitly to every call. This aligns generated templates with the typed-wrapper convention:

```python
from vibecomfy.templates import new_workflow, node, InputSpec
from vibecomfy.handles import Handle

READY_METADATA = {
    "ready_template": "image/my_template",
    "task": "t2i",
    "description": "...",
}

with new_workflow(READY_METADATA, source_path=__file__) as wf:
    # node() reads wf from ContextVar — no explicit wf arg needed
    loader = node("CheckpointLoaderSimple", ckpt_name=InputSpec("ckpt_name", default="..."))
    # ...

wf.finalize_metadata()
```

The `node()` function reads the active workflow from a `ContextVar` set by `new_workflow().__enter__()`. Legacy explicit-`wf` calling conventions still work: `node(wf, class_type, ...)`. The `_current_workflow_or_raise()` helper raises `ContextVarBindingError` (with `next_action="vibecomfy doctor"`) if called outside a `with new_workflow(...)` block.

### Tuple-unpacked multi-output wrappers

Nodes with multiple outputs (e.g., `WanVideoWrapper` returning `(latent, mask)`) use **tuple-unpacked return patterns** in generated templates:

```python
latent, mask = node("WanVideoWrapper", ...)
```

The emitter tracks `return_refs` — a tuple of `(node_id, output_slot)` pairs — and emits assignment targets accordingly. When a node has exactly one output, the return is a single `Handle`. For `pass_raw=True` nodes with list outputs, callers must use `.out('NAME')` explicitly. Use `node("ClassType", ..., _outputs=("latent", "mask"))` to override auto-detected output names in hand-authored templates.

### Materialized subgraphs as Python functions

Subgraphs embedded in workflows are **materialized as inline Python functions** inside `build()`:

```python
def _subgraph_upscale(**kwargs):
    upscale = raw_call("<uuid>", "UpscaleModelLoader", model_name=kwargs["model_name"])
    # ... internal nodes and edges ...
    return upscale

result = _subgraph_upscale(model_name="4x-UltraSharp")
```

The emitter detects subgraph nodes (identified by a named `GroupNode` or UUID-prefixed internal topology), extracts their internal nodes/edges, and emits them as a local function with declared default arguments matching the subgraph's input ports. Subgraph freshness is tracked via `SubgraphFreshnessError` — regenerated templates compare `source_hash` and alert when the embedded subgraph syntax has changed.

### Blank-line / label-preferred emission style

v2.6.4 Fix 8 refines emission formatting: multi-line node calls are **surrounded by blank lines** (one before, one after) for consistent vertical rhythm. Single-line statements pack together. Section comments stay attached to the first multi-line that follows (no blank between section comment and its code). The emitter prefers **label-derived variable names** when available (e.g., `ks_advanced` from a KSampler node's `title` field) over generic `node_3` identifiers.

### widget_N cleanup

The emitter resolves positional `widget_N` keys to their named fields via `object_info` input aliases and the `widget_aliases` module. During `port convert`, unresolved `widget_N` keys trigger a warning (or hard error under `--strict-ready-template`). The `_translate_widget_for_key()` function maps `widget_0` → `seed`, `widget_1` → `steps`, etc. for known class types. The `port inventory` command reports remaining `widget_N` occurrences across all ready templates.

### New CLI commands (v2.7)

```bash
# Runtime eval-node: compile a minimal subgraph to preview one node
python -m vibecomfy.cli runtime eval-node <wf> --node <node_id> [--runtime embedded|server]

# Port validate-call: validate one node call against authoring schema
python -m vibecomfy.cli port validate-call <ClassType> --kwargs '{"seed": 42, ...}' --json

# Nodes compatible-with: find or check socket type compatibility
python -m vibecomfy.cli nodes compatible-with <FromClass> [<ToClass> <ToInput>] --as output --json

# Port doctor-all: run port check + install-plan + validate + doctor + runtime doctor
python -m vibecomfy.cli port doctor-all <wf> --json

# Port export: export a workflow as API JSON
python -m vibecomfy.cli port export <wf> --to json [--json]
```

### wf.lookup_id() and wf.export_to_json()

`wf.lookup_id(node_id)` returns a rich info dict for any node:
```python
info = wf.lookup_id("42")
# {"node_id": "42", "class_type": "KSampler", "variable_name": "ks_advanced",
#  "inputs": {...}, "outputs": [...], "edges_from": [...], "edges_to": [...]}
```

`wf.export_to_json(format="api")` compiles the workflow to API JSON (alias for `wf.compile("api")`). Use this when you need the raw ComfyUI-compatible dict without queuing.

### wf.strict_types

Set `strict_types=True` on a `VibeWorkflow` to enable socket-type compatibility warnings on `wf.connect()`. When enabled, connections between incompatible socket types (e.g., LATENT → IMAGE) log a warning. The `nodes compatible-with` CLI command performs the same check interactively.

### attempt.json, drift, next_action

Before every queue boundary, the session runner writes an **`attempt.json`** snapshot to `out/runs/<run_id>/` containing:
- `compiled_prompt` — the full API dict sent to ComfyUI
- `id_map` — variable-name → node-id mapping
- `node_lookups` — rich info per node (via `wf.lookup_id()`)
- `model_manifest` — expected and actual SHA-256 for every model asset
- `lockfile_snapshot` — the full `custom_nodes.lock` at queue time
- `drift` — pinned-vs-actual comparison for custom-node packs and ComfyUI commit

**Drift detection** (`vibecomfy.runtime.drift`) compares pinned template requirements against the installed pack state (lockfile git HEAD, schema hashes, source file SHAs) and the ComfyUI git commit. Mismatches are logged as warnings; `SessionConfig.strict_drift=True` raises `DriftError` before queueing.

**Structured errors** (`vibecomfy.errors`) all extend `VibeComfyError(RuntimeError)` with an optional `next_action` string suggesting remediation:
- `ModelAssetError` — unresolved model file
- `SchemaValidationError` — failed schema validation
- `QueueError` — enqueue/wait/result failure
- `ContextVarBindingError` — missing or nested workflow context
- `ConversionParityError` — emitted code ≠ source workflow
- `SubgraphFreshnessError` — embedded subgraph stale vs source
- `RuntimeNodeError` — node failed during execution
- `DriftError` — custom-node/model pins drifted from lockfile

All VibeComfyError subclasses are caught by the CLI runner's `(OSError, RuntimeError, ValueError)` catch tuple. The `next_action` field appears in `str(exc)` and is accessible programmatically via `exc.next_action`.

### Bidirectional roundtrip limitations

JSON → Python → JSON roundtripping has known limitations:
- **Helper/UI nodes** (`Note`, `MarkdownNote`, `SetNode`, `GetNode`, `Reroute`) are stripped during conversion and do not survive roundtrip.
- **Unresolved widget_N keys** on community nodes without `object_info` produce positional output that may not roundtrip exactly.
- **Subgraph UUIDs** are replaced by Python function names; re-importing the emitted Python may produce different UUIDs but structurally equivalent graphs.
- **Broadcast edges** (one output → multiple inputs) are preserved but the ordering of parallel edges may differ from the source JSON.
- **Comment nodes** and UI-only metadata are intentionally omitted from the Python representation.

## Known limitations (don't fight these)

- Audio and image-edit verbs are not yet wired in the verb-native API. Use `load_workflow_any("audio/ace_step_1_5_t2a_song")` or `load_workflow_any("edit/qwen_image_edit")` and edit the `VibeWorkflow` directly.
- `image.t2i(model="flux2_klein_9b_gguf")` not exposed via verb-native API yet — same workaround.
- Named outputs `.out("IMAGE")` raise `NotImplementedError` until MP-6 schema integration. Use integer slots: `.out(0)`.
- `MarkdownNote` nodes are stripped during refactor (UI annotations only).

## Decision shortcut

| User wants… | Do |
|---|---|
| "Generate one image / video / song" | `image.t2i(...).run()` / `video.t2v(...).run()` — flow 4 (ops) |
| "Run an exact named workflow" | `python -m vibecomfy.cli run <id> --ready` |
| "Tweak a workflow's prompt/seed/steps/resolution" | Load + setters/patches; flow 1 or 2 |
| "Splice ControlNet / IP-Adapter / etc. into a workflow" | `vibecomfy.patches.controlnet` — flow 2 (topological patch) |
| "Combine two workflows / chain image→video" | Recipe file — flow 5 |
| "New repeatable composition" | Add a recipe in `recipes/` |
| "New full graph for a new model" | Add a ready workflow under `ready_templates/<kind>/...` (see "Adding a new workflow") |
| "Run on a GPU I don't have locally" | `scripts/runpod_validate.py` or the `--runpod` pytest markers |
| "Drive a Reigh live-test run (worker + vibecomfy parity matrix)" | `reigh-worker/.claude/skills/live-test/SKILL.md` — pass `--variant auto` |
| "Inspect why an imported or converted workflow doesn't run" | `port check <workflow> --json`, then `nodes install-plan`, `fetch`, `validate`, or `doctor` based on the report |
| "Inspect why authored Python doesn't run" | `inspect`, `doctor`, `analyze info/trace/path/values`, then `validate` |

## Workflow lifecycle

Use this same gate sequence whether you are importing raw JSON, fixing an existing ready template, forking a ready template, or authoring from scratch:

1. **Identify intent**: media type, task, model family, required inputs, expected output artifact, and whether this is Reigh app parity or supplemental coverage.
2. **Pick the right entry path**:
   - raw Comfy JSON: save the upstream source under `workflow_corpus/...` and run `port check`;
   - existing ready template: load by id/path, inspect metadata/requirements/outputs, then run strict checks before editing;
   - fork: decide recipe/patch vs new ready template. If graph shape, model family, required inputs, outputs, or app capability changes, make a new ready template;
   - from scratch: author with `VibeWorkflow`/blocks, then promote only after the same strict checks.
3. **Programmatic gates**: `port check --json`, `port widgets` when aliases remain, `nodes install-plan`, model metadata/registry updates, `validate`, `doctor`, `port check --strict-ready-template --json`, `tools.refresh_template_index --check`, `python -m tools.check_strict_ready_templates --json`, and focused tests.
   Required/app-active templates must not hide schema-backed widgets, unnamed outputs, missing public inputs, hidden model filenames, or opaque UUID subgraphs. If a violation remains, it must have an exact strict-ready exception with owner, ticket, allowed final category, expiration, and removal condition — exceptions live in `docs/strict_ready_exceptions.md` / `docs/strict_ready_exceptions.json` and are matched by `ready_id` + `violation_code` + `target`.
4. **Agentic checks**: source quality, model provenance, custom-node legitimacy, smoke-size adaptations, LoRA/control/input patch points, Wan2GP/app parity, and intentional differences.
5. **Evidence**: for app parity, update worker capability contracts and record successful focused RunPod evidence. Do not mark a workflow validated from local checks alone.

## Adding a new workflow

The full operating path lives in **`docs/adding_templates_models.md`**. Read it before adding a new family. The short version:

1. **Pick a stable id** in lower snake case encoding model + capability: `qwen3_tts_voice_clone`, `wanvideo_wrapper_21_14b_t2v`. The id becomes the manifest id, file name, RunPod matrix row, artifact path, and CLI handle.
2. **Drop the source JSON** under `workflow_corpus/official/<media>/<id>.json`, `workflow_corpus/custom_nodes/<pack>/<source>/<id>.json`, or `workflow_corpus/community/<source>/<id>.json`. Keep it close to upstream.
3. **Run port preflight**: `python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json`. Resolve hard errors before hand-editing or RunPod.
4. **Declare custom nodes** in `vibecomfy/node_packs.py` (a `CustomNodePack(name, repo, classes, pip_packages)` entry) and pin in `custom_nodes.lock`.
5. **Declare models**: workflow-embedded URLs go in workflow metadata; node-pack-specific layouts go in `vibecomfy/registry/models.yaml`.
6. **Convert to Python** with `python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out out/scratchpads/<id>.py --json`; use `--ready-id <kind>/<name>` only for ready-template candidates.
7. **Add a manifest row** in `workflow_corpus/manifests/coverage.json` with `id`, `path`, `media`, `task`, `coverage_tier`, `ready_template: true`.
8. **Create the Python ready template** with `python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --ready-id <media>/<id> --out ready_templates/<media>/<id>.py --json`, or hand-author it under `ready_templates/<media>/<id>.py` for full control.
9. **Refresh static discovery** with `python -m tools.refresh_template_index` and verify it with `python -m tools.refresh_template_index --check`; do not rely on dynamic plugin/user discovery for checked-in templates.
10. **Validate locally**: `python -m vibecomfy.cli validate ready_templates/<media>/<id>.py`, `python -m vibecomfy.cli port check ready_templates/<media>/<id>.py --strict-ready-template --json`, `python -m tools.check_strict_ready_templates --json`, then targeted tests `pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli.py`.
11. **Validate on RunPod** with a focused scope: `VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py`. Don't run the full matrix while iterating.
12. **For Reigh app parity**, update `../reigh-worker/scripts/capability_contracts/` after the VibeComfy template is valid. The worker contract records route, app, variant, artifact, and live evidence; VibeComfy records workflow validity.
13. **Document failures** in `docs/hiddenswitch_incompatibilities.md`, `docs/structural_issues.md`, or a family coverage doc — never leave fixes only in chat history or pod logs.

For a one-off composition (combining existing workflows), prefer a **recipe** under `recipes/` — that's flow 5 and doesn't need a manifest entry.

## Reference docs (in-repo)

- `docs/authoring.md` — blocks, patches, handles, opaque subgraphs, recipes, escape hatches
- `docs/template_porting_workbench.md` — `port check`, `port convert`, model URL checks, custom-node pack discovery, and RunPod preflight loop
- `docs/vibeworkflow.md` — IR contract
- `docs/python_composition_dsl_plan.md` — Layer 2 architecture
- `docs/custom_nodes.md` — node packs, install/lock/restore
- `docs/runpod.md`, `docs/runpod_smoke.md` — RunPod lifecycle and smoke harness
- `docs/runtime_lifecycle.md`, `docs/runtime_surface.md` — embedded vs server runtime
- `docs/errors_and_doctor.md` — what `doctor` flags and how to fix it
- `AGENTS.md` — agent-facing constraints and rules

When in doubt, the chain you're allowed to descend is always:

```
op → Artifact → preview_workflow → VibeWorkflow → compile("api") → run
```

Stay in Python; only drop to API JSON when handing the graph to ComfyUI.
- For testing user recipes built on VibeComfy: see [docs/testing-user-code.md](docs/testing-user-code.md).
