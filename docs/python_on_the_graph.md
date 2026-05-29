# Representing VibeComfy Python on the ComfyUI Graph ("Nodes 2.0")

**Status:** design proposal / RFC. Not yet implemented.
**Audience:** VibeComfy maintainers, the scratchpad-emitter epic, anyone building the
in-editor surface.
**Relationship to existing work:** this is the design behind emitter-epic **M7
(in-editor-surface)** — the ComfyUI custom-node + JS preview/diff surface. It depends
on the IR↔UI-JSON round-trip that the scratchpad-emitter epic is building (M2–M5) and
on the IR contract hardened by the excellence epic (M3 seams + IR purity).
**Validation provenance:** this doc was pressure-tested by a 10-agent technical
sense-check (identity, emitter determinism, diff/patch, state-sync, sandboxing,
metadata-carriage, transactionality, schema-drift, perf, parity-gate) plus two empirical
gates run against the live ComfyUI + the vendored ComfyUI oracle. Findings are woven in
below and tagged **[verified]** (checked in code or a live run) vs **[claimed]** (asserted
by an agent, not yet independently confirmed). The two load-bearing surprises — the parity
gate is self-referential, and build-time `exec` is an RCE channel — are both **[verified]**
and reorder the build (see §8).

---

## 1. The problem

VibeComfy's premise is that a workflow is *real Python*, not static JSON: users grab a
template, then "write code on top, combine it with other templates / patches / custom
Python, then execute" (`CLAUDE.md`). That Python can contain things a single ComfyUI
graph fundamentally cannot hold:

- **arbitrary code** that computes widget values or post-processes results,
- **`for` loops** (seed sweeps, N variations, batch-of-prompts),
- **conditionals** that branch on a result,
- **multi-workflow composition** (e.g. `image.t2i(...)` → feed the image into
  `video.i2v(...)`) — two independent graph executions with data passed between them.

The "Nodes 2.0" plugin grabs the current ComfyUI workflow, lets the user edit it, and
writes it back (`ComfyUI/custom_nodes/nodes2_poc/`). For it to be a real front-end for
VibeComfy, we need a **generic way to represent these richer constructs on the graph**
and **round-trip them with VibeComfy's Python IR**. This doc proposes how.

---

## 2. What VibeComfy gives us to build on

Three properties of the existing system make this tractable. We exploit all three
rather than inventing new machinery.

### 2.1 One IR, one execution path
Everything funnels through `VibeWorkflow` → `compile("api")` → the ComfyUI API dict
(`vibecomfy/workflow.py`). A `VibeNode` is `class_type + inputs + widgets + metadata`.
The reverse direction (UI/JSON → IR → Python and back) is exactly what the
scratchpad-emitter epic is completing (`.megaplan/chains/scratchpad-emitter.yaml`,
`vibecomfy/porting/{convert,emitter,parity}.py`).

### 2.2 `metadata` is a free-form, round-trippable channel
`VibeNode.metadata` already carries non-runtime information — `subgraph_class_type`,
`block_id`, provenance, `output_names`, source lines (`vibecomfy/workflow.py`). It is
dropped by `compile("api")` (the backend never sees it) but it is the natural place to
store *intent*. On the editor side, litegraph node `properties` and the workflow `extra`
bag survive a `serialize()`/`configure()` round-trip untouched even though ComfyUI's
backend ignores them. **Metadata is the lossless carrier for everything the static graph
can't natively express.**

**[verified]** A live test against the running ComfyUI confirmed the load-bearing case:
a node of an *unregistered* type (`vibecomfy.code`, absent from all 742 registered
classes) both **survived** in the live graph and **retained its full `properties`** — a
`vibecomfy_uid` and a nested intent blob (a multi-line `for`-loop string) — across two
`configure → serialize` cycles. So the carrier holds even before the node pack is
installed. On the IR side the carrier is concretely `VibeNode.metadata["_ui"]["properties"]`
(`vibecomfy/ingest/normalize.py`), preserved through ingest and `finalize_metadata`, and
correctly dropped at `compile("api")` so the backend never sees intent. Residual gap: the
full ComfyUI *Open→Save-to-disk* path (menu/userdata), not just the litegraph
serialize/configure round-trip, is not yet auto-tested — but `serialize()` is what
ComfyUI saves, so this is strong.

