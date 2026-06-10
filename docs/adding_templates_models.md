# Adding Templates And Models

This is the operating path for adding, fixing, forking, or promoting a model family, workflow template, or custom-node workflow in VibeComfy. The goal is that a contributed workflow becomes a reusable Python ready template when appropriate, declares its node/model/output requirements, and can be validated on RunPod without an agent hand-editing the machine.

## Lifecycle Entry Points

The same gates apply from four starting points:

- **Raw Comfy JSON**: save the upstream source under `workflow_corpus/...`, run `port check`, then convert or hand-author.
- **Existing ready template**: inspect current metadata, requirements, outputs, and patch points before editing; rerun strict readiness before RunPod.
- **Fork of a ready template**: use a recipe or patch for run-specific decoration; create a new ready template only when graph shape, model family, required inputs, output semantics, custom nodes, or app capability changes.
- **From-scratch Python workflow**: author with `VibeWorkflow`, blocks, or patches, then promote only after the same model/node/output/index/test/live-evidence gates.

Programmatic gates catch structure, schema, node packs, model assets, output contracts, index freshness, and live execution. Agent judgment is still required for source quality, model provenance, custom-node legitimacy, smoke-size adaptations, app/Wan2GP parity, and documenting intentional differences.

Embedded `vibecomfy run` reconciles model assets by default. It checks the final built workflow, including scratchpad or fork patches, and resolves model-picker fields against authored `model_assets` plus `vibecomfy/registry/models.yaml` before queueing. If a referenced model cannot be resolved, fix the registry or authored metadata before RunPod instead of waiting for Comfy to reject the prompt.

## Target Shape

Every runnable template should move through this pipeline:

```text
raw Comfy workflow JSON
  -> workflow_corpus/... source file
  -> port check report
  -> port-converted Python scratchpad
  -> workflow_corpus/manifests/coverage.json entry
  -> port-converted or hand-authored ready_templates/<media>/<id>.py
  -> tools.refresh_template_index
  -> local validate
  -> focused RunPod matrix scope
  -> checked-in artifact notes/docs if it exposes a new compatibility issue
```

Raw JSON remains import material. `ready_templates/` is the reusable VibeComfy surface. A ready template is only "ready" after it validates locally and has a plausible runtime path for its node packs and models.

Default ready-template discovery is repo-only and index-backed. `workflows list --ready --json` reads checked-in `template_index.json` when present and does not import plugin, cwd-extra, or user-global ready roots. Use `--include-dynamic` only for explicit plugin/user discovery; dynamic rows are marked `source_scope: "dynamic"` and `indexed: false` and are not part of strict-ready CI gates.

Run the porting workbench before manual edits and before RunPod validation:

```bash
python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out out/scratchpads/<id>.py --json
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out ready_templates/<kind>/<id>.py --ready-id <kind>/<id> --json
python -m vibecomfy.cli port check ready_templates/<media>/<id>.py --strict-ready-template --json
python -m vibecomfy.cli port inventory --ready --json
```

When replacing a node or hand-authoring a Python template, inspect the target node schema before writing kwargs:

```bash
python -m vibecomfy.cli nodes spec <ClassType>
python -m vibecomfy.cli validate ready_templates/<media>/<id>.py
```

`nodes spec` uses the generated node index when present and falls back to installed custom-node source that exposes `INPUT_TYPES`. `validate` checks the compiled API graph, not just the pre-compile Python IR, so missing required inputs and unexpected inputs are reported against the payload Comfy will actually receive when schema data is available.

Validation also carries small runtime-compatibility gates for issues schema alone cannot express. One example is LTX audio VAE loading: use `LTXVAudioVAELoader` with the file staged under `checkpoints`; the known-bad `VAELoaderKJ` plus `LTX*_audio_vae*.safetensors` pairing is rejected before RunPod because KJNodes can misclassify that file shape as a normal VAE.

For LTX 2.3 templates that use `LTX2AttentionTunerPatch`, keep `triton_kernels=False` unless that acceleration path has been separately validated on the target RunPod image. The default RTX 4090 validation profile prioritizes portable execution over optional Triton speedups.

Use `--head-check-models` only when you intentionally want model URL HEAD checks. Normal `port check`, `doctor`, `validate`, `fetch`, and `run` paths stay offline by default.

## Checklist

1. Pick a stable template id.
2. Add the raw source workflow under `workflow_corpus/`.
3. Run `port check` and inspect the report before editing.
4. Add or update custom-node catalog entries.
5. Add model registry entries or workflow metadata for model staging.
6. Convert to a Python scratchpad, then decide whether a ready-template candidate is warranted.
7. Add a manifest row.
8. Create the ready template with `port convert --ready-id`, or hand-author it when the reusable template needs clearer runtime behavior.
9. Refresh the ready-template index.
10. Run local validation, strict-ready gates, and tests.
11. Add or update a focused RunPod scope.
12. Run the focused RunPod matrix.
13. Document any new incompatibility or structural issue.

