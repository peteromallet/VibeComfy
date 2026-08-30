# Workflow Onboarding and Parity Tooling

## Goal

VibeComfy should make it easy for an agent or developer to take any workflow source, whether official, community, forked, or built from scratch, and turn it into a pure-Python, app-ready workflow with clear contracts and strong validation.

The bar is not only "it compiles to a Comfy prompt." The bar is:

- the runtime source of truth is pure Python;
- the workflow is easy to understand and edit;
- every app-visible input has a named patch point;
- every model, node pack, and runtime dependency is declared;
- the workflow can be validated before GPU time is spent;
- app parity can be checked against a reference implementation such as Wan2GP;
- performance, VRAM, outputs, and settings are captured in a repeatable way.

## Existing Pieces

VibeComfy already has most of the low-level machinery:

- `vibecomfy.ingest.normalize`
  Converts UI/API workflow JSON into `VibeWorkflow`.

- `vibecomfy.porting.workbench`
  Performs source-level port checks: workflow shape, helper/component diagnostics, custom-node suggestions, model asset analysis, widget alias checks, known runtime-required inputs, and schema validation.

- `vibecomfy.porting.emitter`
  Emits pure Python ready templates from `VibeWorkflow`.

- `tools/convert_ready_templates.py`
  Batch conversion and round-trip checking for legacy ready templates.

- `vibecomfy.registry.ready.ready_template_source_info`
  Classifies ready templates as pure Python, JSON references, JSON runtime wrappers, or API-dict wrappers.

- `vibecomfy.schema.validate`
  Validates compiled prompts against node schemas and catches missing required inputs, unknown inputs, and link shape/type issues.

- `vibecomfy.schema.cache` and `ConversionSchemaProvider`
  Reuse captured ComfyUI `/object_info` JSON as offline runtime schema evidence.
  This is the primary way to resolve installed custom nodes whose source parser
  misses dynamic inputs/outputs. `port check` and `port convert` default to the
  newest `out/cache/object_info*.json` when present, with
  `--object-info-cache` / `--no-object-info-cache` overrides.

- `vibecomfy.patches`
  Reusable graph mutation layer for things like resolution, seed, requirements, low-VRAM LTX changes, and ControlNet wiring.

- `vibecomfy.blocks`
  Authored workflow-building primitives for clean new Python workflows.

These are useful, but they stop one level too low. They can tell us that a graph is structurally valid, but not whether the graph satisfies app-level intent such as "stage 1 conditions on the first frame and stage 2 conditions on the last frame with Wan2GP-compatible sigmas."

## Implemented Pieces (Vertical Slice)

### 1. Semantic Graph Lens ✅

Location: `vibecomfy/lens/core.py`

`WorkflowLens` provides typed graph queries over `VibeWorkflow` without compiling Comfy API JSON. Available queries:

- `edge_source(to_node, to_input)` — returns `EdgeSource(node_id, output_index, output_name)` or `None` for widget-fed inputs
- `edge_targets(from_node)` — returns `[EdgeTarget(node_id, input_name), ...]`
- `edges_to_node(node_id)` — all incoming connections
- `edges_from_node(node_id)` — all outgoing connections
- `registered_input_target(name)` — which node/field a named app input connects to
- `upstream(node_id)` / `downstream(node_id)` — one-level traversal sets
- `outputs()` — `VibeOutput` list (e.g. SaveVideo nodes)
- `node(node_id)` — raw `VibeNode` lookup
- `node_value(node_id, field)` — widget or input value by field name
- `nodes_by_class_type(class_type)` — filtered node list
- `diagnostics()` — human-readable summary with `[node_id] class_type [pack] up={...} down={...}`

All queries operate on `workflow.nodes/edges/inputs/outputs` — no `compile()` call needed.

Example:

```python
from vibecomfy.lens import WorkflowLens

lens = WorkflowLens(workflow)
assert lens.registered_input_target("start_image").node_id == "2004"
assert lens.edge_source("4970", "image").node_id == "4992"
assert lens.node_value("4985", "scheduler.sigmas") == "0.909375, 0.725, 0.421875, 0.0"
print(lens.diagnostics())
```

CLI: `vibecomfy workflows lens <template-or-path> [--json]`