### 2.3 There is already an escape hatch for "not a real Comfy node"
`vibecomfy.blocks.subgraph.opaque()` inserts a node whose `class_type` is an *arbitrary*
string — a subgraph UUID, or a synthetic name like `vibecomfy.placeholder.upscale`
(`recipes/dual_pass_t2i.py`) — with declared input/output slots and `metadata`
(`vibecomfy/blocks/subgraph.py`, `blocks/_utils.py`). Validation tolerates these as a
**warning, not an error** (`vibecomfy/contracts/validation.py`,
`OPAQUE_COMPONENT_CLASS_RE`), and they survive `compile("api")` as a literal
`{"class_type": "...", "inputs": {...}}`. This is the precedent: **any node can be a
typed black box that carries opaque intent and round-trips.** Our entire scheme is a
generalization of this.

---

## 3. The expressiveness boundary

The single most important fact (from auditing `blocks/`, `patches/`, `ops/`, `recipes/`):

| Construct | Lives where today | One ComfyUI graph? |
|---|---|---|
| Direct IR setters, patches (decorate), blocks (extend, incl. opaque splices) | `VibeWorkflow` mutation | ✅ yes |
| Static fan-out (`batch_size` / `EmptyLatentImage` → N images) | one graph | ✅ yes |
| `for` loops over `.run()` (seed/param sweeps, N variations) | hand-written Python in a recipe/script | ❌ separate executions |
| Multi-workflow chains (image→video) | `Artifact.run()` + passing file paths (`vibecomfy/ops/*`, `artifacts.py`) | ❌ two graphs, no shared graph |
| Result-conditional branching | hand-written Python | ❌ decided between runs |

Two consequences:

1. **Loops / branches / cross-workflow data flow have no representation in the IR today.**
   They are pure build-time / run-time Python. The `build()` function the emitter produces
   is strictly straight-line node construction; parity only covers the static DAG
   (`vibecomfy/porting/parity.py`).
2. **The orchestration layer that *would* serialize this — `VibeFlow` — was specced but
   never built** (`docs/python_composition_dsl_plan.md`, SD-004; no `VibeFlow` in code).
   This doc effectively proposes its on-graph representation.

So our design must do two different jobs: (a) represent in-graph richness that *can*
execute as one prompt, and (b) represent orchestration that *cannot*.

---

## 4. Design principles

1. **Metadata is the source of truth.** Special nodes are opaque to ComfyUI's backend;
   their meaning lives in `metadata`/`properties`, and the round-trip rule is "read the
   metadata back into the matching Python construct."
2. **Degrade to native wherever possible.** If a construct can be expressed as plain
   ComfyUI nodes (static unroll, compile-time conditional, native subgraph), do that —
   it executes today, renders natively, and needs no custom node installed.
3. **Always keep I/O typed.** Even a black-box node exposes typed input/output sockets so
   upstream/downstream wiring stays sound and *could* be validated against `object_info`.
   (Note **[verified]**: `compile("api")` does **not** consult `object_info` today and
   emits an unregistered `vibecomfy.*` class with zero error — the graph only fails when
   actually queued. Schema validation is a target to add, not a property we have.)
4. **Build on the round-trip engine, don't fork it.** The plugin exports the edited graph
   as API/UI JSON; the existing emitter/`port export --to ui` (emitter epic) turns it into
   editable Python and back. We add IR + emitter support for the new node kinds; we do not
   build a second serializer.
5. **One extension point.** A single reserved `vibecomfy.*` `class_type` namespace, not a
   sprawl of bespoke mechanisms.
