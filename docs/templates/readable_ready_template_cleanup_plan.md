# Readable Ready Template Cleanup Plan

## Goal

Ready templates should read like maintainable Python workflow builders, not like
Comfy JSON transliterated into Python syntax.

The target is both:

- future imports produce readable, reusable Python by default; and
- existing checked-in workflows can be regenerated or repaired without losing
  parity with their source graphs.

This plan folds together named output handles, widget alias cleanup, runtime
contract information, public input registration, subgraph handling, and
conversion-path consolidation.

## Current Problems

The latest LTX first/last parity template shows the right direction:

- it uses named handles such as `checkpoint.out("vae")`;
- it stores `_outputs=(...)` on nodes;
- it exposes important route metadata and runtime notes.

Other ready templates still show the broader problem:

- thousands of positional `.out(0)` / `.out(1)` calls remain across
  `ready_templates/`;
- generated templates preserve `widget_0`, `widget_1`, etc. even when aliases
  exist;
- some templates contain UUID class types and `n_<uuid>` variables from opaque
  subgraph imports;
- model filenames can be hidden under positional widgets while
  `READY_REQUIREMENTS["models"]` is empty;
- public controls are often only present as `metadata["unbound_inputs"]`, not
  real `wf.register_input(...)` bindings;
- every generated template carries repeated `_node` helper boilerplate;
- conversion paths diverge between older `vibecomfy convert` behavior (now removed
  in Sprint 1 — the command exits non-zero with a migration message pointing to
  `port check` / `port convert`) and the canonical `port convert` /
  `port_convert_workflow()` path.

The cleanup should be generator-led. Hand-polishing individual templates without
fixing the import/emitter path would only make the next import reintroduce the
same issues.

## Target Contract

A ready template is readable enough when it satisfies these rules:

- **Named outputs:** use `.out("name")` whenever schema data knows the output
  name. Numeric `.out(n)` is allowed only when the node schema is unavailable or
  genuinely unnamed.
- **Named inputs/widgets:** do not emit schema-backed `widget_N` fields.
- **No opaque ready graph:** UUID class types are not allowed in strict ready
  templates unless explicitly marked as manual/reference-only. They are allowed
  in scratchpads as an import escape hatch.
- **User controls are real inputs:** template knobs such as prompt, negative
  prompt, seed, width, height, frames, fps, image paths, audio paths, speaker,
  denoise, cfg, and filename prefix are registered with `wf.register_input(...)`
  or a successor API.
- **Constants for author knobs:** repeated prompts, model filenames, dimensions,
  seeds, fps, frame counts, sigmas, cfg, steps, and output prefixes are hoisted
  to named constants.
- **Semantic variable names:** variables describe workflow roles, not just class
  names or source node ids.
- **Source ids are provenance, not the main reading surface:** preserve original
  node ids for parity/debugging, but avoid making raw ids the only way to
  understand or customize the template.
- **Long workflows have sections:** large templates include sparse section
  comments for inputs, loaders, conditioning, sampling, decode, and outputs.
- **Contracts expose the graph surface:** runtime contracts include input
  bindings and output names/types, not only runtime packages and class types.

General migration rule: do not keep compatibility wrappers, shims, or adapter
commands as a long-term strategy. Migrate useful behavior into the canonical
implementation, add tests there, and make the obsolete entry point fail with a
clear migration message.

## Agent Usage Contract

The cleaned template surface should be easy for an agent to use without opening
the template source first.

Canonical use:

```python
from vibecomfy import load_workflow_any

wf = load_workflow_any("video/ltx2_3_lightricks_first_last_parity")
wf.set_input("prompt", "The camera glides from a wide view into a close-up.")
wf.set_input("seed", 42)
api = wf.compile("api")
```

Agents should prefer registry loading (`load_workflow_any`, `workflow_from_ready`,
or the CLI) over importing a ready-template module and calling `build()` directly.
Direct `build()` calls are acceptable for tests and local template development,
but the public API is the loaded `VibeWorkflow` with registered inputs, outputs,
requirements, contracts, and provenance.

A strict-ready template should make these questions answerable from inspection
and contracts:

- Which inputs may I set?
- What type/range/default does each input have?
- Which outputs/artifacts will the workflow produce?
- Which model files, custom nodes, runtime packages, and flags are required?
- Which graph nodes came from the original source workflow?
- Is this template app-active/required, supplemental, reference-only, or a
  scratchpad import?

Canonical discovery surface: `python -m vibecomfy.cli inspect <workflow> --json`
should be the authoritative single-workflow JSON view for agents. `doctor`,
`port check`, and any contract-specific commands may reuse the same data model,
but should not invent competing shapes. `workflows list --ready --json` should
be a cheap index view with enough fields to choose candidates before inspecting
one.

Agent happy path:

```bash
python -m vibecomfy.cli workflows list --ready --json
python -m vibecomfy.cli inspect video/ltx2_3_lightricks_first_last_parity --json
python -m vibecomfy.cli workflows lens video/ltx2_3_lightricks_first_last_parity --json
python -m vibecomfy.cli doctor video/ltx2_3_lightricks_first_last_parity --json
```

The ready list rows should include at least id, capability, readiness class,
app-active/required/reference/supplemental status, blocked reason if any,
required public inputs, public output names, model/custom-node requirement
summary, and strict-ready diagnostic counts. An agent should not need to inspect
every candidate just to choose the right workflow family.

The inspection/contract surface should expose enough structured data for an
agent to render a form, set inputs, dry-run/compile, and find artifacts without
reading generated Python:

```json
{
  "id": "video/example",
  "capability": "first_last_frame_video",
  "public_inputs": [{"name": "prompt", "type": "STRING", "default": "..."}],
  "public_outputs": [
    {
      "name": "video",
      "artifact_kind": "video",
      "mime_type": "video/mp4",
      "expected_filename_prefix": "output"
    }
  ],
  "models": [{"name": "model.safetensors", "subdir": "checkpoints"}],
  "custom_nodes": ["ComfyUI-LTXVideo"]
}
```

After execution, a separate run artifact manifest can use the same semantic
output names:

```json
{
  "run_id": "2026-05-15/example",
  "artifacts": {
    "video": [{"path": "out/example/output_00001.mp4", "mime_type": "video/mp4"}]
  }
}
```

## Public Input Names

Capability-level input names should be stable. Individual templates may expose
extra knobs, but they should not invent alternate names for common concepts.

