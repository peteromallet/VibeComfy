# Python Composition DSL Plan

> Superseded implementation note (2026-09-15): `@python_node` and the
> existing `vibecomfy.exec` runtime now provide the in-graph Python boundary.
> `VibeWorkflow` remains canonical, `vibecomfy.code` remains separate, and
> the historical `ExternalPythonNode` planning name is not a current class.
> See [the as-built exec note](vibecomfy_exec_node_design.md) and [the custom
> Python guide](../guides/custom-python-workflows.md).

## Settled Decisions

- **SD-001** - Keep `VibeWorkflow` as the canonical editable IR. _load_bearing: true_
  Rationale: the current package already normalizes, edits, validates, and compiles through `VibeWorkflow`; the composition layer should make that model easier to author, not replace it.
- **SD-002** - Treat HiddenSwitch GraphBuilder as an optional backend, not the authoring surface. _load_bearing: true_
  Rationale: `compile("graphbuilder")` exists for parity and runtime alignment, while direct `compile("api")` remains the transparent handoff path.
- **SD-003** - Treat ComfyScript as reference material and a possible import adapter, not the primary API. _load_bearing: true_
  Rationale: the plan needs VibeComfy-native Python that can be edited, linted, and traced without depending on live ComfyScript generation.
- **SD-004** - Make multi-stage Python orchestration the default model for mixing Comfy and ordinary Python. _load_bearing: true_
  Rationale: graph output -> Python transform -> next graph is clearer and safer than injecting arbitrary Python into an active Comfy graph.
- **SD-005** - Keep arbitrary Python outside active Comfy graph execution unless it is wrapped by the existing `vibecomfy.exec` runtime node. _load_bearing: true_
  Rationale: Comfy graph execution has serialization and runtime boundaries that ordinary Python objects do not satisfy.
- **SD-006** - Pin custom nodepacks by repository and immutable `git_commit_sha` when specified, with lockfile capture when defaulting to newest. _load_bearing: true_
  Rationale: custom node behavior is part of workflow reproducibility.
- **SD-007** - Provide escape hatches for raw workflow, raw JSON, raw node, and raw runtime configuration paths. _load_bearing: true_
  Rationale: the layer must improve common authoring without blocking workflows whose nodes or schemas are not typed yet.
- **SD-008** - Migrate ready templates manually and iteratively, treating the current Flux 4B native builder as a transition proof point *in spirit, not in API*, with a typed-handle rewrite against `wf.node(...).out(...)` as the canonical end-state. _load_bearing: true_
  Rationale: the repository currently contains many runtime-green API dictionaries; a big-bang migration would add risk without improving execution. The Flux 4B builder uses a private `node()` helper and string `connect()`, so it is not the shape new migrations should copy.
- **SD-009** - Add structured provenance for composition, source, and multi-stage flow execution. _load_bearing: true_
  Rationale: authors need to explain where a graph came from, what changed, and what artifacts moved between stages.
- **SD-010** - Make typed handles first-class and backward compatible with existing string references. _load_bearing: true_
  Rationale: typed handles unlock debugging and validation while preserving existing `node.slot` wiring conventions.
- **SD-011** - Gate direct debug execution helpers on typed handles and schema-backed output metadata. _load_bearing: true_
  Rationale: VibeComfy cannot infer safe preview/save taps until handles know their output types.
- **SD-012** - Keep this delivery to documentation only. _load_bearing: false_
  Rationale: implementation details can follow after the architecture and constraints are explicit.
- **SD-013** - Settle `VibeFlow` lifecycle semantics before P3 ships. _load_bearing: true_
  Rationale: cancellation, concurrency, run-dir naming, and resume identity are preconditions for P3, not tunables. Specifically: (a) cancellation shields the in-flight `Comfy.queue_prompt_api` call (`vibecomfy/runtime/session.py:144`) and propagates cancel by stopping the watchdog and recording the partial run; VibeComfy does not attempt to abort HiddenSwitch mid-prompt. (b) One `VibeFlow` runs stages serially against a single embedded session by default (`vibecomfy/runtime/session.py:92`); explicit multi-session opt-in is deferred. (c) Run-dirs become `out/runs/<flow-id>/stage-<n>/...` with a monotonic stage index, replacing the `run-<int(time.time())>` naming at `vibecomfy/runtime/session.py:127`. (d) `RunResult` gains `flow_id` and `stage_index` fields so resume and idempotency are possible.

## Desired Authoring Experience

The public API should read like ordinary Python that happens to execute Comfy graphs. Authors compose one graph, run it, inspect typed artifacts, transform with Python, and feed the result into the next graph without dropping into API dictionaries. These four shapes are the target, not a claim that every helper exists today.

Single-graph Template (Flux-style t2i, written against the proposed `wf.node().out()` API; compiles through `vibecomfy/workflow.py:170`):

```python
from vibecomfy import VibeWorkflow

wf = VibeWorkflow("flux_klein_4b_t2i")
clip   = wf.node("CLIPLoader", clip_name="t5xxl.safetensors").out("CLIP")
model  = wf.node("UNETLoader", unet_name="flux-2-klein-4b.safetensors").out("MODEL")
vae    = wf.node("VAELoader",  vae_name="flux-vae.safetensors").out("VAE")
cond   = wf.node("CLIPTextEncode", text="ceramic speaker, studio lighting", clip=clip).out("CONDITIONING")
latent = wf.node("EmptyLatentImage", width=1024, height=1024, batch_size=1).out("LATENT")
samples = wf.node("KSampler", model=model, positive=cond, latent_image=latent, seed=42).out("LATENT")
image  = wf.node("VAEDecode", samples=samples, vae=vae).out("IMAGE")
wf.node("SaveImage", images=image, filename_prefix="flux_klein")
```

