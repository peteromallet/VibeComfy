# M1: Layout Contract And Graph Facts

## Outcome

Implement the foundation for a ComfyUI workflow reorganisation capability: deterministic layout assessment, graph-fact extraction, a Pythonic agent-facing layout projection, and a strict `LayoutPlan v1` contract/parser/validator. This milestone does not compute final coordinates.

## Scope

In scope:

- Add `vibecomfy/porting/reorganise/` foundation modules for assessment, projection, plan types, parsing, validation, classification, and reporting stubs.
- Define a strict `LayoutPlan v1` schema, preferably with dataclasses plus JSON-schema/Pydantic-style validation.
- Use canonical scoped node refs everywhere: `["scope_path", "uid"]`.
- Reject unknown section kinds, unknown keys, forbidden topology fields, duplicate ownership, missing refs, and bare UID plan output.
- Generate deterministic graph facts before the agent pass:
  - terminal paths and terminal types;
  - WCC/SCC component IDs;
  - topological rank;
  - role hints with confidence;
  - fan-in/fan-out counts;
  - shared-node signatures;
  - candidate parallel branch sets;
  - sampler relation candidates;
  - Set/Get effective virtual links;
  - reroute chains and edge-path hints;
  - existing group membership and coherence score;
  - current UI position, size, color, title, mode, and pinned state.
- Render a non-executable Pythonic dataflow projection for agent reasoning.
- Render scoped/subgraph structure explicitly: nested Pythonic blocks plus a canonical-ref table.
- Add deterministic layout quality assessment: overlap count, backward edge ratio, missing/weak group signal, spacing density, group coherence, and helper-distance warnings.
- Preserve the lossless LiteGraph UI JSON as the apply source of truth.

Out of scope:

- Final coordinate layout.
- CLI or `/reorganise_comfy_workflow` user surface.
- Agent model calls.
- Main-flow auto integration.
- Set/Get conversion or graph rewiring.

## Locked Decisions

- Agent input is an intuitive Pythonic projection plus explicit graph facts.
- Agent output is strict JSON, not executable Python.
- `flows` are not agent-authored in v1; topology is compiler/backend-owned.
- `shared_nodes.consumers` are compiler-derived; the agent can choose only `home` and an optional label.
- Every non-helper node must be owned by exactly one section or fall through `unassigned_policy`; omitted policy normalizes to `classify_deterministically` and must be reported.
- Helper nodes use a separate `helper_placements` channel with required fields by placement kind: `target` for near-producer/consumer, `from`/`to` for edge-path, and `section_id` for inside-section.
- Default grouping policies: immediate `VAEDecode -> Save/Preview/VideoCombine` folds into output; simple latent source folds into sampling; two equivalent single-node siblings are `pair`; branch pipelines keep their own decode/output terminal nodes.
- Subgraph boundaries are layout containers in v1. Cross-scope primary section ownership is invalid unless represented as a parent-scope container.
- The current edit projection is precedent only; it is not sufficient for layout planning as-is.

## Open Questions

- Should schema validation use Pydantic, dataclasses plus custom parser, or a JSON Schema artifact generated from dataclasses?
- What exact group coherence weights should be used in v1?
- Which custom-node Set/Get class names beyond `SetNode`/`GetNode` should be recognized initially?

## Constraints

- Do not mutate graph topology, widgets, links, or node classes.
- Do not rely on raw LiteGraph integer IDs as durable plan references.
- Keep projection bounded for large workflows with summarized nodes and focused subprojections.
- Keep tests deterministic and offline.

## Done Criteria

- `LayoutPlan v1` schema is documented and enforced.
- Pythonic layout projection emits stable scoped refs and deterministic graph facts.
- Assessment returns a structured score/verdict and report details.
- Plan parser rejects malformed or unsafe output with typed diagnostics.
- Plan validator catches duplicate ownership, unknown refs, missing required ownership, bare refs, forbidden fields, invalid helper placements, cross-scope ownership errors, and contradictory sampler relations when topology proves otherwise.
- Tests cover simple T2I, prompt pair, Set/Get, reroute, existing groups, scoped/subgraph refs, multiple sampler relation detection, unassigned-policy defaulting, and malformed plans.

## Touchpoints

- `vibecomfy/porting/reorganise/*`
- `vibecomfy/porting/edit/ledger.py`
- `vibecomfy/porting/edit/projection.py`
- `vibecomfy/porting/layout/*`
- `vibecomfy/porting/layout_store.py`
- `tests/test_reorganise_assess.py`
- `tests/test_reorganise_projection.py`
- `tests/test_reorganise_plan_parse.py`
- `tests/test_reorganise_validate.py`
- `docs/plans/reorganise-comfy-workflow-plan.md`

## Anti-Scope

- Do not add a user-facing command yet.
- Do not call an LLM yet.
- Do not generate final UI JSON candidates yet.
- Do not introduce visual browser tests yet.

## Rubric

Overall plan difficulty: 4/5; selected profile: partnered-4; because the planning risk is contract/schema design across lossless UI identity, scoped graph facts, and future agent output validation.
