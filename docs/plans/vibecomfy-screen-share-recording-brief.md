# VibeComfy Screen-Share Speaking Guide

Use this as a glanceable talk track, not a script.

## Core Idea

> VibeComfy gives agents a readable, structured workspace for understanding and
> changing ComfyUI workflows. ComfyUI JSON remains the application and runtime
> format; VibeComfy helps the agent understand the graph, propose a bounded
> change, validate it, and turn it back into ordinary ComfyUI.

The recording order:

1. Grow one workflow through four live edits.
2. Quickly show three more complex Demo Picker edits.
3. Explain concretely how VibeComfy works.
4. Go deeper on representation, validation, correction, community knowledge,
   MCP, and ComfyScript.
5. Show the technical work that remains and point people to the GitHub issues.
6. Finish with concrete contribution asks.

## 1. Grow One Workflow

Start on the canvas. Keep the introduction to one or two sentences.

### A. Generate SD 1.5

Prompt:

> Create a basic SD 1.5 text-to-image workflow.

Show:

- A clean canvas becoming the familiar checkpoint → conditioning → latent →
  sampler → VAE decode → output graph.
- The completed graph long enough for the audience to understand the baseline.

Say:

- This is normal ComfyUI, not a replacement runtime or proprietary graph.
- We will keep evolving this same workflow rather than loading disconnected
  examples.

### B. Convert it to SDXL

Prompt:

> Convert this workflow from SD 1.5 to SDXL.

Show:

- The candidate before Apply.
- The coordinated checkpoint, conditioning, latent-size, and compatibility
  changes.

Say:

- A model-family conversion is not just changing a filename.
- The agent must identify roles and dependencies, preserve what remains valid,
  and replace what SDXL makes incompatible.

### C. Convert it to image-to-image

Prompt:

> Turn this SDXL text-to-image workflow into image-to-image.

Show:

- The input-image and VAE-encoding path being added.
- The encoded latent connected to the sampler.
- The denoise control and, if practical, a generated result.

Say:

- This is a capability and topology change, not a parameter tweak.

### D. Replace image-to-image with IP-Adapter

Prompt:

> Make this use IP-Adapter instead of image-to-image.

Show:

- The image-to-image latent-init path being removed or bypassed.
- The IP-Adapter, vision encoder, and model-conditioning path being added.
- The sampler returning to an appropriate latent input.
- The structural diff before Apply.

Say:

- In image-to-image, the source image initializes the latent. With IP-Adapter,
  it becomes reference conditioning on the model.
- The agent has to understand the image's role in the graph, not merely replace
  one node name with another.
- This is the hardest opening edit because it creates nodes and rewires several
  parts of the workflow.

Transition:

> This went from a basic SD 1.5 graph to SDXL, then image-to-image, then a
> different reference-image technique—all by continuing to work on the graph in
> front of the agent.

## 2. Three Demo Picker Edits

These replay saved real agentic runs; they are not fresh model calls. Move
quickly and use each to name a different class of edit.

### A. Semantic edit — plastic to fabric

> Change the SDXL material from shiny plastic to woven fabric.

- The user names a visual outcome, not a field.
- The agent finds the relevant positive and negative conditioning.
- The edit stays scoped to the part of the graph that controls the outcome.

### B. Multi-target edit — grid cells to 512px

> The preview grid looks too small and blurry—make each cell 512×512.

- One request maps to four resize nodes.
- The agent recognizes a repeated pattern rather than changing the first
  plausible value.
- Validation can check that every intended target changed consistently.

### C. Structural edit — grid to horizontal row

> Arrange the four variations in a single horizontal row instead of a 2×2 grid.

- A component is replaced rather than tuned.
- A different node is introduced and four branches are rewired.
- Preview, scoped diffs, and structural validation matter most here.

## 3. Explain How It Works

```text
current ComfyUI workflow
→ import and identify the graph
→ present a named Python and typed-graph view
→ interpret bounded edit operations
→ build and validate a candidate
→ preview the exact change
→ Apply or Reject
→ export ordinary ComfyUI JSON
```

Talk through:

- Parsing JSON establishes its syntax, nodes, fields, and links. Understanding
  the workflow means identifying node roles, causal dependencies, safe edit
  boundaries, and the outcome the user is trying to change.
- Raw ComfyUI JSON is accurate, but much of its meaning is spread across
  numeric IDs, link arrays, widget positions, editor state, and custom-node
  conventions.