## v2.4 Reproducibility Data

Ready templates must be reproducible offline before GPU validation:

- `MODELS` uses `ModelAsset(filename, url, subdir, target_path=None, sha256=None, hf_revision=None, size_bytes=None)`. Run `python -m tools.fetch_hf_metadata` to populate `out/cache/hf_metadata.json`; `vibecomfy.porting.emitter` reads that cache when rendering model blocks. Gated/private repositories should keep `hf_revision="gated"` and an inline `# gated: <repo_id>` note rather than silently leaving fields empty.
- `READY_METADATA.comfy_core` comes from `python -m tools.refresh_comfy_metadata`, which writes `vibecomfy/comfy_metadata.json`. The narrator copies version, commit, and tested timestamp into regenerated templates.
- `READY_METADATA.requirements["custom_node_refs"]` mirrors `custom_nodes.lock`. Rich lock entries are TOML tables with `slug`, `source`, `url`, `commit`, `version`, `schema_hash`, `class_set`, and `last_seen_at`.
- `hardware` is required where there is known evidence, especially pilots, LTX, and Qwen TTS families. Use `vram_gb_min`, `vram_gb_recommended`, `requires_flash_attention`, and `tested_on`.
- `python_env` is only required when a family has known constraints, such as torch or custom-node package minimums.

The local gates for template changes are:

```bash
python -m tools.check_strict_ready_templates
python -m tools.validate_templates_against_packs
python -m tools.validate_template_traceability --strict
```

## 1. Template Id

Use lower snake case and encode the model family plus capability:

```text
qwen3_tts_voice_clone
flux2_klein_4b_image_edit_base
wanvideo_wrapper_21_14b_t2v
ltx2_3_lightricks_iclora_motion_track
```

The id should be stable because it becomes the manifest id, ready template filename, RunPod matrix row, artifact path, and CLI handle.

## 2. Source Workflow

Put imported source JSON where its ownership is clear:

```text
workflow_corpus/official/<media>/<id>.json
workflow_corpus/custom_nodes/<node_pack>/<source>/<id>.json
workflow_corpus/community/<source>/<id>.json
```

Prefer official Comfy templates when they exist. Use custom-node examples when the capability only exists there. Keep the raw JSON as close to upstream as possible; runtime-smoke edits belong in the ready template, not in the source file, unless the source is a small hand-authored API smoke fixture.

## 3. Custom Nodes

If the workflow uses custom classes, add them to `vibecomfy/node_packs.py`:

```python
CustomNodePack(
    name="ComfyUI-QwenTTS",
    repo="https://github.com/1038lab/ComfyUI-QwenTTS.git",
    classes=frozenset({"AILab_Qwen3TTSVoiceClone"}),
    pip_packages=("soundfile", "librosa", "accelerate"),
)
```

Then update `custom_nodes.lock` when the pack should be pinned. Pinning by commit is the default for runtime matrix work. Use floating latest only for exploration, not for a ready template.

Run:

```bash
uv run python -m vibecomfy.cli port check workflow_corpus/custom_nodes/.../<id>.json --json
uv run python -m vibecomfy.cli nodes install-plan workflow_corpus/custom_nodes/.../<id>.json
uv run python -m vibecomfy.cli doctor workflow_corpus/custom_nodes/.../<id>.json
```

## 4. Models

There are two model paths:

1. Workflow-embedded model URLs: keep them in workflow metadata or the ready
   template `READY_REQUIREMENTS["models"]`.
2. Node-pack-specific model layouts: add them to `vibecomfy/registry/models.yaml` so staging can hardlink or symlink the same downloaded asset into every path expected by each node pack.

For one workflow-specific custom-node asset, use `target_path` in the ready template's `model_assets`. `subdir` remains a logical grouping, while `target_path` is the repo-relative destination under the VibeComfy checkout:

```python
{
    "name": "dw-ll_ucoco_384_bs5.torchscript.pt",
    "url": "https://huggingface.co/hr16/DWPose-TorchScript-BatchSize5/resolve/main/dw-ll_ucoco_384_bs5.torchscript.pt",
    "subdir": "controlnet_aux",
    "target_path": "custom_nodes/comfyui_controlnet_aux/ckpts/hr16/DWPose-TorchScript-BatchSize5/dw-ll_ucoco_384_bs5.torchscript.pt",
}
```

Use the registry when a model has aliases, multiple target directories, custom-node naming conventions, or a minimum-size sanity check. The matrix should not hide model staging inside one-off shell snippets long term.

## 5. Manifest Row

