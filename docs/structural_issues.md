# Structural Issues

Running log of cross-cutting issues found while building the workflow corpus, converter, ready templates, and RunPod execution harness.

These are not one-off workflow bugs. They are places where the system needs a stable policy so future templates get smoother instead of requiring manual rescue.

## Template State Model

Status: `Active`

Current distinction:

- `raw_json`: upstream Comfy workflow material imported as source.
- `converted`: raw JSON normalizes into API JSON and `VibeWorkflow`.
- `ready_template`: curated Python template checked into `ready_templates/`.
- `runtime_ready`: model files, input media, custom nodes, and smoke patch policy are declared.
- `runtime_green`: baseline Comfy and VibeComfy both generated expected media on RunPod.

Structural issue:

- "Ready" can be confused with "runtime green". They are different. A ready template is reusable Python source; runtime green is evidence from a real GPU run.

Policy:

- Keep raw JSON under `workflow_corpus/` or `vendor/`.
- Keep generated scratchpads under `out/`.
- Keep curated reusable Python templates under `ready_templates/`.
- Record runtime-green evidence in RunPod artifacts and coverage docs.

Current ready-template corpus:

- `ready_templates/image/`: Z-Image, Flux Klein 4B T2I, Flux Klein 9B GGUF T2I.
- `ready_templates/edit/`: Qwen image edit, Flux Klein 4B image edit.
- `ready_templates/video/`: official Wan, Kijai WanVideoWrapper, Lightricks LTX, Runexx LTX, IAMCCS LTX.
- `ready_templates/audio/`: ACE Step 1.5 text-to-audio/song.

Current runtime-green corpus:

- Image/edit: `z_image`, `flux2_klein_4b_t2i`, `flux2_klein_4b_image_edit_distilled`, `flux2_klein_9b_gguf_t2i`.
- Wan: `wanvideo_wrapper_21_14b_t2v`, `wanvideo_wrapper_21_14b_i2v`, `wanvideo_wrapper_21_14b_flf2v`, `wanvideo_wrapper_22_5b_i2v_controlnet`, `wanvideo_wrapper_13b_control_lora`, `wanvideo_wrapper_21_14b_v2v_infinitetalk`.
- LTX: `ltx2_3_t2v`, `ltx2_3_i2v`, `ltx2_3_lightricks_iclora_motion_track`, `ltx2_3_lightricks_iclora_union_control`.
- Audio: `ace_step_1_5_t2a_song`.

## Converter Generality

Status: `Active`

Observed issue:

- The converter handles mainline Comfy workflows well, but custom-node families need node-class-aware patch policies.
- Widget-position conversion is fragile when workflows use primitive links, subgraphs, or node versions with hidden widgets.

Current improvements:

- Family policies for WanVideoWrapper, LTX, Flux GGUF, and ACE Step.
- UI-node stripping for unreferenced group, preview, and helper nodes.
- Model-name normalization for LTX and Wan ecosystems.
- Explicit input contracts for ACE audio instead of positional widget inference.
- Subgraph materialization for official templates whose top-level graph is not directly runnable as a normal API graph.
- Primitive-node link replacement for smoke-safe values such as seed and duration.
- Media-aware override policy so audio and custom video workflows are not mutated by image-only prompt replacement.

Policy:

- Use raw JSON as import material, not as the native authoring surface.
- Normalize to API JSON, then `VibeWorkflow`, then port-convert or hand-author Python ready templates.
- Prefer node-class and input-name mapping over widget-index mapping.
- When widget-index mapping is unavoidable, add a regression test using the exact source workflow shape.

Known converter risks:

- Comfy UI JSON can contain subgraphs, group nodes, visual notes, preview-only nodes, hidden widgets, and primitive links. A shallow "nodes plus widgets" pass is not enough.
- API JSON can be valid structurally but still fail against HiddenSwitch node input contracts.
- A source workflow can intentionally contain multiple branches; smoke materialization needs to keep the branch under test and remove or bypass unreferenced expensive branches.

## Custom Nodes

Status: `Active`

Observed issue:

- Custom-node workflows fail for users unless node packs, dependency packages, model paths, and node-version contracts are handled as one unit.

Current approach:

- Matrix setup installs known node packs for required runtime coverage.
- Ready templates include custom-node metadata.
- Source indexing records node availability before conversion.

