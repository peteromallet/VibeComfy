# Reorganise Comfy Workflow Capability Plan

## Goal

Add a workflow reorganisation capability that can make messy ComfyUI workflows readable, shareable, and consistent without changing runtime behaviour.

The full capability should eventually run in two ways:

- Explicitly, via `/reorganise_comfy_workflow` and a CLI/API surface.
- Opportunistically, in the main agent-edit flow, when deterministic assessment says the current workflow likely needs reorganisation.

The eventual v1 capability is layout-only: no node additions/removals, no rewiring, no widget changes, and no Set/Get conversion. The later apply step may change UI furniture such as `pos`, `size` when needed, `title`, `color`, `bgcolor`, `groups`, and layout metadata. M1 stops before that apply step.

## Principles

The target style follows Nathan Shipley's Comfy workflow legibility method:

- Big labels and clear functional groups.
- Left-to-right dataflow.
- Model pipe separated from the main generation/output path.
- Color-coded groups by function.
- Enough spacing to see noodles and drag-select groups.
- No overlapping nodes.
- Set/Get and reroutes handled responsibly, not hidden into confusing layouts.

The system should be beautiful because it is consistent and semantic, not because an agent hand-places coordinates.

## Existing Surfaces To Reuse

The repo already has the right primitives:

- `vibecomfy/porting/edit/projection.py` renders an address-preserving agent projection from LiteGraph UI JSON.
- `vibecomfy/porting/edit/ops.py` defines strict typed edit ops and target references.
- `vibecomfy/porting/edit/apply.py` applies typed operations to the original UI substrate instead of regenerating the whole graph.
- `vibecomfy/porting/layout/engine.py` computes deterministic layout from graph structure.
- `vibecomfy/porting/layout/types.py` exposes `LayoutResult(positions, groups)`.
- `vibecomfy/porting/layout/groups.py`, `lanes.py`, `layering.py`, `sizing.py`, `reconcile.py`, `layout_vector.py`, and `delta.py` provide grouping, ordering, sizing, preservation, and drift measurement utilities.

The reorganiser should use the same overall discipline as agent-edit:

```text
lossless LiteGraph UI JSON
  -> address-preserving reasoning projection
  -> strict typed model output
  -> deterministic validation/interpreter
  -> UI-only candidate graph
  -> structural no-op guard
```

## Recommended Architecture

Add a new package:

```text
vibecomfy/porting/reorganise/
  __init__.py
  assess.py
  projection.py
  plan_types.py
  parse.py
  validate.py
  compile.py
  classify.py
  report.py
```

Responsibilities:

- `assess.py`: deterministic layout quality score and "needs reorganisation" verdict.
- `projection.py`: agent-facing Pythonic dataflow projection.
- `plan_types.py`: `LayoutProjection`, `LayoutPlan`, `LayoutSection`, `LayoutCluster`, `IntraGroupPlan`, validation result types.
- `parse.py`: strict JSON parsing of agent output.
- `validate.py`: target existence, ownership, topology truth, no-layout-only violations.
- `compile.py`: convert semantic plan into concrete positions, groups, colors, and node titles.
- `classify.py`: deterministic fallback role classification for unassigned or low-confidence nodes.
- `report.py`: before/after score, movement summary, warnings, and rationale.

## M1 Foundation Contract Status

M1 lands the read-only contract and graph-fact substrate for later layout work. It deliberately does not add a coordinate compiler, CLI command, API endpoint, LLM call path, topology mutation, or automatic main-flow integration.

The authoritative apply-time substrate remains the original LiteGraph UI JSON plus the layout-store sidecar envelope. Reorganisation modules may read that substrate to derive facts, projections, validation diagnostics, and assessment reports, but M1 does not rewrite widgets, links, node classes, graph topology, or final coordinates.

The contract path uses frozen dataclasses plus a custom strict parser/validator. M1 intentionally does not add `pydantic` as a runtime dependency and does not emit a standalone schema artifact; `vibecomfy.porting.reorganise.parse.LAYOUT_PLAN_SCHEMA_V1` is the in-code schema dictionary and parser-adjacent documentation source.

## Agent Input: Pythonic Dataflow Projection

The agent should not receive only a flat node list plus edge list. That is less intuitive than how Python values feed into calls.

Instead, give it a non-executable Pythonic projection with stable scoped references:

```python
# VibeComfy Layout Projection v1
# Non-executable. Stable refs are authoritative.

ckpt = CheckpointLoaderSimple(
    ckpt_name="model.safetensors",
)  # ref: ["", "ckpt_uid"] role_hint=model_loader ui=(120, 80)

model = ckpt.MODEL
clip = ckpt.CLIP
vae = ckpt.VAE

positive = CLIPTextEncode(
    clip=clip,
    text="a cinematic portrait",
)  # ref: ["", "pos_uid"] role_hint=positive_prompt ui=(400, 360)

negative = CLIPTextEncode(
    clip=clip,
    text="blur, low quality",
)  # ref: ["", "neg_uid"] role_hint=negative_prompt ui=(400, 620)

latent = EmptyLatentImage(
    width=1024,
    height=1024,
)  # ref: ["", "latent_uid"] role_hint=latent_source ui=(430, 900)

samples = KSampler(
    model=model,
    positive=positive.CONDITIONING,
    negative=negative.CONDITIONING,
    latent_image=latent.LATENT,
    steps=30,
    cfg=7,
)  # ref: ["", "sampler_uid"] role_hint=sampler ui=(900, 520)

image = VAEDecode(
    samples=samples.LATENT,
    vae=vae,
)  # ref: ["", "decode_uid"] role_hint=decode ui=(1280, 520)

SaveImage(
    images=image.IMAGE,
    filename_prefix="vibecomfy",
)  # ref: ["", "save_uid"] role_hint=output ui=(1640, 520)
```

This should be accompanied by compact derived facts:

```text
terminal_path ["", "save_uid"]: ["", "sampler_uid"] -> ["", "decode_uid"] -> ["", "save_uid"]
shared_node ["", "ckpt_uid"]: consumers=["", "pos_uid"], ["", "neg_uid"], ["", "sampler_uid"], ["", "decode_uid"]
candidate_pair ["", "pos_uid"], ["", "neg_uid"]: relation=parallel_prompt_pair
virtual_link ["", "set_model_uid"] -> ["", "get_model_uid"]: name=ModelPipe
existing_group Sampling: nodes=[["", "sampler_uid"]]
```

The projection should include current UI facts: existing group, position, size, mode, pinned flag, helper status, fan-in/fan-out counts, upstream/downstream role hints, and Set/Get virtual links.

This cannot reuse `render_edit_projection(...)` as-is. The edit projection is useful precedent for address preservation, but it does not include enough layout-specific facts. `render_layout_projection(...)` must add deterministic graph facts before the agent sees the workflow:

- Terminal paths, with terminal type: image, video, audio, preview, save.
- WCC and SCC component IDs.
- Topological rank and semantic role hints with confidence.
- Fan-in/fan-out counts and shared-node signatures.
- Candidate branch sets: shared upstream, shared downstream, no dependency.
- Sampler relation candidates: sequential, parallel, alternative, separate terminal path, ambiguous.
- Effective virtual links for Set/Get and other broadcast helpers.
- Reroute chains and edge-path hints.
- Existing group membership and a group coherence score.
- Current UI position, size, color, title, mode, and pinned state.
- Scope path for every node and group.

The agent-facing data should be intuitive, but the backend-owned graph facts must be explicit enough that the agent is not forced to rediscover topology from prose.

## Agent Output: Semantic LayoutPlan

The agent should output JSON, not executable Python and not raw full-workflow coordinates. The M1 envelope is `LayoutPlan v1`:

Example:

```json
{
  "version": 1,
  "sections": [
    {
      "id": "model_pipe",
      "title": "MODEL PIPE",
      "kind": "loaders",
      "role_hint": "loader",
      "nodes": [["", "ckpt_uid"]]
    },
    {
      "id": "prompts",
      "title": "PROMPTS",
      "kind": "conditioning",
      "role_hint": "conditioning",
      "nodes": [["", "pos_uid"], ["", "neg_uid"]]
    },
    {
      "id": "sampling",
      "title": "SAMPLING",
      "kind": "sampling",
      "role_hint": "sampler",
      "nodes": [["", "latent_uid"], ["", "sampler_uid"]]
    },
    {
      "id": "output",
      "title": "OUTPUT",
      "kind": "output",
      "role_hint": "output",
      "nodes": [["", "decode_uid"], ["", "save_uid"]]
    }
  ],
  "shared_nodes": [
    {
      "node": ["", "ckpt_uid"],
      "home": "model_pipe",
      "label": "model/clip/vae"
    }
  ],
  "helper_placements": [],
  "sampler_relations": [],
  "unassigned_policy": "classify_deterministically"
}
```

