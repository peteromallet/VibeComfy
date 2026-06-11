# Agent-Edit Phase 1 — Implementation Plan

The keystone phase from `docs/agent_edit_solution_spec.md` (v2): turn the edit path
into `apply(original_ui, delta)` over an identity-stamped substrate, with the agent
reading an address-preserving projection. Authoring is untouched. Lands behind a
flag, alongside the current path, then cut over. Incorporates a 3-model review
(Claude Opus + Sonnet + DeepSeek, 2026-06-02): the gaps they found are folded into
the components that own them — there is no separate "revision" section.

## Relationship to existing work
- **Reuses unchanged:** runtime wiring (`runtime`/`worker`/
  launcher), session/accept/audit/idempotency (`agent_session.py`, the accept
  routes), the panel UX, the scoped-uid machinery (`porting/uid.py`), the layout
  engine (`porting/layout*`, `layout_store.py`), and `EditorAheadError`
  (`refuse.py`) for user edits made between turns.
- **Replaces — on the edit path only:** `_stage_convert` (port convert),
  `_stage_load_python`, `_stage_lower`, `_stage_emit` (emit_ui_json regen), and the
  full-file prompt in `build_messages`. All of these stay for **authoring**.
- **Evolves:** the Phase-0 identity stamp (`_stamp_identity_on_original`) — moved to
  first-contact on the substrate, made subgraph-aware, and folded into C0; and
  `guard_emit` (API-space → full-UI assert, C6).

## Components and touchpoints

### C0. Substrate normalization + identity/bookkeeping ledger — NEW (foundation)
The single owner of identity and id allocation; everything downstream mints from it.
- **Scope-qualified identity.** Walk the graph *including nested subgraph scopes* and
  assign each node a stable `(scope_path, uid)` via `make_uid` / `mint_inner_uid`
  (`porting/uid.py:20`, `porting/scope.py:103`), written to
  `properties.vibecomfy_uid`. (The existing `_stamp_identity_on_original`,
  `agent_edit.py:210`, does a flat top-level node-id match over `graph["nodes"]` only
  — it must traverse subgraph definitions.) The uid lives in `properties`, which is a
  first-class field in litegraph `serialize()`/`configure()`, so it round-trips
  through accept→re-edit unchanged (the one structurally sound pillar — verified by
  review). Note: the legacy `vibecomfy_id` renumber is in `emit_ui_json`
  (`ui_emitter.py:1876`), *not* `convert_to_vibe_format`; the v2 edit path bypasses
  `emit_ui_json` entirely, so that renumber is not on our path — no short-circuit
  needed (legacy-path hygiene only).