Multi-stage VibeFlow with one Python transform between two graphs (orchestration container is the new piece; each `flow.run(...)` compiles a `VibeWorkflow` through `vibecomfy/workflow.py:170` and dispatches via `vibecomfy/runtime/session.py:144`):

```python
from vibecomfy import VibeFlow
from vibecomfy.templates import flux, ltx
from vibecomfy.python import image_ops

flow = VibeFlow("prompt_refine_video")
draft = flow.run(flux.klein.t2i("editorial portrait through rain on glass", model="4b", seed=42)).image
crop = image_ops.center_crop_square(draft)
caption = image_ops.describe(crop)
video = flow.run(ltx.i2v(crop, prompt=f"slow cinematic camera push, {caption}", frames=97)).video
flow.save(video, "final/portrait_video")
```

Custom-node use through the generic `wf.node(class_type=...)` path (covers any class known only by name, including UUID subgraphs; preserves the opaque pattern from `vibecomfy/blocks/subgraph.py:47`):

```python
wf = VibeWorkflow("custom_demo")
image = wf.node("LoadImage", image="input.png").out("IMAGE")
processed = wf.node(class_type="SomeCustomNode", image=image, widget_3=0.75).out(0)
wf.node("SaveImage", images=processed, filename_prefix="custom_demo")
```

Escape hatch via raw API dict (re-enters composition through a future `VibeWorkflow.wrap_api_dict`, so raw workflows can still participate in `VibeFlow` and yield `RunResult`/`Artifact` values; existing import path is `convert_to_vibe_format` at `vibecomfy/registry/ready_template.py:19`):

```python
api_dict = json.load(open("legacy_workflow.json"))
wf = VibeWorkflow.wrap_api_dict(api_dict, name="legacy_import")
result = flow.run(wf)            # participates in VibeFlow as a stage
api_workflow = wf.compile("api") # round-trips back to the raw dict
```

## Goals

- Provide a concise pure-Python authoring layer for users who want to tweak, refine, update, and combine ComfyUI workflows without hand-editing API dictionaries.
- Keep execution through HiddenSwitch and ComfyUI: Python composition builds `VibeWorkflow`, `VibeWorkflow` compiles to Comfy API JSON, and HiddenSwitch executes that graph.
- Make multi-stage orchestration first-class so ordinary Python can run before, after, and between Comfy graph executions using typed media/file handles.
- Add typed handles, artifacts, and provenance hooks that make debugging and workflow explanation easier than raw `node.slot` strings.
- Work with the current VibeComfy package without forking HiddenSwitch, ComfyUI, or the existing `VibeWorkflow` storage model.

## Non-Goals / Constraints

- This is not a new runtime. HiddenSwitch remains the execution boundary, either through embedded `Comfy()` or server-backed queueing.
- This is not a parallel workflow IR. `VibeWorkflow` remains canonical, matching the current class at `vibecomfy/workflow.py:74`.
- Authoring must not require a live `/object_info` request. A checked-in or cached schema snapshot is enough for typed affordances; raw/opaque nodes remain possible when schema data is missing.
- No direct single-node execution is promised as a core runtime feature. HiddenSwitch accepts whole-graph API dictionaries via `/prompt` and embedded `Comfy.queue_prompt_api`, so VibeComfy should compile small graphs when it needs focused debug runs.
- No arbitrary Python is injected inside an active Comfy graph. Runtime Python inside a graph would have to cross an explicit serialized node boundary; the planned `ExternalPythonNode` (P3) is the eventual mechanism. Until it ships, the request is refused rather than routed.

## API Concepts

- **Template** - the reusable single-graph builder shape. A template exposes its underlying `VibeWorkflow`, default requirements, metadata, and documented override points.
- **VibeFlow** - the multi-stage orchestration container. It runs one or more graph stages and ordinary Python stages in order, carrying typed artifacts between them.
- **Nodes** - `wf.node(class_type, **kwargs)` is the authoring wrapper over `VibeWorkflow.add_node(...)`. It returns an object with `.out(name_or_index)` for a typed handle while still compiling into the same node/edge model.
- **Blocks** - `@block` functions are authoring-time helpers that mutate a `VibeWorkflow` and return handles. They are the local shape for reusable graph fragments, loaders, samplers, decoders, save nodes, and opaque subgraphs.
- **Patches** - patches transform an existing `VibeWorkflow` and never return handles. The signature is `(workflow: VibeWorkflow) -> VibeWorkflow`, matching the existing `Patch` dataclass at `vibecomfy/patches/types.py:9` and every shipping patch in `vibecomfy/patches/` (e.g. `controlnet`, `gguf_unet`). Blocks return `Handles` and construct nodes; patches mutate topology/policy and return the workflow. The signature difference is the contract — there is no "intent-only" patch over a block contract.
- **Stages** - a stage is one step in a `VibeFlow`: a graph execution, an ordinary Python transform, or final artifact collection.
- **Typed Handles** - `Handle[T]` names a node output or artifact with `node_id`, output slot, optional name, and schema/runtime type metadata. It is additive over today's string references.
- **Run Results / Artifacts** - `RunResult` records execution metadata and maps named graph outputs to `Artifact` values such as images, audio, video, JSON metadata, or files.
- **ExternalPythonNode** - the planned (P3) runtime boundary for Python that must execute inside a Comfy graph. Not implemented today; not an authoring-time block.
- **Escape Hatches** - raw refs, raw node construction, opaque subgraphs, `compile("api")`, `compile("graphbuilder")`, raw API import/export, and raw HiddenSwitch configuration remain available when typed helpers are incomplete.