6. **Parse, don't exec — the agent's Python is data, never code we run.** **[verified]**
   Every VibeComfy loader (`scratchpad_loader.py:24`, `registry/ready.py`, `porting/loader.py`,
   and `convert.py` twice) does `spec.loader.exec_module()` then `build()` with **no sandbox,
   timeout, or resource limit** — and `validate`/`doctor`/`inspect`/`run` all hit that path,
   so "run validate first" *is* code execution. Fine for a human running their own templates
   (the documented "trusted local Python" posture, `m7-plugin-verbs-release.md`); an RCE /
   exfil / DoS channel the moment the *agent* writes the Python. The emitter's `build()` is
   straight-line, closed-vocabulary node construction — an ideal target to reconstruct the IR
   from the **AST without executing it**. The agent loop must parse, not exec; `exec` stays
   behind an explicit trusted-author boundary. (This also resolves "is Python the right edit
   medium?": Python-as-*data* is safe; Python-as-*code-we-run* is not.)
7. **Verify against an independent oracle, not against ourselves.** **[verified]** The
   current parity gate compares VibeComfy's `compile("api")` to VibeComfy's `compile("api")`
   (§6) — it cannot catch a systematic ingest/compile error because both sides inherit it.
   Any "this round-trips" claim must be gated by ComfyUI's *own* `convert_ui_to_api`
   (`vibecomfy/comfy_backend.py`), not by VibeComfy agreeing with itself.

---

## 5. The proposal: a `vibecomfy.*` node namespace + a 3-tier scheme

### 5.1 The unifying primitive
Reserve a `class_type` namespace for **VibeComfy nodes** — opaque to the ComfyUI backend,
rendered specially by the Nodes 2.0 frontend, round-tripped via metadata:

| `class_type` | Represents | Renders as |
|---|---|---|
| `vibecomfy.code` | arbitrary Python with typed I/O | a code-editor node |
| `vibecomfy.loop` (paired start/end) | iteration | expandable loop band |
| `vibecomfy.branch` | conditional | a lazy switch |
| `vibecomfy.workflowref` | a whole sub-workflow stage | a stage card |

Each is a V3-schema node (`define_schema() -> io.Schema`, ComfyUI's "Nodes 2.0" node
model) with **typed sockets** plus a `metadata`/`properties` blob:

```jsonc
// node.properties (verified to survive the editor serialize/configure round-trip)
{
  "vibecomfy_uid": "stable-id-for-roundtrip",   // NOTE the underscore — see below
  "vibecomfy": {
    "kind": "code" | "loop" | "branch" | "workflowref",
    "intent": { /* kind-specific: source / loop spec / predicate / ready_id */ },
    "io": { "inputs": [["name","TYPE"]...], "outputs": [["name","TYPE"]...] }
  }
}
```

This is the `opaque()` mechanism (§2.3) with a reserved namespace and a documented
metadata contract — nothing structurally new in the IR. Two **[verified]** corrections to
an earlier draft of this contract:

- **uid key spelling.** Ingest reads identity from `properties["vibecomfy_uid"]`
  (underscore — `vibecomfy/porting/uid.py:mint_local_uid`). A dotted `vibecomfy.uid` would
  silently *not* match and fall back to minting from the litegraph int id, breaking
  round-trip identity. Use the underscore key; keep the rest of the intent under a single
  `vibecomfy` sub-object.
- **validation rule needed.** `OPAQUE_COMPONENT_CLASS_RE` (`vibecomfy/contracts/validation.py`)
  only matches subgraph UUIDs, so dotted `vibecomfy.*` nodes currently pass validation
  **unflagged** (more tolerant than this doc implied). The reserved namespace needs its own
  rule: warn "inline/lower before runtime" and assert the typed-socket + `vibecomfy.kind`
  contract is present.

### 5.2 Tier A — static → plain nodes / native subgraphs (no custom node needed)
When a count or condition is known at build time, **lower it to ordinary nodes**:

- a loop with a literal count **unrolls** to N node copies (the "display multiple times"
  intuition), optionally wrapped in a **ComfyUI native subgraph** (organizational
  container, released Aug 2025) for tidy rendering;
- a compile-time conditional simply **doesn't emit the dead branch**.

These execute today, render natively, and round-trip back to a `loop(...)`/`branch(...)`
call by reading `vibecomfy.intent` off the wrapper. **Tier A is where we start** — it
needs no runtime support and rides the existing emitter almost immediately.

### 5.3 Tier B — dynamic in-graph → custom VibeComfy nodes (one execution)
When the loop count / branch is only known at runtime but the work *can* still run inside
a single prompt, lean on ComfyUI's **execution-model inversion** (PR #2666 / #931): nodes
may expand into a subgraph at runtime and edit the graph mid-execution. This is the
substrate behind ComfyUI-Easy-Use's `forLoopStart/forLoopEnd` and lazy conditionals, and
**HiddenSwitch — VibeComfy's embedded runtime — shares this execution model.** Represent:

- **`vibecomfy.loop`** as paired start/end anchor nodes; body nodes sit between them;
  `metadata.intent = {over, var}`.
- **`vibecomfy.branch`** as a lazy switch (unevaluated branch never runs).
- **`vibecomfy.code`** as a multiline-`code` widget + typed sockets (exactly how every
  Python-eval node in the ecosystem is shaped).

### 5.4 Tier C — cross-workflow orchestration → a meta-graph (NOT one execution)
image→video and `.run()` loops cannot be one Comfy prompt. Represent them on an **outer
orchestration canvas** of `vibecomfy.workflowref` nodes — each = a template id + patches +
inputs — with edges carrying **artifacts** (an image path flowing into an `i2v` input).
This outer graph is the on-graph serialization of the (unbuilt) `VibeFlow`: VibeComfy
executes it **stage by stage**, never as a single prompt. Round-trips to the obvious
recipe Python:

```python
img  = image.t2i(prompt).run(runtime="embedded")
clip = video.i2v(img.outputs[0], "the subject turns").run(runtime="embedded")
```

---

## 6. The round-trip contract

```
ComfyUI editor (UI JSON, incl. vibecomfy.* nodes + properties)
   ⇅  (Nodes 2.0 plugin: serialize / configure — verified lossless for registered nodes)
VibeWorkflow IR  (vibecomfy.* nodes as opaque VibeNodes; intent in metadata)
   ⇅  (emitter / port export --to ui — emitter epic M2–M5)
VibeComfy Python (build(): straight-line nodes + loop()/branch()/recipe calls)
   →  compile("api")  →  API JSON  →  runtime
```

- **Lossless carriers:** node identity via a durable `vibecomfy.uid` (added by the emitter
  epic); intent via `metadata`/`properties`; UI layout via the existing `.layout.json`
  sidecar + `metadata.virtual_wires`.
- **What the emitter must learn:** today `build()` is straight-line and parity covers only
  the static DAG. Tiers B/C require the emitter to map a `vibecomfy.loop`/`branch`/
  `workflowref` node ⇄ a `loop(...)`/`branch(...)`/recipe-call. Tier A needs only an
  unroll/subgraph-wrap pass, which the emitter can already approximate.
- **Validation:** every `vibecomfy.*` node keeps typed sockets, so the graph stays
  checkable against `/api/object_info` (the independent oracle the emitter epic already
  uses via the vendored ComfyUI `convert_ui_to_api`).

---

## 7. Editor-side robustness (the plugin half)

Because the plugin writes the graph back, the swap itself must be bulletproof. From live
testing against ComfyUI (see `ComfyUI/custom_nodes/nodes2_poc/README.md`):

- **Replace in place via `graph.clear()` + `graph.configure()`**, never `loadGraphData()`
  (it forks a workflow tab and resets undo history).
- **Undo:** ComfyUI's `ChangeTracker` only auto-snapshots on real user input. Wrap each
  programmatic edit in `ct.beforeChange()` … mutate … `ct.afterChange()` (or the
  deprecated `checkState()`) to record exactly one undo step. Verified: multi-level
  undo/redo round-trips, lossless for registered-node graphs.
- **Scope:** operate on `app.rootGraph` and detect subgraph context — `app.graph` is the
  *active* graph and may be a subgraph.
- **Atomicity:** snapshot → validate the candidate → `try { clear; configure; verify }
  catch { configure(snapshot) }`; re-entrancy lock; refuse while a prompt is executing.
- **Unregistered nodes** (incl. our `vibecomfy.*` types before the pack is installed):
  detect against `LiteGraph.registered_node_types`; the frontend renders them from
  metadata regardless, so they survive editing even on a vanilla ComfyUI.

---

## 8. Phased approach

1. **Spec the contract.** Write the `vibecomfy.*` node schema (V3) + the `metadata` keys
   that round-trip. This is the missing IR piece both the emitter and a future `VibeFlow`
   need. (Doc + small IR additions; no runtime risk.)
2. **Tier A + `vibecomfy.code`.** Static unroll / native-subgraph wrapping, and a code
   node. Both round-trip through the existing emitter with minimal change and need no
   execution-inversion. Ship the Nodes 2.0 special rendering for these.
3. **Tier B.** Loop anchors + lazy branch on execution-inversion; emitter mapping to
   `loop()`/`branch()`. Requires a small installed node pack.
4. **Tier C / `VibeFlow`.** The orchestration meta-graph + `workflowref`; this is also the
   moment to actually build the `VibeFlow` container the DSL plan specced.

Sequencing tracks the emitter epic: Tier A/`code` align with M3–M5 (round-trip), the
in-editor rendering is M7, and Tier C is the natural home for the long-deferred `VibeFlow`.

---

## 9. Open questions / risks

- **Emitter ⇄ control-flow mapping fidelity.** Reconstructing a `for`/`if` from anchor
  nodes is harder than straight-line emission; needs its own parity gate (extend
  `vibecomfy/porting/parity.py` beyond the static DAG).
- **How much code is "arbitrary"?** A `vibecomfy.code` node that can run any Python is
  powerful but unverifiable and a trust/security surface — decide whether code runs in the
  build step, in-graph (execution-inversion), or only in the orchestration layer
  (`docs/python_composition_dsl_plan.md` keeps arbitrary Python *out* of an active graph;
  the only sanctioned in-graph path is the unbuilt `ExternalPythonNode`).
- **Native-subgraph stability.** Subgraphs are recent; serialization shape may drift —
  pin a tested frontend range and validate via the vendored ComfyUI oracle.
- **Two source-of-truth risk.** If both the graph and the Python are editable, define which
  wins on conflict. Proposal: the IR is canonical; the graph is a projection; edits flow
  graph → IR → Python via the emitter, never Python text-patched directly.

---

## 10. Appendix — worked example

A seed sweep, three ways, all the same VibeComfy intent:

```python
# VibeComfy Python (authoring)
for seed in [1, 2, 3]:
    image.t2i(prompt, seed=seed).run()
```

- **Tier A (static):** unrolls to 3 copies of the t2i graph, wrapped in a native subgraph
  titled "seed sweep [1,2,3]"; `properties.vibecomfy.intent = {over: [1,2,3], var: "seed"}`.
- **Tier B (dynamic count):** a `vibecomfy.loop` start/end pair around one t2i body, the
  count wired from an upstream node.
- **Tier C (if it fed a later stage):** a `vibecomfy.workflowref("image/...")` stage on the
  orchestration canvas with an edge carrying the produced images onward.

In every case the round-trip rule is identical: the node's `vibecomfy.intent` metadata is
read back into the `for`/`loop(...)`/recipe call that produced it.