| Capability | Required public inputs | Common optional inputs |
| --- | --- | --- |
| `text_to_image` | `prompt`, `seed`, `width`, `height` | `negative_prompt`, `steps`, `cfg`, `model`, `filename_prefix` |
| `image_edit` | `prompt`, `image`, `seed` | `negative_prompt`, `width`, `height`, `denoise`, `strength`, `model`, `filename_prefix` |
| `image_to_video` | `prompt`, `image`, `seed`, `width`, `height`, `frames`, `fps` | `negative_prompt`, `steps`, `cfg`, `model`, `filename_prefix` |
| `first_last_frame_video` | `prompt`, `first_image`, `last_image`, `seed`, `width`, `height`, `frames`, `fps` | `negative_prompt`, `first_strength`, `last_strength`, `model`, `filename_prefix` |
| `video_to_video` | `prompt`, `video`, `seed`, `frames`, `fps` | `negative_prompt`, `width`, `height`, `denoise`, `strength`, `model`, `filename_prefix` |
| `text_to_audio` / TTS | `text`, `seed` | `speaker`, `language`, `reference_audio`, `voice_prompt`, `filename_prefix` |

Aliases are allowed only when recorded as aliases. For example, `seed_first` and
`seed_last` may exist as explicit alternate names, but `seed` should remain the
primary input unless the workflow truly has independent first/last random
streams. Duplicate public names bound to the same node field should be explicit
alias metadata, not accidental repeated registrations.

Public input descriptors should carry enough information for agents and apps:

```json
{
  "name": "frames",
  "type": "INT",
  "required": false,
  "default": 121,
  "range": {"min": 1, "max": 257, "step": 8},
  "aliases": ["length"],
  "target": {"node_id": "42", "field": "value"},
  "media_semantics": null
}
```

For file inputs, descriptors must state whether values are local paths, URLs to
download/stage, Comfy input filenames already present in the input directory, or
references to already-staged assets.

Capability-level required inputs should start as advisory diagnostics until
templates declare capability, app-active status, primary aliases, and duplicate
alias semantics consistently.

## Generated Template Anatomy

Generated ready templates should have a predictable structure:

1. imports;
2. constants for public defaults, model filenames, reusable presets, and output
   prefixes;
3. `READY_METADATA` and `READY_REQUIREMENTS`;
4. optional reusable block/helper functions for domain fragments;
5. `build()`;
6. no local `_node` helper boilerplate.

Constants should be selective. Hoist public defaults such as prompt, negative
prompt, seed, width, height, frames, fps, cfg, steps, filename prefix, guide
strengths, model filenames, and repeated sampler presets. Do not turn every
internal enum, one-off numeric setting, or UI-only display string into global
constant soup. Drop UI-only display strings when they are safe to remove.

## Before / After Target

The current generated style often looks like this:

```python
primitiveint = _node(wf, "PrimitiveInt", "42", value=121)
checkpointloadersimple = _node(
    wf,
    "CheckpointLoaderSimple",
    "127",
    ckpt_name="ltx-2.3-22b-distilled-fp8.safetensors",
)
samplercustomadvanced = _node(
    wf,
    "SamplerCustomAdvanced",
    "120",
    guider=cfgguider.out(0),
    latent_image=ltxvconcatavlatent.out(0),
    noise=randomnoise.out(0),
    sampler=samplereulerancestral.out(0),
    sigmas=manualsigmas.out(0),
)
wf.register_input("frames", "42", "value", value=121)
```

The desired output is closer to this condensed module skeleton. Helper names are
proposed public helpers that should be introduced before generated templates use
them.

```python
from __future__ import annotations

from vibecomfy.ready_helpers import bind_input, bind_output, finalize_ready_template, ready_node, ready_workflow
from vibecomfy.workflow import VibeWorkflow


DEFAULT_PROMPT = "The camera glides from a wide view into a close-up."
DEFAULT_NEGATIVE = "blurry, low quality"
DEFAULT_SEED = 42
DEFAULT_SIZE = (1280, 720)
DEFAULT_FRAMES = 121
DEFAULT_FPS = 24
DEFAULT_FIRST_STRENGTH = 1.0
DEFAULT_LAST_STRENGTH = 1.0
DISTILLED_SIGMAS = "1., 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
CHECKPOINT = "ltx-2.3-22b-distilled-fp8.safetensors"
OUTPUT_PREFIX = "output"


READY_METADATA = {
    "ready_template": "video/example_first_last",
    "capability": "first_last_frame_video",
    "model_assets": [{"name": CHECKPOINT, "subdir": "checkpoints"}],
}

READY_REQUIREMENTS = {
    "models": READY_METADATA["model_assets"],
    "custom_nodes": ["ComfyUI-LTXVideo"],
}


def build() -> VibeWorkflow:
    wf = ready_workflow(READY_METADATA, source_path=__file__)

    # Inputs
    first_image = ready_node(wf, "LoadImage", source_id="31", outputs=("image", "mask"), image="first.png")
    last_image = ready_node(wf, "LoadImage", source_id="39", outputs=("image", "mask"), image="last.png")
    width = ready_node(wf, "PrimitiveInt", source_id="113", outputs=("value",), value=DEFAULT_SIZE[0])
    height = ready_node(wf, "PrimitiveInt", source_id="98", outputs=("value",), value=DEFAULT_SIZE[1])
    frames = ready_node(wf, "PrimitiveInt", source_id="102", outputs=("value",), value=DEFAULT_FRAMES)
    fps = ready_node(wf, "PrimitiveFloat", source_id="123", outputs=("value",), value=DEFAULT_FPS)

    # Loaders
    checkpoint = ready_node(
        wf,
        "CheckpointLoaderSimple",
        source_id="127",
        outputs=("model", "clip", "vae"),
        ckpt_name=CHECKPOINT,
    )

    # Conditioning
    prompt = ready_node(
        wf,
        "CLIPTextEncode",
        source_id="128",
        outputs=("conditioning",),
        text=DEFAULT_PROMPT,
        clip=checkpoint.out("clip"),
    )

    # Sampling / decode. Details omitted for brevity; real generated code should
    # keep the same sectioned, named-handle shape.
    sampled_av_latent = ready_node(
        wf,
        "SamplerCustomAdvanced",
        source_id="120",
        outputs=("output", "denoised_output"),
        guider=guider.out("guider"),
        latent_image=av_latent.out("latent"),
        noise=noise.out("noise"),
        sampler=sampler.out("sampler"),
        sigmas=sigmas.out("sigmas"),
    )

    save_video = ready_node(
        wf,
        "SaveVideo",
        source_id="68",
        video=video.out("video"),
        filename_prefix=OUTPUT_PREFIX,
    )

    finalize_ready_template(wf, READY_METADATA, READY_REQUIREMENTS, source_path=__file__)
    bind_input(wf, "prompt", prompt, "text", default=DEFAULT_PROMPT)
    bind_input(wf, "seed", noise, "noise_seed", default=DEFAULT_SEED, aliases=("seed_first", "seed_last"))
    bind_input(wf, "width", width, "value", default=DEFAULT_SIZE[0])
    bind_input(wf, "height", height, "value", default=DEFAULT_SIZE[1])
    bind_input(wf, "frames", frames, "value", default=DEFAULT_FRAMES)
    bind_input(wf, "fps", fps, "value", default=DEFAULT_FPS)
    bind_output(wf, "video", save_video, artifact_kind="video", mime_type="video/mp4", filename_prefix=OUTPUT_PREFIX)
    return wf
```

