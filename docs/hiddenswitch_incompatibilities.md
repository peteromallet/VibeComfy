# HiddenSwitch Incompatibilities

Running log of incompatibilities observed while validating VibeComfy workflows against the HiddenSwitch ComfyUI pip fork.

Current runtime under test:

```text
comfyui==0.18.2
hiddenswitch/ComfyUI commit c5ed940244b1373daf855c0adbf2f7fd6dec327a
RunPod RTX 4090 validation
```

## Runtime-Green Evidence So Far

These are the workflows that have generated real media through both baseline `comfyui run-workflow` and VibeComfy converted scratchpad execution on RunPod.

| Family | Workflow | Media | Artifact | Baseline | VibeComfy | Notes |
| --- | --- | --- | --- | ---: | ---: | --- |
| Z-Image | `z_image` | image | `out/runpod_artifacts/1777175257` | 121s | 81s | Official Comfy template path. |
| Flux Klein 4B | `flux2_klein_4b_t2i` | image | `out/runpod_artifacts/1777175257` | 100s | 80s | Official Comfy template path. |
| Flux Klein 4B | `flux2_klein_4b_image_edit_distilled` | image | `out/runpod_artifacts/1777175257` | 90s | 80s | Official edit template path. |
| Flux Klein 9B GGUF | `flux2_klein_9b_gguf_t2i` | image | `out/runpod_artifacts/1777175257` | 90s | 90s | Public GGUF path through ComfyUI-GGUF. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_t2v` | video | `out/runpod_artifacts/1777186120` | 140s | 140s | Kijai wrapper, source-authored prompt/sampler. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_i2v` | video | `out/runpod_artifacts/1777186120` | 171s | 160s | Kijai wrapper, image-to-video. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_flf2v` | video | `out/runpod_artifacts/1777186120` | 190s | 180s | First/last-frame video. |
| WanVideoWrapper | `wanvideo_wrapper_22_5b_i2v_controlnet` | video | `out/runpod_artifacts/1777186120` | 131s | 130s | 5B I2V ControlNet. |
| WanVideoWrapper | `wanvideo_wrapper_13b_control_lora` | video | `out/runpod_artifacts/1777186120` | 90s | 80s | Control LoRA. |
| WanVideoWrapper | `wanvideo_wrapper_21_14b_v2v_infinitetalk` | video | `out/runpod_artifacts/1777191469` | 220s | 210s | Focused InfiniteTalk rerun after initial failure. |
| LTX 2.3 | `ltx2_3_t2v` | video | earlier focused run | 265s | n/a | Green T2V smoke from earlier focused run; keep rerunning for complete artifact parity. |
| LTX 2.3 | `ltx2_3_i2v` | video | `out/runpod_artifacts/1777195666` | 295s | 355s | Official/Lightricks path. |
| LTX 2.3 | `ltx2_3_lightricks_iclora_motion_track` | video | `out/runpod_artifacts/1777195666` | 95s | 95s | Official IC-LoRA motion-track. |
| LTX 2.3 | `ltx2_3_lightricks_iclora_union_control` | video | `out/runpod_artifacts/1777195666` | 350s | 362s | Official IC-LoRA union control. |
| ACE Step 1.5 | `ace_step_1_5_t2a_song` | audio | `out/runpod_artifacts/1777204423` | 110s | 110s | Official subgraph materialized to API-shaped audio graph. |

Known green count so far:

- Images/edits: 4.
- Wan video: 6.
- LTX video: 4.
- Audio: 1.

## Status Legend

- `Open`: still blocks at least one runtime-green workflow.
- `Mitigated`: VibeComfy has a workaround, but the underlying fork mismatch remains.
- `Fixed (local)`: a previously-mitigated VibeComfy-side bug has been fixed in this repository; entry retained for historical context.
- `Fixed upstream required`: should ideally be fixed in HiddenSwitch or the relevant custom-node package.
- `Watch`: passed current smoke tests, but fragile enough to keep in the compatibility ledger.

## Root Cause Taxonomy

Every entry must declare at least one root cause label. Multiple labels are allowed when a failure has more than one cause; list them comma-separated.

- `local_bug`: bug in VibeComfy's materializer, harness, converter, or override logic. The fork is innocent.
- `fixture_gap`: synthetic test fixture (silent video, missing audio track, placeholder image) does not match what the workflow actually expects. Real input would not fail.
- `runtime_observability`: the failure is opaque because we lack diagnostics (no per-node progress, no VRAM sampling, no watchdog), not because the runtime itself is wrong.
- `model_layout`: model file exists but is not at the path or under the name the node pack expects. Includes alias, directory convention, and registry-discovery mismatches.
- `fork_behavior`: HiddenSwitch's pip fork diverges from upstream ComfyUI (lagging node defs, renamed inputs, different CLI semantics, embedded-execution context gaps) in a way that affects this workflow.
- `custom_node_contract`: a custom node pack (KJNodes, WanVideoWrapper, Lightricks, ComfyUI-GGUF, etc.) has an internal contract — declared schema, expected object attributes, server-context assumptions — that breaks under our usage.

## Open / Active

### LTX Runexx 22B runtime path

Status: `Open (now diagnosable via watchdog; LatentUpscaleModelManageable fix pending upstream)`

Root cause: `fork_behavior`

Affected workflows:

- `ltx2_3_runexx_first_last_frame`
- `ltx2_3_runexx_video_to_video_extend`
- other Runexx community 22B workflows when promoted from supplemental to runtime-gated

Observed failures:

- Several community graphs depend on node packs that are not present by default in the HiddenSwitch pip environment.
- After installing the node packs and normalizing model names, the workflows still hit runtime incompatibilities or stalls under the smoke budget.
- `LTXVLatentUpsampler` path crashed with `AttributeError: 'LatentUpscaleModelManageable' object has no attribute 'model_mmap_residency'`. Originally attributed to a KJNodes/HiddenSwitch object mismatch — investigation showed it is a HiddenSwitch-internal Protocol/runtime asymmetry, not a KJNodes bug. KJNodes' `LTXVLatentUpsampler` loads its model through HiddenSwitch's `LatentUpscaleModelLoader`, which wraps it in `LatentUpscaleModelManageable` (`comfy_extras/nodes/nodes_latent_upscaler.py:15`); that class extends `ModelManageableStub`, which lacked `model_mmap_residency`/`pinned_memory_size`/`partially_unload_ram` — three methods `load_models_gpu` invokes on every loaded model. Fixed in vendored fork branch and submitted upstream.

Current VibeComfy mitigation:

- Use official/Lightricks LTX workflows as runtime-green coverage.
- Convert Runexx workflows into ready templates but do not claim runtime-green until the fork mismatch is resolved.
- Bypass `LTXVLatentUpsampler` in smoke runs and remove unreferenced latent-upscale loader nodes.
- Failed runs now produce a `vibecomfy/runtime/watchdog.py` report (`out/runs/<run>/watchdog.json`) naming the active node, class type, elapsed-in-node, recent progress events, and recent VRAM samples. This converts mid-sampler stalls and contract-gap crashes into actionable diagnoses rather than opaque "no output before timeout" failures.
- Local fork at `vendor/ComfyUI/` on branch `fix/latentupscale-model-mmap-residency` (commit `15c739ff`) carries the `ModelManageableStub` fix. Verified end-to-end on RTX 4090: vanilla HiddenSwitch `c5ed9402` reproduces the AttributeError; the patched build runs `load_models_gpu([LatentUpscaleModelManageable(...)])` to completion.
- Upstream PR: https://github.com/hiddenswitch/pip-and-uv-installable-ComfyUI/pull/60

Candidate root fixes:

- ~~Patch or pin a KJNodes version whose latent upscaler object contract matches HiddenSwitch.~~ Not the right layer — KJNodes is innocent. Fixed at `ModelManageableStub` instead.
- Wait for upstream PR #60 to merge, then drop `vendor/ComfyUI/` and pin the released HiddenSwitch version that includes the fix.
- Once the contract gap is closed, re-enable `LTXVLatentUpsampler` in smoke runs and use the watchdog to triage any remaining stalls behind a larger timeout / stronger model-cache policy.

## Mitigated

### Preview nodes can assume a server context

Status: `Mitigated`

Root cause: `custom_node_contract, fork_behavior`

Affected families:

- WanVideoWrapper preview nodes
- KJNodes/LTX preview paths

Observed failure:

- Some preview nodes accessed `serv.last_node_id` during embedded or CLI execution, where the server context can be missing or incomplete.

Current VibeComfy mitigation:

- Patch preview nodes to tolerate missing server node id:

```python
node_id = serv.last_node_id or "0"
```

Policy:

- Smoke runs should disable preview output where possible.
- Doctor should warn when workflows contain server-context preview nodes in embedded/CLI execution mode.

### Custom-node discovery is not enough

Status: `Mitigated + partial validator guard`

Root cause: `fork_behavior`
Detected by: `unknown_class_type` (validator) — at submit time, before runtime crashes

Observed failure:

- HiddenSwitch can report missing node classes only at validation/execution time. That is too late for a smooth corpus run.

Current VibeComfy mitigation:

- Matrix setup installs known custom-node packages for WanVideoWrapper, LTXVideo, KJNodes, VHS/video helpers, Easy-Use, rgthree, GGUF, and related dependencies.
- `vibecomfy sources sync` indexes official workflows, external workflows, and custom nodes before materialization.
- The pre-submit validator (`vibecomfy/schema/validate.py`) now emits `unknown_class_type` issues against `/object_info` *before* a graph is submitted, so missing-node-pack failures surface as hard validation errors during `vibecomfy validate`/`vibecomfy run`, not as runtime crashes.

Policy:

- Required workflows must declare their custom-node source in the corpus manifest or the matrix setup.
- Ready templates should carry custom-node metadata even when runtime validation is deferred.

## Watch Items

### `_meta` annotation: ComfyUI adds per-node display metadata, vibecomfy does not

Status: `Watch`

Root cause: `fork_behavior`
Detected by: `test_bypass_equivalence_against_convert_ui_to_api` (T14c, `VIBECOMFY_COMFY_SMOKE=1`)

Family: `_meta_field`

Issue:

- ComfyUI's `convert_ui_to_api` adds a `_meta: {"title": "<node_display_name>"}` field to every
  node in the API JSON output. This field is used by the ComfyUI frontend to display node titles
  in the history/queue panel.
- vibecomfy's `compile('api')` does not add `_meta`. The API contract enforced by
  `queue_prompt` ignores unknown top-level keys per node, so this has **no effect on execution
  semantics**.

Minimal repro:

```python
import json, sys
sys.path.insert(0, "vendor/ComfyUI")
from vibecomfy.comfy_backend import ensure_nodes; ensure_nodes()
from comfy.component_model.workflow_convert import convert_ui_to_api
from vibecomfy.ingest.normalize import convert_to_vibe_format

