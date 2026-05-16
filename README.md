# VibeComfy

**VibeComfy is an agentic interface for you and your agent to build on top of ComfyUI.** You load a workflow (a ready template, an indexed JSON workflow, or one you author from scratch) into a single editable IR — `VibeWorkflow` — tweak it, and then build on top of it, combining it with other workflows and plain Python into an agentic loop. The goal is to make it as easy as possible to build complex creative loops on top of Comfy that run entirely locally.

![VibeComfy explainer](docs/assets/explainer.png)

## Give this to your agent to get started

Paste this into your coding agent (Claude Code, Cursor, Codex, …):

```
Please set up VibeComfy for me:

1. Clone https://github.com/peteromallet/VibeComfy into the current directory.
2. Install it with `uv sync` (or `pip install -e .`). This pulls in ComfyUI
   as a normal Python dependency via hiddenswitch/pip-and-uv-installable-ComfyUI.
3. Run `python -m vibecomfy.cli sources sync` to build the indexes.
4. Read .claude/skills/vibecomfy/SKILL.md to learn the authoring surface.
5. Ask me what I'd like to create (image, video, or audio), then run a small
   test generation end-to-end to confirm everything works. The
   `image/z_image` ready template is a good cheap default for a first run.
```

That's the whole install. The bundled skill at [`.claude/skills/vibecomfy/SKILL.md`](.claude/skills/vibecomfy/SKILL.md) teaches the agent the full surface — discovery, loading, editing, patches, blocks, recipes, and the embedded / server / RunPod runtimes.

## Porting ComfyUI workflows

Before manually editing a raw Comfy workflow, converting it into a template, or spending RunPod time, run the porting preflight:

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port check <workflow> --strict-ready-template --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port inventory --ready --json
```

`port check` reports helper/UI nodes, unresolved custom-node packs, missing required inputs, positional widget aliases, output-contract gaps, and model asset issues while staying offline by default. Use `--strict-ready-template` before promoting or RunPod-testing production/app-parity templates; it turns schema-backed unresolved widgets, missing or broken public inputs, missing or unnamed outputs, hidden model filenames, and opaque UUID subgraphs into hard errors. Use `--head-check-models` only when you want URL HEAD checks without downloading model bodies.

`port convert` uses atomic writes (temp file → validate/parity-check → `Path.replace()`), refuses to overwrite `# vibecomfy: manual` templates, and supports `--dry-run` (emit evidence without writing) and `--diff` (unified diff + JSON metadata). Parity evidence includes widget snapshots, output counts, class type counts, and topology snapshots.

`port inventory` scans only checked-in `ready_templates/**/*.py` and reports readability issues (positional `.out(<int>)`, `widget_N` fields, UUID class types, local `_node` copies, missing output contracts), marker classification, and source-provenance flags. The JSON output is deterministic and versioned.

See [docs/template_porting_workbench.md](docs/template_porting_workbench.md) for the command map and live validation loop.

Ready-template discovery is repo-indexed by default. `python -m vibecomfy.cli workflows list --ready --json` reads the checked-in `template_index.json` when it exists and does not import plugin, cwd-extra, or user-global template code. Use `--include-dynamic` only when you explicitly want plugin/user rows; those rows are marked `source_scope: "dynamic"` and `indexed: false` and are excluded from strict-ready CI gates.

When replacing or hand-authoring a node, inspect the node's real accepted inputs first:

```bash
python -m vibecomfy.cli nodes spec ImageResizeKJv2
```

`nodes spec` reads the local index when available and falls back to installed custom-node source with `INPUT_TYPES`, so it is useful before swapping a node class or translating a JSON widget payload into explicit Python keyword arguments.

Some custom nodes download annotator or preprocessor weights into their own package folders instead of Comfy's `models/` tree. Declare those as `model_assets` with `target_path` so `vibecomfy run` stages them before execution:

```python
{"name": "yolox_l.onnx", "url": "...", "subdir": "controlnet_aux", "target_path": "custom_nodes/comfyui_controlnet_aux/ckpts/yzd-v/DWPose/yolox_l.onnx"}
```

Loader-specific model folders matter. For example, LTX audio VAE files used by `LTXVAudioVAELoader` must be staged under `checkpoints`, not `vae`; `validate` rejects the known-bad `VAELoaderKJ` plus LTX audio VAE pairing before runtime.

