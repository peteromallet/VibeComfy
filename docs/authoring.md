# Authoring

> See [docs/python_composition_dsl_plan.md](python_composition_dsl_plan.md) for the broader composition-layer architecture this doc fits into.

`VibeWorkflow` is the only editable IR. Blocks and patches mutate that object; API JSON is an escape hatch produced by `wf.compile("api")`, not an authoring surface.

## Port Before Manual Editing

When starting from a ComfyUI JSON export, indexed workflow, or failing ready template, run the porting workbench before hand-editing graph code or launching RunPod:

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

`port check` is the cheap preflight for helper/UI nodes, missing custom-node packs, missing required inputs, widget alias drift, and model asset problems. `port convert` turns the source into Python scratchpad form by default; add `--ready-id <kind>/<name>` only when you are intentionally creating a ready-template candidate. `port convert` uses atomic writes (temp file → validate/parity-check → `Path.replace()`), refuses to overwrite `# vibecomfy: manual` templates, and supports `--dry-run` and `--diff` modes. `port inventory` reports readability issues and source-provenance across all checked-in templates.

See [template_porting_workbench.md](template_porting_workbench.md) for the full workflow and when to use `doctor`, `validate`, `nodes install-plan`, `fetch`, and `--head-check-models`.

The canonical promotion path is raw workflow source -> `port check` -> optional scratchpad -> `port convert --ready-id` or hand-authored Python ready template -> `tools.refresh_template_index` -> `validate`/`doctor`/strict-ready checks. Raw JSON and compiled API dictionaries are source/runtime material, not the reusable authoring surface.

## Emitting a UI view

`port export --to ui` produces a litegraph JSON envelope that the ComfyUI editor can load. It uses the M4 layout engine to compute positions so the graph is readable without manual arrangement. Run it against any workflow (source JSON, scratchpad, or ready template):

```bash
python -m vibecomfy.cli port export my_workflow.json --to ui --out out/my_workflow.ui.json
```

**Fresh layout (no prior store).** When no prior UI JSON or layout sidecar exists, `port export --to ui` produces a clean fresh layout via the M4 engine. Every node gets an engine-computed position; the change report marks `no prior layout found — fresh layout applied`.

**When to commit the emitted `.json`.** Authors of code-first templates (ready templates, scratchpads) typically should **not** commit the emitted `.json`. The `.json` is regenerated on demand from the Python source and the layout sidecar (`.layout.json`), which IS committed. The sidecar records the preserved positions so subsequent exports are stable.

**When to version a layout.** When you DO want to share or version a specific layout — for example, to freeze the editor arrangement for sharing with a ComfyUI user — commit the emitted `.json`. The preserve-by-default loop (`--from` or sidecar auto-discovery) then keeps the committed positions stable across subsequent `port export` runs.

**Dry-run preview.** Pass `--dry-run` to preview the recovery report, change summary, and output path without writing any files:

```bash
python -m vibecomfy.cli port export my_workflow.json --to ui --dry-run
```

## v2.6 Ready Template Surface

New ready templates declare data first and build the graph second:

- `MODELS: dict[str, ModelAsset]` lists every authored model file, including URL, Comfy subdir, and when available `sha256`, `hf_revision`, and `size_bytes`.
- `PUBLIC_INPUTS: dict[str, InputSpec]` is the public contract. Each input points at a node id and field and can carry aliases, type, required state, default, and media semantics.
- `READY_METADATA = ReadyMetadata.build(...)` is the reproducibility identity: capability, public contract, requirements, model assets, custom-node pack provenance, `vibecomfy_version`, `comfy_core`, optional hardware, and optional `python_env`. Template id, source workflow, output prefix, and other static fields are derived when they match repository conventions.
- `with new_workflow(READY_METADATA, source_path=__file__) as wf:` binds the active workflow through a `ContextVar`, allowing generated wrappers to omit the first `wf` argument.
- `return wf.finalize(PUBLIC_INPUTS, output_node="...")` applies metadata, registers inputs, binds the output, and checks that the graph still matches the public contract.