The compiled Comfy API still uses numeric links internally. The readability
change is at the Python authoring surface.

## Shared Helper API

Do not add `source_id=` or `outputs=` directly to `VibeWorkflow.node(...)`.
`VibeWorkflow.node()` passes keyword arguments to the Comfy node, so helper-only
arguments could collide with real node inputs.

Introduce a separate helper module, for example `vibecomfy.ready_helpers`:

```python
def ready_node(
    wf: VibeWorkflow,
    class_type: str,
    *,
    source_id: str | None = None,
    outputs: tuple[str, ...] | None = None,
    output_types: tuple[str | None, ...] | None = None,
    extras: dict[str, object] | None = None,
    **kwargs,
) -> NodeHandleBuilder:
    ...
```

Responsibilities:

- call `wf.node(class_type, **kwargs)`;
- preserve the source node id either as the actual node id or as
  `node.metadata["source_node_id"]`;
- store `node.metadata["output_names"]` and `node.metadata["output_types"]`;
- apply `extras` for non-identifier input names such as dotted fields;
- update edges when source-id remapping is used;
- remain a thin authoring helper, not a second workflow IR;
- avoid template policy, requirements, runtime packages, or capability semantics;
- avoid runtime schema lookup inside generated templates. Schema-derived names
  should be baked into emitted metadata by the converter.

Input registration also needs a helper or lifecycle rule. Today
`VibeWorkflow.finalize_metadata()` clears `workflow.inputs`, so public input
registration must happen after finalization unless `finalize_metadata()` is
changed to preserve manual inputs.

Required rule:

```python
wf.finalize_metadata()
apply_ready_template_policy(...)
bind_input(wf, "prompt", positive_prompt, "text", default=DEFAULT_PROMPT)
```

Tests must prove that `wf.set_input("prompt", "...")` updates the intended node
after build and changes the compiled API at the expected field. `bind_input`
should validate that the node exists and the resolved field exists in
`node.inputs` or `node.widgets`; a bad binding should fail early rather than
silently writing to the wrong dict.

Helper rollout gate: do not emit generated public inputs until this lifecycle is
settled. Either `bind_input`/`bind_output` are explicitly post-finalize,
contract-aware operations, or `finalize_metadata()` is changed and tested to
preserve manual bindings. The generated skeleton assumes the post-finalize
contract-aware model.

Output registration should be explicit for public artifacts:

```python
bind_output(wf, "video", save_video, artifact_kind="video", mime_type="video/mp4", filename_prefix=OUTPUT_PREFIX)
```

This can coexist with `finalize_metadata()` output inference, but strict-ready
templates should expose stable public output names and artifact expectations.

## Future Import Pipeline

### 1. Use schema before emission

The converter should select schema through a provenance-aware composite provider.
Current `get_schema_provider("auto")` chooses one provider; implementing this
plan requires conversion-time composition and source labels.

Desired precedence:

1. committed `node_index.json` or other pinned repo-owned schema snapshot;
2. source parser for `INPUT_TYPES`, `RETURN_TYPES`, and `RETURN_NAMES`;
3. cached object_info only when the cache records matching custom-node package,
   version/hash, and generation source;
4. local widget alias table as a fallback;
5. live/runtime `/object_info`, only when explicitly requested.

Default conversion should stay deterministic and offline. Live runtime
`/object_info` should require an opt-in flag such as `--runtime-object-info` and
should record the server URL/cache key as provenance. It must not unexpectedly
start Comfy or depend on runtime state during a normal local import.

The selected schema provider should flow into emission, not only post-emission
validation.

Each class schema should record:

- provider name;
- package/repo/version/hash when known;
- cache path/source path/server URL;
- confidence level;
- conflicts with lower-priority providers;
- reason a lower-priority source was ignored.

When providers disagree, prefer higher-priority evidence but keep conflict
diagnostics. Do not silently rewrite widgets or outputs from a conflicting schema
without a parity check.

For each node, normalize schema details into `VibeNode.metadata`:

```python
node.metadata["output_names"] = ["model", "clip", "vae"]
node.metadata["output_types"] = ["MODEL", "CLIP", "VAE"]
node.metadata["input_aliases"] = {"widget_0": "ckpt_name"}
node.metadata["schema_source"] = "object_info"
```

This is a metadata schema migration. Current import mostly stores only
`output_names`, and only when every output has a name. The new metadata needs
tests for partial outputs, blank names, duplicate names, and provider conflicts.

### 2. Emit readable graph code

The emitter should:

- generate `_outputs=(...)` or `outputs=(...)`;
- generate `.out("name")` for known outputs;
- resolve `widget_N` to schema-backed field names;
- hoist repeated author-facing literals to constants;
- pick semantic variable names from graph role and downstream usage;
- emit real public input registrations;
- use a shared helper instead of copying `_node` into every template.

Named output emission algorithm:

1. For each incoming edge `(from_node, from_slot)`, look up the source node's
   `metadata["output_names"]`.
2. Emit `.out("name")` only when `from_slot` is in range and the name is unique,
   non-empty, and stable.
3. If the name is blank, duplicated, unknown, or from a conflicting schema,
   keep `.out(n)` and emit a diagnostic.
4. Compile the emitted template and verify the resulting API still uses the same
   numeric link target.

Widget alias safety rules:

- resolve `widget_N` only when schema/widget evidence maps it unambiguously;
- use parity tests to catch UI widget-order drift;
- keep `widget_N` with a diagnostic when schema order is uncertain;
- allow a manual override table for known bad custom-node schemas.

Model asset safety rules:

- compare model-like values in the original compiled API, regenerated compiled
  API, `READY_REQUIREMENTS["models"]`, `workflow.requirements.models`, and
  `READY_METADATA["model_assets"]`;
- fail strict-ready regeneration when aliasing hides or drops model filenames;
- keep unresolved model-like values as diagnostics until a model asset or
  registry entry is declared.

### 3. Keep runtime materialization numeric

`_NodeBuilder.out("vae")` should return a `Handle` with the numeric slot stored
internally. `workflow.compile("api")` should continue to produce Comfy-compatible
numeric links. Names are for authoring, diagnostics, contracts, and human/agent
understanding.