- VibeComfy gives nodes stable identities and exposes named dependencies,
  inputs, outputs, and—when declared or indexed—models, node packs, and
  provenance.
- The agent works through a constrained Python-shaped surface. Supported
  statements are parsed into typed graph operations, not executed as arbitrary
  model-written Python.
- The edit becomes a candidate before it touches the canvas. It can be
  inspected, rejected, corrected, or applied.
- JSON remains what ComfyUI receives, and the canvas remains the visual
  interface for people.

### Optional technical riffs

These are self-contained two-to-four-minute cue cards. Record whichever feel
interesting.

#### Read one real workflow as Python

- Show `ready_templates/image/z_image.py` beside
  `ready_templates/sources/official/image/z_image.json`: 80 lines versus 1,169.
- Compare Python lines 47–56 with JSON lines 843–932. The KSampler becomes ten
  contiguous named lines instead of roughly 90 serialized lines with wiring
  stored elsewhere.
- VibeComfy does not hide ComfyUI concepts. `KSampler`, `CLIPTextEncode`, and
  `VAEDecode` stay visible; serialization bookkeeping disappears.
- `steps=steps` names meaning that JSON leaves implicit in positional widget
  order, while assignments make link-chasing into readable dataflow.
- Lines 21–37 turn an anonymous subgraph into
  `text_to_image_z_image_base(...)`, with an explicit interface and traceable
  source UUID/hash.
- Run `vibecomfy inspect image/z_image` to statically show ten nodes, ten edges,
  four public inputs, the output, and model dependencies.
- Complex backup: `ltx2_3_lightricks_two_stage.py` turns a 2,949-line canvas
  into 249 lines exposing two sampling passes, audio/video latents, upscale,
  recombination, and decode.

#### Stable identity and source-preserving edits

- Show a one-field edit in a large graph beside a filtered diff or preservation
  report.
- The dangerous approach is regenerating an approximation of the entire graph
  to change one field.
- VibeComfy gives graph entities stable identities and applies a typed delta to
  the submitted workflow, preserving untouched positions, groups, notes,
  reroutes, properties, and links.
- Stable identity lets the agent keep referring to the same node across turns.
- Manually alter the canvas after Preview and show stale-candidate refusal.
- If durable identity metadata is stripped, recovery for legacy graphs is more
  limited and must fail closed where matching is ambiguous.

#### Python-shaped does not mean arbitrary Python execution

- Show `ksampler.steps = 30` becoming a typed `SetNodeFieldOp`, then show
  `import`, `open`, or `exec` being rejected.
- The agent gets familiar Python-shaped syntax without receiving a general code
  execution surface: an allow-listed AST grammar lowers into typed operations.
- Show a type-wrong link, its diagnostic, and the corrected statement. The
  edit surface teaches the model the available fields, classes, and sockets.
- The constraint is deliberate: this is a replayable workflow edit language,
  not full Python.

#### Preview and Apply are one transaction

- Show a scoped candidate diff, its baseline/mutation-plan hashes, and Apply
  consuming that candidate.
- Preview is meaningful only if Apply consumes the same normalized mutation
  plan the person reviewed.
- Alter the canvas after Preview to show that an old valid edit cannot be
  applied to a different current graph.
- Reject, rollback, and recovery are transaction semantics, not UI decoration.
- Rehearse one known-good lifecycle path; do not imply that every recovery path
  has already converged onto the final architecture.

#### A workflow can carry its environment contract

- Show `MODELS`, `PUBLIC_INPUT_METADATA`, and `READY_METADATA`, then run
  `vibecomfy inspect` or a port check.
- A raw workflow often means “this worked on one unknown machine.”
- Machine-readable models, node packs, commits, schema hashes, runtime
  packages, provenance, and outputs make compatibility auditable before a run.
- Schema hashes can reveal a custom-node interface changing underneath the
  workflow.
- The contract is only as complete as its declared provenance and dependency
  data; arbitrary imported workflows may still be incomplete.

## 4. The Strongest Ideas

### Representation changes what an agent can understand

- A representation determines which identities, relationships, and possible
  edits are obvious.
- In raw JSON, the agent spends effort reconstructing meaning before it can
  solve the user's problem.
- Names, keyword arguments, dependencies, inputs, outputs, and requirements
  make more of that meaning explicit.
- This should mean less context, fewer reconstruction steps, lower latency, and
  lower cost.
- It may also let smaller models handle edits that would require a much more
  capable model on raw JSON.