```python
from vibecomfy.nodes.core import CLIPTextEncode, SaveImage
from vibecomfy.templates import InputSpec, ReadyMetadata, new_workflow

PUBLIC_INPUTS = {
    "prompt": InputSpec(node="6", field="text", default="a glass teapot", type="STRING", required=True),
}
MODELS = {}
READY_METADATA = ReadyMetadata.build(
    capability="text_to_image",
    inputs=PUBLIC_INPUTS,
    models=MODELS,
)

def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        positive = CLIPTextEncode(_id="6", text=PUBLIC_INPUTS["prompt"], clip=...)
        SaveImage(_id="9", images=positive, filename_prefix="image/example")
        return wf.finalize(PUBLIC_INPUTS, output_node="9", output_type="SaveImage")
```

The explicit workflow form remains available for compatibility outside a
workflow context:

```python
wf = new_workflow(READY_METADATA, source_path=__file__)
positive = CLIPTextEncode(wf, _id="6", text="hello", clip=...)
```

Deprecated for generated or newly authored templates:

- `bind_input(...)`
- `bind_output(...)`
- `apply_ready_template_policy(...)`
- direct `wf.register_input(...)` calls inside `build()`

Those APIs remain for old templates and tests, but they emit `PendingDeprecationWarning`. Use `python -m tools.convert_ready_templates --all --write --include-manual` for the repository batch-migration path, `python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<id> --out ready_templates/<kind>/<id>.py --json` for individual sources, or `python -m vibecomfy.cli copy-to-recipe <id> --out recipes/<name>.py` to fork a generated template into `recipes/` for hand-editing. `tools.narrate_template` has been removed (M0 cleanup); use `vibecomfy.porting.emitter` instead.

## Blocks

A block is a small function that mutates a workflow and returns `Handles`. Most blocks use `workflow.add_node()` plus `workflow.connect()`, but blocks may use any `VibeWorkflow` method — including `disconnect()` and `replace_edge()` for blocks that splice into existing topology. The contract is "mutate and return handles," not "add_node/connect only."

```python
from vibecomfy.blocks import Handle, Handles

def my_block(wf, *, prompt: str) -> Handles:
    node = wf.add_node("CLIPTextEncode")
    node.widgets["widget_0"] = prompt
    node.metadata["block"] = "my_package.my_block"
    return Handles({"text": Handle(node_id=node.id, output_slot=0, name="text")})
```

Built-in blocks also record `metadata.block`, `metadata.block_id`, and `metadata.widget_kwargs` on produced nodes. This keeps generated graphs inspectable without making node ids part of the public contract.

Use blocks when the call changes the handles available to the caller: a loader creates `model`, `clip`, and `vae`; a sampler creates `samples`; a decode block creates `images`.

## Typed Handles in P1

P1 ships typed handle metadata, not mypy-grade static validation. New authoring code should prefer `wf.node(...).out(<slot_or_name>)`, which returns a `Handle` carrying the source node id, output slot, optional output type, and optional name. Blocks should return `Handles({"image": Handle(node_id=node.id, output_slot=0, name="image")})` instead of raw string references.

Named output strings such as `.out("image")` are supported when the node has `metadata["output_names"]` and the requested name maps unambiguously to a slot. Use integer slots only when output names are genuinely unavailable or ambiguous. See [readable_ready_template_cleanup_plan.md](readable_ready_template_cleanup_plan.md) for the plan to make named handles the generated-template default.

## Patches

A patch is a `Patch(name, applies_to, apply, rationale)`.

```python
from vibecomfy.patches import Patch

def applies_to(wf):
    return any(node.class_type == "SaveImage" for node in wf.nodes.values())

def apply(wf):
    for node in wf.nodes.values():
        if node.class_type == "SaveImage":
            node.widgets["widget_0"] = "demo"
    return wf.finalize_metadata()

patch = Patch("demo_prefix", applies_to, apply, lambda wf: "sets a demo prefix")
```

Use patches when the call decorates or adjusts existing handles: seed, resolution, save prefix, loader policy, or runtime policy. A patch should return the same workflow object.

Patches may use any `VibeWorkflow` method, including `disconnect()` and `replace_edge()`. This is the difference between *mutational* decoration (set a widget, swap a class — what `seed`, `resolution`, `gguf_unet` do) and *topological* decoration (splice a node into an existing edge — what ControlNet, IP-Adapter, and similar conditioning patches require). Both are patches.

Rule of thumb: changes-handles -> new template; decorates-handles -> patch.