Avoid introducing additional synonyms. "Recipe" is dropped from the public surface, including the provenance schema. "Pipeline" is also dropped: `Template` covers single-graph builders and `VibeFlow` covers multi-stage orchestration; nothing else has a non-overlapping role today. If an async/streaming variant of `VibeFlow` ever ships, it will be named distinctly at that time rather than reserving "Pipeline" speculatively.

## Architecture

```text
Python composition layer (new)
  - Template
  - VibeFlow
  - Blocks
  - Patches
  - typed Handle[T]
  - RunResult / Artifact
          |
          v
VibeWorkflow (canonical IR)
  - nodes, edges, inputs, outputs, metadata
  - class defined at vibecomfy/workflow.py:74
          |
          +--> compile("api") at vibecomfy/workflow.py:170
          |       |
          |       v
          |   HiddenSwitch / ComfyUI
          |     - embedded Comfy()
          |     - server /prompt
          |
          +--> compile("graphbuilder") parity branch
          |       - backend implementation at vibecomfy/workflow.py:184
          |
          +--> ComfyScript import-only adapter
                  - future one-way import into VibeWorkflow

Multi-stage flow:

Stage(Python setup)
  -> Graph A (VibeWorkflow -> HiddenSwitch)
  -> Stage(Python transform / decision)
  -> Graph B (VibeWorkflow -> HiddenSwitch)
  -> Stage(Python finalize)
```

The "Desired Authoring Experience" section above is the product shape. The architecture exists to preserve that experience while keeping `VibeWorkflow` canonical, HiddenSwitch as the execution boundary, and lower-layer escape hatches available.

## Typed Handles (and Backward Compatibility)

`Handle` carries `(node_id, output_slot, output_type | None, name | None)`. The required fields are the graph output identity; the optional fields are authoring and validation affordances that improve over time as schema snapshots get better.

Backward compatibility is explicit: `str(handle)` returns the existing `f"{node_id}.{slot}"` form. Current consumers that expect string refs keep working unchanged, including the opaque subgraph convention that returns `f"{node.id}.{slot}"` today in `vibecomfy/blocks/subgraph.py:47`.

This is additive because `Handles` already wraps arbitrary values at `vibecomfy/blocks/__init__.py:12`. The doc target for the block return shape is `Mapping[str, Handle]` rather than today's `Mapping[str, Any]`: every value should be a `Handle` (which still coerces to `"node.slot"` via `__str__`), so callers see a uniform handle surface rather than a mixed handle/string bag. Tightening the `Handles` class itself is an MP-2 task; this plan only commits to the surface claim.

Be precise about "typed." P1 delivers typed metadata and lintable handles: runtime validation, doctor messages, IDE discoverability on curated wrappers, and surface for the lint rules below. P1 does **not** deliver mypy-grade static safety; `wf.node("SaveAudio", images=image_handle)` still type-checks because every `Handle` is `Handle[Any]` until a class-discriminated mechanism lands. Full static typing requires either `@overload`-per-known-class with `Literal`-discriminated `.out(name)` returns, or codegen plus a published `SCHEMA_TYPE_REGISTRY: dict[str, type]` mapping Comfy output strings (`"IMAGE"`, `"LATENT"`, `"WANVIDEOMODEL"`, …) to Python symbols with a documented fallback for unmapped types. Neither is committed to a phase here; the plan only names the dependency so later phases can pick the mechanism honestly.

The string-coercion bridge is necessary but dangerous. Any implicit conversion to `"node.slot"` erases type metadata, so lint should flag coercion and raw string refs when a typed handle was available.

New code should prefer:

```python
image = wf.node("VAEDecode", samples=samples, vae=vae).out("image")
wf.node("SaveImage", images=image, filename_prefix="example")
```

Templates migrate incrementally. There is no flag day: old `"12.0"` refs, `Handles(image="12.0")`, and new `Handle[Image]` values coexist while blocks are upgraded.

## Multi-Stage Orchestration (Comfy ⇄ Python)

The primary mixing model is:

```text
Graph A
  -> typed outputs / files / metadata
  -> ordinary Python transform or decision
  -> Graph B
```

Arbitrary Python runs before, after, and between graph executions. It can inspect `RunResult`, read and write files, branch on metadata, update prompts, choose models, or decide which graph should run next.

Arbitrary Python does not run inside an active Comfy graph. The planned `ExternalPythonNode` (P3) would be the only sanctioned compile target for in-graph Python; until it lands the request is refused. This boundary is deliberate: Comfy graph execution exchanges serialized node inputs and outputs, not arbitrary live Python objects.

`VibeFlow` is the orchestration container for this model. It holds an ordered list of `Stage` entries, where each stage is either:

- a `VibeWorkflow` to compile and execute through HiddenSwitch; or
- a `Callable[..., StageResult]` that runs ordinary Python and returns typed values, files, artifacts, or metadata for later stages.