Policy:

- Every ready template should declare:
  - custom-node packages
  - required model files
  - expected input files
  - known runtime flags
  - smoke-patch policy

Needed improvement:

- Add `vibecomfy doctor` output that can say:
  - missing custom node package
  - installed package but missing node class
  - node class exists but required input contract changed
  - model path missing
  - model path present but below expected size

Custom-node policy learned so far:

- Kijai/WanVideoWrapper is a primary Wan source, not an edge case.
- Lightricks/ComfyUI-LTXVideo is the preferred runtime-green LTX source.
- Kijai/KJNodes is required infrastructure for several LTX workflows.
- RuneXX and IAMCCS are useful LTX capability sources, but should stay supplemental until runtime-green.
- ComfyUI-GGUF is required for the public Flux Klein 9B path.

## RunPod Lifecycle

Status: `Mitigated, needs hardening`

Observed issue:

- Real validation requires RunPod, but launching pods manually creates cost and cleanup risk.

Current approach:

- Matrix runs use `runpod-lifecycle`.
- Generic pods launched by the harness are terminated after completion or failure.
- Peter's long-lived named pods are left alone.
- The upload tarball excludes `.venv`, `.git`, `out`, `output`, `vendor`, `.desloppify`, and `.megaplan`. This matters operationally: one Qwen Image 2512 run spent several minutes extracting unnecessary local baggage before model staging. Upload size should stay small enough that setup time reflects dependency/model work, not repo debris.

Operational rule:

- Terminate generic pods launched during validation.
- Leave named `text-ip-adapter-*` pods alone unless explicitly asked.
- Always list pods after a long run because the local harness can report termination while a stale generic pod is still visible briefly.
- Do not rely on `runpodctl` inside the pod for cleanup; it may not be configured there. Termination should happen from the local `runpod-lifecycle` credentials or from the launcher guard that created the pod.

Policy:

- Use a context-manager-like lifecycle for every validation run.
- Add signal handlers so Ctrl-C or local process failure terminates launched pods.
- Keep a server-side TTL backstop for every launched pod.
- Save artifacts before termination.
- List pods after validation and terminate any generic orphaned pods.
- Artifact collection commands must be portable across macOS and Linux. Avoid GNU-only `find -printf` in local artifact summaries unless the command is only run on the Linux pod.

Needed improvement:

- Expose RunPod lifecycle as a first-class VibeComfy CLI tool so users can run:

```bash
vibecomfy runpod matrix --scope wan_creation_types
vibecomfy runpod list
vibecomfy runpod terminate <pod-id>
```

Result artifacts:

- Every run should download `out/corpus_matrix/results.tsv`, `ready_results.tsv`, logs, patched workflows, generated scratchpads, and produced media before pod termination.
- Artifact directories should be referenced in docs when they are used as evidence.

## Runtime Modes

Status: `Active`

Observed issue:

- We use three execution surfaces:
  - baseline `comfyui run-workflow`
  - VibeComfy embedded runtime
  - managed HTTP server runtime

Structural risk:

- A workflow can pass one surface and fail another because prompt overrides, server context, preview nodes, cache behavior, and output waiting differ.
- Generic `--prompt` and `--steps` overrides are not valid for every workflow. Qwen Image 2512 uses primitive step/cfg nodes routed through `ComfySwitchNode`; baseline Comfy can run the patched graph, while VibeComfy correctly rejects `--steps` because there is no directly registered mainline sampler field.

Policy:

- Required runtime-green evidence must include baseline Comfy and VibeComfy execution.
- HTTP queue submission alone is not enough; we need completed output evidence.
- Use embedded mode for one-shot proof of execution.
- Use managed server mode for warm-cache/session testing.
- Matrix scopes need per-family override policy. When a preparation/materialization policy already sets steps, cfg, resolution, LoRA switch, and seed inside the graph, the run command should not also pass universal CLI overrides for those fields.

Recent example:

- `qwen_image_2512` generated a baseline Comfy PNG and a VibeComfy PNG on RunPod. The first matrix pass failed only because the VibeComfy phase passed `--steps`; rerunning the same generated scratchpad with `--seed` and `--prompt` succeeded. The matrix now has a Qwen 2512-specific override path.