### 4. Preserve parity before readability churn

Before changing emitter behavior broadly, add a parity harness:

- original normalized API vs regenerated-template compiled API;
- widget value mapping snapshots;
- import/build/compile/schema validation;
- output node count and expected artifact comparison;
- representative fixtures across image, edit, audio, video, custom-node, and
  subgraph-heavy workflows.

Semantic variable naming and constant hoisting should come after schema/widget
correctness and helper consolidation. They create larger diffs and should not be
allowed to obscure parity regressions.

Variable naming must be deterministic. Use a stable priority order such as
public role name, unique output/artifact role, known node alias table, class-type
slug, then source id suffix for collisions. Regeneration tests should fail if
unchanged source material produces different variable names or avoidable noisy
diffs.

## Existing Workflow Cleanup

### Generated templates

Generated templates should be regenerated through the improved emitter.

Do not hand-edit generated templates except when the generator cannot represent
the needed shape. If a generated template requires substantial manual work,
change its marker to manual and record why.

Regeneration must be atomic:

- emit to a temporary file;
- import/build/compile/schema-check/parity-check the temporary file;
- replace the target only after all checks pass;
- provide dry-run/diff mode for review;
- refuse to overwrite `# vibecomfy: manual` files unless an explicit
  manual-template repair command is used.

Regeneration also needs a manifest before broad rewrites. Each generated ready
template should have machine-readable provenance: ready id, source JSON/path,
source hash, emitter version, schema source hashes, patch/override files,
generated/manual marker, app-active/required status, and last successful parity
evidence. Without this manifest, regeneration can accidentally compare old
Python to new Python instead of proving parity with the original graph.

### Manual templates

Manual templates should be repaired conservatively:

- replace `.out(n)` with `.out("name")` only when schema or existing metadata
  maps the slot unambiguously;
- add output names/types to nodes where known;
- hoist repeated literals into constants;
- add or repair public input registration;
- wrap dense one-line nodes;
- add sparse section comments to long workflows.

Manual semantic renames should be reviewed. They are worthwhile for app-active
routes but riskier than output/widget rewrites.

Manual repair tooling should exist before app-active curation starts. It should
parse generated/manual markers, offer dry-run diffs, emit a per-file review
packet, and separate safe mechanical rewrites from semantic edits. Mechanical
mode can apply unambiguous output-name, formatting, and metadata repairs.
Semantic mode should require explicit review for variable renames, function
extraction, public input choices, and subgraph promotion.

## Existing Template Migration Matrix

| Template class | Allowed approach | Gates |
| --- | --- | --- |
| Generated scratchpad | Regenerate freely | import/build/compile parity |
| Generated ready template | Regenerate through canonical emitter | strict-ready warnings, compile parity, output parity |
| Manual app-active template | Conservative AST fixes plus human review | strict-ready errors, contract validation, app-specific tests |
| Manual supplemental template | Conservative fixes when touched | strict-ready warnings unless promoted |
| Reference-only/blocked template | Keep explicit marker and reason | no app-active route without promotion |
| Opaque subgraph import | Scratchpad only until expanded or replaced | strict-ready fail |

Baseline inventory should happen before implementation:

- count positional outputs;
- count `widget_N` fields;
- count UUID class types and `n_<uuid>` variables;
- list generated/manual/app-active/supplemental templates;
- list templates with missing model assets, missing public inputs, and missing
  outputs.

## Subgraphs: Practical Policy

Subgraphs need two different treatments depending on what they represent.

### Opaque imported subgraphs

If a workflow import contains a UUID class type or an opaque component node, do
not silently promote it to a strict ready template.

Policy:

- scratchpad import: allowed with a warning;
- supplemental/reference ready template: allowed only with an explicit marker and
  explanation;
- app-active or strict ready template: fail until the subgraph is expanded,
  replaced, or promoted into a named Python block whose nodes, inputs, outputs,
  requirements, and parity are testable.

The issue is not only readability. Opaque subgraphs hide runtime requirements,
inputs, outputs, model files, and failure modes.

Current conversion code may treat opaque component diagnostics as hard errors
before mode-specific policy is applied. Implementing this policy requires
severity to depend on conversion mode: scratchpad warnings, strict-ready errors.

### Reusable subgraphs as Python functions

When an imported subgraph is repeated or semantically meaningful, the practical
target should be a Python function/block that mutates a workflow and returns
named handles.

Do not satisfy strict-ready by wrapping an opaque UUID runtime node in a nicer
Python name. Promotion means the hidden graph is represented as real workflow
builder code, or replaced by a known first-class node whose requirements and
contract are declared.

Example shape:

```python
from typing import NamedTuple


class GuideHandles(NamedTuple):
    positive: Handle
    negative: Handle
    latent: Handle


def ltx_first_last_guides(
    wf: VibeWorkflow,
    *,
    first_image: Handle,
    last_image: Handle,
    base_positive: Handle,
    base_negative: Handle,
    latent: Handle,
    vae: Handle,
    source_ids: dict[str, str] | None = None,
    first_strength: float = 1.0,
    last_strength: float = 1.0,
) -> GuideHandles:
    source_ids = source_ids or {}
    first_guide = ready_node(
        wf,
        "LTXVAddGuide",
        source_id=source_ids.get("first_guide"),
        outputs=("positive", "negative", "latent"),
        frame_idx=0,
        strength=first_strength,
        image=first_image,
        latent=latent,
        negative=base_negative,
        positive=base_positive,
        vae=vae,
    )
    last_guide = ready_node(
        wf,
        "LTXVAddGuide",
        source_id=source_ids.get("last_guide"),
        outputs=("positive", "negative", "latent"),
        frame_idx=-1,
        strength=last_strength,
        image=last_image,
        latent=first_guide.out("latent"),
        negative=first_guide.out("negative"),
        positive=first_guide.out("positive"),
        vae=vae,
    )
    return GuideHandles(
        positive=last_guide.out("positive"),
        negative=last_guide.out("negative"),
        latent=last_guide.out("latent"),
    )
```

Use this when:

- the same graph fragment appears in multiple templates;
- a fragment has stable semantic inputs/outputs;
- the function name explains the graph better than individual nodes;
- the function can be tested independently by compiling its resulting workflow.

Do not force every group box into a function. Some imported groups are visual
organization, not reusable abstractions. A good rule: extract only when it makes
the calling workflow easier to read and the function has a stable domain name.

For now, preserve actual source node ids as `VibeNode.id` during generation.
Moving to semantic node ids is a separate migration that requires a source-id
provenance map and stronger parity tests. If that later happens, store the
original id in `node.metadata["source_node_id"]` and expose it in contracts.

## Conversion Path Consolidation

There should be one canonical conversion implementation.