The parser must reject unknown top-level and nested keys, unknown section kinds, malformed helper placements, forbidden backend-owned fields, and bare UID references. The validator then rejects unknown refs, duplicate or missing primary ownership, invalid helper targets, cross-scope primary ownership, invalid subgraph boundaries, forbidden topology and coordinate payloads, and sampler relationship contradictions proven by graph facts.

Allowed M1 section kinds are semantic ownership buckets:

- `loaders`
- `conditioning`
- `latent`
- `sampling`
- `decode`
- `output`
- `control`
- `postprocess`
- `utility`
- `branch`
- `container`
- `custom`

Canonical node refs are always:

```json
["scope_path", "uid"]
```

Never use bare UIDs, because subgraphs and scoped nodes need the same address model as agent-edit.

`scope_path` is the scope-chain string and `""` means the root workflow scope. Raw LiteGraph integer IDs are not durable plan references.

Backend-owned fields are not agent-authored in v1. This includes coordinates (`pos`, `position`, `coords`, `x`, `y`, `size`), topology (`links`, `link`, `edges`, `flow`, `flows`, `topology`), widgets and node payloads (`widgets`, `node_payload`, `raw_node`, `raw_link`), and derived ownership/fact fields such as `shared_nodes.consumers`. The backend computes topology, consumers, dependency order, and future coordinates from the LiteGraph UI JSON and graph facts.

Every non-helper node must be owned by exactly one primary section. Helper nodes may be handled through `helper_placements`. If the agent leaves nodes unassigned, the plan may set an explicit `unassigned_policy`:

```json
{
  "unassigned_policy": "classify_deterministically"
}
```

Allowed unassigned policies:

- `reject`
- `classify_deterministically`
- `preserve_existing`

Schema default for v1: `classify_deterministically`. Omission is normalized to this value, not rejected, but the report must list every backend-assigned node.

Optional `sampler_relations` are semantic claims only. Allowed kinds are `same_sampler_pair`, `parallel_sampler_branch`, `sampler_refines`, `sampler_precedes`, and `independent_samplers`. They cannot override topology facts.

The agent decides semantic structure:

- Which nodes belong together.
- Which sections are shared infrastructure.
- Which branches are parallel.
- Which paths are sequential.
- Which helpers should be near producers or consumers.
- Which groups deserve special names.

The backend decides coordinates.

## Helper Placement Contract

Set/Get, reroute, primitives, switches, and notes should not be forced into primary semantic ownership when that would make the layout misleading.

M1 uses a separate helper placement channel:

```json
{
  "helper_placements": [
    {
      "helper": ["", "set_model_uid"],
      "kind": "near-producer",
      "target": ["", "ckpt_uid"],
      "reason": "ModelPipe producer"
    },
    {
      "helper": ["", "get_model_uid"],
      "kind": "near-consumer",
      "target": ["", "sampler_uid"],
      "reason": "ModelPipe consumer"
    },
    {
      "helper": ["", "reroute_uid"],
      "kind": "edge-path",
      "from": ["", "pos_uid"],
      "to": ["", "sampler_uid"]
    }
  ]
}
```

Allowed helper placements:

- `near-producer`
- `near-consumer`
- `edge-path`
- `inside-section`

Required fields by placement:

| `kind` | Required fields | M1 validation behavior |
|---|---|---|
| `near-producer` | `target` | `helper` must be a helper/UI node and `target` must be a non-helper node in the same scope. |
| `near-consumer` | `target` | `helper` must be a helper/UI node and `target` must be a non-helper node in the same scope. |
| `edge-path` | `from`, `to` | `helper` must be a helper/UI node; both endpoints must be valid non-helper refs in the helper's scope. |
| `inside-section` | `section_id` | `helper` must be a helper/UI node and `section_id` must refer to an existing section. |

Missing required fields are parser or validation errors. Helper/UI nodes are invalid in primary section ownership and shared-node home channels.

Graph facts include Set/Get virtual links and reroute/source passthrough facts for reasoning, ranking, and validation. M1 does not add/remove Set/Get/reroute nodes or change helper topology.

## Top-Level Grouping Rules

The agent should use ownership rules:

- A node belongs to the group for the job it primarily performs.
- Shared infrastructure lives in the earliest shared upstream section.
- Nodes with one main consumer live near that consumer, unless their role has a standard section and there are multiple sibling nodes of that role.
- Constants, primitives, and filename widgets live near the node they configure.
- Set nodes live near producers; Get nodes live near consumers.
- Reroute nodes are visual furniture and should usually be preserved or placed on the edge path. Cross-group reroutes float between group boxes and are excluded from primary group bounding boxes.
- Existing human groups are preserved by default if coherent.

Default semantic roles:

- `input`: image/video/audio/mask loads, dimensions, source media.
- `model`: checkpoint, UNet, CLIP, VAE, LoRA, model patches.
- `conditioning`: prompts, conditioning combine/concat, CLIP text encodes.
- `control`: ControlNet, IPAdapter, reference image conditioning, pose/depth guidance.
- `preprocess`: resize/crop/depth/pose/segmentation/image preprocessing.
- `sampling`: KSampler and sampler-related latent/noise scheduling.
- `decode`: VAE decode and immediate decode transforms.
- `postprocess`: upscale, enhance, composite, interpolation, color/post effects.
- `output`: Save/Preview/VideoCombine/audio terminal output.
- `utility`: primitives, switches, math, Set/Get, reroutes.
- `annotation`: notes and labels.

Default ownership policy:

- `VAEDecode` and immediate decode-to-terminal transforms live in `output` when the path is simply `sampler -> decode -> save/preview/video combine`.
- Use a separate `decode` section only when there are multiple decode nodes, decode-side branching, decode-specific controls, or post-decode transforms before terminal output.
- `EmptyLatentImage` and latent source nodes live in `sampling` when their only consumer is a sampler. They live in `input` only when they behave like user-facing source media or feed several downstream paths.
- Prompt pairs (`positive`/`negative`) are grouped in a `conditioning` section and may receive a future local `pair` template.
- Two equivalent single-node siblings may use a future local `pair` template; promote to a future `parallel_branches` local template when each sibling owns an internal chain or terminal path.
- Symmetric branches with no objective primary should use neutral names such as `BRANCH A`, `BRANCH B`, or role-derived names. Use `MAIN`/`VARIATION` only when topology, title, active output, or user metadata supports that distinction.
- For parallel sampler branches with their own decode/output terminal path, keep `latent -> sampler -> decode -> save` inside each branch pipeline. Do not split decode/output into separate top-level sections unless the terminal path is shared or complex.
- `shared_nodes` is for broad infrastructure and cross-section producers whose home matters visually, especially model, CLIP, VAE, source media, and reusable masks. It is not required for every ordinary edge that crosses section boundaries.
- Separate `VAELoader`, `CLIPLoader`, LoRA, and model-patch nodes are independent shared infrastructure nodes and should receive their own home in the model pipe or model modifier section.

## Multiple Samplers

Multiple samplers require relation classification before layout:

### Sequential / Refiner

If sampler B consumes sampler A's latent/image output, they are sequential.

```text
BASE SAMPLER -> REFINER SAMPLER -> DECODE -> OUTPUT
```

M1 plan shape:

```json
{
  "version": 1,
  "sections": [
    {
      "id": "two_stage_sampling",
      "title": "TWO-STAGE SAMPLING",
      "kind": "sampling",
      "role_hint": "sampler",
      "nodes": [["", "sampler_base_uid"], ["", "sampler_refiner_uid"]]
    },
    {
      "id": "output",
      "title": "OUTPUT",
      "kind": "output",
      "role_hint": "output",
      "nodes": [["", "decode_uid"], ["", "save_uid"]]
    }
  ],
  "sampler_relations": [
    {
      "kind": "sampler_refines",
      "samplers": [["", "sampler_base_uid"], ["", "sampler_refiner_uid"]],
      "source": ["", "sampler_base_uid"],
      "target": ["", "sampler_refiner_uid"]
    }
  ]
}
```

### Parallel Siblings

If samplers share upstream model/prompt inputs and do not depend on each other, they are parallel.

```text
SAMPLER A -> DECODE A -> OUTPUT A
SAMPLER B -> DECODE B -> OUTPUT B
```

M1 plan shape:

```json
{
  "version": 1,
  "sections": [
    {
      "id": "sampling_main",
      "title": "MAIN",
      "kind": "branch",
      "role_hint": "sampler",
      "nodes": [["", "latent_a_uid"], ["", "sampler_a_uid"], ["", "decode_a_uid"], ["", "save_a_uid"]]
    },
    {
      "id": "sampling_variation",
      "title": "VARIATION",
      "kind": "branch",
      "role_hint": "sampler",
      "nodes": [["", "latent_b_uid"], ["", "sampler_b_uid"], ["", "decode_b_uid"], ["", "save_b_uid"]]
    }
  ],
  "shared_nodes": [
    {"node": ["", "model_uid"], "home": "model_pipe"},
    {"node": ["", "positive_uid"], "home": "prompts"},
    {"node": ["", "negative_uid"], "home": "prompts"},
    {"node": ["", "vae_uid"], "home": "model_pipe"}
  ],
  "sampler_relations": [
    {
      "kind": "parallel_sampler_branch",
      "samplers": [["", "sampler_a_uid"], ["", "sampler_b_uid"]]
    }
  ]
}
```