- Treat the speed, cost, and model-size point as the product hypothesis until
  it has been measured in a controlled benchmark.

### Python is the reading and editing language

- Python gives agents familiar names, calls, keyword arguments, functions, and
  dependencies.
- It is first a reading language: the agent can orient itself without mentally
  rebuilding the graph from JSON bookkeeping.
- It is also a constrained editing language: supported statements lower into
  typed graph operations.
- JSON remains the import, export, and runtime boundary.
- Python and JSON are not two independent documents that the model edits
  separately. They are views over the same workflow substrate.
- An edit targets stable graph identities; VibeComfy applies it to the workflow
  and regenerates the relevant views while preserving untouched concrete
  content.

### “Valid” has several meanings

| Claim | What it establishes | Needs execution? |
|---|---|---|
| Mechanically faithful delta | The intended fields or edges changed and untouched content was preserved. | No. |
| Structurally valid | Available schemas and graph invariants agree with the candidate. | No. |
| Accepted by ComfyUI | The live environment accepts the graph for queuing. | It requires a live environment; actual submission may begin execution. |
| Runtime successful | The workflow executes and produces an artifact. | Yes. |
| Request satisfied | The result fulfills the user's natural-language intent. | Usually needs semantic or human judgement. |
| Artistically good | The output succeeds aesthetically. | Needs the output and human judgement. |

Strongest pre-execution claim:

- VibeComfy can inspect the delta, compare it with the starting graph, check
  available node and graph contracts, and preserve untouched content.
- It can refuse candidates that fail the available structural, schema,
  preservation, or task-specific checks.
- That is strong evidence that an edit is mechanically faithful and
  structurally legitimate.
- It does not prove the workflow will render, the request was understood
  correctly, or the output will be good.

### The model can be wrong without the system becoming wrong

- Treat the model answer as a proposal, not an overwrite.
- Keep the starting graph and proposed operations separate.
- Validate before mutating the canvas.
- Return specific feedback and let the model correct the proposal while
  correction is still cheap.
- Make Apply consume the candidate the human actually reviewed.
- Preserve evidence of what changed or why the system refused.

### Community workflows become reusable knowledge

- A workflow contains tacit knowledge: wiring patterns, model choices,
  settings, and incompatibilities that documentation may omit.
- Conversations may explain practical gotchas; live schemas show what the
  current environment supports.
- The useful object is the workflow plus its purpose, dependencies,
  provenance, compatibility evidence, failures, and output contract.
- Search only finds a precedent. The agent still has to adapt it to the current
  graph, models, node versions, and user request.
- Because the project is file-based, a person can ask an agent to preserve a
  found workflow, pattern, compatibility note, test, or negative result.
- A success can become a ready template or cited precedent. A failure can
  become a diagnostic, regression test, incompatibility record, or warning.
- Shared publication remains deliberate: provenance, permission, evidence, and
  review still matter.
- Do not claim that the system silently learns from every user.

Show:

```text
community workflow, discussion, or fix
→ preserve source and provenance
→ translate and describe it
→ retrieve it as a precedent
→ adapt it to the current graph
→ validate or run it
→ preserve the useful success or failure
```

### Creative practice becomes agent-legible

- The canvas expresses spatial structure well for people.
- Named Python and typed graph views express dependencies well for agents.
- The agent can inspect structure, requirements, and known behavior without
  first running the workflow and guessing from the output.
- It still cannot know the artistic result from structure alone.
- The goal is translation between complementary forms while preserving the
  author's work, not replacing the canvas with one universal medium.

## 5. The Comparisons

### VibeComfy and MCP

- MCP answers: how can an agent connect to ComfyUI and call capabilities?
- VibeComfy answers: how should an agent represent, understand, research,
  validate, and safely transform a workflow?
- Capable ComfyUI MCP servers can build and edit graphs.
- The distinction is the intelligence underneath the interface: representation,
  stable identity, precedent, validation, preview, refusal, and recovery.
- VibeComfy could expose an MCP interface. It is a domain layer, not a
  competing transport protocol.

### VibeComfy and ComfyScript

ComfyScript is the other Python workflow project.

- ComfyScript compiles a graph into compact, runnable-looking procedural
  Python—useful for scripting and for people who understand the workflow.
- On complex graphs, meaning can remain implicit in call order, positional
  arguments, `None` placeholders, comments, and variable reuse.
- VibeComfy uses Python as an agent-editable workflow contract rather than
  optimizing for the shortest script.