Target:

```bash
python -m vibecomfy.cli port check <workflow> --json
python -m vibecomfy.cli port convert <workflow> --out out/scratchpads/<name>.py --json
python -m vibecomfy.cli port convert <workflow> --ready-id <kind>/<name> --out ready_templates/<kind>/<name>.py --json
python -m vibecomfy.cli port check ready_templates/<kind>/<name>.py --strict-ready-template --json
```

The older `vibecomfy convert` path should be removed after any unique behavior is
migrated into the canonical `port convert` implementation. Do not keep a wrapper
that can drift or hide which conversion path was used. If someone invokes the
old command, it should fail with a short migration message pointing to `port
convert`.

Before removal, inventory the old path for useful behavior:

- raw workflow loading quirks;
- scratchpad compatibility;
- API-dict fallback behavior;
- tests or fixtures that rely on the older output shape.

Add golden tests before replacement:

- old CLI invocation receives a clear migration error;
- ready-id behavior is preserved through `port_convert_workflow()`;
- API-dict fallback behavior is either preserved or explicitly unsupported;
- any migrated legacy behavior is covered on the canonical path.

After consolidation:

- docs should point only to `port check` / `port convert`;
- the agent skill should describe that path as canonical;
- tests should cover the old command removal error message;
- new conversion work should land in one module, not two.

## Doctor And CI

Add a readability tier to the ready-template doctor.

Current code has top-level `doctor` and `port check --strict-ready-template`.
Either add a new workflow-scoped doctor command intentionally, or implement this
as shared diagnostics surfaced by:

```bash
python -m vibecomfy.cli doctor <workflow> --readability --json
python -m vibecomfy.cli port check <workflow> --strict-ready-template --json
```

Diagnostics should include:

- `avoidable_positional_output`;
- `schema_backed_widget_alias_not_resolved`;
- `uuid_class_type_in_ready_template`;
- `uuid_variable_name`;
- `missing_public_input_registration`;
- `metadata_unbound_input_not_registered`;
- `model_filename_not_declared`;
- `large_inline_author_literal`;
- `generated_template_has_local_node_helper`;
- `large_template_missing_sections`;
- `contract_missing_input_binding`;
- `contract_missing_output_names`;
- `public_input_missing_target`;
- `public_input_points_to_missing_field`;
- `duplicate_public_input_without_alias_metadata`;
- `disconnected_public_input`;
- `output_name_collision`;
- `output_handle_name_type_mismatch`;
- `missing_output_artifact_contract`;
- `generated_variable_name_too_long`;
- `long_one_line_node_call`;
- `strict_template_has_local_node_helper`;
- `generated_template_not_formatted`;
- `public_input_does_not_change_compiled_api`;

Rollout:

1. warnings only, to establish baseline;
2. errors for high-confidence strict-ready issues;
3. CI gate for app-active and required templates;
4. broader CI gate after generated templates are regenerated.

Because agents and CI will consume these diagnostics, diagnostic stability is a
public contract. Add snapshot tests for diagnostic code names, severity levels,
JSON fields, text/JSON consistency, and severity transitions before promoting
warnings to errors.

## Runtime Contract Updates

The runtime contract should record the workflow's public and graph surface, not
only package/runtime requirements.

This is an additive migration on the existing runtime contract. Keep
`WorkflowRuntimeContract.version == 1` during the migration window. Current
contracts store legacy `inputs` as `list[str]` and legacy `outputs` as compact
node dictionaries; those fields remain intact for old consumers. The public v2
descriptor data is exposed under explicit additive fields instead of changing
the meaning of legacy fields.

Add `contract_shape`, `public_inputs`, `public_outputs`, and `graph_contract`
fields from the shared serializer in `vibecomfy/contracts/model.py`. Keep
legacy `inputs` and `outputs` intact until downstream consumers migrate:

```json
{
  "version": 1,
  "contract_shape": "workflow_runtime_contract.v1.public_descriptors.v2",
  "inputs": ["prompt"],
  "public_inputs": [
    {
      "name": "prompt",
      "target": {"node_id": "128", "field": "text"},
      "default": "The camera moves...",
      "type": "STRING",
      "required": false,
      "aliases": []
    }
  ],
  "public_outputs": [
    {
      "name": "video",
      "node_id": "68",
      "artifact_kind": "video",
      "mime_type": "video/mp4",
      "filename_prefix": "output",
      "expected_cardinality": "one"
    }
  ],
  "graph_contract": {
    "schema_sources": ["object_info", "source"],
    "named_output_coverage": 0.98,
    "unresolved_positional_outputs": [],
    "unresolved_widgets": [],
    "nodes": [
      {
        "node_id": "127",
        "class_type": "CheckpointLoaderSimple",
        "outputs": [
          {"slot": 0, "name": "model", "type": "MODEL"},
          {"slot": 1, "name": "clip", "type": "CLIP"},
          {"slot": 2, "name": "vae", "type": "VAE"}
        ]
      }
    ]
  }
}
```

Alias semantics are descriptor metadata, not a legacy `inputs` replacement:
primary input names continue to appear in legacy `inputs`, and aliases appear
only in `public_inputs[].aliases`. Primary names win over aliases. Alias
collision handling is strict in the IR/helper layer: duplicate aliases, aliases
that equal any primary name, and primary names that equal existing aliases fail
at bind/registration time instead of creating ambiguous callable names.

Reigh and Astrid should be able to inspect this contract to understand:

- what can be set before a run;
- what output artifacts to expect;
- whether the workflow source is strict-ready or still a scratchpad/reference
  import;
- what schema evidence was used to name handles and inputs.

Split pre-run contracts from post-run manifests. `public_outputs` describes what
the workflow is expected to produce before queueing, including semantic output
names and expected artifact metadata such as kind, MIME type, filename prefix,
and cardinality when known. A run artifact manifest records what was actually
produced after execution, keyed by the same semantic output names when
confidently attributable and by `unmapped` otherwise. Legacy run metadata fields
such as `artifact_paths` and `outputs` remain as produced path lists for old
consumers; they are not the pre-run output contract.

## Agent Skill And Documentation Updates

The agent-facing skill and human docs should say the same thing:

- raw JSON is import material, not the reusable source of truth;
- canonical low-level path is `port check` then `port convert`;
- once implemented, the default agent/human path for a ready-template candidate
  is the staged `port ready` command, which runs preflight, conversion, contract
  draft, diagnostics, review packet generation, and promotion gates;
- strict ready templates require named outputs, named widgets, declared assets,
  registered inputs, and no opaque subgraphs;
- old conversion commands are removed with clear migration errors after their
  useful behavior is migrated;
- subgraphs should be expanded or extracted into named Python functions/blocks
  before promotion when they carry semantic workflow logic;
