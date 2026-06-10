---
name: vibecomfy
description: 'Drive the VibeComfy package to discover ComfyUI workflows, load ready Python templates, edit and compose them in a `VibeWorkflow` IR, validate, and execute either embedded locally or on a RunPod GPU. Use whenever the user wants to generate images / video / audio / edits via ComfyUI from Python, swap params on a template, splice templates together, write logic on top of a graph, or run one of the existing `ready_templates` end-to-end. Triggers: "run a workflow", "tweak this template", "combine wan and z_image", "generate an image / video / song", "compose a custom pipeline", "execute on RunPod", "build a recipe".'
---

# VibeComfy

VibeComfy is a Python package at `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/` for driving ComfyUI from real Python instead of JSON. Everything funnels through one editable IR — `VibeWorkflow` — and one execution path — `wf.compile("api") -> queue_prompt(dict)` against an embedded or remote ComfyUI runtime.

This skill teaches an agent how to use it. The user wants to: **grab a template, write code on top, combine it with other templates / patches / custom Python, then execute** (locally or on RunPod).

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

## CLI implementation guidance

- The console entrypoint is `vibecomfy = "vibecomfy.cli:main"`.
- Top-level command registration belongs in `vibecomfy/commands/__init__.py`.
- Individual command modules should expose `register(subparsers)` and keep command execution in private `_cmd_*` helpers.
- Keep command registration explicit. Do not add plugin discovery or dynamic filesystem scanning unless the task asks for it.
- `workflows list`, `nodes list`, `inspect`, `doctor`, `sources sync`, `analyze info`, and `analyze diff` support `--json`; keep existing text output stable.

## Testing expectations

- Add or update focused tests when changing command routing, parser behavior, workflow conversion, validation, search, or runtime-facing code.
- Prefer subprocess CLI smoke tests only when behavior depends on process-level invocation or current working directory.
- Keep tests deterministic and avoid requiring ComfyUI, RunPod, network access, or local model files unless the test is explicitly marked or scoped for that environment.

## Agent-edit policy

- Prefer direct static graph edits first. If the request can be lowered into ordinary nodes, do that instead of emitting intent nodes.
- Use `vibecomfy.loop` only for bounded, visible sweeps that cannot be lowered cleanly. The metadata must carry a stable `vibecomfy_uid`, `properties.vibecomfy.kind`, typed `io.inputs` / `io.outputs`, and a bounded `count` / `iterations` / `over` contract with no more than 128 iterations.
- Use `vibecomfy.code` only for inspectable typed logic when no more specific shipped shape fits. `intent.source` or `intent.spec` must stay within 64 KiB (new modes) or 16 KiB (legacy `expression_v1`). Default execution mode is `sandboxed_loose` (broad builtins + restricted imports: math/statistics/re/json/random/itertools/datetime). `sandboxed_strict` allows no imports. `unrestricted` is **human-only opt-in** — the agent prompt explicitly raises on it; never emit `unrestricted` from agent code. Legacy `expression_v1` is preserved byte-identical for back-compat (single-expression eval, 16-name builtins, 1 s timeout).
- Reject side-effecting, unbounded, runtime-only, external-I/O, or otherwise unrepresentable requests at policy level. Do not imply sandboxed execution that does not exist.
- Editor-only intent nodes may be valid for Canvas Apply, but they are still Queue blockers until lowered to normal runtime nodes.
- When emitting an intent node programmatically, build the metadata with `intent_node_properties(...)` rather than hand-rolling `properties.vibecomfy`.

## Vocabulary

VibeComfy uses ComfyUI's two-word distinction precisely:

- **Workflow** = any graph. The thing in your editor right now is a workflow. The 47 JSON files under `workflow_corpus/` are workflows. A `VibeWorkflow` is the editable IR for one workflow.
- **Template** = a workflow specifically curated as a **starting point you clone-and-edit**. ComfyUI itself has a "Browse Templates" feature for exactly this concept. In VibeComfy these live in `ready_templates/` and are addressable by id (`image/z_image`, `video/wan_t2v`).

Use "workflow" when referring to any graph; use "template" only when you mean a starting-point workflow from `ready_templates/`.

**M6 public import surface.** The authoritative source for import claims is
`artifacts/m6-public-api.md`. Use `VibeWorkflow.compile("api")` to export a
workflow to the ComfyUI API JSON shape accepted by runtime execution. There is
no separate public export method to teach here.

These names are public from `vibecomfy` and present in `vibecomfy.__all__`:

| Loader / helper | What it does |
|---|---|
| `load_workflow_any(path_or_id)` | The universal entry point — accepts a ready id, scratchpad path, or JSON file |
| `workflow_from_ready(id)` | Loads a *template* by id (e.g. `image/z_image`) |
| `workflow_from_id(id)` | Loads any workflow by id — checks ready templates first, then the indexed corpus |
| `workflow_from_file(path)` | Loads a JSON workflow from a path |
| `load_workflow_json(path)` | Low-level: read+validate JSON only, no normalization |
| `ready_template_ids` | Lists ready template ids |

Compatibility aliases: `workflow_from_template` is kept as a back-compat alias for
`workflow_from_id`, and `load_template` is kept as a back-compat alias for
`load_workflow_json`. New code should use the new names.

Other top-level imports:

- Runtime helpers: `run`, `run_sync`, `run_embedded`, `run_embedded_sync`
- Ops namespaces: `image`, `video`
- Core IR types: `VibeWorkflow`, `VibeNode`, `VibeEdge`, `VibeInput`, `VibeOutput`, `WorkflowRequirements`, `WorkflowSource`, `ValidationIssue`, `ValidationReport`
- Handles: `Handle`
- Layer-2 namespaces: `blocks`, `patches`, `router`
- Artifact result types: `Artifact`, `Image`, `Video`, `Audio`, `Latent`, `Mask`
- Plugin hook: `ensure_plugins_loaded`

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
python -m vibecomfy.cli workflows list                # indexed JSON corpus
python -m vibecomfy.cli search wan --task i2v         # weighted search; tasks: i2v, t2v, t2i, controlnet, audio_reactive, ...
python -m vibecomfy.cli nodes list                    # node classes (Comfy core + installed packs)
python -m vibecomfy.cli nodes spec KSampler           # input/output schema for a node
python -m vibecomfy.cli inspect image/z_image         # metadata, requirements, runnable status
python -m vibecomfy.cli analyze info <wf>             # full graph dump (also: trace, path, values, diff, subgraph, unconnected)
```

Indexes that back these: `workflow_index.json`, `node_index.json`, `external_workflow_index.json`, `custom_nodes.lock` (all generated by `sources sync`).

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

To **convert** an arbitrary JSON workflow into an editable Python scratchpad you can hack on:
```bash
python -m vibecomfy.cli port convert <workflow_id_or_path> --out out/scratchpads/<name>.py --json
```
To fork an existing ready template into `recipes/` for hand-editing:
```bash
python -m vibecomfy.cli copy-to-recipe <id> --out recipes/<name>.py
```

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
python -m vibecomfy.cli fetch <wf>                      # fetch this workflow's declared assets
python -m vibecomfy.cli models stage --select-phase core
```

### 4. Validate

Cheap; run it before queuing.

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

```python
from vibecomfy import run_embedded_sync
result = run_embedded_sync(wf)            # blocking
# or async: from vibecomfy import run_embedded; await run_embedded(wf)
```

**Remote server:**
```bash
python -m vibecomfy.cli run <wf> --runtime server --server-url http://host:8188
```

**RunPod (ephemeral GPU pod).** This is a separate harness — it provisions a pod, uploads the repo, runs validation, tears the pod down. See the `runpod-lifecycle` skill for pod management; the VibeComfy entry points are:
```bash
python scripts/runpod_validate.py                       # cheap smoke (~$0.05–$1)
pytest --runpod -m runpod tests/smoke/test_layer2_runpod_ops.py
pytest --runpod-full -m runpod_full tests/smoke/test_layer2_runpod_matrix.py
python -m vibecomfy.cli runpod list|status|terminate|gpu-types|corpus-matrix
```

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

- `out/scratchpads/<name>.py` — generated by `convert`
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
| "Inspect why something doesn't run" | `inspect`, `doctor`, `analyze info/trace/path/values`, then `validate` |

## Adding a new workflow

The full operating path lives in **`docs/adding_templates_models.md`**. Read it before adding a new family. The short version:

1. **Pick a stable id** in lower snake case encoding model + capability: `qwen3_tts_voice_clone`, `wanvideo_wrapper_21_14b_t2v`. The id becomes the manifest id, file name, RunPod matrix row, artifact path, and CLI handle.
2. **Drop the source JSON** under `workflow_corpus/official/<media>/<id>.json`, `workflow_corpus/custom_nodes/<pack>/<source>/<id>.json`, or `workflow_corpus/community/<source>/<id>.json`. Keep it close to upstream.
3. **Declare custom nodes** in `vibecomfy/node_packs.py` (a `CustomNodePack(name, repo, classes, pip_packages)` entry) and pin in `custom_nodes.lock`.
4. **Declare models**: workflow-embedded URLs go in workflow metadata; node-pack-specific layouts go in `vibecomfy/registry/models.yaml`.
5. **Add a manifest row** in `workflow_corpus/manifests/coverage.json` with `id`, `path`, `media`, `task`, `coverage_tier`, `ready_template: true`.
6. **Run port preflight**: `python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json`. Resolve hard errors (helper nodes, missing packs, model asset issues, widget alias drift) before hand-editing or RunPod.
7. **Convert to a ready template** with `python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --ready-id <media>/<id> --out ready_templates/<media>/<id>.py --json`, or hand-author it under `ready_templates/<media>/<id>.py` for full control (see `ready_templates/image/z_image.py` for the canonical hand-authored shape). To fork a generated template into `recipes/` for hand-editing, use `python -m vibecomfy.cli copy-to-recipe <id> --out recipes/<name>.py`.
8. **Validate locally**: `vibecomfy validate ready_templates/<media>/<id>.py`, then targeted tests `pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli.py`.
9. **Validate on RunPod** with a focused scope: `VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py`. Don't run the full matrix while iterating.
10. **Document failures** in `docs/hiddenswitch_incompatibilities.md`, `docs/structural_issues.md`, or a family coverage doc — never leave fixes only in chat history or pod logs.

For a one-off composition (combining existing workflows), prefer a **recipe** under `recipes/` — that's flow 5 and doesn't need a manifest entry.

## Reference docs (in-repo)

- `docs/authoring.md` — blocks, patches, handles, opaque subgraphs, recipes, escape hatches
- `docs/vibeworkflow.md` — IR contract
- `docs/python_composition_dsl_plan.md` — Layer 2 architecture
- `docs/custom_nodes.md` — node packs, install/lock/restore
- `docs/runpod.md`, `docs/runpod_smoke.md` — RunPod lifecycle and smoke harness
- `docs/runtime_lifecycle.md`, `docs/runtime_surface.md` — embedded vs server runtime
- `docs/errors_and_doctor.md` — what `doctor` flags and how to fix it
- `CLAUDE.md` — canonical long-form agent constraints and rules

When in doubt, the chain you're allowed to descend is always:

```
op → Artifact → preview_workflow → VibeWorkflow → compile("api") → run
```

Stay in Python; only drop to API JSON when handing the graph to ComfyUI.
