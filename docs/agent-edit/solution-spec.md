# VibeComfy Agent-Edit — Deep Solution Spec

The proper, root-level design for editing a user's live ComfyUI graph with an LLM
agent, faithfully. Companion to `concrete-tree.md` (rationale) and
`../local_agent_text_to_graph_blockers.md` (evidence). This doc is the *spec to
implement*; the overall strategy is fixed — this is its tightest form.

> **v2 — jury verdict incorporated (2026-06-01).** Codex (GPT-5.5) and Claude Opus
> reviewed v1 independently and *converged*: heart **yes**, elegant **not yet —
> "one inversion short."** Both said: the read view must be a uid-annotated
> projection of the *original*, not a re-canonicalized Python rewrite; the resolver
> and the scratchpad emitter then leave the edit path entirely. Both flagged the
> same two understatements (scoped identity; edges-as-first-class). v2 below is the
> elegant form they pointed at.

## 0. The one invariant (everything below is a consequence of it)

> **Identity spine.** Every node has a stable, **scope-qualified** identity
> (`(scope_path, uid)` — `scope_path` handles subgraph-internal nodes), assigned
> once at first contact and preserved verbatim through the view the agent reads, the
> delta it emits, and the candidate that is applied. An edit names targets only by
> `(scope_path, uid, field_path)` for fields and by link identity for wires.

If this holds, faithful editing is no longer a round-trip problem at all. The
existing scoped-uid machinery (`vibecomfy/porting/uid.py`, subgraph stamping in
`ui_emitter.py`) supplies the scope.

## 1. Core model

Editing is a **pure function over the original UI JSON**:

```
apply(original_ui, delta) -> candidate_ui
```

- `original_ui` is the user's verbatim ComfyUI graph (the **substrate**). We never
  reconstruct it; we never leave it.
- `delta` is an ordered list of **typed ops**, each addressing the substrate by
  `uid` (+ a `field-path` for set-ops). The delta is **declared by the agent**, not
  inferred by diffing.
- `apply` mutates only the nodes/edges named in `delta`; every other node is the
  original object, untouched.

Three things that were separate mechanisms collapse into consequences:

| Old mechanism | Becomes |
|---|---|
| "preserve unchanged nodes" | copy every node whose `uid` is not named in `delta` (trivial) |
| `guard_emit` (delta-scope guard) | assert `candidate[uid] == original[uid]` for every `uid` not in `delta` — **true by construction**, so the guard is an *assertion*, not an oracle |
| convert-parity gate | deleted from the edit path entirely (kept for *authoring* only) |

There is no IR round-trip on the apply path, no canonicalization, no parity
equivalence check, no inference of "what changed."

## 2. The four pieces to build

### 2.1 Identity spine (stamp once, before anything reads the graph)
On first contact, assign each node a `uid` and write it into the substrate
(`properties.vibecomfy_uid`). `uid` is stable and 1:1 with a substrate node.
Re-edits reuse the existing uid. (Today: stamped late, on a copy, *after* the view
is rendered — wrong; must move to first-contact, on the substrate.)

### 2.2 The read view = an address-preserving projection of the original (NO resolver)
**The jury's central correction.** The agent reads a **compact, uid-annotated
projection of the original UI itself** — not a re-canonicalized Python scratchpad.
The projection is the original graph rendered for legibility: per node, its
`(scope_path, uid)`, `class_type`, fields with their **substrate** names (dotted
names kept verbatim, no `widget_N` aliasing, no helper lowering, no flattening),
edge summaries, and schema hints (defaults/choices). Pretty labels are allowed only
as a *reversible alias table carried with the projection*.

Because the view's addresses **are** the substrate's addresses, there is **no
resolver** — an op target is a dictionary lookup that either hits exactly one
substrate field or is rejected. The lossy canonical Python view and the scratchpad
emitter **leave the edit path entirely** (kept for authoring). This is what makes
"no unresolvable target" true *by construction* instead of by a fail-loud check.

### 2.3 The edit contract (typed delta)
The agent returns a `delta`, not a file. Op set (edges are first-class — links, not
endpoints):

```
set_node_field { target:[scope_path,uid,field_path], value }   # field_path keeps dotted names
add_node       { scope_path, class_type, fields, position?, uid<-minted }  # minted uid: collision-free, idempotent across retries
remove_node    { target:[scope_path,uid] }
upsert_link    { id?, from:[scope_path,uid,out_slot], to:[scope_path,uid,in_field] }
remove_link    { id | to:[scope_path,uid,in_field] }
reorder        { target:[scope_path,uid], axis: widgets|slots, order:[...] }  # widget/slot order is a real fidelity axis
set_mode       { target:[scope_path,uid], mode: 0|2|4 }   # enable/mute/bypass — `mode` is a node field, not a widget
```

`field_path` addresses nested/dotted inputs+widgets verbatim (e.g.
`["model","prompt"]`). Links are addressed as substrate facts (link id / endpoints
through reroutes & virtual wires), not by a bare `(node,slot)` pair, because
reroutes, virtual wires and multi-output named slots are real LiteGraph constructs.
`add_node` **mints** a fresh scope-unique uid (idempotent across the B13 retries).

### 2.4 Apply + assert
`apply(original_ui, delta)` deep-copies the original, mutates only the targeted
nodes/edges, and returns the candidate. Then a cheap assertion: for every `uid` not
named in `delta`, `candidate[uid]` is byte-identical to `original[uid]` (full UI
JSON — positions, widget order, annotations included, **not** an API projection).
This replaces `guard_emit`'s API-space comparison. *(Refinement — verified live:
`serialize→configure→serialize` is byte-stable on a real 81-node graph, so byte
identity is a real target; normalize both sides through one such pass before
comparing to absorb any non-idempotent node types without false refusals. See the
Phase-1 plan C5.)*