raw = json.loads(open("workflow_corpus/official/image/z_image.json").read())
wf = convert_to_vibe_format(raw)
vc_node = wf.compile("api")["6"]
comfy_node = convert_ui_to_api(raw)["6"]
print("vibecomfy keys:", sorted(vc_node.keys()))   # no _meta
print("comfy keys:    ", sorted(comfy_node.keys()))  # includes _meta
```

Policy:

- `_meta` is purely cosmetic. VibeComfy does not need to emit it for correctness.
- If a downstream consumer requires `_meta` (e.g. a custom frontend panel), add it in a
  separate post-processing step outside `compile('api')`.
- `test_bypass_equivalence_against_convert_ui_to_api` strips `_meta` before comparing; the
  divergence is listed in `_KNOWN_XFAIL_FAMILIES["_meta_field"]` in
  `tests/test_compile_invariance.py`.



### HiddenSwitch pip fork and official Comfy template drift

Status: `Watch + partial validator guard`

Root cause: `fork_behavior`
Detected by: `unknown_class_type`, `unknown_input`, `missing_required_input`, `value_out_of_range`, `value_not_in_enum` (validator)

Issue:

- Official Comfy templates may assume current Comfy core node definitions, while HiddenSwitch pip may lag, rename inputs, or expose a different API contract.

Examples:

- ACE Step official subgraph required explicit materialization.
- ACE text node required fields not visible in the first shallow conversion pass.
- Qwen Image 2512 required a workflow-family policy rather than universal CLI step overrides. The official template routes step/cfg selection through primitive nodes and `ComfySwitchNode`; HiddenSwitch baseline execution works after graph preparation, but VibeComfy must not inject `--steps` unless metadata has an eligible sampler target.

Policy:

- Validate against `/object_info` or embedded node definitions, not just raw template shape. The pre-submit validator now does this for the `vibecomfy run` and `vibecomfy validate` paths, so most schema-drift surfaces as a hard error before submission. Templates that drift in subtler ways (semantic shape changes, default-value drift) can still slip through and need the watch.
- Doctor output that names missing required node inputs and suggests the patch/materialization location is still TODO (deferred per the wave-1 decision; revisit if validator-as-lint isn't sufficient).
- Treat CLI override eligibility as part of runtime compatibility. A workflow can be valid and runnable while still rejecting `--prompt` or `--steps`; that should become a matrix policy decision, not a template failure.

### Watchdog completion semantics for embedded runs

Status: `Open`

Root cause: `runtime_observability`
Detected by: watchdog JSON and successful output mismatch

Issue:

- A Qwen Image 2512 embedded VibeComfy run produced a PNG and returned `rc=0`, but the watchdog log reported `diagnosis=crashed` with no prompt/node id. This is a false-negative diagnosis for runtime-green evidence: the output exists and the process succeeded, but the watchdog report is misleading.

Policy:

- Runtime-green evidence should still require generated media and process success.
- Watchdog diagnosis should be used for debugging, but `diagnosis=crashed` with `rc=0` and valid output should be treated as a watchdog bug until the event-stream lifecycle is fixed.
- Fix target: align watchdog shutdown with successful embedded prompt completion so completed runs produce `diagnosis=completed`, or mark "event stream ended after output" distinctly.

## Resolved

The following entries were closed by structural fixes that landed on 2026-04-26. Kept as a one-line history rather than full entries; see the named modules and `git log` for the implementation. If any of these regress, re-open with a new entry rather than reanimating the old one.

- **ACE Step audio prompt/runtime path** (was `local_bug, fork_behavior`). Caught by validator (`value_out_of_range` for `bpm=2`, `missing_required_input` for omitted ACE API fields) and by family-aware overrides (refuses to wire `--prompt` into `TextEncodeAceStepAudio1.5`). Files: `vibecomfy/schema/validate.py`, `vibecomfy/metadata.py`.
- **LTX Runexx audio extraction and audio-shape assumptions** (was `fixture_gap`). Real `speech_smoke.wav` (~94KB, mono 16kHz, ~2.94s) plus four audio-bearing guide videos shipped under `workflow_corpus/input/`. Bootstrap unified in `vibecomfy/fixtures.py` with `python -m vibecomfy.fixtures copy --target input`. See `workflow_corpus/input/FIXTURES.md`. Remaining gap: workflows requiring specific speech *content* (talking-head / lip-sync, music-conditioned) are still unverified — re-open as a new entry if a specific workflow needs more than the generic clip.
- **Long-running LTX community graphs do not fail cleanly** (was `runtime_observability`). WebSocket-based execution watchdog with diagnoses (`completed | errored | slow_node | stalled_runtime | oom_ish | missing_event_stream | crashed | in_progress`) wired into both session backends. File: `vibecomfy/runtime/watchdog.py`. Opt-out via `VIBECOMFY_WATCHDOG=0`. The workflows themselves still stall — those stalls now roll up into `LTX Runexx 22B runtime path` and are diagnosable per-incident.
- **Generic prompt and step overrides assume mainline image nodes** (was `local_bug`). Class-type allowlists in `_register_common_inputs` (`PROMPT_NODE_CLASSES`, `STEPS_NODE_CLASSES`); CLI errors loudly when `--prompt`/`--steps` has no eligible target. Matrix-level workaround removed. Reversibility: `VIBECOMFY_LEGACY_OVERRIDES=1`. Files: `vibecomfy/metadata.py`, `vibecomfy/commands/run.py`, `scripts/runpod_corpus_matrix.py`.
- **UI JSON to API JSON link representation** (was `local_bug`). Validator catches `invalid_link_shape` structurally — dict-shaped link payloads on inputs whose schema isn't `DICT`/`*` now fail at submit. File: `vibecomfy/schema/validate.py`.
- **Model name and directory conventions differ across node packs** (was `model_layout`). Flat YAML registry (`vibecomfy/registry/models.yaml`) declaring canonical id → source → list of `(node_pack, target_path)` pairs + accepted aliases. Single source of truth for both staging (`stage_many` via `vibecomfy models stage` CLI) and runtime alias normalization. Files: `vibecomfy/registry/{models.yaml, models_loader.py, __init__.py}`, `vibecomfy/commands/models.py`, `scripts/runpod_corpus_matrix.py`, `scripts/runpod_matrix_remote.py`.
- **Model downloader known-model registry** (was `model_layout, fork_behavior`). Folded into the registry above; HiddenSwitch's downloader is no longer the source of truth — the YAML is.

## Compatibility Checklist

Before calling a workflow `runtime_green` on HiddenSwitch:

- Baseline `comfyui run-workflow` generated the expected media.
- VibeComfy generated the expected media from the converted scratchpad.
- Pre-submit validator passes against `/object_info` (no `unknown_class_type`, `missing_required_input`, `unknown_input`, `value_out_of_range`, `value_not_in_enum`, or `invalid_link_shape` issues). Disable temporarily with `--no-schema` only when intentionally testing the gate's reversibility lever.
- Watchdog dump for the run produces `diagnosis=completed`. Any other diagnosis (`slow_node`, `stalled_runtime`, `oom_ish`, etc.) is a runtime-green failure even if media was eventually produced.
- Required custom nodes are installed or intentionally absent (validator's `unknown_class_type` covers this).
- Required model files are declared in `vibecomfy/registry/models.yaml` and present at every `(node_pack, target_path)` the registry lists. `vibecomfy models stage --dry-run` reports zero missing.
- CLI overrides (`--prompt`, `--steps`) only invoked against workflows whose nodes match the allowlists — if they don't, the CLI now errors loudly rather than misrouting.
- Audio-extraction workflows pull from a `workflow_corpus/input/` guide video (all four committed guides carry an AAC audio track) or an explicit `LoadAudio("speech_smoke.wav")`.
- Preview/server-only nodes are disabled, removed, or patched.
- UI JSON subgraphs have been materialized into a full API-compatible graph (validator's `invalid_link_shape` catches dict-shaped link regressions).
- Failure logs and watchdog dumps are archived under `out/runpod_artifacts/<run>/` and `out/runs/<run>/watchdog.json`.

## Contributing Entries

To prevent this doc from degrading into an unindexed pile of tribal exceptions, every new entry — and every PR that adds one — must satisfy two requirements:

1. **Declare a root cause label** from the Root Cause Taxonomy above. Place a `Root cause:` line directly under the `Status:` line. Multiple labels are allowed when a failure has more than one cause; list them comma-separated. The label is what lets future readers (and tooling) tell `local_bug` from `fork_behavior` from `fixture_gap` without reading the full prose.

2. **Cross-reference prior entries.** In the PR description, link any existing entry whose mitigation, observed failure, or affected family overlaps with the new one — or explicitly state "no prior entry applies." This forces the author to read the doc before adding to it, which is the only mechanism keeping mitigations from being silently reinvented.

If a previously `Mitigated` entry's underlying cause is later resolved upstream (HiddenSwitch fix, custom-node fix, etc.), update the status and root cause rather than deleting the entry — the historical record of what failed and why is part of the doc's value.