The executor passes typed media handles between stages. A Python stage can receive an image artifact from Graph A, write a transformed file, and pass that file handle into Graph B without pretending the transform was part of either Comfy graph.

`VibeFlow` lifecycle semantics are settled in SD-013: cancellation shields `queue_prompt_api` and propagates by stopping the watchdog and recording the partial run (no mid-prompt abort against HiddenSwitch); a single `VibeFlow` runs stages serially against one embedded session (multi-session opt-in deferred); run-dirs are `out/runs/<flow-id>/stage-<n>/...` with monotonic stage index; `RunResult` carries `flow_id` and `stage_index` for resume identity.

## ExternalPythonNode (Aspirational, Distinct from @block)

`ExternalPythonNode` is a P3 deliverable, not a current primitive. Nothing in the repository implements it today; this section describes the intended shape so the boundary it occupies is reserved against accidental alternative inventions.

`@block` is authoring-time sugar that exists today. The protocol at `vibecomfy/blocks/__init__.py:38` mutates a `VibeWorkflow` and returns `Handles`; it never executes during Comfy runtime.

When `ExternalPythonNode` ships, it will emit a real Comfy custom node, or an external-process custom node, registered through `NODE_CLASS_MAPPINGS`. Its inputs and outputs would cross explicit serialization boundaries: typed file handles, tensor/media handles, strings, numbers, and other Comfy-compatible values only. No live Python objects would cross that boundary. Until it lands, runtime Python inside a graph is not supported and SD-005 is enforced by refusing the request rather than by routing through this primitive.

The names stay different on purpose. `@block` helps Python authors build a graph. `ExternalPythonNode` is the planned, sanctioned way for VibeComfy to run Python inside an active graph once P3 codegen exists.

| Surface | Status | When it would run | Where it lives | Returns |
| --- | --- | --- | --- | --- |
| `@block` (`vibecomfy/blocks/__init__.py:38`) | Implemented | Authoring time | Python builder code | `Handles` |
| `ExternalPythonNode` | Planned (P3) | Comfy runtime | Would compile to a Comfy custom node + `NODE_CLASS_MAPPINGS` | Comfy-typed outputs (IMAGE/LATENT/STRING/…) |

## Custom Nodes — Adding On the Fly

Pre-run install, discovery, and sync are in scope. The authoring layer should extend `vibecomfy nodes install-plan` and `vibecomfy doctor` so a workflow can declare required nodepacks, resolve them through the catalog and lockfile, and prepare the runtime before graph execution.

Hot-loading a new nodepack into an already-running HiddenSwitch executor is not the default. Adding a new pack defaults to session reload or restart:

```text
session.stop()
install or update nodepack
session.start()
```

That default matches the existing lifecycle shape in `vibecomfy/runtime/session.py`: the session protocol has `start()` and `stop()` methods (`vibecomfy/runtime/session.py:72`, `vibecomfy/runtime/session.py:84`), embedded sessions open a `Comfy()` context on start (`vibecomfy/runtime/session.py:95`), embedded sessions close that context on stop (`vibecomfy/runtime/session.py:169`), and server-session reconfiguration already uses `stop()` before `start()` when the runtime argv changes (`vibecomfy/runtime/session.py:255`).

Embedded sessions reload by closing and reopening the `Comfy()` context. Server sessions restart `comfyui serve`. External server mode can report that a restart is required, but it should not terminate a server it does not own.

This needs a real lifecycle verb, not just guidance. The API should expose something like `session.reload_for_nodepack_change(reason=...)` so nodepack reload has a contract, can refuse while a run is in flight, and can emit a specific "external server restart required" error when VibeComfy does not own the server.

An optional Python import-and-load path may exist later, but only behind a feature flag and only for proven-safe packs: no global side effects beyond `NODE_CLASS_MAPPINGS`, no module-level GPU initialization, and no runtime monkey-patching that assumes process startup order. It is never the default path.

## Custom Nodes — Pinning, Hashes, and Lockfiles

SD-006 is settled: custom node dependencies are pinned by repository and immutable commit when specified; otherwise VibeComfy may resolve newest once and capture the result in the lockfile. The current lockfile already records pinned entries for `ComfyUI-KJNodes` and `ComfyUI-WanVideoWrapper` (`custom_nodes.lock:1`, `custom_nodes.lock:2`), matching the existing custom-node documentation (`docs/custom_nodes.md:3`).

The lockfile fields should use precise names:

- **`git_commit_sha`** - required primary pin for locked Git nodepacks. It is the immutable Git commit SHA-1 of the nodepack repository and pins the whole repository tree at lock time.
- **`semantic_label`** - optional advisory label such as a tag, branch, or human name like `v1.4.0` or `main`. It resolves to a `git_commit_sha` at lock time and is never enough to install by itself.
- **`source_sha256`** - optional per-node-class SHA-256 hex digest of an individual node-class source file's bytes at lock time. Use it only for packs that vendor classes from multiple upstream sources or expose many classes where class-level provenance matters. Skip it for typical packs whose `git_commit_sha` already pins all classes.

The distinction is load-bearing: `git_commit_sha` is a Git repository-object hash that pins the whole tree; `source_sha256` is a content digest of one class file. They can coexist, but neither replaces the other.

`custom_nodes.lock` remains the package-level manifest and is extended to record the new fields. A future `vibecomfy nodes lock` command rewrites it after resolving `semantic_label` values, installing nodepacks, and optionally computing any per-class `source_sha256` values.

