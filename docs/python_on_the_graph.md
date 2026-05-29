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
6. **The agent edits the IR through structured tools — Python is for control-flow, not
   surgery.** Two **[verified]** findings combine into the single most important interaction
   decision:
   - *Security:* every VibeComfy loader (`scratchpad_loader.py:24`, `registry/ready.py`,
     `porting/loader.py`, `convert.py` twice) does `spec.loader.exec_module()` then `build()`
     with **no sandbox, timeout, or resource limit** — and `validate`/`doctor`/`inspect`/`run`
     all hit that path, so "run validate first" *is* code execution. Fine for a human running
     their own templates; an RCE/exfil/DoS channel the moment the *agent* writes the Python.
   - *Editability:* a capability probe (an agent editing real generated templates) found that
     generated VibeComfy Python optimizes for round-trip fidelity, **not** editability —
     non-local hoisted constants (a one-line change has graph-wide effect), literals with no
     exposed param (a buried `seed`), invisible kwarg-as-edge wiring, manual `_id=` that
     collide on duplication, and subgraph functions that hide the editable surface from
     `build()`. Param tweaks on an obvious literal are safe; **add-node / duplicate-chain /
     rewire are high-risk of "compiles but means the wrong thing."**
   → **Rule:** the agent performs graph *structure* edits via the structured IR API
   (`add_node`/`node()`/`connect`/`replace_edge`/`set_seed`/`finalize_metadata`) which owns id
   allocation, edge integrity, and metadata rebuild — **not** by emitting Python text we parse
   or (worse) exec. Python is reserved for **control-flow and composition** (loops, recipes,
   the `vibecomfy.*` constructs); even there it is treated as **data — reconstructed from the
   AST, never executed** — and `exec` stays behind an explicit trusted-author boundary. This
   simultaneously closes the RCE surface and sidesteps most of the round-trip-fidelity risk
   for the common (structural) edit, since the agent never round-trips edited text at all.
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

- **Lossless carriers:** node identity via a durable `vibecomfy_uid` (added by the emitter
  epic, M2); intent via `metadata["_ui"]["properties"]`; UI layout via the existing
  `.layout.json` sidecar + `metadata.virtual_wires`.
- **What the emitter must learn:** today `build()` is straight-line and parity covers only
  the static DAG. Tiers B/C require the emitter to map a `vibecomfy.loop`/`branch`/
  `workflowref` node ⇄ a `loop(...)`/`branch(...)`/recipe-call. Tier A needs only an
  unroll/subgraph-wrap pass, which the emitter can already approximate.

### 6.1 Reality check — what the round-trip actually does today (measured)

A harness was built that round-trips the corpus through VibeComfy and compares against
ComfyUI's *own* `convert_ui_to_api` oracle (`vibecomfy/comfy_backend.py`) — the comparison
the parity gate never makes. **[verified] findings, in priority order:**

- **The parity gate is self-referential.** Both operands are VibeComfy's `compile("api")`
  (`convert.py:333` source vs `:400-402` emitted), diffed by `compile_equivalent`
  (`parity.py`). The ComfyUI oracle runs *only at ingest* (`normalize.py:44`), upstream of
  both sides, so it cancels out. The gate proves **emit→reimport stability** (the Python
  emitter is faithful to the IR), **not correctness vs ComfyUI**. It is blind to any
  systematic ingest/IR/compile error, because both sides inherit it. → **Fix: feed
  `convert_ui_to_api(original_ui)` as side A** so "parity passes" means "ComfyUI would
  accept this." This is prerequisite #1 for trusting the loop.
- **Fidelity against the real oracle is low on the curated corpus: ~29% exact** (7/48 exact
  + 7 a *benign* convention diff where VibeComfy inlines a `PrimitiveInt` literal the oracle
  keeps as a live node — semantically identical). The honest headline is **not** "corrupts
  most workflows" — **no silent value corruption was observed**. Rather, **~35% (17/48) are
  hard Get/Set-broadcast resolver failures** where VibeComfy raises `ConversionParityError`
  and produces *no graph at all*; the rest are extra/missing-node diffs concentrated in
  community Kijai/LTX graphs. Official image/video/edit families round-trip cleanly. Caveat:
  this is the *curated* corpus, not the messy community long tail (which is likely worse).
  → The agent must be fenced to the families that round-trip, and the Get/Set resolver is a
  concrete, prioritized gap to close.
