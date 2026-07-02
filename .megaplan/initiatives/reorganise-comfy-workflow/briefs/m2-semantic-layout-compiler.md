# M2: Semantic Layout Compiler

## Outcome

Implement the deterministic compiler that turns a validated `LayoutPlan v1` into concrete ComfyUI UI layout changes: node positions, section group boxes, titles, colors, spacing, and metrics, while preserving runtime graph semantics.

## Scope

In scope:

- Implement `vibecomfy/porting/reorganise/compile.py`.
- Treat this as a new semantic layout compiler, not a thin wrapper over the existing topology-first layout engine.
- Normalize sections and fill unassigned nodes using deterministic role classification.
- Resolve shared-node ownership and helper placement.
- Implement helper placement formulas for Set/Get/reroutes/notes before final overlap resolution; cross-group reroutes float between groups and do not expand primary group boxes.
- Build section dependency graph from effective graph topology.
- Collapse cycles into local clusters.
- Assign left-to-right group rank from graph topology plus semantic minimum ranks.
- Assign rows/bands using Nathan-style defaults:
  - model pipe on top row where warranted;
  - inputs/preprocess/conditioning/control/sampling/decode/postprocess/output on main row;
  - utilities/notes as sidebars or near their producer/consumer.
- Stack sibling groups vertically when they share rank/role/upstream/downstream and have no dependency.
- Implement local templates:
  - `single`, `pair`, `row`, `pipeline`, `fan_in`, `fan_out`, `parallel_branches`, `alternatives`, `grid`, `hub_and_spokes`, `notes_sidebar`.
- Implement default ownership policies from the plan: immediate decode folds into output; non-trivial decode becomes its own section; latent source folds into sampling unless it behaves like user-facing input; parallel sampler branches keep their terminal decode/output path inside each branch.
- Compute group bounding boxes with title/header space and stable role colors.
- Define a concrete role color palette and spacing presets: `compact`, `balanced`, `wide`.
- Implement existing-group policies: `preserve`, `rename_only`, `resize_only`, `rename_and_resize`, `semantic_preserve`, `dissolve_with_warning`, `force_regroup`.
- Implement disconnected-island ordering and auto-naming from dominant role/terminal importance.
- Implement subgraph-container layout semantics: lay out child scope internally, then place the scoped container in the parent.
- Add huge-workflow top-down decomposition for workflows over the configured node/edge/projection-token thresholds.
- Report numeric gates:
  - no node overlaps;
  - no unintended group overlaps;
  - bounded backwards-edge ratio;
  - crossing proxy improves or stays below threshold;
  - minimum gutters;
  - bounded helper distance;
  - idempotence delta;
  - structural hash unchanged.

Out of scope:

- Agent calls.
- CLI or skill surfaces.
- Main-flow integration.
- Whole-graph rewrites or Set/Get conversion.

## Locked Decisions

- Exact coordinates are compiler-owned, not agent-authored.
- Group dependency order is computed from topology, not model-provided `flows`.
- Effective virtual edges participate in rank/proximity scoring, but v1 does not add/remove helper nodes.
- Existing coherent groups are preserved/renamed/resized by policy; incoherent groups are handled with warnings.
- Sequential sampler normalization uses direct edges and bridge-whitelisted paths only; mixed 3+ sampler relation graphs compose into pipeline branches or trigger second-stage planning.
- Beauty must be measurable through deterministic metrics before browser screenshots are considered.

## Open Questions

- Exact default color palette values for each role.
- Exact threshold for `backwards_edge_ratio` in large workflows.
- How much to prioritize preserving existing user geometry versus achieving semantic layout.

## Constraints

- Structural graph hash must remain unchanged, excluding UI-only fields.
- Compiler output must be deterministic and near-idempotent.
- No network, ComfyUI runtime, or model files required for tests.
- Preserve pinned nodes unless force options explicitly override.

## Done Criteria

- Compiler accepts validated plans and returns a layout result/candidate patch with positions, groups, colors, titles, and metrics.
- Simple T2I, prompt pair, ControlNet parallel branches, IPAdapter-like reference chain, sequential samplers, parallel samplers, mixed sampler relation graphs, alternatives, shared VAE/model, Set/Get, reroutes, existing groups, disconnected islands, huge-workflow decomposition, and subgraph containers have deterministic tests.
- No-overlap and structural-hash gates pass for fixture workflows.
- Re-running the compiler produces idempotent or near-idempotent output.
- Failure reports explain which layout gate failed and why.

## Touchpoints

- `vibecomfy/porting/reorganise/compile.py`
- `vibecomfy/porting/reorganise/classify.py`
- `vibecomfy/porting/reorganise/report.py`
- `vibecomfy/porting/layout/*`
- `vibecomfy/porting/emit/ui.py`
- `vibecomfy/porting/layout_store.py`
- `tests/test_reorganise_compile.py`
- `tests/test_reorganise_multiple_samplers.py`
- `tests/test_reorganise_existing_groups.py`

## Anti-Scope

- Do not add frontend controls.
- Do not auto-run from agent-edit.
- Do not invent new ComfyUI node classes or helper nodes.

## Rubric

Overall plan difficulty: 4/5; selected profile: partnered-4; because the hard planning risk is a new deterministic layout compiler with aesthetic and semantic constraints that can pass structural tests while still producing poor visual results.