Tests: `VibeComfy/tests/test_workflow_lens.py` (21 tests covering authored workflows and LTX parity template)

### 2. Workflow Contracts ✅

Location: `vibecomfy/contracts/` (`validation.py`, `ltx_first_last.py`)

Contracts validate app-level semantic intent against a `VibeWorkflow`. They produce structured `ContractReport` objects with typed `ContractIssue` entries (code, message, severity, detail).

**`LTXFirstLastTwoStageContract`** — 10 focused checks:

1. Named inputs: 12 required (first_image, last_image, prompt, negative_prompt, seed_first, seed_last, width, height, frames, fps, stage_2_sigmas, seed_last_alt)
2. First/last conditioning: stage 1 on first frame, stage 2 on last frame (LTXVImgToVideoConditionOnly + LTXVPreprocess/ResizeImageMaskNode)
3. Prompt/negative paths: CLIPTextEncode fed by LTXAVTextEncoderLoader
4. Seeds: both RandomNoise nodes with noise_seed + control_after_generate=fixed
5. Dimensions/frames/FPS: EmptyLTXVLatentVideo width/height, PrimitiveInt frames, PrimitiveFloat fps
6. Stage-2 sigmas: ManualSigmas "0.909375, 0.725, 0.421875, 0.0"
7. Strength defaults: stage 1 and 2 widget_0 = 1.0
8. Custom nodes: ComfyUI-LTXVideo + ComfyUI-KJNodes
9. No Runexx-only packs: guards against LTXVAddGuide, LTXICLoRALoaderModelOnly, LTXAddVideoICLoRAGuide, LTX2MemoryEfficientSageAttentionPatch, LTX2SamplingPreviewOverride + rgthree-comfy
10. Video output: SaveVideo with upstream connectivity

All checks use `WorkflowLens` — no compiled Comfy API JSON access.

Example:

```python
from vibecomfy.contracts import LTXFirstLastTwoStageContract

contract = LTXFirstLastTwoStageContract()
report = contract.validate(workflow)
print(report.summary())  # "LTXFirstLastTwoStageContract: PASSED (0 errors, 0 warnings)"
for issue in report.errors:
    print(f"  [{issue.severity}] {issue.code}: {issue.message}")
```

CLI: `vibecomfy workflows contract-validate <template-or-path> --type ltx-first-last-two-stage [--json]`

> **Critical rule**: Tests must use contracts and lens for app-intent assertions. Compiled Comfy API JSON is **runtime materialization only**, not the workflow source of truth. App intent should be validated through `VibeWorkflow`, lens helpers, and contracts.

### 3. CLI Integration ✅

The existing `vibecomfy workflows` command family now includes:

```bash
# Lens: graph diagnostics for any template or workflow path
vibecomfy workflows lens <template-or-path> [--json]

# Contract validation: semantic app-intent checks
vibecomfy workflows contract-validate <template-or-path> --type ltx-first-last-two-stage [--json]
```

Both accept template IDs (e.g., `video/ltx2_3_lightricks_first_last_parity`) or file paths via `cli_loader.load_workflow_any()`.

Other existing workflow subcommands:
```bash
vibecomfy workflows list
vibecomfy workflows source-info <template-or-path>
vibecomfy workflows enrich-targets <template-or-path> [--hires-fix] [--resolution WxH]
```

The old `port check`, `port convert`, and `validate` commands remain available for porting workflows.

## Missing / Proposed Pieces

### App Route Contracts

For Reigh, each supported route should declare:
- route key;
- template ID;
- required capability;
- required input patch points;
- parity-sensitive settings;
- model and node-pack requirements;
- validation status;
- reference implementation;
- RunPod validation evidence.

Currently tracked in route-support docs (`docs/sprint-12-route-support.md`, worker-local trackers) and live-test manifests. Machine-readable route contracts are a follow-up item.

### Fork and Apply Helpers

Helpers for common workflow transformations (`vibecomfy workflow fork`) — deferred. The LTX first/last parity template was hand-authored as a pure-Python ready template.

### Parity Runner and Evidence Format

Standard evidence format for app parity runs. Current live-test flow (reigh-worker `scripts/live_test/`) captures run reports. Full VibeComfy-side parity runner is a follow-up item.