- **Coverage holes the emitter drops:** bypassed/muted nodes lose `mode` (hardcoded `0` →
  round-trip back *active*); node `groups` are dropped (`ui_emitter.py`); reroutes and
  subgraph internals are resolved/stripped before parity so corruption inside them is
  invisible. These are real fidelity bugs for an editor-facing tool.
- **Identity: the diff keys on `vibecomfy_uid`, never the litegraph int id** (the ints are
  unstable/renumbered). The uid scheme was tested against the *installed* code, not just
  reasoned about — **[verified]** results:
  - A *stamped* `vibecomfy_uid` is **deterministic** (same source → same uid),
    **collision-immune** (distinct stamps stay distinct even at the same int id), and
    **survives the editor `serialize/configure` round-trip** (even on unregistered nodes).
    For stamped nodes, identity is solid.
  - **Fresh editor- and agent-created nodes carry NO `vibecomfy_uid`** — `createNode` doesn't
    stamp; only VibeComfy's emitter (`ui_emitter`) does, on the export hop. So a node has no
    durable identity until it has round-tripped through VibeComfy once.
  - Two *unstamped* nodes sharing an int id **collide** (both mint uid `"N"`). This does NOT
    happen from in-session editor delete+add (this litegraph's ids are monotonic — verified),
    but DOES happen across the round-trip/renumber boundary and across independent workflows —
    which is exactly the diff's domain.
  - `mint_local_uid` is **precedence-only** (properties → int id → fallback); it has **no
    collision-proof generator**, so a brand-new node can't get a safe uid from it.
  - **[verified — measured per channel]** the **editor channel (ingest → emit → re-ingest)
    is uid-stable end to end**: durable uids survive a full round *and* a second round
    (idempotent fixpoint), stamped at `ui_emitter.py:659-660`. The **API channel is uid-blind**:
    `compile("api")` keys on the int id and re-derives uid from it (0/N durable uids survived in
    test). → The editor channel must be IR ⇄ UI-JSON; an IR → API-JSON → editor path
    regenerates uid and must be forbidden.
  - **[verified — repro'd] subgraph rename breaks inner identity.** `sg_key` embeds the
    user-editable subgraph *name* (`scope.py:99`: `f"{name}:{digest}"`), and that name is a
    literal prefix of every contained node's `vibecomfy_uid`. Renaming a subgraph changes all
    inner uids → the diff sees the whole subgraph body as removed+re-added. The M2 idea file is
    self-contradictory here (specifies name-in-key, yet claims stability only vs UUID-regen).
  - **→ Concrete build items, all milestone-mappable (§11):**
    1. **Identity minting** *(mostly there).* `node()` already mints collision-proof,
       prefix-namespaced uids (`_mint_uid`, `workflow.py:368`; `n{counter}`/`id:{...}` can't
       collide with bare-integer ingested uids). Close the two gaps: hoist the mint into
       `add_node` (the raw path leaves `uid=""`), and add a **uniqueness assertion** in
       `finalize_metadata` — today *nothing* enforces uid uniqueness and explicit `uid=` is
       written verbatim.
    2. **Subgraph-scope fix:** make `sg_key` rename-stable — anchor it on a durable
       subgraph-instance id (or the digest alone), not the name (`scope.py:99`).
    3. **Patch re-stamp:** the diff/patch apply must write `vibecomfy_uid` into each newly
       `createNode`'d live node so the next cycle matches.
    4. **uid-bijection precondition:** if any node lacks a uid or a uid is duplicated, fall
       back to wholesale replace.
- **Schema-drift risk.** Ingest/emit hard-code the litegraph serialization shape (links as
  6-element arrays — ComfyUI is migrating to objects; positional `widgets_values`; node
  envelope fields). → Put one format-version-gated adapter in `vibecomfy/ingest/normalize.py`
  (the sole external-JSON entry point) so a ComfyUI format change is a one-file fix.
- **Perf.** `_topological_node_order` (`emitter.py`) is O(N²) (rebuilds `set(out)` per node
  per iteration) and runs 3+ times per convert; convert does 5–7 full-graph passes. Replace
  with Kahn's algorithm (O(N+E)) — ~50–80% emit speedup at 1k+ nodes; matters for live
  in-editor latency. The emitter *is* byte-deterministic across `PYTHONHASHSEED`
  **[verified]** but nothing gates it — add a cross-process determinism test.

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
- **Atomicity — specced but NOT yet implemented [verified].** The PoC `apply()` currently
  does `clear()` → `configure()` with *no* try/catch/snapshot, so a mid-apply throw leaves
  the editor **empty**. This recipe is the fix, not the current behavior: snapshot →
  validate the candidate → `try { clear; configure; verify } catch { configure(snapshot) }`;
  re-entrancy lock; operate on `app.rootGraph`; refuse while a prompt is executing. The
  Python side already has the right pattern (`convert.py` atomic temp-file replace + gate) —
  mirror it. Commit point = the browser apply+verify succeeds; the durable `.py` write goes
  *last*, so a failure never leaves a half-written file **and** a half-cleared editor.
- **Unregistered nodes** (incl. our `vibecomfy.*` types before the pack is installed):
  detect against `LiteGraph.registered_node_types`; **[verified]** the editor preserves
  their `properties` through serialize/configure, so they survive editing even on a vanilla
  ComfyUI (they only fail when actually *queued* to a backend lacking the node).
- **Write-back mechanism (forward-looking, viable).** Wholesale `clear()+configure()` is the
  verified default. A **uid-keyed diff/patch** (match by `vibecomfy_uid`, mutate only deltas
  via the live LiteGraph API, one undo bracket) is viable as a guarded optimization for large
  graphs — gated behind preconditions (uid bijection, registered types, no group/primitive
  constructs) and a live verification of `createNode/connect/disconnect`. Concurrency: the
  agent reasons over a snapshot, so apply needs **optimistic drift detection** (uid-set + a
  cheap content token) with a uid-keyed 3-way rebase and a hard tab-switch/execution guard.
  Both designs are sound on paper but need the live-API and `changeCount` probes in §9.

---

## 8. Phased approach

The sense-check **reordered this to foundation-first**: the round-trip and execution model
are weaker than the tier work assumes, so harden them before building the agent layer on
top. Phase 0 is new and gating.

0. **Foundation hardening (gating — do before any tier/agent work).**
   - **Oracle-back the parity gate:** make side A `convert_ui_to_api(original_ui)`, not a
     second VibeComfy compile, so "round-trips" means "ComfyUI agrees" (§6.1).
   - **Parse-don't-exec:** an AST→IR reconstruction path for agent-authored Python; demote
     `exec` to a trusted-author boundary (principle 6). Spike: measure what fraction of
     `ready_templates/**` the emitter grammar can be reconstructed from AST alone.
   - **Two repro'd bug-fixes (highest leverage, §12):** (i) the **Get/Set resolver key
     mismatch** — ~3 lines, unblocks 33% of the corpus (currently producing no graph); (ii) the
     **KSampler emit widget-shift** — `emit_ui_json` must keep the `control_after_generate` slot
     so emitted `widgets_values` are 7-long, not 6 (today silently shifts steps/cfg/sampler).
     Both have repros and verified-safe fixes.
   - **Close coverage holes:** `mode` (bypass/mute) + `groups` + color/title preservation on
     emit; the two divergent `UI_ONLY_CLASS_TYPES` sets; pin `WIDGET_SCHEMA` to the runtime
     (schema-skew guard).
   - **Agent-edit-loop integrity:** assert the mutable-IR invariants after each edit (§12);
     gate runnability on `doctor` + warm-cache `validate` (compile ≠ runs).
   - **Cheap fixes:** browser-side atomic rollback (§7); the `vibecomfy_uid` spelling + the
     `vibecomfy.*` validation rule (§5.1); Kahn's-algorithm topo sort + a determinism CI
     gate (§6.1); the bad `pyproject.toml` entry point that crashes the oracle catalog walk.
   - **Run the two empirical gates** (§9) and keep them as regression checks.
1. **Spec the contract.** Write the `vibecomfy.*` node schema (V3) + the `metadata` keys
   that round-trip (using the corrected `vibecomfy_uid` / `vibecomfy` blob, §5.1). The
   missing IR piece both the emitter and a future `VibeFlow` need.
2. **Tier A + `vibecomfy.code`.** Static unroll / native-subgraph wrapping, and a code
   node. Both round-trip through the existing emitter with minimal change and need no
   execution-inversion. Ship the Nodes 2.0 special rendering for these.
3. **Tier B.** Loop anchors + lazy branch on execution-inversion; emitter mapping to
   `loop()`/`branch()`. Requires a small installed node pack.
4. **Tier C / `VibeFlow`.** The orchestration meta-graph + `workflowref`; this is also the
   moment to actually build the `VibeFlow` container the DSL plan specced.

Sequencing tracks the emitter epic: Phase 0 overlaps M3–M5 (the round-trip work), Tier A/
`code` and the in-editor rendering are M7, and Tier C is the natural home for the
long-deferred `VibeFlow`.

---

## 9. Open questions / risks

**Empirical gates — still to run (these change decisions, so run them before Phase 1):**

- **Full Open→Save-to-disk identity survival.** §2.2 verified the litegraph
  serialize/configure round-trip; the remaining test is a real ComfyUI *save to file →
  reload* on an unregistered `vibecomfy.*` node, to rule out any stripping in ComfyUI's save
  pipeline (userdata).
- **Corpus fidelity at scale, oracle-backed.** §6.1 measured the *curated* corpus (~29%);
  the decision-grade number is the messy **community long tail** through the
  `convert_ui_to_api` oracle, with the failure taxonomy driving which families the agent may
  touch.
- **Live diff/patch API surface.** Confirm `LiteGraph.createNode` / `graph.add/remove` /
  `node.connect/disconnectInput` / `widget.value=` mutate the rendered graph and that one
  `beforeChange/afterChange` bracket around raw mutations = exactly one undo step.
- **`changeCount` for drift detection.** The optimistic-sync design wants a cheap version
  token; confirm `ChangeTracker.changeCount` exists/monotonic in the pinned frontend, else
  fall back to a content hash.
- **AST-reconstruction coverage.** What fraction of `ready_templates/**` the parse-don't-exec
  path can rebuild without the `exec` fallback (opaque subgraphs / `apply_ready_template_policy`
  are the likely escape hatches).

**Design risks:**

- **Emitter ⇄ control-flow mapping fidelity.** Reconstructing a `for`/`if` from anchor
  nodes is harder than straight-line emission; needs its own parity gate (extend
  `vibecomfy/porting/parity.py` beyond the static DAG — *and* make that gate oracle-backed,
  not self-referential, §6.1).
- **How much code is "arbitrary"?** A `vibecomfy.code` node that can run any Python is
  powerful but unverifiable and a trust/security surface — decide whether code runs in the
  build step, in-graph (execution-inversion), or only in the orchestration layer
  (`docs/python_composition_dsl_plan.md`'s SD-005 keeps arbitrary Python *out* of an active
  graph; the only sanctioned in-graph path is the unbuilt `ExternalPythonNode`). Note SD-005
  governs the *in-graph* boundary; principle 6 covers the *build-time* `exec` hole SD-005
  never addresses.
- **Native-subgraph stability.** Subgraphs are recent; serialization shape may drift —
  pin a tested frontend range and validate via the vendored ComfyUI oracle.
- **Diff-noise from variable renumbering.** Inserting one node renumbers downstream emitted
  var names (`KSampler_2`→`KSampler_3`) even though `vibecomfy_uid` is stable — text-keyed
  diffs/caching will be noisy. Key diffs on uid, not source text.
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

---

## 11. How this maps to the scratchpad-emitter epic

This work is **not** a separate track — most of it *is* epic milestones. The mapping (and
where the sense-check findings land):

| Milestone | What it owns | This doc / findings that land on it |
|---|---|---|
| **M2 — identity-and-ingest** | the durable `vibecomfy_uid` | The diff *consumes* M2's uid as its join key, and the editor-channel round-trip is **[verified] uid-stable**. Two **M2 defects** surfaced (both with repros): (a) raw `add_node` leaves `uid=""` and *nothing* asserts uid uniqueness — hoist the existing `_mint_uid` into `add_node` + assert in `finalize_metadata`; (b) `sg_key` embeds the subgraph **name** (`scope.py:99`), so a rename nukes inner identity — the M2 idea file is self-contradictory on this. Both are **M2 hardening**, not new milestones. |
| **M3 — emitter + oracle** *(in flight)* | `port export --to ui`, `convert_ui_to_api` as oracle | **Oracle-back the parity gate** (§6.1) — it's currently self-referential; this is an M3/M5 gate fix, not new work. |
| **M4–M5 — layout + preserve-roundtrip** | faithful UI-JSON round-trip | Close the **Get/Set-broadcast resolver** (~35% hard-fail), **`mode`/bypass** and **`groups`** loss (§6.1). These are M5 fidelity bugs. |
| **M7 — in-editor-surface** | the ComfyUI custom-node + **JS preview/diff** | The Nodes 2.0 plugin **and the diff/patch itself are M7.** Build items (2)+(3) in §6.1 and the atomic-rollback fix (§7) are M7 work. |

**The clean boundary (the ambiguity worth stating plainly):** the epic ends at M7 = a
faithful, editable, diff-able round-trip surface over one IR. Everything *above* M7 — the
**LLM agent loop**, the **`vibecomfy.*` control-flow representation** (Tiers A–C), and the
**parse-don't-exec / sandboxing** that the agent loop requires — is a **new layer built on a
finished M7**, not in the current epic's scope. So: the epic delivers the spine and the
surface; this doc's tier scheme + the agent frontend is the next thing that stands on it.
Phase 0 (§8) is mostly "land the epic's own milestones correctly (oracle-backed, coverage
closed, identity hardened) before building the layer above."

---

## 12. Second-pass VibeComfy-internal edge cases (10-agent sweep)

A second sense-check swept the VibeComfy internals (runtime, schema source, virtual wires,
models, packs, plugins, control-flow, mutable IR state). Tagged **[verified]** (repro'd /
read in code) vs **[claimed]**. The two repro'd fidelity bugs are now top of Phase 0.

**Round-trip fidelity defects:**
- **[verified, repro'd — TOP FIX] Get/Set resolver key mismatch.** The normalizer maps a
  GetNode's value to `inputs["name"]` (`normalize.py`, schema `["name"]` at
  `_widget_aliases.py:537`) but the resolver `broadcast_name()` reads only `inputs["widget_0"]`
  (`_workflow_helpers.py:176-182`) → `ConversionParityError: no broadcast name`. **17/52 corpus
  files (33%) contain Get/Set and currently produce NO graph.** ~3-line fix (`name = inputs.get("name", inputs.get("widget_0", ...))`),
  simulated 16→0 failures, back-compat preserved. The unit tests inject `widget_0` directly,
  bypassing the normalizer — green suite, broken corpus. **Single highest-leverage fidelity fix.**
- **[verified, repro'd — TOP FIX] KSampler widget-value shift on emit.** `emit_ui_json`
  emits `widgets_values` against `_compacted_widget_names` (strips the `control_after_generate`
  `None` slot → 6 elements), but ComfyUI/read-back expect 7. Result: a KSampler round-trips as
  `steps=7.5, cfg='euler', sampler_name='simple'` — every value shifts one slot. Affects any
  node with a `None` control slot in `WIDGET_SCHEMA` (KSampler/KSamplerAdvanced). The emit must
  keep the control slot (emit 7, re-inserting the control value). `ui_emitter.py:411-422` vs
  `normalize.py:328-331`.
- **[verified] Schema skew, no version guard.** Widget mapping reads a hand-curated,
  version-*frozen* `WIDGET_SCHEMA` (`_widget_aliases.py:133`, a static "runpod-snapshot"),
  consulted first and short-circuiting the live schema. If the user's installed pack reorders a
  widget, values silently land in the wrong slot. No check ties the schema to installed packs.
- **[verified] UI furniture lost on emit.** node `color`/`bgcolor`/`title`, `groups`, `flags`,
  `mode` are all ingested into metadata but **not re-emitted** (`ui_emitter.py` hardcodes
  `groups:[]`/`flags:{}`/`mode:0`, omits color/title) — recoverable only from the `.layout.json`
  sidecar. A human reopening a round-tripped graph sees it uncolored/untitled/ungrouped with
  bypassed nodes reset to active. Annotation *nodes* (Note/MarkdownNote) survive. Also: two
  divergent `UI_ONLY_CLASS_TYPES` sets — `Label`/`PreviewAny` leak into `compile("api")`.

**Agent-edit-loop integrity (the IR-tools path's own sharp edges):**
- **[verified] Mutable IR-state hazards.** `finalize_metadata` is idempotent ✅, but `connect`
  is append-only (no dedupe → duplicate edges, compile last-writer-wins), `_next_node_id`
  **reuses freed ids** (a dangling edge silently re-targets a new node), and `_id_map` goes
  stale on delete. The agent loop must assert invariants after each edit (delete only via
  `remove_node`; prune `_id_map`; no dangling/duplicate edges; `finalize_metadata` before
  reading inputs/outputs). Dangling edges *are* caught at compile (safety net).

**Run/resolve correctness:**
- **[verified] compile ≠ runs.** `compile("api")` is class/model/schema-blind; real validation
  is HiddenSwitch's `queue_prompt_api`. Missing models/nodes, unconnected-required, type-mismatch
  degrade silently when the object_info cache is cold. `run_embedded_sync(wf)` from Python
  defaults `ensure_models=False` (won't download). Cheapest gate: `doctor` + warm-cache `validate`.
- **[verified] Agent can't safely change models.** Requirements inference only scans `*_name`
  keys (`metadata.py`) while the runtime resolver covers more fields — scope mismatch; hidden
  `widget_N` model filenames are diagnosed but **not** write-blocked; metadata `model_assets` and
  the registry can diverge undetected.
- **[verified] Custom packs: no alias resolution, no shadowing detection, drift tolerated.** An
  agent-added pack node is installable only if the class name matches a known pack *verbatim*;
  a renamed class → `unresolved_runtime_class`; a pack class shadowing a core class is silently
  masked. Lock-vs-installed drift is observed but not blocked (unless `strict_drift`).
- **[verified] Plugin surface not collision-safe / not deterministic.** Block & patch registries
  silently overwrite on collision; routes silently duplicate; entry-point load order is
  non-deterministic; **one malformed plugin throws and poisons the entire discovery pass** (no
  try/except in `extras.py`).

**Control-flow (Tier B/C) reverse path:**
- **[verified] Python→IR is done by *executing* `build()`, not parsing it.** The only AST reader
  (`source_map.py`) walks flat call-sites; there's no `For`/`If` handling. So Tier-B dynamic
  loops are **not closed-form round-trippable** — you can round-trip the *intent* but can't
  mechanically reconcile it against the N-node static expansion the (self-referential) parity
  gate sees. Needs: an AST→IR reader, an **intent-equivalence** parity gate, and (Tier C) a new
  **artifact-across-graph-boundary edge** that `VibeEdge` can't express today.