## 3. The agent loop, end to end

```
first edit:  stamp uids on substrate
each turn:   render uid-faithful view  ->  agent returns delta (ops)
             resolve every op target on the substrate (fail loud)
             candidate = apply(original_ui, delta)
             assert untouched-outside-delta (full UI)
             show candidate; on accept -> graph.clear(); graph.configure(candidate)
                              (NOT loadGraphData — it forks a new tab)
re-edit:     the accepted candidate IS the new substrate (uids already present)
```

Authoring (template creation from a graph) keeps the existing canonicalizing
round-trip untouched. **One substrate, two policies.**

## 4. Code touchpoints

- `agent_edit.py::_stage_ingest` — stamp uids on `state.graph` (substrate) before
  anything renders; carry it as the apply base.
- `vibecomfy/comfy_nodes/agent/provider.py::build_messages` — stop demanding "complete replacement file";
  request a `delta` of ops; render the uid-faithful view.
- new `apply_delta(original_ui, delta)` + `resolve_target(original_ui, op)` — the
  pure apply + resolver (replaces `_stage_load_python`/`_stage_lower`/`_stage_emit`
  on the edit path).
- `refuse.py::guard_emit` — replace API-space compare with full-UI untouched-
  outside-delta assertion.
- convert-parity (`convert.py`) — removed from the edit path; retained for authoring.

## 5. What this dissolves (map to blockers.md)
A (path norm), B/C (helper lowering), B7/E (PreviewAny/MarkdownNote), B8 (dotted
inputs), B12 (guard no-op), B13 (full-file flakiness), and the convert-parity hard-
fail — all gone, because untouched nodes are never re-serialized and edits are
declared in resolvable coordinates. **Node-pack-agnostic by construction.**

## 6. Phases
1. **Identity spine + edit contract + uid-faithful view + apply/resolver + full-UI
   assertion + editing corpus.** (Keystone; everything above.)
2. Migrate the agent prompt + UI panel to the delta contract; retire the IR
   round-trip from the edit path.
3. Retire convert-parity from the edit path (keep for authoring).

## 7. Test corpus (the only correctness bar editing needs)
For N real workflows (LTX set, Gemini/ByteDance, standard): scripted edit (e.g.
"set the positive prompt"), assert (a) the targeted field changed, (b) **every other
node is byte-identical to the original UI**, (c) no unresolvable-target escapes.

## 8. Open questions — RESOLVED by the v2 jury (both reviewers converged)
- *Python read view needed?* **No.** Edit against the uid-keyed projection of the
  original; drop the scratchpad emitter from the edit path. (Both, decisive.)
- *Collapse view+resolver?* **Yes.** The view's addresses are the substrate's, so
  the resolver vanishes. Keeping lossy Python "reintroduces exactly the accidental
  complexity the spec is trying to kill." (Both.)
- *Is `(uid, field_path)` enough?* **No** — needs scope (`scope_path`) for
  subgraph-internal nodes, and edges must be first-class link ops, not endpoint
  pairs. (Both.) Folded into §0/§2.3.

## 8b. Node creation, positioning, and data (the additions policy)

Existing nodes are byte-preserved; **new nodes are the only thing constructed.**
Additions are the *authoring* node-builder applied to one node and inserted into the
preserved original — so "one substrate, two policies" composes at node granularity
(preserve each existing, author each new). The schema is touched **only** for the
new node, so creation cannot reintroduce the lossy-regeneration blockers (those need
re-serializing an *existing* node, which the edit path never does).

**Agent works in semantics; system does the litegraph mechanics.** The agent never
emits a raw node object or pixel coordinates. `add_node` carries `class_type`, named
`fields`, wired `inputs` (by identity), and a *semantic* `anchor`:

```
add_node { class_type, fields:{by-name}, inputs:{in_field: (scope,uid,out_slot)},
           anchor:{ near:(scope,uid) | between:[(..),(..)], relation: right_of|below|between } }
```

The system materializes the full UI node from `object_info`: input/output sockets in
schema order, `widgets_values` built from named `fields` (defaults for the rest),
fresh scope-unique minted `uid` + litegraph id.

**Positioning = a pure function over the original geometry.** The substrate carries
every existing node's `pos`/`size` (byte-preserved). `place(original_geometry,
anchor, relation) -> pos` puts the node near its anchor (default: downstream/right of
the node feeding its main input), avoids overlapping existing boxes, falls back to a
free region. It is the *only* new geometry introduced; existing positions are never
moved. Poor placement is cosmetic (draggable), never a correctness gate. Reuses the
existing layout engine (`layout_store` / `ui_emitter` layout).

**Data + types.** Fields are set by schema name (the projection supplied names,
types, choices, defaults), mapped to the positional `widgets_values` once, for the
new node only. Links are typed: the system checks source-output vs target-input type
from the schema and **rejects mismatched wiring loudly**. Required-input completeness
is a queue-validate *warning*, not a fidelity failure.

## 9. Honest build framing (jury correction)
"Mostly reorienting existing machinery" was too generous. Genuine reorientation:
the identity stamp (move to first-contact, on the substrate) and the existing
scoped-uid machinery. **New build:** the address-preserving projection, the typed
`apply(original_ui, delta)`, and the full-UI untouched-outside-delta assertion
(`guard_emit` today is an *API-space* compare — this is a rewrite, not a tweak).
**Cut out of the edit path entirely:** `port convert`, replacement-file prompting,
`load_agent_generated_scratchpad`, lowering, `emit_ui_json`, API-space `guard_emit`.
The edit path is **cut over**, not gently rearranged. Authoring keeps all of the
above unchanged.