### Alternatives

If one sampler is active and others are muted/bypassed/disconnected alternatives, place active first and alternatives lower or to the side.

### Separate Terminal Paths

If samplers feed different terminal output types, such as image and video, split into terminal-path branches or separate groups.

### Ambiguous

If topology does not establish the relationship, trigger a second-stage intra-group agent pass or use deterministic fallback with a warning.

Deterministic sampler decision table:

| Evidence | Relationship | Layout |
|---|---|---|
| Sampler B consumes Sampler A latent/image directly or through decode/encode bridge | sequential/refiner | `pipeline` |
| Samplers share model and prompt inputs, have no path between them, and feed equivalent terminal types | parallel siblings | `parallel_branches` |
| One sampler is muted/bypassed or disconnected while another active sampler reaches terminal output | alternatives | `alternatives` |
| Samplers feed different terminal output types or unrelated terminal paths | separate terminal paths | separate sections or stacked branches |
| Samplers are in different WCCs | disconnected islands | separate island sections |
| None of the above | ambiguous | second-stage agent or reject with feedback |

Sequential/refiner detection should use a short whitelist for bridge paths. Treat direct latent/image consumption, `VAE Decode -> VAE Encode`, and known latent/image bridge nodes as sequential. Do not infer sequential through arbitrary upscale, postprocess, or utility chains unless node taxonomy explicitly marks them as bridge-compatible.

For 3+ samplers, classify relations pairwise, then compose:

- all sequential: one `pipeline`;
- all parallel equivalent terminal paths: one `parallel_branches`;
- one sequential chain plus independent equivalent terminal path(s): `parallel_branches` where one branch is a `pipeline`;
- mixed output modalities: separate terminal-path sections stacked by output type;
- contradictory or incomplete relation graph: second-stage agent with boundary nodes.

For alternatives, inspect terminal reachability, not only sampler node state. If a sampler is active but its terminal path is muted/bypassed/disconnected, treat that path as an alternative.

The validator must reject or normalize contradictions. If the agent marks two samplers as parallel but topology shows a direct or bridge-whitelisted dependency, the backend rewrites to `pipeline` with a warning. If the dependency is indirect and not bridge-whitelisted, reject or send to second-stage planning.

For ambiguous sampler clusters, second-stage boundary nodes are the shared upstream producers consumed by two or more sampler paths, terminal outputs reachable from those samplers, and one-hop external consumers/producers needed to interpret branch purpose. The second-stage agent receives only those boundary summaries plus the cluster nodes.

## Programmatic Layout Compiler

The compiler takes `LayoutPlan` and computes actual layout.

This is a real semantic layout compiler, not a thin wrapper over the existing topology-first layout engine. The current engine can supply algorithms and helpers, but semantic group layout requires additional code for section ranking, branch layout, group preservation, and aesthetics.

Steps:

1. Normalize sections and fill unassigned nodes with deterministic role classification.
2. Validate every referenced UID exists.
3. Resolve shared node ownership.
4. Build a group dependency graph: if any node in group A feeds any node in group B, add `A -> B`.
5. Collapse cycles into local clusters if needed.
6. Assign left-to-right rank by longest upstream path.
7. Apply semantic minimum ranks.
8. Assign rows/bands by workflow template and group role.
9. Cluster same-rank siblings into vertical stacks.
10. Layout nodes inside each group using local templates.
11. Apply helper layout for Set/Get/reroutes/notes using the helper placement contract.
12. Compute group bounding boxes from primary node rectangles plus padding; cross-group helpers do not expand group bounds.
13. Resolve overlaps by pushing lower-priority stacks downward.
14. Apply colors, titles, and metadata.
15. Verify structural hash unchanged, excluding UI-only fields.

### Group Left-To-Right Order

Use dependency rank first:

```text
rank(group) = max(parent.rank + 1 for parent in upstream_groups)
```

Then apply semantic minimum order:

```text
input
model
preprocess
conditioning
control
sampling
decode
postprocess
output
utility
annotation
```

In medium/complex workflows, use Nathan-style two-row layout:

```text
Top row:
MODEL PIPE -> MODEL MODIFIERS -> FINAL MODEL

Bottom row:
INPUTS -> PREPROCESS -> CONDITIONING/CONTROL -> SAMPLING -> DECODE/POSTPROCESS -> OUTPUT
```