Pinning is not meaningful until it is checked. `doctor` and runtime startup should compare installed nodepacks against the lockfile and use a defined mismatch policy. Default should be fail-closed for reproducible templates, with an explicit `--allow-drift` or equivalent for exploratory work.

## Custom Nodes — Authoring Surface

The schema source for custom-node authoring is the combination of `/object_info` snapshot, `node_index.json`, and `custom_nodes.lock`. The authoring layer must work when a class is known only opaquely.

The generic path is always available:

```python
node = wf.node(class_type="SomeCustomNode", **inputs)
```

That path also covers UUID subgraph classes and opaque nodes. The existing opaque subgraph helper proves the pattern by preserving unknown class types and returning string-compatible handles from `vibecomfy/blocks/subgraph.py:47`.

Hand-written blocks remain optional sugar for high-traffic packs such as Wan, LTX, KJNodes, GGUF, and ACE Step. They should improve ergonomics for common workflows, not become a prerequisite for using a custom node.

Out of scope: auto-generating typed Python wrappers for all 1,202 runtime node classes. The local runtime surface records 1,202 node definitions from `/object_info` (`docs/runtime/surface.md:36`), so the default design must remain generic-first and schema-assisted rather than wrapper-complete.

## Relationship to HiddenSwitch GraphBuilder

GraphBuilder stays optional. That matches the historical spike decision to enable it as an optional backend (`docs/historical/graphbuilder_spike.md:8`) and the current `VibeWorkflow.compile("graphbuilder")` implementation path (`vibecomfy/workflow.py:184`).

GraphBuilder is not the authoring surface:

- it ties authoring to an installed HiddenSwitch runtime;
- it exposes only positional `.out(int)` outputs rather than typed `Handle[T]` names;
- it does not carry VibeComfy provenance, template metadata, or composition traces; and
- it does not produce diff-friendly VibeComfy Python builders.

VibeComfy should borrow GraphBuilder's `id=` convention for explicit node IDs and use GraphBuilder as a parity-test target. The primary authoring path remains Python composition -> `VibeWorkflow` -> `compile("api")`.

## Relationship to ComfyScript

ComfyScript is "learn", not "adopt". That is the historical spike decision (`docs/historical/comfyscript_spike.md:7`) and it remains the plan.

The useful future shape is a one-way import adapter:

```text
ComfyScript script -> VibeWorkflow
```

It is not the core VibeComfy authoring API because the spike found three mismatches: the transpiler requires a live Comfy server and `/object_info` (`docs/historical/comfyscript_spike.md:13`), successful output uses ComfyScript-flavored calls rather than `VibeWorkflow` edits (`docs/historical/comfyscript_spike.md:23`), and common UI-only nodes such as `MarkdownNote` broke several conversions (`docs/historical/comfyscript_spike.md:17`).

Use ComfyScript as evidence for node naming, examples, and possible import/export ergonomics. Do not block template ingestion, scratchpad editing, or execution on ComfyScript.

## Limits of Direct Node Execution

HiddenSwitch executes whole graphs. The HTTP surface queues a prompt with `POST /prompt {"prompt": <api workflow dict>}` (`docs/runtime/surface.md:32`), and the embedded surface calls `comfy.queue_prompt_api(api_workflow)` (`docs/runtime/surface.md:50`). There is no `run_node(class_type, **inputs)` API for executing one Comfy node in isolation.

Supported workarounds:

- Author a one-node-plus-sink subgraph and run it through the normal runtime path, such as `run_embedded_sync`.
- Later, provide `wf.run_until(handle)` as a debug runner that compiles a minimal graph ending at a sink inferred from the handle's output type.

`wf.run_until(handle)` is gated on P4. It requires the typed-`Handle` rollout and a populated schema snapshot so the handle has an `output_type`. Until handles carry `output_type`, the debug runner is unavailable; users manually attach `SaveImage`, `PreviewImage`, `SaveAudio`, or another appropriate sink.

Do not promise inferred save/preview/audio taps before typed handles and schema metadata land. Runtime lifecycle remains graph-level: sessions start, run a compiled workflow, flush or reconfigure, and stop (`docs/runtime/lifecycle.md:9`, `docs/runtime/lifecycle.md:26`).

The P1-P3 contract is explicit: until P4, `wf.run_until(handle)` raises `NotImplementedError` if `handle.output_type is None`. Hand-populated `output_type` may happen to work pre-P4 but is unsupported and will not survive the P4 cutover; downstream code must not form against partial behavior.

## Ready Template Migration

The repository already shows both sides of the migration. There are 42 ready-template `.py` files, 41 of them currently embed `API_WORKFLOW` dictionaries, and one is already a native VibeComfy Python builder. `ready_templates/image/z_image.py:6` is representative of the API-dict precedent; `ready_templates/image/flux2_klein_4b_t2i.py:81` is the native builder precedent — but it is the migration model **in spirit, not yet in API**. It defines its own private `node()` helper at `ready_templates/image/flux2_klein_4b_t2i.py:172` and uses raw string `connect(...)` calls rather than `wf.node(...).out(...)`. The final shape is what the "Desired Authoring Experience" section shows; the existing builder is a *transition precedent* that proves native Python builders work, not the canonical end-state.

Migration policy:

- Leave runtime-green API-dict templates untouched until they need editing.
- When a template is being tweaked, re-author it through the composition layer using the **target** `wf.node(...).out(...)` / typed-handle shape, not the transitional Flux 4B private-helper shape.
- Keep round-trippability: every authored template should `compile("api")` to a graph that matches its prior runtime-green API JSON within an allowed-difference set.

Allowed differences should stay narrow: node IDs may move when the authored builder intentionally chooses clearer IDs, and UI-only `MarkdownNote` nodes may be stripped when they have no runtime effect. Behavioral graph nodes, model names, prompts, dimensions, sampler settings, and output sinks should remain explainably equivalent.

Manual/iterative migration is the policy. There is no big-bang codemod, and this plan does not promise a codemod CLI. The right migration moment is when a ready template is being touched for a product reason: a model update, a parameter override, a new block, a broken runtime dependency, or a documentation improvement.

## Reconciliation with docs/authoring.md

`docs/authoring.md:99` says ready templates "should be hand-curated Python builders" and that retiring the materializer is intentional. This plan softens, not supersedes, that rule: hand-curated Python builders remain the destination shape, and the Flux 4B builder is the transition proof point (in spirit, not in API), but the plan accepts the current 41-of-42 API-dict reality and migrates manually when a template is edited.

The Flux 4B builder is not the final API ideal. It uses explicit node IDs, a private `node()` helper at `ready_templates/image/flux2_klein_4b_t2i.py:172`, and string `connect(...)` calls. The canonical migration shape is the public `wf.node(...).out(...)` / typed-handle API shown in the "Desired Authoring Experience" section. Until the existing builder is rewritten against that surface, it remains evidence that native Python builders work, not evidence that the authoring surface is finished.

A one-line pointer added to `docs/authoring.md` in this same delivery links readers back to this plan. The core authoring rules in `docs/authoring.md` remain authoritative: blocks mutate workflows and return handles, patches decorate or transform workflows, edge primitives support topology changes, and `finalize_metadata()` refreshes discoverable inputs, outputs, and requirements.

## Provenance

The current block helper already writes node-level provenance: produced nodes record `block`, `block_id`, and `widget_kwargs` in `VibeNode.metadata` (`vibecomfy/blocks/_utils.py:22`). The composition layer should extend that pattern upward instead of replacing it.

Add `workflow.metadata["composition_trace"]` as an ordered list of block, template, patch, and stage calls. Each entry should record the public callable name, stable call ID when available, selected kwargs, and output handles. This gives `wf.explain()` and analysis commands a readable path from Python authoring calls to graph nodes.

Populate `workflow.source.provenance` on the existing source container (`vibecomfy/workflow.py:10`) with structured source data such as:

```python
{
    "authored": True,
    "template": "image.t2i",
    "source_template": "image/z_image",
    "builder_path": "<abs path>",
}
```

Keep `metadata.subgraph_class_type` for opaque UUID subgraphs. The authoring guide already documents that opaque subgraphs preserve UUID class types and set that metadata field (`docs/authoring.md:84`).

For multi-stage flows, write `flow_trace` to `out/runs/<run-id>/metadata.json`. It should record each stage type, stage inputs, stage outputs, artifact paths, selected runtime backend, and node-pack lock SHAs, including both `git_commit_sha` and any per-class `source_sha256`.

## Debugging

Debugging helpers depend on typed handles. The initial affordances should be:

- `wf.show()` and `vibecomfy analyze info` print the composition trace alongside the node graph.
- `wf.run_until(handle)` compiles a minimal graph that terminates at a sink inferred from the handle type.
- `wf.tap("save_image", from_handle)` inserts a preview/save tap without rewriting downstream wiring.

`wf.run_until(handle)` is available only after typed handles and schema-backed output types land in P4. Until then, authors should manually attach the relevant `SaveImage`, `PreviewImage`, `SaveAudio`, or other sink node.

Reuse the old analysis backlog for before/after reasoning. The historical port rationale explicitly calls out `analyze`, `trace`, and `diff` as workflow-understanding commands to carry forward (`docs/historical/old_vibecomfy_port_rationale.md:30`).

## Layered Debug Affordances

Every high-level object should reveal its lower layer. The composition API should make the desired path short without hiding the graph that will run.

- `template.workflow` exposes the underlying `VibeWorkflow`.
- `handle.node_id` and `handle.slot` expose the graph output identity.
- `result.outputs` exposes runtime outputs and named artifacts.
- `wf.compile("api")` exposes the exact Comfy API dictionary.
- `wf.explain()` shows composition trace, node provenance, and requirements.
- `wf.doctor()` checks missing models, custom nodes, stale metadata, and schema mismatches.

## Lint / Guardrail Ideas

These are future static-analysis ideas, not P1 deliverables:

- `untyped_raw_ref` - a string ref is used where a typed `Handle[T]` is available.
- `stale_metadata` - nodes changed after the last `finalize_metadata()` or trace update.
- `unbound_input_unused` - a declared prompt/seed/model override is never bound to a node.
- `artifact_vs_node_handle` - a Python artifact path is passed where a Comfy node handle is required, or the reverse.
- `ready_not_runtime_green` - a ready template migration lacks runtime parity evidence.
- `widget_index_escape` - code uses `widget_N` for a node whose schema has named inputs.
- `unknown_custom_node_commit` - a custom nodepack is used without a locked `git_commit_sha`.
- `http_queue_only` - a test or debug path relies only on HTTP queue submission when completed outputs are required.

## Escape Hatches