Add a row to `workflow_corpus/manifests/coverage.json`:

```json
{
  "id": "qwen3_tts_voice_clone",
  "path": "workflow_corpus/custom_nodes/qwen_tts/1038lab/qwen3_tts_voice_clone.json",
  "source": "1038lab/ComfyUI-QwenTTS distilled API smoke template",
  "model_family": "qwen3-tts",
  "media": "audio",
  "task": "text_to_speech_voice_clone",
  "coverage_tier": "supplemental",
  "ready_template": true,
  "approach": "reference-audio voice cloning with a bundled smoke fixture",
  "runtime_note": "Uses workflow_corpus/input/speech_smoke.wav as the reference clip."
}
```

`coverage_tier: required` means it runs in the default matrix. `supplemental` needs an explicit scope unless it belongs to an existing scoped family. Use `ready_template: true` when it should have checked-in Python.

## 6. Python Ready Template

Create `ready_templates/<media>/<id>.py` by converting source JSON or by
hand-authoring a `VibeWorkflow` builder.

Use conversion when the raw workflow is already close to executable:

```bash
uv run python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json \
  --ready-id <media>/<id> \
  --out ready_templates/<media>/<id>.py \
  --json
```

Hand-author when the reusable template needs clearer parameters, loops,
conditional patching, or model/runtime decisions that are awkward in raw JSON.
Either way, use the ready template to make smoke-time normalization explicit:

- reduce resolution, duration, frame count, steps, or batch size;
- replace gated/huge models with public smoke variants;
- normalize stale class names or widget fields;
- inject committed fixtures such as `speech_smoke.wav`;
- set deterministic seeds and output prefixes;
- add `runtime_variant`, `input_fixtures`, or `runtime_note` metadata.

Do not use the policy to paper over missing custom-node or model declarations. Those belong in `node_packs.py`, `custom_nodes.lock`, or `models.yaml`.

Refresh the static ready-template index after adding, renaming, or removing a
ready template:

```bash
uv run python -m tools.refresh_template_index
uv run python -m tools.refresh_template_index --check
```

## 7. Local Validation

First confirm the port report is clean enough to edit and convert:

```bash
uv run python -m vibecomfy.cli port check workflow_corpus/.../<id>.json --json
uv run python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json --out out/scratchpads/<id>.py --json
```

Run validation on the generated ready template:

```bash
uv run python -m vibecomfy.cli validate ready_templates/<media>/<id>.py
uv run python -m vibecomfy.cli port check ready_templates/<media>/<id>.py --strict-ready-template --json
```

`--strict-ready-template` is the promotion gate for production/app-parity templates. It fails schema-backed unresolved positional widgets, missing or broken public input targets, missing or unnamed public outputs, hidden model filenames, and opaque UUID component classes locally, while still reporting unavailable-schema community widgets as porting warnings until object_info or committed widget aliases exist.

Required and app-active templates cannot regress behind hidden widgets or opaque subgraphs. Either expose named public inputs/outputs and transparent graph structure, or record an exact strict-ready exception with owner, ticket, final category, expiration, and removal condition. Allowed final categories are `reference`, `supplemental`, `blocked`, and `scratchpad-only`.

Then run targeted tests:

```bash
uv run pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli.py
```

For a new scope, add a unit test in `tests/test_runpod_matrix.py` so the selected rows cannot silently disappear.

If the workflow is used by Reigh app parity, also update the worker-side
capability contract in `../reigh-worker/scripts/capability_contracts/` and run
that repo's `python -m scripts.capability_contracts.report validate`. VibeComfy
owns graph/template validity; the worker contract owns product route, variant,
artifact, app-inventory, and live-evidence claims.

Worker-side patches should target semantic fields exposed by the ready template
(`prompt`, `seed`, `width`, `height`, `control_video`, LoRA slots, etc.). Treat
new worker code that writes arbitrary `widget_N` fields as a migration smell:
either move the alias into VibeComfy widget schema/template code, expose a named
input, or document a temporary deferral in the worker capability contract with
the source node/class and removal condition.

## 8. RunPod Validation

Use focused scopes. Do not run the full matrix while iterating on one family:

```bash
uv run python -m vibecomfy.cli port check video/wanvideo_wrapper_22_wan_animate_preprocess_kijai --json
VIBECOMFY_MATRIX_SCOPE=qwen_tts uv run python scripts/runpod_corpus_matrix.py
VIBECOMFY_MATRIX_SCOPE=flux2_4b uv run python scripts/runpod_corpus_matrix.py
VIBECOMFY_MATRIX_SCOPE=wan_creation_types uv run python scripts/runpod_corpus_matrix.py
```