### Existing Group Policy

Existing groups must have an explicit policy. Compute group coherence before the agent pass:

```text
coherence =
  role_purity
  + edge_internality
  + bounding_box_fit
  + title_signal
  - overlap_penalty
  - orphan_penalty
```

Policies:

- `preserve`: keep nodes, title, color, and bounding where possible.
- `rename_only`: keep membership and bounding, update title/color.
- `resize_only`: keep membership/title/color, recompute bounding.
- `rename_and_resize`: keep membership, update title/color, and recompute bounding.
- `semantic_preserve`: keep coherent members, move only incoherent outliers.
- `dissolve_with_warning`: remove/rebuild incoherent group, report why.
- `force_regroup`: ignore existing groups.

Default:

- Coherent group with bad title and bad bounds: `rename_and_resize`.
- Coherent group with bad title only: `rename_only`.
- Coherent group with bad bounds only: `resize_only`.
- Incoherent group: `semantic_preserve`.
- User-selected `--force-regroup`: `force_regroup`.

### Which Groups Get Stacked

Stack groups vertically when they are siblings:

- Same rank and same role family.
- Same upstream signature and same downstream signature.
- No dependency between them.
- Parallel branches.
- Separate terminal paths.
- Alternatives.
- Disconnected islands.

Example:

```text
CONTROL DEPTH -> SAMPLING
CONTROL POSE  -> SAMPLING
CONTROL CANNY -> SAMPLING
```

These share downstream `SAMPLING`, have compatible role, and no edges between them, so they stack in the same column.

Disconnected islands are sorted by terminal path importance, then semantic minimum order, then original canvas position. Islands that contain no terminal output and only model/utility setup should attach visually to the nearest consuming island when virtual/effective edges exist; otherwise they become a separate stacked island titled from their dominant role, for example `MODEL SETUP ISLAND`, `UTILITY ISLAND`, or `DISCONNECTED ISLAND 2`. Mixed top-row/bottom-row islands keep the two-row template inside each island rather than floating unrelated model-only islands across another island's generation row.

### Local Group Templates

The compiler should support a small deterministic template library:

- `single`: one node centered.
- `pair`: two related nodes side-by-side or stacked.
- `row`: ordered left-to-right.
- `pipeline`: topological left-to-right chain.
- `fan_in`: input nodes stacked left, target centered right.
- `fan_out`: source left, outputs stacked right.
- `parallel_branches`: branch pipelines stacked vertically.
- `alternatives`: active branch first, inactive below/side.
- `grid`: many equivalent nodes in a compact grid.
- `hub_and_spokes`: shared node with many consumers.
- `notes_sidebar`: notes above or left.

Template coordinates are deterministic:

```text
group.x = rank * GROUP_COLUMN_PITCH
group.y = row_offset + stack_index * (group_height + STACK_GAP)

node.x = group.x + local_col * NODE_COLUMN_PITCH
node.y = group.y + local_row * NODE_ROW_PITCH
```

Then recompute group bounds from actual node sizes.

### Aesthetic Constants And Acceptance Metrics

Define concrete geometry constants before implementation:

```text
CANVAS_MARGIN_X = 80
CANVAS_MARGIN_Y = 80
GROUP_PAD_X = 48
GROUP_PAD_Y = 56
GROUP_TITLE_RESERVED_Y = 44
GROUP_COLUMN_GAP = 180
GROUP_STACK_GAP = 120
NODE_COLUMN_GAP = 90
NODE_ROW_GAP = 48
BRANCH_ROW_GAP = 96
MIN_GROUP_WIDTH = 420
MIN_GROUP_HEIGHT = 180
```

Spacing presets can scale these:

- `compact`: 0.75x
- `balanced`: 1.0x
- `wide`: 1.35x

The compiler must report numeric metrics:

- `node_overlap_count == 0`
- `group_overlap_count == 0`, except allowed nested/group-contained cases
- `backwards_edge_ratio <= 0.10` for visible non-helper links
- `crossing_proxy_score` improves versus baseline or remains below threshold
- `min_node_gutter_px >= NODE_ROW_GAP`
- `max_helper_distance_px <= configured threshold` unless a later compiler explicitly preserves an existing helper position
- `idempotence_pos_delta_px <= 2` on second reorganise pass
- `unassigned_non_helper_count == 0`
- `structural_hash_unchanged == true`

Beauty gates should be deterministic first. Browser/screenshot review can be added later for golden examples, but v1 needs numeric layout gates to avoid producing merely non-overlapping but ugly graphs.