Escape hatches stay public, but they must be able to re-enter composition. A raw API dict should be wrappable as a `VibeWorkflow` stage through a future `VibeWorkflow.wrap_api_dict(...)` or equivalent, so raw workflows can still participate in `VibeFlow` and produce `RunResult` / `Artifact` values.

Each escape hatch loses some provenance unless the caller fills it back in:

- Raw JSON load via `convert_to_vibe_format` (`vibecomfy/registry/ready_template.py:19`). This preserves graph structure but may not know the original template, block call stack, or source builder path.
- Raw node construction via `wf.add_node(class_type, **inputs)`. This preserves the node in `VibeWorkflow` but skips block-level `block`, `block_id`, and `widget_kwargs` metadata unless the caller sets it.
- Raw API-dict pass-through by assembling a dict and calling `Comfy.queue_prompt_api` directly. This bypasses `VibeWorkflow`, so VibeComfy loses composition trace, typed handles, patch provenance, requirements inference, and schema-backed validation unless the caller separately records them.

## Enforcement Gates

Every load-bearing invariant needs a code-level gate before the feature depends on it:

- **Serialization gate:** `compile("api")` rejects non-JSON-serializable live Python objects in node inputs/widgets unless they belong to a recognized runtime boundary such as `ExternalPythonNode`.
- **Handle-aware connect:** add a `wf.connect(handle_a, handle_b)` path that does not route through string splitting, while keeping string refs for compatibility.
- **Raw API wrapping:** add `VibeWorkflow.wrap_api_dict(...)` or equivalent so raw workflows can become `VibeFlow` stages.
- **Nodepack reload verb:** add `session.reload_for_nodepack_change(...)` with in-flight run protection.
- **Lockfile verification:** `doctor` and startup compare installed nodepacks against `custom_nodes.lock` and report/fail on drift according to policy.
- **Schema type registry:** publish a mapping from Comfy schema type strings to Python handle types before P4 ungates `run_until`.

## Rollout

Each phase is gated on the previous phase. Do not move `wf.run_until(handle)` earlier than P4.

## End-to-End Implementation Guidance

This plan is intended to be executed as one coherent end-to-end build, including the ready-template migration. The right implementation shape is not a narrow prototype; it is a complete pass that leaves users with one clear Python composition model, migrated templates, validation, runtime checks, and escape hatches that still compose.

Keep the execution order disciplined. Build the core authoring path first, then wire runtime boundaries, then migrate templates, then validate everything. Do not leave the repository in a mixed state where some templates are "ready" but still depend on private helpers or raw API dictionaries as their primary authored form.

The target authored template shape is:

```python
wf = VibeWorkflow("flux_klein_4b")
model = wf.node("UNETLoader", unet_name="flux-2-klein-4b.safetensors").out("MODEL")
conditioning = wf.node("CLIPTextEncode", text=prompt, clip=clip).out("CONDITIONING")
samples = wf.node("KSampler", model=model, positive=conditioning, ...).out("LATENT")
image = wf.node("VAEDecode", samples=samples, vae=vae).out("IMAGE")
wf.node("SaveImage", images=image, filename_prefix="flux_klein")
```

The full implementation should deliver:

- `wf.node(...)` returning a node wrapper with `.out(name_or_index)`.
- `Handle` values carrying `node_id`, `slot`, optional `name`, and optional `output_type`, with `str(handle)` preserving `"node.slot"` compatibility.
- Handle-aware input serialization in `compile("api")`, so node inputs can receive either a `Handle` or an existing string ref.
- A serialization gate that rejects live Python objects in graph inputs unless they belong to an explicit supported boundary.
- `VibeWorkflow.wrap_api_dict(...)` or equivalent, so imported raw API workflows can re-enter the composition layer before migration.
- `VibeFlow` orchestration for graph -> Python -> graph flows, including flow-scoped output directories, stage identity, cancellation behavior, and artifact passing.
- `ExternalPythonNode` only if needed by an existing ready template or validation target; otherwise keep the boundary documented and fail explicitly when requested.
- Custom-node lifecycle support through install planning, lockfile verification, and a real `session.reload_for_nodepack_change(...)` or equivalent restart/reload path.
- `doctor` checks for missing models, missing nodepacks, lockfile drift, schema mismatches, stale metadata, and unsupported live Python objects.
- `wf.run_until(handle)` only after typed `output_type` metadata and sink inference exist; before that, it must fail explicitly with `NotImplementedError`.
- All ready templates migrated from raw `API_WORKFLOW` dictionaries or private helper styles into public Python composition, except for explicitly documented technical exceptions.
- Raw API dict templates retained only as import fixtures, provenance-preserving fallbacks, or documented exceptions with a tracked reason.
- Round-trip/parity checks proving migrated templates compile to valid API JSON and preserve the meaningful runtime graph.
- Runtime validation for the migrated ready-template corpus, with results recorded as ready-template evidence rather than assumed from schema checks alone.

Template migration should be comprehensive:

- Start by rewriting the current Flux Klein 4B native builder into the public `wf.node(...).out(...)` style — its private `node()` helper and string `connect()` calls are the transition shape, not the target.
- Convert every existing `ready_templates/**/*.py` file whose primary payload is an `API_WORKFLOW` dict into an authored Python builder.
- Preserve source provenance for each migrated template: original raw JSON/template source, conversion timestamp or migration note, required models, required nodepacks, and validation result.
- Keep model families organized by capability, not by accident of source: image, video, audio, editing, inpaint/outpaint, control/conditioning, LoRA/IP-adapter, and utility/debug templates.
- Prefer official Comfy templates as source material where available, then curated upstream project examples, then high-quality custom-node examples.
- For each major model family under active use, keep at least one runtime-green template per important capability rather than many redundant variants of the same path.