- **Scope-aware monotonic allocator.** Carry node-id/link-id counters seeded from the
  graph root's `last_node_id`/`last_link_id` (`ui_emitter.py:2023`) **and per-subgraph
  definition** `state.lastNodeId`/`lastLinkId`. `add_node`/`upsert_link` mint from the
  right scope's counter and always advance the **root** counter for global uniqueness
  (the vendored backend dedupes subgraph ids against root `last_node_id` —
  `vendor/ComfyUI/comfy/component_model/workflow_convert.py:721`). Without this,
  applying the candidate collides ids or drops links, and the per-node C5 assert can't
  catch it (root/scope counters aren't per-node fields).
- Touch: `agent_edit.py::_stage_ingest`; new `porting/edit_ledger.py` (scope-aware uid
  traversal + allocator); reuses `porting/uid.py` + `porting/scope.py`.

### C1. Address-preserving projection (the read view) — NEW, replaces the scratchpad on the edit path
- Pure `project(original_ui, ledger) -> view`: compact, legible, **lossless on
  identity**. Per node: `(scope_path, uid)`, `class_type`, `mode` (so the agent sees
  bypassed/muted = 2/4), and each field by **substrate name** with its *kind* —
  literal widget vs input socket vs currently link-driven (a widget-converted-to-
  input shows as socketed, not as a writable literal). Dotted names verbatim; no
  `widget_N`, no helper lowering, no flattening. Plus edge summaries, schema
  hints (types/choices/defaults from `object_info`), and the **section** each node
  sits in (the group whose `bounding` box contains it — derived geometrically;
  verified on a real graph: "Decode" 5, "Sampler - First Pass" 18, "MODELS" 11, …)
  so the agent can target edits/additions by section name.
- **Virtual wires are KEPT as real nodes — never resolved (policy, not a flag).**
  Resolving Get/Set/Reroute away is an *authoring* transform (clean templates). The
  edit path copy-patches the verbatim original, which already contains those nodes, so
  there is nothing to resolve: the projection shows `Reroute`/`GetNode`/`SetNode` as
  ordinary nodes (annotated with their channel/passthrough role + the resolved
  endpoints *for the agent's comprehension only*), and every op addresses the **real**
  substrate node/link by uid. This dissolves the would-be inverse-map / re-stitch /
  fan-out complexity: a `GetNode` is just a node with N output links; "editing the link
  between A and B that runs through a reroute" means addressing the real `A→R` / `R→B`
  links, which the projection shows. (`keep_virtual_wires` stays a flag only for
  authoring.)
- **Untrusted content is fenced.** Node titles, widget values, group names and dotted
  field names are user-controlled and the v2 path has no AST sandbox. The projection
  wraps every such string in explicit data sentinels and the system prompt instructs
  the agent to treat sentinel-fenced content as data, never instruction; the op
  validator additionally refuses any op whose target/values were lifted verbatim from
  an injected delta-shaped string. (Defence-in-depth: the user still reviews the
  candidate before accept, and ops are structurally validated + applied under the
  guard — so worst case is a mis-proposed edit, not silent harm.)
- **Bypass-aware:** for an edge crossing a `mode:4` (bypass) node, annotate the
  *effective* dataflow source so the agent doesn't reason about a path the runtime
  reroutes around.
- **Budget-aware:** a 140-node graph is ~20–60K tokens of projection. Provide a
  focused/sparsified rendering (e.g. full detail for the task-relevant neighborhood,
  summary elsewhere) with a hard token gate — never a blind dump.
- No resolver: the view's addresses *are* the substrate's.
- Touch: new `porting/edit_projection.py`; `agent_provider.build_messages` renders
  this instead of the Python scratchpad.

### C2. Typed delta contract — NEW
- Ops (see spec §2.3/§8b): `set_node_field`, `add_node`, `remove_node`,
  `upsert_link`, `remove_link`, `reorder`, **`set_mode`**. JSON schema; the agent
  returns a `delta`, not a file (this also kills B13 — no fragile full-file parse).
- **`set_mode { target:[scope,uid], mode: 0|2|4 }`** — `mode` is a top-level litegraph
  node field (not a widget/input), so `set_node_field`'s `field_path` can't reach it;
  a dedicated op lets the agent honor "disable/bypass/mute this node" without touching
  any widget. (Without it, "disable the upscaler" is unexpressible.)
- `add_node.anchor` is **semantic** (the agent never emits pixels): a group title
  (place in that section), a node uid + `relation` (`near`/`right_of`/`below`), or
  `between:[uid,uid]`. C4 resolves it to coordinates.
- `build_messages` asks for the delta + the op schema; output is validated against
  the schema (unknown ops rejected).
- Touch: new `comfy_nodes/edit_ops.py` (schema + validation); `agent_provider`.

### C3. `apply(original_ui, delta) -> candidate_ui` — NEW (the core)
Two strict phases: **resolve-all, then mutate** (atomic).
- **Resolve pass (no mutation):** resolve every op target against the substrate to
  exactly one node/field/link. Because virtual wires are kept as nodes (C1), links are
  addressed as **real substrate links** by endpoint `(scope,uid,slot)` — no
  resolved↔raw inverse-map. Checks, all fail-loud, **reject the whole delta** (no
  half-applied candidate) with per-op diagnosis:
  - **Target resolvability:** `(scope_path, uid, field_path)` and link endpoints must
    each resolve to exactly one substrate location (else reject).
  - **Value validity:** for `set_node_field`/`add_node` fields where the schema is
    known, validate against `InputSpec.choices/min/max` and coerce/type-check
    (`schema/provider.py` parses these but nothing consumes them today — Area 2). An
    out-of-enum COMBO or out-of-range int is rejected here, not left to fail at queue
    time. Schema-less fields (uninstalled / v3 dotted) are written best-effort.
  - **Link type:** reject only when **both** endpoints have *known, concrete,
    incompatible* types. `*`/wildcard, COMBO, and missing-schema endpoints are allowed
    (the only existing predicate `socket_types_compatible`, `validate.py:484`, already
    treats `*`/missing as pass but at warning severity — we elevate the *known-vs-known*
    mismatch to rejection). Rationale: real user graphs are full of uninstalled custom
    nodes; hard-rejecting every no-schema link (as a naive read of Area 3 suggests)
    would block legitimate edits on exactly the graphs we care about.
- **Mutate pass (deep-copy original, touch only named targets):**
  - `set_node_field` → set one nested field (field_path). **If the input is
    currently driven by a link**, either remove that link (recorded in the audit) or
    reject with "field X is link-driven — unlink first"; never write a literal that
    the link silently overrides. Handle the widget↔input-socket dual location
    (`widgets_values[N]` and `inputs[]` `{"widget":…}`): `widgets_values` is a
    *positional* array, so when the schema is absent (v3 dotted field), recover the
    name→index map from the node's own `inputs[].widget.name` stubs (present even on
    link-driven widgets) rather than the schema — Area 6. Reject if a field_path
    resolves to two locations holding *different* values (an already-desynced
    original), rather than guess which wins.
  - `add_node` → materialize a LiteGraph UI node via a **new
    `materialize_litegraph_node(class_type, fields, schema, id, uid, pos)`** —
    extracted from `emit_ui_json`'s node loop (`ui_emitter.py:1744`). The existing IR
    builders (`workflow.py` `_NodeBuilder`, `templates.py:node`) produce IR/Python,
    **not** a UI node object, so they are NOT reusable here (review-corrected). Socket
    order + widget defaults come from `object_info` (`schema/parsing.py`); an
    uninstalled class returns no schema (`schema/provider.py:581`) → reject. Mint
    `(scope_path, uid)` + litegraph id from the C0 ledger; `place(...)` for `pos`.
  - `upsert_link`/`remove_link` → link mutations, **type-checked** vs schema; mint
    link ids from the ledger.
  - `remove_node` → if the node is a **passthrough** (Reroute/GetNode/SetNode),
    **re-stitch** upstream→downstream so data flow survives (reuse the conversion
    resolver's `_resolve_passthrough`, `subgraph_resolve.py:145`, which already
    rewires origin→consumer); for a plain node, **cascade-remove its dangling links**.
    Either way the link-only edits this forces on otherwise-untouched downstream nodes
    are exempted by C6. (Area 4: "cascade-remove" alone would sever a mid-chain
    reroute.)
  - `reorder` → widget/slot order on a named node.
- Touch: new `porting/edit_apply.py`.

### C4. Placement function — small NEW, reuses layout engine
`place(original_geometry, groups, new_node_links, anchor, relation) -> pos` — a
single-node, anchored variant of the existing layout engine. Best-effort cosmetic;
**never a correctness gate** (a mis-placed node still runs; the user can drag it).
Existing node positions never move. Algorithm:
1. **Reference point from connectivity** (graphs flow left→right): wired from `U` and
   into `D` → between them (x between `U.right` and `D.left`, y averaged); only `U` →
   right of it; only `D` → left of it. The agent's `anchor`/`relation` overrides.
2. **Collision-avoid:** candidate rect = pos + default size from schema (widget count
   → height, title → width); nudge down/right until it overlaps no existing or
   already-placed node.
3. **Section placement:** clamp inside the target group's `bounding`; if it would
   overflow, **grow that box minimally** to contain it (the one root-field mutation,
   tied to the add — C5 whitelists it as part of this op's delta).

**Section choice:** the target group is (a) the one the agent named in `anchor` (a
group title or a node uid — C1's projection labels each node with its section, which
is derivable purely by bounding-box overlap; verified on a real graph: "Decode" 5
nodes, "Sampler - First Pass" 18, "MODELS" 11, …), else (b) the group of the new
node's primary neighbor (its main input source / output target), else (c) free canvas
outside all boxes.

Root `groups` (and `extra`, `config`, `definitions`, `floatingLinks`, any unknown
root field) are otherwise preserved **verbatim** by C5's root passthrough —
forward-compatible by construction; only a box explicitly grown by an `add_node` is a
permitted change.
- Touch: `porting/edit_apply.py` calling into the existing layout engine.

### C5. Full-UI assert — NEW (replaces API-space `guard_emit` on the edit path)
- For every node **not** named in `delta` (after accounting for cascade link-cleanup
  from `remove_node`): assert `candidate[node] == original[node]` byte-identical
  (positions, widget order, annotations included — the content the API-space
  `guard_emit` drops).
- **Measured assumption (so this isn't illusory).** A fundamental-mechanism review
  warned the litegraph round-trip might churn untouched nodes, defeating byte-equality.
  Tested live on the 81-node LTX graph: `serialize() → configure() → serialize()` was
  **byte-stable** (zero per-node and zero root-field churn). So byte-identity IS a
  real target *provided* the apply uses `configure` (below). For robustness against
  node types that may not be idempotent, the assert normalizes **both** sides through
  one `serialize→configure→serialize` pass before comparing, so cosmetic churn can't
  cause a false refusal while content differences still do.
- Scope the comparison to `nodes[]`; **pass root-level fields (`groups`, `extra`, the
  id counters) through from the original** except for the explicit, op-attributed
  changes: the id counters advanced by C0's allocator, and a single group `bounding`
  **grown by C4** to contain an `add_node`. Those are whitelisted as effects of their
  ops; any *other* root-field or untouched-node change is a violation.
- **Performance (Area 9):** the normalize is **once per graph** (not per-node), and
  comparison is scoped to out-of-delta nodes; deep-copy is structural (LoadImage holds
  a *filename*, not base64, so no blob copy). Still, time-box the normalize (~200 ms);
  on a graph large enough to exceed it, fall back to a raw-dict compare with a small
  known-cosmetic-churn allow-list — **never silently skip the assert**.
- **Determinism prerequisite (Area 7):** the byte-assert only holds if emission is
  deterministic. The layout/placement engine *is* (verified: pure, sorted,
  no wall-clock/random) — except `_role_color_for_subgraph` (`groups.py:73`) uses
  `hash(name)`, which is `PYTHONHASHSEED`-randomized, so a group's `color` varies per
  process and would false-trip the assert. **Fixed now** in `groups.py`
  (`hash()` → `blake2b`); also benefits authoring determinism.
- Touch: `porting/edit_apply.py` (or `refuse.py::guard_full_ui`).

### C6. Editing test corpus — NEW (the only correctness bar for editing)
For the LTX set, the Gemini/ByteDance graph, and standard graphs, scripted deltas:
- `set_node_field` on a prompt **and** on a currently link-driven input (the seed
  case) — assert the link-vs-literal rule fires correctly.
- `add_node` + `upsert_link` inserting a node — assert it's valid, placed without
  overlap, and counters advanced.
- `remove_node` with downstream consumers — assert cascade cleanup + no spurious
  assert failure.
- A subgraph-internal target — assert scope resolution.
- A multi-turn re-edit — assert uid stability across accept→re-edit.
- `remove_node` on a **mid-chain Reroute** — assert re-stitch (flow preserved), not severed.
- `set_mode` to bypass a node — assert mode flips, nothing else changes.
- Rejection cases: an out-of-enum/out-of-range value; a known-vs-known
  type-incompatible `upsert_link` — assert the *whole delta* is rejected with per-op
  diagnosis (atomic), candidate unchanged.
- Every case asserts: targeted change present; **every other node byte-identical**;
  no unresolvable op escapes.
- **Audit (Area 8):** add a structured `delta_ops` section to `write_audit`
  (`agent_audit.py`) — each op + its collateral effects (e.g. the link a
  `set_node_field` unlinked, the re-stitch a `remove_node` performed). Today's audit
  has no op-structure, so the plan's "recorded in the audit" promises had no receiver.
  (Confirmed safe by review: idempotency already holds via response-replay; no
  double-apply; ledger is rebuilt per ingest so no stale uid leak.)
- Touch: `tests/test_agent_edit_apply.py` + fixtures; `agent_audit.py` (`delta_ops`).

## Wiring into the turn (flagged)
New edit path: `ingest (C0 stamp+ledger, C1 project)` → `agent (C2 delta)` →
`apply (C3 resolve→mutate)` → `assert (C5)` → accept. **Apply the accepted candidate
in place via `graph.clear(); graph.configure(candidate)` — NOT
`app.loadGraphData(candidate)`** (`vibecomfy_roundtrip.js:2410/2750`), which forks a
new workflow tab so the artifact the user keeps editing isn't the one we asserted on,
and `configure` is the path measured byte-stable above. Behind
`VIBECOMFY_AGENT_EDIT_V2=1`; the current path stays default until C6 is green, then
flip. `_stage_convert/_stage_load_python/_stage_lower/_stage_emit` are bypassed on
the v2 edit path (kept for authoring). **Concurrency (review-corrected):** the
backend stale-state gate (`submit_graph_hash`, under `SessionStateLock`) still
guards, but `EditorAheadError` only fires inside `emit_ui_json` — which v2 bypasses —
so its protection does NOT carry over and must be re-provided: re-validate the live
canvas snapshot immediately before `graph.clear(); graph.configure(candidate)` (an
optimistic-lock token captured at submit, checked atomically at apply), to close the
snapshot-check→apply window. The B4 dual-hash accept (match against *either* the
canonical or the browser hash) widens the window and should be tightened on this path.

## Build order within Phase 1
1. **C0** ledger (scope-aware uids + allocator) + **C2** op schema/validation.
2. **C3** resolve→mutate for `set_node_field`/`remove_node`/`upsert_link` (incl.
   link-driven rule + cascade cleanup) + **C5** assert (mutation-only; no creation) →
   **C6** items (i)–(iv). *Prove byte-preservation on the LTX set before any creation.*
3. **C1** projection + `build_messages` delta prompt → first real agent delta turn.
4. **C3** `add_node` + **C4** `place` + type-checked links → **C6** add/insert items.
5. Multi-turn re-edit stability → **C6** re-edit item.
6. Flip the flag; retire the IR round-trip from the edit path (its code stays for
   authoring).

## Risks / watch-items
- Projection legibility vs the agent's edit quality, and its token budget on large
  graphs — both measured/gated on C6 (the budget gate is a hard requirement of C1,
  not a nice-to-have).
- Scope/namespace correctness for subgraph-internal targets and reroute/virtual-wire
  links — the reviewers' #1 understatement; owned by C0 (traversal) + C3 (resolve),
  gated by the subgraph corpus item.
- Atomicity: the resolve pass must be total before any byte changes — gated by the
  partial-delta corpus case.
- Placement quality is cosmetic, never a correctness gate.

## Sizing
Self-contained but real new code (C0/C1/C3/C5/C6 are the bulk). Roughly a focused
multi-day effort; a good candidate for a single `megaplan` (sprint-sized), with C6
as the gate. Authoring path and all kept infrastructure are out of scope.