Execution standard:

- A workflow is not runtime-green unless it produces media in both baseline and VibeComfy paths.
- `validate` passing is necessary but not sufficient.
- A ready template that imports and validates is reusable, but still not proof that models/custom nodes/runtime are correctly staged.

## Prompt and Parameter Overrides

Status: `Active`

Observed issue:

- Generic overrides like `--prompt`, `--steps`, and `--seed` are not universal graph transforms.
- They work for many mainline image workflows but fail on custom prompt/sampler/audio/video node families.

Policy:

- Mainline image workflows may use generic CLI overrides.
- Custom-node workflows should use source-authored prompt wiring plus family-specific API patches.
- Smoke reduction must happen through explicit node-class policies.

## Model Distribution and Caching

Status: `Active`

Observed issue:

- Large workflows are slow if every run redownloads models or reloads common weights.
- Different node packs expect the same model under different directory names.

Current approach:

- RunPod uses persistent Hugging Face and pip caches under `/workspace/.cache`.
- Matrix setup materializes model aliases into multiple expected paths.
- Large Wan and LTX runs use explicit staging and size checks.

Policy:

- Required templates must list exact model URLs or Hugging Face repo paths.
- Model staging should be deterministic and size-checked.
- Alias paths should be declared centrally, not patched per failure.
- Warm runtime tests should measure cache/reuse behavior separately from cold-launch install time.

Known model-staging needs:

- Image core: Qwen edit, Z-Image, Flux Klein 4B, Flux Klein 9B GGUF.
- Wan: Kijai and Comfy-Org repackaged diffusion models, clip vision, LoRAs, ControlNet, InfiniteTalk GGUF, MelBandRoFormer where needed.
- LTX: LTX 2.3 checkpoint, text projection, video/audio VAE, preview VAE, distilled LoRA/upscaler 1.1 assets.
- Audio: ACE Step text encoders, VAE, and diffusion model.

## Coverage Shape

Status: `Active`

Target:

- 5-6 main workflows per major video family where possible:
  - T2V
  - I2V
  - I2I / edit where applicable
  - V2V
  - first/last-frame or image anchors
  - ControlNet / LoRA / IC-LoRA
  - audio/voice-to-video where applicable

- Main image families:
  - Z-Image
  - Flux Klein 4B
  - Flux Klein 8B/9B-class
  - Qwen image edit

- Audio:
  - ACE Step text-to-audio/song
  - Qwen voice/TTS where we have a reliable node/workflow source

Current gap analysis:

| Family | Green | Ready but not green | Main gap |
| --- | ---: | ---: | --- |
| Image/edit | 4 | Qwen edit ready | Need Qwen edit runtime-green if not already covered by a later run. |
| Wan | 6 | many Kijai variants | More S2V/audio/camera/control variants can be promoted after model staging is cheap. |
| LTX | 4 | Runexx/IAMCCS community workflows | Need stable community 22B path or alternative official workflows for FLF/V2V/audio. |
| Audio | 1 | none beyond ACE in current ready set | Need Qwen voice/TTS standalone coverage. |

Structural issue:

- "Major model" coverage should not be a pile of random examples. It needs a capability matrix with one representative ready template per capability.

Policy:

- Promote workflows from supplemental to required only when they cover a missing capability or model family.
- Prefer official Comfy templates first.
- Use Kijai and other prominent custom-node sources when official templates do not cover the capability.
- Keep failed community workflows as supplemental ready templates with documented blockers instead of deleting them.

## Failure Handling

Status: `Active`

Observed issue:

- The same class of failure repeats unless it is turned into a reusable doctor/converter/runtime rule.

Policy:

- Every RunPod failure should be classified as one of:
  - conversion bug
  - missing custom node
  - missing model
  - wrong model path/name
  - node input contract mismatch
  - runtime fork incompatibility
  - OOM/VRAM policy
  - timeout/performance bottleneck
  - output detection bug

- For each class, add one of:
  - converter patch
  - ready-template patch
  - doctor rule
  - matrix setup dependency
  - docs entry with known blocker

Concrete failures converted into reusable rules:

- ACE generic prompt failure -> media-aware override policy.
- ACE missing required inputs -> explicit node-contract materialization.
- ACE widget-position `bpm=2` failure -> avoid positional widget inference for safety-critical fields.
- ACE dict links -> full UI link array materialization.
- Wan generic prompt/step incompatibility -> source-authored Wan prompts and sampler wiring.
- KJ preview server-context issue -> preview-node patch and future doctor warning.
- LTX missing models/path names -> model alias staging and family-specific normalization.
- LTX latent upscaler object mismatch -> bypass in smoke and document HiddenSwitch/KJNodes incompatibility.

## Raw-shape `@stub` object_info snapshots report 0 outputs (latent arity bug)

Status: `Open — follow-up` (found 2026-06-09 during node_resolution_epic m3)

Five hand-authored object_info snapshots are stored in raw ComfyUI
`object_info` shape — outputs as two parallel arrays, `output` (type strings)
and `output_name` (display names) — rather than the normalized
`outputs: [{name, type}]` shape that the 19 captured snapshots use:

- `ComfyUI-MelBandRoformer@stub.json`
- `comfyui_controlnet_aux@stub.json`
- `ComfyUI-Florence2@stub.json`
- `ComfyUI-GIMM-VFI@stub.json`
- `ComfyUI-Custom-Scripts@stub.json`

`vibecomfy/porting/object_info/consume.py::output_names`/`output_types` only
read the normalized `outputs` key, so **every class in those five stubs reports
0 outputs**. `class_output_count` therefore returns 0, and
`check_output_arity_consensus` raises a false `ArityDisagreementError`
("cached snapshot declares 0 outputs but UI declares N") on any workflow that
wires one of those nodes. This is what makes
`tests/test_porting_convert.py::test_real_fixture_talking_avatar_getnode_resolves_to_named_broadcast`
fail (it is in the m3 baseline of pre-existing failures and is allowlisted in
`tests/known_failures.txt`).

The minimal fix is to make `output_names`/`output_types` derive normalized
specs from the raw `output`/`output_name` arrays when `outputs` is absent (or to
normalize the five stub files). **But that fix is not free**: it surfaces a
calibrated dependency in the ready-template corpus. Once `DWPreprocessor`
(controlnet_aux) correctly reports its two outputs (`IMAGE`, `POSE_KEYPOINT`),
at least eight LTX/Wan video templates that reference its output without an
explicit `.out('IMAGE')` start raising
`ValueError: ... has 2 outputs (...); specify .out('NAME') explicitly` from
`build()`. Those raises also expose a **workflow-context leak**: a ready
template whose `build()` raises after `new_workflow(...)` has eagerly bound the
`_CURRENT_WORKFLOW` ContextVar (and is never released by `finalize()`) leaves
the binding active, so every subsequent template load — and the next
`build_strict_ready_report()` call — fails with
`ContextVarBindingError: Nested workflow contexts not supported`. The defensive
cleanup in `templates.py::new_workflow` only clears a leaked binding whose owner
has been GC'd (token already `None`); it does not handle the common
`build()`-raised-after-binding case.

Proper follow-up (own piece of work, not a pre-merge tweak):
1. Make the consume accessors shape-tolerant (or normalize the five stub files).
2. Add explicit `.out('IMAGE')` disambiguation to the ~8 DWPreprocessor-using
   video templates.
3. Isolate each template load in `tools/check_strict_ready_templates.py`
   (reset `_CURRENT_WORKFLOW` in a `finally`) so a failed `build()` cannot poison
   later loads, and/or broaden `new_workflow`'s leaked-binding cleanup to the
   raised-after-binding case without breaking the genuine-nested-`with` contract.
4. Re-baseline `tests/known_failures.txt` once the corpus is green.

## Immediate Backlog

- Keep ACE Step audio in the runtime-green set and add doctor coverage for the issues it exposed.
- Add doctor checks for missing required node inputs and media-specific prompt override hazards.
- Add a compatibility test fixture for official subgraph materialization.
- Promote RunPod lifecycle operations into the VibeComfy CLI.
- Add a machine-readable ready-template manifest with state: `ready_template`, `runtime_ready`, `runtime_green`.
- Separate cold install time from execution time in the RunPod result TSVs.
- Keep pushing LTX community workflows, but avoid claiming runtime-green until HiddenSwitch/KJNodes incompatibilities are fixed or pinned.