Execution order:

1. Implement `Handle`, node wrapper, handle-aware compilation, serialization gates, and provenance updates.
2. Add raw API wrapping so existing templates can run through the same composition-facing surface while they are being migrated.
3. Add custom-node lockfile verification and session reload/restart semantics.
4. Add `VibeFlow` orchestration with graph stages, Python stages, artifacts, run directories, stage identity, and cancellation semantics.
5. Add schema-backed validation and `doctor` checks.
6. Migrate the ready-template corpus into public Python composition.
7. Run schema, compile, parity, doctor, and runtime validations against the migrated corpus.
8. Record validation evidence and leave any remaining raw templates explicitly marked as exceptions with reasons and follow-up work.

The implementation should feel boring in the best sense: one public node-construction path, one handle type, one compile path, one orchestration model, one custom-node lifecycle model, and one validation story for all templates. If an abstraction does not help the end-to-end corpus become clearer, more reliable, or easier to debug, remove or defer it.

- **P1** - Add typed-metadata `Handle` API on top of the current IR with string-coerce backward compatibility; add `wf.node(...)` as the wrapper over node creation; add handle-aware `connect`; add the P1-P3 `run_until` raise contract; add parity tests against `compile("graphbuilder")`.
- **P2** - Expand block library coverage for Wan, LTX, KJNodes, GGUF, and ACE Step; replace positional `widget_N` keys with named widgets where schema is known; add the compile-time serialization gate and raw-ref/coercion lints.
- **P3** - Add `VibeFlow` multi-stage orchestration for Comfy <-> Python with typed media handles, but only after failure semantics, run-dir naming, stage identity, raw API wrapping, and nodepack reload are settled; add `ExternalPythonNode` codegen for rare cases that need Python at graph-execution time; add custom-node session-reload helpers; add `vibecomfy nodes lock` writing `git_commit_sha`, optional `semantic_label`, and optional `source_sha256` to `custom_nodes.lock`.
- **P4** - Add schema-backed validation against a `/object_info` snapshot in CI, following the schema-validation direction in `docs/historical/old_vibecomfy_port_rationale.md:14`; populate typed-handle `output_type`; ungate the `wf.run_until(handle)` debug runner.
- **P5** - Complete the ready-template migration manually and iteratively, using a *rewritten* Flux 4B builder (now in `wf.node(...).out(...)` shape) as the canonical reference; add the optional ComfyScript import adapter and any further public docs.

`wf.run_until(handle)` lands in P4, not P1. P1 can create typed handles and preserve string compatibility, but it cannot infer safe save/preview/audio sinks until P4 provides schema-backed `output_type`.

## Open Questions

- Should `Handle` carry source `block_id` or template/flow context directly for debugging, or should that stay in the composition trace only?
- Should raw API-dict pass-through strip `MarkdownNote`-style UI nodes, or preserve them verbatim and let validation flag runtime irrelevance?
- For the first `ExternalPythonNode` codegen path, should the boundary be an external subprocess or an in-process custom-node module?

## Assumptions

- `VibeWorkflow` remains the canonical IR.
- GraphBuilder remains an optional backend.
- ComfyScript remains import-only/reference material, not the authoring API.
- Direct single-node execution is out of scope; debug runs are gated on P4.
- Schema-backed validation uses a `/object_info` snapshot.
- Ready-template migration is manual and iterative; the current Flux 4B builder is a transition precedent in spirit (proves native builders work) but not in API (uses a private `node()` helper and string `connect()`); the canonical target is the public `wf.node(...).out(...)` typed-handle shape.
- Custom-node pinning uses `(repo_url, git_commit_sha)` with optional `semantic_label` and `source_sha256`.
- Adding new nodepacks defaults to session reload or restart.
- Multi-stage orchestration is the primary mixing model for Comfy and Python.
- `ExternalPythonNode` is the *planned* (P3) path for Python that must run inside a Comfy graph; it is not implemented today.
- `@block` is authoring-time only; `ExternalPythonNode` will be runtime when it lands.
- Typed `Handle` is additive and keeps `str()` coercion. P1 delivers typed metadata and lintable handles, not mypy-grade static safety.
- Block return shape narrows toward `Mapping[str, Handle]` (MP-2 work); P1 docs the surface, MP-2 enforces it.
- Patches have signature `(workflow) -> VibeWorkflow` and never return handles, matching `vibecomfy/patches/types.py:9`.
- "Recipe" and "Pipeline" are not public types; only `Template` and `VibeFlow` describe authoring containers.
- `VibeFlow` lifecycle (cancellation, single-session serial execution, flow-scoped run-dirs, resume identity) is settled in SD-013.
- `wf.run_until(handle)` raises `NotImplementedError` until P4 ungates it via schema-backed `output_type` plus a published `SCHEMA_TYPE_REGISTRY`.
- The deliverable is two markdown edits: this plan plus the pointer in `docs/authoring.md`.
- The final document should stay within roughly 300-550 lines.
- Custom-node coverage starts generic-first with `wf.node(...)`, plus hand-curated blocks for high-traffic packs.