- named `.out("...")` is supported when node metadata contains output names;
  older docs saying named outputs are unavailable must be corrected in the same
  implementation series.

Docs should update with each public surface change, not only at the end. Every
phase that changes commands, helper APIs, contract fields, or generated-template
style should include matching README/skill/example updates.

Docs to update through the implementation:

- `README.md`;
- `docs/authoring.md`;
- `docs/templates/porting_workbench.md`;
- `docs/templates/adding_templates_models.md`;
- `docs/agent-skill/SKILL.md`;
- any installed Codex/Hermes skill copy, if this repo owns one.

## Example-Driven Acceptance

The cleanup is not done until an agent/developer can complete this path without
opening the generated Python:

1. load a ready template by id;
2. print all settable inputs with type/default/range/aliases;
3. set prompt, seed, frames, and media path inputs;
4. compile API and verify the intended fields changed;
5. dry-run or run through the selected runtime;
6. locate produced artifacts by semantic output name;
7. see missing model/custom-node/runtime requirements before queueing.

## Implementation Sequence

1. Baseline inventory: count positional outputs, widget aliases, opaque UUID
   classes, local helper copies, missing outputs, and generated/manual/app-active
   template categories.
2. Add parity harnesses before changing emitters: original API vs regenerated
   API, widget-value snapshots, output artifact counts, and representative
   image/edit/audio/video fixtures.
3. Inventory conversion paths and add golden tests for legacy `vibecomfy convert`
   behavior before changing either path.
4. Migrate useful legacy behavior into the canonical `port convert` path, then
   remove the old command with a clear migration error. The end state may keep a
   failing command handler that prints the migration message, but not a
   behavioral wrapper.
5. Thread `schema_provider` into the emitter and enrich node metadata before
   rendering Python.
6. Emit schema-backed widget aliases and `_outputs=(...)`.
7. Emit named `.out("...")` handles where safe.
8. Add shared ready-template helper functions before mass regeneration, including
   the finalized `bind_input` / `bind_output` lifecycle gate.
9. Emit public input registrations from schema, metadata, and capability rules
   only after `set_input()` mutation tests pass for generated bindings.
10. Expand runtime contracts with input bindings, graph contract fields, and
    output artifact contracts.
11. Add readability doctor diagnostics as warnings.
12. Add and populate the template regeneration manifest, then regenerate
    generated templates category by category with compile-equivalence gates.
13. Add semantic variable naming and constant hoisting once parity is stable.
14. Manually repair app-active/manual templates.
15. Promote strict-ready diagnostics to errors and CI gates.
16. Keep docs and agent skill instructions updated alongside each public surface
    change; final pass checks that agents follow the canonical path.

## Two-Week Sprint Breakdown

This is a feature-complete path split into ambitious but bounded two-week
sprints. Each sprint should leave the repo better than it found it and should
avoid depending on broad manual cleanup before the mechanical pipeline is safe.

### Sprint 1: Safe Compiler Foundation ✅ (Completed)

Goal: make conversion safe to run repeatedly before changing generated output
style broadly.

Scope (all completed):

- ✅ `port inventory --ready --json` — baseline inventory command for ready-template readability issues;
- ✅ Parity harness comparing original normalized API to emitted-template compiled API;
- ✅ Widget-value snapshot comparison for representative workflows (image, edit, audio/TTS, Wan, LTX, opaque);
- ✅ Atomic conversion writes: temp file, validate/parity check, then replace (`port_convert_and_write`);
- ✅ `--dry-run` / `--diff` mode for regeneration;
- ✅ Explicit refusal to overwrite `# vibecomfy: manual` templates (`ManualTemplateRefusal`);
- ✅ Golden tests for legacy `vibecomfy convert` behavior;
- ✅ Legacy converter removed — exits non-zero with migration message pointing to `port check` / `port convert`;
- ✅ Regeneration manifest schema (`ready_templates/sources/manifests/ready_regeneration.json`);
- ✅ All docs updated: README, AGENTS, authoring, porting workbench, adding templates/models, cleanup plan.

Representative fixtures:

- one simple image workflow;
- one edit workflow;
- one audio/TTS workflow;
- one Wan video workflow;
- one LTX workflow;
- one workflow with unresolved/opaque subgraph behavior.

Exit criteria:

- failed conversion cannot overwrite a checked-in template;
- generated output can be parity-checked before promotion;
- legacy conversion behavior migrated to the canonical path is documented and
  tested;
- docs/skill say new work uses `port check` / `port convert`.
- every generated ready template has known source provenance or is flagged for
  manual/reference review before regeneration.

### Sprint 2: Schema-Backed Readable Emission

Goal: make future generated templates use named outputs and safe widget aliases
without changing semantics.

Scope:

- conversion-time provenance-aware schema composition, offline by default;
- opt-in live `/object_info` evidence flag with provenance;
- enriched node metadata for output names/types, widget aliases, and schema
  source;
- named output emission algorithm with numeric fallback diagnostics;
- schema-backed widget alias emission with parity guardrails;
- model-like value comparison across original API, regenerated API,
  requirements, and metadata assets;
- strict/readability diagnostics as warnings for avoidable positional outputs,
  unresolved schema-backed widgets, hidden model filenames, and output-name
  ambiguity.

Exit criteria:

- emitter uses `.out("name")` only when names are unique and safe;
- schema-backed `widget_N` values are translated where parity proves it;
- ambiguous output/widget cases remain numeric/positional with diagnostics;
- representative fixtures compile to equivalent API.

### Sprint 3: Public Helper And Template Shape

Goal: make emitted Python look like maintainable workflow-builder code rather
than a copied graph dump.

Scope:

- introduce shared ready-template helpers:
  `ready_workflow`, `ready_node`, `finalize_ready_template`, `bind_input`,
  `bind_output`;
- settle helper lifecycle: `bind_input`/`bind_output` are post-finalize,
  contract-aware operations, or `finalize_metadata()` preserves them with tests;
- add focused tests that `set_input()` mutates the compiled API for helper-bound
  inputs before generated templates emit public input bindings;
- remove local `_node` helper boilerplate from newly generated strict-ready
  templates;
- enforce generated-template anatomy:
  imports, constants, metadata, optional blocks, `build()`;
- add selective constant hoisting for public defaults, model names, output
  prefixes, guide strengths, and repeated presets;
- add section comments for large generated workflows;
- add style diagnostics for local helpers, long one-line node calls, unformatted
  output, and excessive generated variable names;
- keep semantic variable naming conservative and parity-safe.

Exit criteria:

- new generated templates use shared helpers;
- output is formatted and sectioned;
- public helper API has focused tests;
- helper/input lifecycle is frozen before generated public input emission;
- generated code quality warnings exist before mass regeneration.