## Second-Stage Intra-Group Planning

Most groups should be laid out by code only. Use a second agent pass only for complex or ambiguous groups.

Complexity score:

```text
complexity =
  node_count
  + 2 * branch_count
  + 2 * sampler_count
  + terminal_count
  + helper_count
  + 3 if mixed_roles
  + 3 if cyclic_or_unrankable
```

Suggested thresholds:

- `0-8`: deterministic layout only.
- `9-15`: deterministic layout plus validation.
- `16+`: ask second-stage agent for intra-group plan.
- Any group with `sampler_count > 1`: second-stage unless topology clearly says sequential or parallel.

The second-stage agent should receive only the group plus boundary nodes:

```text
Boundary inputs: model, positive, negative, vae
Group nodes: samplers, latent ops, decoders
Boundary outputs: save image, video combine
```

It returns `IntraGroupPlan v1`, such as branch decomposition and template selection. The backend still computes exact coordinates.

For huge workflows, add a top-down decomposition pass before section-level planning:

- If `node_count > 80`, `edge_count > 160`, or projected prompt exceeds the configured token budget, emit a compact projection first: terminal paths, WCCs, SCCs, role histograms, sampler relation graph, existing groups, and high-fanout shared producers.
- Partition into coarse islands/terminal paths/model-pipe units before asking for detailed section plans.
- Send each coarse unit through the normal section/intra-group pipeline with boundary summaries.
- Scale complexity thresholds relative to graph size for large workflows: `simple <= max(8, 0.08 * node_count)`, `validate <= max(15, 0.15 * node_count)`, and second-stage above that.
- Avoid O(n^2) edge-crossing checks on large graphs; use sampled or rank-adjacent crossing proxies with runtime budgets.

## Subgraph Scopes

Subgraphs use the same canonical scoped refs as agent-edit: `["scope_path", "uid"]`. The projection should show nested scopes explicitly, preferably as indented Pythonic blocks plus a flat canonical-ref table.

Default v1 policy:

- Treat subgraph boundaries as layout containers. The compiler lays out the inside of a subgraph in that scope, then places the subgraph container as a unit in the parent scope.
- Do not assign nodes from different scopes to the same primary section unless the section is explicitly marked as a parent-scope container.
- Shared nodes that cross a subgraph boundary keep their home in the scope where the producer lives; parent layout sees only a boundary summary and effective edge.
- Existing groups inside subgraphs are scored and preserved within that subgraph scope.
- Validation rejects incoherent cross-scope section membership and bare refs.

Add a section kind only if implementation needs it:

- `subgraph_container`: parent-scope section that represents a child scope as one visual unit.

Tests must include a non-trivial subgraph pipeline, shared producer crossing a scope boundary, existing groups inside a subgraph, idempotence on scoped layouts, and rejection of incoherent cross-scope ownership.

## Automatic Main-Flow Integration

The automatic path is conservative. Explicit organisational intent uses the
dedicated `reorganise` route; ordinary functional edits stay functional and may
only receive layout advice after the edit candidate is already successful and
applyable.

Before or alongside classify, deterministic layout hints are derived from the
existing reorganise assessment and graph-facts helpers. When a graph appears
hard to review, the compact hint can be added to classify context:

```text
The current workflow layout appears hard to read: overlap_count=..., backward_edges=..., missing_groups=...
Consider offering a reorganisation candidate if the user request implies readability or if a functional edit would be hard to review in the current layout.
```

These hints are advisory evidence only. They must not route a concrete
functional request to `reorganise` on their own, and they must stay compact:
verdict, overlap signal, backward-edge signal, spacing/group/helper signal, and
a concise review-hostile flag.

Do not silently reorganise. Do not auto-apply. Do not start a second hidden edit
phase.

Config:

```text
VIBECOMFY_REORGANISE_AUTO=off|suggest|candidate
```

Default: `suggest`.

Semantics:

- `off`: no post-edit layout offer is emitted.
- `suggest`: after a successful applyable functional candidate, deterministic
  before/after layout evidence may add `layout_reorganisation` advisory metadata
  and suggest `/reorganise_comfy_workflow`. The functional candidate graph is
  not moved or replaced.
- `candidate`: experimental rollout mode. After a successful applyable
  functional candidate, reuse `preview_reorganise_workflow` and the existing
  durable candidate lifecycle to prepare an optional layout-only candidate. If
  previewing, structural no-op evidence, candidate write, or apply eligibility
  fails, retain the functional candidate and report the failed closed state.