The LTX low-VRAM policy is the main counter-example. It decorates a template, but it changes enough loader classes and smoke dimensions that it would be a separate template if users needed both forms equally. Today it is a patch because the low-VRAM form is the supported local default.

## Edge Primitives

`VibeWorkflow.disconnect(to_ref)` removes the edge feeding `to_ref` (e.g. `"5.positive"`). `VibeWorkflow.replace_edge(to_ref, new_from_ref)` does the same and then connects a new source.

Topological patches use these to splice a node into an existing path. `vibecomfy.patches.controlnet` is the canonical example: it finds the edge feeding `KSampler.positive`, redirects the original source through a `ControlNetApplyAdvanced` node, and reconnects the apply node's output to the sampler.

```python
def apply(wf, *, control_net_name="depth.safetensors", strength=1.0):
    sampler_id = next(nid for nid, n in wf.nodes.items() if n.class_type == "KSampler")
    pos_edge = next(e for e in wf.edges if e.to_node == sampler_id and e.to_input == "positive")
    loader = wf.add_node("ControlNetLoader", widget_0=control_net_name)
    apply_node = wf.add_node("ControlNetApplyAdvanced", widget_0=strength)
    wf.connect(f"{pos_edge.from_node}.{pos_edge.from_output}", f"{apply_node.id}.positive")
    wf.connect(f"{loader.id}.0", f"{apply_node.id}.control_net")
    wf.replace_edge(f"{sampler_id}.positive", f"{apply_node.id}.0")
    return wf
```

Topology mutation is allowed by the patch contract; the `add_node/connect only` rule from earlier drafts has been retired.

## Metadata

Call `wf.finalize_metadata()` after assembling a workflow outside an individual block. It rebuilds discoverable inputs, outputs, and requirements from the current nodes.

Do this after applying patches that change prompts, seeds, model names, save nodes, or class types. The method returns `wf`, so builders can end with:

```python
return wf.finalize_metadata()
```

## Opaque Subgraphs

Some ComfyUI templates contain UUID class-type subgraph nodes. `vibecomfy.blocks.subgraph.opaque()` preserves those nodes without unpacking them.

```python
from vibecomfy.blocks import subgraph

handles = subgraph.opaque(
    wf,
    class_type="9b9009e4-2d3d-445f-9be5-6063f465757e",
    widgets=["prompt", 1024, 1024],
    outputs=("image",),
)
```

The block sets `metadata.subgraph_class_type` to the UUID class type. Wire its returned handles like any other block output.

## Ready Templates and Recipes

Ready templates should be hand-curated Python builders. Do not use `scripts/materialize_ready_templates.py` for new work; the materializer was useful for bootstrapping, but it hid authoring decisions inside copied API dictionaries.

`MarkdownNote` nodes are dropped during refactor because they are ComfyUI UI annotations with no execution effect. Snapshot tests filter them at capture time so runnable graph parity is compared without those notes.

Ready templates change the handles a workflow exposes. Recipes decorate handles by composing ready templates and patches for worked examples. This is the Layer 2 form of the Layer 1 rule: changes-handles -> new template; decorates-handles -> patch.

Required and app-active ready templates must not rely on hidden widgets, unnamed public outputs, missing public inputs, hidden model filenames, or opaque UUID subgraphs. Register public input targets with stable names, bind semantic outputs with artifact metadata where known, and resolve schema-backed `widget_N` aliases before promotion. Remaining non-compliance belongs in the strict-ready exception inventory with an owner, ticket, final category, and removal condition.

## Artifacts and Ops

The verb-native API is lazy. `image.t2i`, `video.t2v`, and `video.i2v` return typed `Artifact` objects (`Image` or `Video`) without running ComfyUI. `Artifact.run()` triggers execution; `Artifact.preview_workflow()` returns the editable `VibeWorkflow`.

```python
from vibecomfy import image

artifact = image.t2i("a small glass teapot")
wf = artifact.preview_workflow()
api = wf.compile("api")
result = artifact.run(runtime="embedded")
```

The public escape-hatch chain is:

```text
op() -> Artifact -> preview_workflow() -> VibeWorkflow -> compile() -> API JSON -> run()
```