The matrix launches a fresh pod, uploads the checkout, installs VibeComfy and HiddenSwitch ComfyUI, syncs sources, installs selected custom nodes, stages models, executes baseline `comfyui run-workflow`, converts the workflow, runs the generated VibeComfy scratchpad, downloads artifacts, and terminates the launched pod in `finally`. It also writes an offline `port check --json` report and port-convert preview artifacts beside the existing logs so GPU failures can be compared with the cheap local preflight.

For Reigh app-active parity, prefer the prebuilt validation environment once it
exists. Reigh selects the exact cases/routes/templates; VibeComfy enriches that
selection with source, schema, and model-asset metadata; `runpod-lifecycle`
probes or reconciles the attached RunPod volume. Keep the package boundary:
Reigh must not import VibeComfy to build the target manifest, and
runpod-lifecycle must not guess assets from plain target JSON.

```bash
# In reigh-worker: selected targets only.
python -m scripts.live_test.main --variant fresh --backend vibecomfy \
  --case z_image_turbo \
  --emit-targets-json /tmp/reigh-targets.json

# In vibecomfy: source/schema/model asset enrichment.
python -m vibecomfy.cli workflows enrich-targets \
  --targets-json /tmp/reigh-targets.json \
  --output /tmp/reigh-targets.enriched.json \
  --models-root /workspace/reigh-livetest-prebuilt/models

# In runpod-lifecycle: portable 4090 prebuilt health check.
rl prebuilt check --data-center <DATA_CENTER_ID> \
  --attention-profile portable \
  --enriched-targets-json /tmp/reigh-targets.enriched.json
```

`rl prebuilt reconcile --dry-run --targets-json ...` should only print the
enrichment command. Fetch plans require `--enriched-targets-json` or an explicit
asset manifest so the selected asset name, category/path, paths checked, URL,
and expected location are all known before RunPod work starts.

Prebuilt is not a second source of workflow truth. The reusable workflow source
still lives in `ready_templates/<media>/<id>.py`; raw JSON belongs in
`workflow_corpus/` as source/corpus/import material only. A ready template is
not app-parity ready until source classification, schema validation, asset
resolution, a cheap prebuilt health check, a smoke run, and the relevant matrix
evidence are recorded.

That means the machine should not require hand setup for a checked-in matrix scope. If an agent has to SSH in and run ad hoc commands, convert that into code in one of these places:

- custom-node install: `vibecomfy/node_packs.py`, `custom_nodes.lock`, or `scripts/runpod_corpus_matrix.py`;
- model staging: `vibecomfy/registry/models.yaml` and `vibecomfy.registry.models_loader`;
- workflow patching: `scripts/runpod_matrix_remote.py`;
- ready-template conversion: `python -m vibecomfy.cli port convert ... --ready-id ...`;
- ready-template index: `python -m tools.refresh_template_index`;
- fixtures: `workflow_corpus/input/` and `vibecomfy.fixtures`;
- override behavior: matrix scope policy or the family-aware override layer.

## 9. What Is Automatic Today

Already automatic:

- source indexing via `vibecomfy sources sync`;
- port reports for helper nodes, custom-node packs, model assets, schema issues, and widget aliases;
- UI JSON to API JSON normalization;
- API JSON to `VibeWorkflow`;
- ready template generation for required rows and `ready_template: true` rows;
- custom-node requirement discovery from known class names;
- local ready-template validation;
- RunPod launch, upload, polling, artifact download, and termination;
- smoke fixture copy into pod `input/`;
- focused matrix row selection by scope;
- baseline plus VibeComfy execution for matrix rows.

Partially automatic:

- custom-node installation is catalog-backed, but each RunPod scope still declares which packs it installs;
- model staging has a registry path, but some family-specific staging is still inline in `scripts/runpod_corpus_matrix.py`;
- workflow compatibility patches are centralized in `scripts/runpod_matrix_remote.py`, but new custom-node drift still needs a patch once discovered;
- family-specific override stripping exists in the matrix, but should become declarative per workflow family.

Still too manual:

- choosing high-quality source workflows;
- deciding the smoke variant for expensive models;
- adding new RunPod scopes for new model families;
- promoting discovered one-off shell fixes into reusable code;
- updating docs when a new HiddenSwitch incompatibility or structural issue appears.

## 10. Documentation Rule

Every runtime failure should land in one of three buckets:

- `docs/hiddenswitch_incompatibilities.md` when HiddenSwitch differs from mainline Comfy or a custom node assumes mainline behavior;
- `docs/structural_issues.md` when the problem is in VibeComfy architecture, tooling, staging, fixtures, or validation;
- a family coverage doc when the issue is specific to Wan, LTX, Flux, Z-Image, Qwen TTS, ACE-Step, or another model family.

Do not leave successful fixes only in chat history or RunPod logs. If the next agent would need to rediscover it, it belongs in code or docs.