For reusable workflows, the checked-in surface is Python, not raw JSON. Keep upstream/source workflows in `workflow_corpus/`, convert or author the reusable version in `ready_templates/<kind>/<id>.py`, record it in `workflow_corpus/manifests/coverage.json`, and refresh the static discovery index:

```bash
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out ready_templates/<kind>/<id>.py --ready-id <kind>/<id> --json
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
python -m vibecomfy.cli validate ready_templates/<kind>/<id>.py
python -m vibecomfy.cli port check ready_templates/<kind>/<id>.py --strict-ready-template --json
python -m vibecomfy.cli doctor ready_templates/<kind>/<id>.py --json
```

The manifest/index tests catch missing ready-template rows, stale `template_index.json`, and manifest entries that point at Python templates that do not exist.

Required or app-active ready templates must stay on the clean path: public inputs are named and target real built nodes/fields, public outputs are semantically named, hidden model filenames are exposed through public inputs or model metadata, schema-backed `widget_N` aliases are resolved, and opaque UUID subgraphs are either replaced with transparent graph code or covered by an explicit strict-ready exception. Document any remaining non-compliant template as `reference`, `supplemental`, `blocked`, or `scratchpad-only` with an owner and follow-up ticket.

`doctor` is the local readiness pass for a built workflow. It reports missing
model assets, node-pack drift, suggested patches, and runtime warnings that
schema validation cannot infer. For video workflows, it also flags generated
frame-count bindings that are paired with uncapped video loaders; either bind
`frame_load_cap` to the same effective frame count or have the caller
materialize a capped source clip before runtime.

### Semantic Graph Lens and Contract Validation

For app-active workflows, validate intent before GPU time:

```bash
# Graph diagnostics: nodes, edges, inputs, outputs, upstream/downstream
python -m vibecomfy.cli workflows lens <template-or-path> [--json]

# Semantic contract validation for LTX first/last two-stage
python -m vibecomfy.cli workflows contract-validate <template-or-path> --type ltx-first-last-two-stage [--json]
```

From Python:

```python
from vibecomfy.lens import WorkflowLens
from vibecomfy.contracts import LTXFirstLastTwoStageContract

lens = WorkflowLens(workflow)
print(lens.diagnostics())
report = LTXFirstLastTwoStageContract().validate(workflow)
print(report.summary())
```

> **Compiled Comfy API JSON is runtime materialization only, not the workflow source of truth.** App intent should be validated through `VibeWorkflow`, the lens, and contracts. Tests may inspect compiled API for runtime smoke, but semantic assertions use the lens and contract layers.

## Thanks

VibeComfy is a thin Python authoring layer. The real work belongs to:

- **[`pip-and-uv-installable-ComfyUI`](https://github.com/hiddenswitch/pip-and-uv-installable-ComfyUI)** by [Dr. Pangloss / hiddenswitch](https://github.com/hiddenswitch) — the fork that makes ComfyUI installable as a normal Python package, which is what lets VibeComfy embed Comfy at all.
- **[ComfyUI](https://github.com/comfyanonymous/ComfyUI)** by **Comfy Anonymous** and the Comfy team / community, plus the custom-node pack authors VibeComfy indexes (KJNodes, VideoHelperSuite, WanVideoWrapper, LTXVideo, rgthree, was-node-suite, and many more).
- **The workflow builders** whose graphs the ready templates are based on — [Kijai](https://github.com/kijai), the [Comfy team's official examples](https://github.com/comfyanonymous/ComfyUI_examples), and many others across the community whose published workflows we adapted into the `ready_templates/` set.
- **The open-source model authors** whose weights every workflow actually runs — Black Forest Labs (Flux), Tencent (Hunyuan), Alibaba (Wan, Qwen), Lightricks (LTX-Video), Stability AI (SD/SDXL), and the long tail of fine-tuners and LoRA authors releasing openly on Hugging Face and Civitai.

## Code quality

![Code quality scorecard](docs/assets/scorecard.png)

## License

MIT — see [LICENSE](LICENSE).

## Testing

- [Internal testing contract](docs/testing.md)
- [Testing your VibeComfy recipes](docs/testing-user-code.md) — assertions, dry-run runtime, snapshot CLI, pytest plugin