## Implementation Status

### Vertical Slice Complete

The first vertical slice (LTX 2.3 first/last no-control) is implemented end-to-end:

- **Lens**: `vibecomfy/lens/core.py` with `WorkflowLens` (14 query methods + module-level stateless equivalents)
- **Contracts**: `vibecomfy/contracts/` with `ContractReport`, `ContractIssue`, `LTXFirstLastTwoStageContract` (10 checks)
- **CLI**: `workflows lens` and `workflows contract-validate` subcommands with JSON and human-readable output
- **Tests**: Lens tests (21), contract-backed ready-template tests, CLI tests for lens/contract validation
- **Template**: `video/ltx2_3_lightricks_first_last_parity` — pure Python, 12 named inputs, Lightricks two-stage spine
- **Routing**: Both `ltx2` and `ltx2_distilled` no-control first/last routes resolve to the parity template
- **Adapter**: Scratchpad uses `workflow.set_input(...)` with named inputs — no Runexx node-id patching

### Backlog / Follow-up Slices

- Full Wan VACE contract coverage
- LTX raw-video guide and IC-LoRA control contracts
- Full animation/preprocess contracts
- Fork/apply CLI helpers
- Machine-readable route contracts
- Parity runner and comparison UX

## Design Principles

- **Pure Python is the source of truth.** JSON is allowed only as corpus/reference/input material.
- **Node IDs are allowed internally**, but public tests and contracts should speak in workflow concepts.
- **The workflow lens should be a thin query layer**, not a second workflow representation.
- **Contracts should be concise and route-focused**; avoid forcing every workflow into one universal schema.
- **Validation should happen before GPU runs** wherever possible.
- **Runtime evidence should be saved in a standard format.**
- **Agents should have one obvious workflow-onboarding path.**
- **Compiled Comfy API JSON is runtime materialization only** — app intent lives in `VibeWorkflow`, the lens, and contracts.

## Agent-Facing Commands (Quick Reference)

When onboarding, forking, or modifying a workflow, use this sequence:

```bash
# 1. Inspect the graph structure
vibecomfy workflows lens <template-or-path>

# 2. Validate app-intent semantics
vibecomfy workflows contract-validate <template-or-path> --type ltx-first-last-two-stage

# 3. Schema validation (runtime materialization)
vibecomfy validate <template-or-path>

# 4. Port check (source-level diagnostics)
vibecomfy port check <template-or-path> --strict-ready-template

# 4a. Optional: force a specific captured runtime schema
vibecomfy port check <template-or-path> --strict-ready-template --object-info-cache out/cache/object_info.<runtime>.json

# 5. Doctor (model/assets/runtime readiness)
vibecomfy doctor <template-or-path> --json
```

Agent checklist:
1. Identify the source and record provenance.
2. Run `vibecomfy workflows lens` for graph diagnostics.
3. Run `vibecomfy port check` for source-level issues.
4. Convert or author the workflow as pure Python.
5. Register named app patch points.
6. Attach or update a semantic contract.
7. Run `vibecomfy workflows contract-validate`.
8. Run `vibecomfy validate` for schema checks.
9. Ensure models, custom nodes, and runtime-only schema evidence are declared or captured.
10. Run a small local or RunPod smoke.
11. Run app-sized parity validation when promoting an app route.
12. Save evidence and update the route contract status.

> **Bright-line rule**: Do not treat compiled Comfy API JSON as the workflow source of truth. It is only the runtime materialization target. Tests may inspect compiled API for runtime smoke, but app intent should be validated through `VibeWorkflow`, lens helpers, and contracts.

## What Excellence Looks Like

An agent can say:

```bash
vibecomfy workflow onboard https://example.com/workflow.json --as video/new_flow --route reigh/foo
```

And VibeComfy guides it through:

- fetching the source;
- checking provenance;
- diagnosing missing nodes/models/inputs;
- converting to pure Python;
- suggesting semantic bindings;
- creating or updating a contract;
- validating the final template;
- running smoke tests;
- recording parity evidence.

The agent should spend time making real workflow decisions, not remembering which node ID feeds which input or rediscovering why a JSON-shaped graph failed at runtime.
</azureparameter>