### Sprint 4: Public Inputs, Outputs, And Contract V2

Goal: make ready templates usable as public APIs without opening source.

This is the riskiest API sprint. It should start with an explicit contract-shape
freeze gate: one canonical inspect JSON shape, one pre-run workflow contract
shape, one post-run artifact manifest shape, and documented behavior for legacy
`inputs`.

Scope:

- implement public input descriptors with type, default, required, range,
  aliases, target, and media semantics;
- implement `bind_input` validation so bad targets fail early;
- prove `set_input()` mutates the intended compiled API field;
- implement public output/artifact descriptors via `bind_output`;
- add additive contract fields: `public_inputs`, `public_outputs`,
  `graph_contract`;
- keep legacy contract `inputs` intact during the migration window;
- add contract v1/v2 round-trip and text/JSON CLI snapshot tests;
- make `inspect --json` the canonical agent discovery surface, with `doctor` and
  `port check` reusing the same structured model where relevant;
- update list/inspect output so agents can discover inputs, outputs, model
  assets, custom nodes, and artifact expectations.

Exit criteria:

- an agent can list settable inputs and expected outputs without reading Python;
- public input aliases are explicit metadata;
- output artifacts have stable semantic names;
- pre-run output contracts and post-run artifact manifests are distinct;
- old contract consumers keep working.

### Sprint 5: Import-To-Ready Orchestrator

Goal: provide a default staged process for taking a raw workflow to a ready
candidate.

Scope:

- add a VibeComfy-owned command such as:
  `python -m vibecomfy.cli port ready <workflow> --ready-id <kind>/<name>`;
- staged execution:
  preflight, schema enrichment, mechanical conversion, compile parity, contract
  draft, readability doctor, manual review packet, final gates, atomic promote;
- manual review packet for ambiguous widgets, output names, public knobs,
  subgraphs, models, and runtime requirements;
- mode-specific opaque subgraph policy:
  scratchpad warning, strict-ready error;
- clear status output and JSON artifacts for agents;
- no RunPod or live runtime by default.

Exit criteria:

- clean workflows can become ready-template candidates through one command;
- ambiguous workflows produce actionable review packets instead of bad templates;
- the command does not overwrite manual files or skip gates.

### Sprint 6: Generated Template Regeneration

Goal: apply the new pipeline to existing generated templates category by
category.

Scope:

- regenerate generated image templates;
- regenerate generated edit templates;
- regenerate generated audio templates;
- regenerate generated video templates in batches;
- require a populated regeneration manifest entry before replacing any generated
  ready template;
- run parity, strict-ready warnings, formatting, and index checks per batch;
- keep manual templates untouched except for explicitly approved repairs;
- update template indexes and coverage manifests as needed.

Exit criteria:

- generated templates no longer carry local helper boilerplate where strict-ready
  eligible;
- avoidable `.out(n)` and schema-backed `widget_N` are substantially reduced;
- generated templates compile equivalently to source material;
- no manual app-active workflow is overwritten.

### Sprint 7: Manual And App-Active Curation

Goal: bring important manual/app-active routes to the higher elegance bar.

Scope:

- curate LTX first/last and other app-active video routes;
- build/use manual repair tooling with marker parsing, dry-run AST rewrites,
  review packets, and separate mechanical vs semantic modes;
- hoist constants and section long `build()` functions;
- replace remaining avoidable positional handles;
- add or repair public inputs and output artifacts;
- extract repeated semantic subgraphs into named functions/blocks only when they
  make the caller easier to read;
- validate runtime contracts and app-specific semantic contracts;
- update Reigh/Astrid consuming expectations where needed.

Exit criteria:

- app-active templates are readable, inspectable, and elegant Python;
- public input/output contracts match Reigh/Astrid needs;
- no opaque subgraph remains in app-active strict-ready workflows.

### Sprint 8: Strict Gates And Documentation Finalization

Goal: make the new standard durable.

Scope:

- promote high-confidence diagnostics from warnings to strict-ready errors;
- add CI gates for required/app-active templates;
- add broader CI checks for generated-template style where stable;
- finalize README, authoring docs, template porting workbench docs, adding
  templates docs, and agent skill copies;
- add example-driven acceptance tests:
  discover, inspect, set inputs, compile, dry-run/run, locate artifacts;
- document remaining exceptions with owners and follow-up tickets.

Exit criteria:

- future imports default to the clean path;
- required/app-active workflows cannot regress into hidden widgets, unnamed
  outputs, missing public inputs, or opaque subgraphs;
- agents have one documented path from raw workflow to ready template;
- remaining non-compliant templates are explicitly categorized as reference,
  supplemental, blocked, or scratchpad-only.

## Megaplan Profiles

Each two-week sprint should be its own megaplan. Do not run this whole roadmap
as one megaplan; the brief-to-execution distance would be too large and review
would lose focus.

Recommended profile choices:

| Sprint | Recommended profile | Why |
| --- | --- | --- |
| 1. Safe Compiler Foundation | `thoughtful//high @codex` | Cross-cutting compiler safety and atomic-write behavior; planner needs repo structure in view. |
| 2. Schema-Backed Readable Emission | `thoughtful//high @codex` | Schema enrichment, widget aliasing, and named output emission have subtle parity risks. |
| 3. Public Helper And Template Shape | `thoughtful//medium @codex` | New helper API plus generated style; judgment matters, but scope is narrower after Sprints 1-2. |
| 4. Public Inputs, Outputs, Contract V2 | `premium/standard/high @codex` | Public contract shape affects VibeComfy, Reigh, Astrid, and agents; this is the highest-stakes API sprint. |
| 5. Import-To-Ready Orchestrator | `thoughtful//high @codex` | Staged command touches many surfaces and must preserve safety gates. |
| 6. Generated Template Regeneration | `basic/standard` or `led/standard @codex` | Mostly mechanical once the pipeline is safe; use `led` if batch planning/order is non-trivial. |
| 7. Manual And App-Active Curation | `thoughtful//medium @codex` | Domain judgment over important workflows; less compiler architecture. |
| 8. Strict Gates And Documentation Finalization | `thoughtful/standard/medium @codex` | Cross-cutting policy/docs/CI work with moderate judgment. |

Use `+prep` only when a sprint brief depends on unknown external Comfy or
object_info behavior. The default should stay no-prep because most discovery is
inside this repo. Escalate Sprint 4 to `super-premium/robust/high` only if the
team is actively deciding a cross-system contract that downstream sprints cannot
change later.

Example starts:

```bash
megaplan init <sprint-1-brief> --profile thoughtful --depth high --vendor codex
megaplan init <sprint-4-brief> --profile premium --depth high --vendor codex
```