`audio.t2a` raises `NotImplementedError("no audio template registered")` until an audio ready template is routed. `image.edit` and `edit.qwen` also raise `NotImplementedError` in v1. `image.t2i(model="flux2_klein_9b_gguf")` and `image.edit(model in {"qwen", "flux2_klein_4b"})` are not yet exposed via the verb-native API; use `load_workflow_any("image/flux2_klein_9b_gguf_t2i")` or `load_workflow_any("edit/qwen_image_edit")` and edit the `VibeWorkflow` directly until MP-6 ships schema-backed UUID-subgraph input validation.

## Router

Ops call `router.pick(verb_kind, verb_name, **inputs)` implicitly. Callers can use it directly to inspect the route before loading or mutating a workflow.

```python
from vibecomfy import router

result = router.pick("video", "i2v", model="ltx")
```

`RouterResult` contains `template_id`, `explicit_patches`, and `applicable_patches`. `explicit_patches` are part of the route. `applicable_patches` is the remaining gap reported by `find_applicable(workflow)` after loading the selected template; for as-shipped LTX templates it should be `[]` because the low-VRAM and resolution policy is already applied inline.

## Plugin Discovery

`ensure_plugins_loaded()` discovers plugins lazily from three sources:

- project-local `./vibecomfy_extras/{blocks,patches,ops,recipes,ready_templates}/*.py`
- user-global `~/.vibecomfy/{blocks,patches,ops,recipes,ready_templates}/*.py`
- pip entry points in the `vibecomfy.plugins` group

Entry-point callbacks receive `PluginAPI`. The API exposes `register_block`, `register_patch`, `register_op`, `register_route`, and `register_ready_root(path)`. Built-in ready-template ids win on collisions; plugin collisions warn instead of raising.

Static ready-template discovery is separate from plugin discovery. The default `workflows list --ready --json` surface is backed by checked-in `template_index.json` and does not load plugin, cwd-extra, or user-global ready roots when that index exists. Pass `--include-dynamic` only when dynamic plugin/user rows are needed; those rows are marked `source_scope: "dynamic"` and `indexed: false`, and they are not protected by repo strict-ready gates.

## Metadata Contracts

`wf.register_input(name, node_id, field, value=None)` records a public input target when `finalize_metadata()` cannot infer it from the node class alone. `OUTPUT_NODE_NAMES` includes image, video, and audio save nodes (`SaveVideo`, `SaveAudio`, `SaveAudioMP3`), and `finalize_metadata()` sorts outputs deterministically by numeric node id and then string node id.

Prompt-bearing authored templates must register or infer `prompt` consistently:

| Template | Prompt field |
| --- | --- |
| `image/z_image` | builder calls `register_input` on the UUID subgraph prompt widget |
| `image/flux2_klein_4b_t2i` | builder calls `register_input` on `PrimitiveStringMultiline` |
| `video/wan_t2v` | inferred from `CLIPTextEncode` |
| `video/wan_i2v` | inferred from `CLIPTextEncode` |
| `video/ltx2_3_t2v` | builder preserves prompt registration after LTX patches |
| `video/ltx2_3_i2v` | builder preserves prompt registration after LTX patches |

The UUID-opaque `flux2_klein_9b_gguf_t2i`, `qwen_image_edit`, and `flux2_klein_4b_image_edit_distilled` templates intentionally do not register prompt or instruction fields in v1.

## JSON Output

The commands `workflows list`, `nodes list`, `inspect`, `port check`, `port convert`, `doctor`, `sources sync`, `analyze info`, and `analyze diff` support `--json`. Text output remains the default compatibility surface. `inspect --json` includes `applicable_patches`; `doctor --json` includes `suggested_patches`; `port check --json` emits the full port report for preflight automation. For `analyze info` and `analyze diff`, `--json` is an alias for `--format json`, and an explicit `--format` wins.

## Escape Hatches

Every layer stays public and inspectable. Use `load_workflow_any()` for ready ids, scratchpads, JSON files, and indexed workflow references:

```python
from vibecomfy import load_workflow_any
from vibecomfy.runtime import run_embedded_sync

wf = load_workflow_any("image/z_image")          # the editable IR
api = wf.compile("api")                          # the dict ComfyUI accepts
result = run_embedded_sync(wf)                   # actually run it
path = result.outputs[0]                         # the saved file
```

Pipelines are ordinary Python. Use blocks for new graph structure, patches for policy, and `compile("api")` only when handing the graph to ComfyUI.

Agent-facing constraints live in [../AGENTS.md](../AGENTS.md).