- It can keep explicit public inputs, named subgraphs, dependencies, model and
  node-pack requirements, provenance, output semantics, and validation
  behavior.
- The difference is the job: scripting a graph versus helping an agent
  understand and safely edit one.

## 6. What Still Needs Improvement

The current mechanisms are real, but Agent Edit still has several browser and
backend paths that can independently interpret graph identity, native ComfyUI
normalization, mutation, verification, workflow scope, and transaction state.
That creates opportunities for a correct decision in one layer to be
reinterpreted later.

The in-progress **Agent Edit Complete Robustness** epic is collapsing those
responsibilities into one authoritative pipeline:

```text
Agent intent
→ canonical delta
→ workflow-scoped controller
→ native LiteGraph adapter
→ operation-specific verifier
→ durable finalize or verified rollback
```

Talk about:

- One native graph adapter should own capture, ComfyUI normalization, stable
  identity, mutation, restoration, and serialization.
- Canonical deltas should become the sole forward mutation language for
  Preview, Apply, Undo, rollback, recovery, and rehydration.
- One verifier should own preconditions, landed-operation checks,
  postconditions, finalization, and rollback comparison.
- Each workflow needs an isolated controller so tab switching and late
  asynchronous results cannot leak authority into another workflow.
- Every durable post-prepare state needs a deterministic, idempotent recovery
  path.
- The composed system needs pinned real-ComfyUI tests for success, failure,
  refresh, workflow switching, rollback, persistence, and representative
  extensions.

Current status:

- M0 incident foundation and M1 contracts are complete.
- M2, the native adapter and ownership transfer, is in progress.
- The verifier, workflow controller, exhaustive recovery, real-ComfyUI
  composition suite, and final audit remain.

Be explicit about the boundary:

- This does not promise a universal semantic oracle or replace the Python edit
  language.
- Root workflow scope is the target for this epic; unsupported nested scopes
  fail closed.
- The goal is not more agent autonomy. It is one trustworthy path for every
  authorized mutation.

Roadmap issue:

- [Complete Agent Edit robustness with one canonical controller → adapter →
  verifier pipeline](https://github.com/peteromallet/VibeComfy/issues/153)
- [All open VibeComfy issues](https://github.com/peteromallet/VibeComfy/issues)

## 7. Finish

- ComfyUI already contains an extraordinary amount of creative knowledge.
- Ask people to share workflows with intent, dependencies, and known-good
  outputs.
- Ask them to preserve the exact request, graph, failure, and fix when
  something goes wrong.
- Ask contributors to distinguish structurally converted, queueable, and
  genuinely runtime-tested work.

Closing line:

> The aim is to make ComfyUI's knowledge legible to agents, adaptable to the
> workflow in front of them, and safe enough that people can inspect, reject,
> and improve what the agent does.

## Production Notes

Preflight:

- Launch the recording instance with `VIBECOMFY_DEMO_PICKER=1`.
- Rehearse SD 1.5 → SDXL → image-to-image → IP-Adapter.
- Verify the checkpoints, IP-Adapter node pack, IP-Adapter model, and vision
  encoder.
- Save a clean graph and a checkpoint after each live step.
- Verify the three Demo Picker scenarios and every prompt.
- Hide keys, notifications, private paths, tabs, and workflow data.

Capture:

- Requests, candidate previews, diffs, Apply, Reject, warnings, and blocked
  states.
- Clean before/after canvases.
- Raw JSON beside the Python representation.
- One validation success and one useful refusal.
- Search, selected precedent, requirements, provenance, and generated outputs.
- Five-second handles around important screen states.

Avoid claiming:

- Static validation proves a render.
- Every edit or Python round-trip is guaranteed correct.
- MCP cannot edit ComfyUI.
- VibeComfy is the only live graph editor.
- Community discussion is authoritative.
- The knowledge base contains every workflow or learns automatically from every
  user.
- Structural validity proves request satisfaction or artistic quality.

References:

- [Why Python, Not JSON?](../comparisons/why_python_not_json.md)
- [VibeComfy and ComfyScript](../comparisons/comfyscript.md)
- [Python authoring and edit surface](../architecture/python_authoring_edit_surface.md)
- [Candidate transaction contract](../agent-edit/candidate-transaction-contract.md)
- [Agent-edit end-state audit](../agent-edit/end-state-and-pipeline-audit.md)
- [Workflow precedent research plan](workflow-precedent-research-plan.md)