## Decisions To Make Up Front

These decisions are accepted for the roadmap. Treat them as defaults during
implementation unless a later concrete code constraint proves one of them
wrong. Keeping them explicit prevents agents from stalling for human review or
making inconsistent local choices.

| Decision | Needed by | Accepted direction |
| --- | --- | --- |
| Legacy `vibecomfy convert` fate | ✅ Sprint 1 | Removed. The command exits non-zero with a migration message pointing to `port check` and `port convert`. Useful behavior (source acceptance) migrated to canonical `port convert`. No behavioral wrapper. |
| Default schema mode | Sprint 2 | Offline deterministic by default; live `/object_info` only behind explicit flag. |
| Output-name safety | Sprint 2 | Emit named `.out("...")` only for unique, non-empty, non-conflicting names; otherwise numeric fallback with diagnostic. |
| Widget alias conflict policy | Sprint 2 | Alias only when schema evidence plus parity agrees; keep `widget_N` with diagnostic otherwise. |
| Shared helper module/API names | Sprint 3 | `vibecomfy.ready_helpers`: `ready_workflow`, `ready_node`, `finalize_ready_template`, `bind_input`, `bind_output`. |
| Source id policy | Sprint 3 | Preserve source ids as actual `VibeNode.id` for now; defer semantic node ids to a later migration. |
| Public input alias semantics | Sprint 4 | One primary input name plus explicit aliases; duplicate bindings without alias metadata are diagnostics. |
| Contract evolution shape | Sprint 4 | Bias toward simplicity: add `public_inputs`, `public_outputs`, and `graph_contract` while keeping legacy `inputs`; avoid broader contract redesign unless forced. |
| Canonical agent JSON surface | Sprint 4 | `inspect --json` is the authoritative single-workflow discovery view. Other commands may reuse the same model but should not define competing shapes. |
| Output contract vs artifact manifest | Sprint 4 | `public_outputs` is pre-run expected output metadata. Produced paths belong in a post-run artifact manifest keyed by semantic output name. |
| Doctor surface | Sprint 5 or 8 | Shared diagnostics surfaced through top-level `doctor --readability` and `port check --strict-ready-template`. |
| Diagnostic stability | Sprint 5 or 8 | Diagnostic code names, severity levels, JSON fields, and text/JSON consistency are public enough to snapshot before CI promotion. |
| Opaque subgraph mode policy | Sprint 5 | Scratchpad warning, strict-ready/app-active error, with an explicit promotion path to proper Python code via named functions/blocks when the subgraph has stable semantic inputs/outputs. |
| Reusable subgraph promotion | Sprint 5-7 | Promote repeated or semantically coherent imported subgraphs into named Python functions/blocks when that makes the generated workflow easier to read or reuse. Do not preserve opaque wrappers as the final app-active shape. |
| Regeneration provenance | Sprint 6 | Require a regeneration manifest entry with source path/hash, schema hashes, emitter version, overrides, marker, status, and parity evidence before replacing generated templates. |
| Semantic variable naming | Sprint 6-7 | Deterministic priority order only; unchanged source material must not produce noisy variable-name diffs. |
| Manual template repair policy | Sprint 6-7 | Never overwrite `# vibecomfy: manual` through regeneration; provide explicit repair/codemod tools that can operate on manual templates under review. These tools should support safe mechanical fixes and separate reviewed semantic edits. |
| Regeneration overwrite policy | Sprint 6 | Generated files only, atomic replace after gates. Manual files require explicit repair command and review. |
| App-active template list | Sprint 7 | Declare the exact required/app-active workflows before manual curation starts. |
| Strict gate promotion threshold | Sprint 8 | Start with app-active/required templates only; broaden after exceptions are categorized. |

## Human Review Blockers To Remove

The import-to-ready process should not block on humans for mechanical questions.
Human review should be reserved for semantic choices where the code cannot know
intent.

Remove these blockers by encoding defaults and diagnostics:

- **Legacy conversion path choice:** remove the legacy path in Sprint 1 after
  migrating useful behavior into `port convert`.
- **Schema source ambiguity:** define offline-default precedence and conflict
  diagnostics before Sprint 2.
- **Named output ambiguity:** numeric fallback should be automatic; do not ask a
  human unless a strict-ready workflow needs a semantic name and schema cannot
  provide one.
- **Widget alias ambiguity:** keep `widget_N` plus diagnostic automatically when
  unsafe; do not block conversion.
- **Public input duplicates:** require primary name plus aliases; diagnostics
  identify accidental duplicate controls.
- **Manual-file overwrite:** automatic refusal removes the need for ad hoc human
  judgment during regeneration; manual-template repair uses explicit tools.
- **Opaque subgraphs:** mode-specific severity removes ambiguity: scratchpad can
  continue; strict-ready cannot until the subgraph is expanded, replaced, or
  promoted into a named function/block.
- **Runtime/live object_info:** opt-in flag removes hidden environment questions
  from normal conversion.

Keep human review for:

- choosing which weird upstream knobs are public API;
- deciding whether a repeated or semantically meaningful subgraph deserves a
  named function/block, and what that function's public inputs/outputs should be;
- naming outputs when no stable schema name exists but a human-facing artifact
  needs one;
- approving manual/app-active template curation;
- choosing whether a supplemental workflow should be promoted to required or
  app-active;
- resolving cross-system contract semantics in Sprint 4.

## Open Questions

- Which exact workflows are app-active/required for Sprint 7 curation?
- Which capability-level public inputs should be advisory vs hard-required once
  templates declare capability consistently?
- Which imported subgraph patterns are common enough to become shared
  first-class reusable blocks rather than per-template local functions?
- For promoted subgraphs, what is the minimum block contract: just inputs and
  returned handles, or also declared model/custom-node requirements and artifact
  outputs?
- Which supplemental/reference templates should be promoted, blocked, or left as
  scratchpad-only after generated regeneration?
- Does source-id-as-actual-node-id remain sufficient after this roadmap, or
  should a later migration introduce semantic node ids with source-id
  provenance?
- What should the manual-template repair command be called, and should it offer
  separate modes for safe mechanical rewrites vs reviewed semantic edits?
- Which manual-template repairs are safe enough for mechanical codemods, and
  which must remain explicit reviewed edits?
- What exact legacy `vibecomfy convert` behaviors, if any, must be migrated
  before the command is removed?
# Superseded

This historical plan predates the canonical import hard cut. Its command
examples describe the retired `port check`/`port convert` surface and are kept
only as historical context. Current workflows use `vibecomfy import`,
`validate`, `doctor`, and `templates create`; see `docs/authoring.md` and
`docs/templates/adding_templates_models.md`.