Invalid config values fail closed to `off` with visible config metadata. The
default remains `suggest` for rollout because it preserves main-flow behavior
while collecting reviewable advice and golden/browser coverage evidence.

## CLI And Skill Surface

Add:

```bash
vibecomfy reorganise workflow.json --assess
vibecomfy reorganise workflow.json --preview --out cleaned.json
vibecomfy reorganise workflow.json --apply
```

Add skill:

```text
docs/agent-skill/skills/reorganise-comfy-workflow/SKILL.md
```

Route `/reorganise_comfy_workflow`, "organise this workflow", "clean up the
canvas", and "make this readable" to the explicit reorganise path using
canonical `route="reorganise"` and `task="layout_reorganise"`. It should
produce a candidate and report rather than immediately applying, and it should
use the normal candidate accept/reject/apply-eligibility lifecycle instead of a
parallel apply path.

## Validation And Guardrails

Hard gates:

- Every referenced node UID exists.
- Each node has at most one primary owner.
- Shared nodes have one home group.
- Agent cannot request raw graph topology changes.
- If plan says branches are parallel but graph has a dependency, normalize to sequential or reject.
- Pinned nodes preserve positions unless force is enabled.
- Existing groups are preserved unless `force_regroup` is enabled.
- Structural hash is unchanged except UI-only fields.
- No reorganise path may change topology: node classes, node identities, links,
  widget values, prompts, runtime payloads, generated API graph state, and edge
  endpoints are outside the layout contract.
- Candidate round-trips through LiteGraph/VibeComfy without losing identity.
- Final layout has no node overlaps.
- Second reorganise pass is idempotent or near-idempotent.
- The plan schema is strict and rejects unknown section kinds or unknown keys.
- The compiler owns topology and group dependency order; agent-authored hints cannot override graph facts.
- Effective virtual edges participate in rank/proximity scoring.

## Aesthetic Acceptance Criteria

The result should be scored by deterministic checks:

- Zero node overlaps.
- Most edges flow left-to-right.
- Major role groups exist and have readable titles.
- Groups use stable role colors.
- Parallel siblings are stacked consistently.
- Sequential chains are left-to-right.
- Shared infrastructure is upstream and visually central to consumers.
- Helpers are near producers/consumers, not isolated randomly.
- The canvas has enough spacing for visible connections.
- Re-running the organiser produces the same layout.

These criteria must be compiled into measurable report fields rather than left as prose.

## Test Plan

Add focused tests:

- `tests/test_reorganise_assess.py`
- `tests/test_reorganise_projection.py`
- `tests/test_reorganise_plan_parse.py`
- `tests/test_reorganise_validate.py`
- `tests/test_reorganise_compile.py`
- `tests/test_reorganise_multiple_samplers.py`
- `tests/test_cli_reorganise.py`

Important scenarios:

- Simple text-to-image workflow.
- Positive/negative prompt pair.
- ControlNet depth/pose parallel branches.
- IPAdapter with shared reference input.
- Sequential base/refiner samplers.
- Parallel sampler variation paths.
- Alternative muted/bypassed sampler branches.
- Shared VAE/CLIP/model nodes.
- Set/Get virtual links.
- Existing coherent groups.
- Existing bad groups with `force_regroup`.
- Large workflow with multiple terminal paths.
- Subgraph scopes.

## Open Questions

- Should model pipe be top-row for every workflow, or only when model nodes are shared across more than one downstream role?
- How much of existing group membership should be trusted when group names are vague or bounding boxes are wrong?
- Should color be applied to groups only in v1, or also node `color`/`bgcolor`?
- Should `/reorganise_comfy_workflow` expose a `wide`, `balanced`, and `compact` spacing preset?
- Do we need a visual screenshot/regression oracle for layout beauty, or are geometric/semantic metrics enough for v1?

## Codex Review Follow-Ups

A high-reasoning Codex review on this plan agreed with the broad architecture but flagged these required tightenings before implementation:

- Treat the semantic compiler as a new layout engine, not a wrapper over the current topology layout.
- Use canonical scoped node refs everywhere.
- Make `LayoutPlan` a strict discriminated schema.
- Compute group dependencies from graph topology; remove agent-authored `flows` from v1.
- Give the agent explicit graph facts, not just Pythonic dataflow prose.
- Add `helper_placements` for Set/Get/reroute/note handling.
- Define existing-group coherence and policies.
- Define numeric geometry and aesthetic acceptance gates.
- Keep automatic main-flow behaviour suggestion-only by default. Golden fixtures
  and browser coverage are the gate for enabling experimental `candidate` mode
  in a specific deployment.
