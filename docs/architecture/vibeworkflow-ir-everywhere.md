# The VibeWorkflow IR — one representation, used everywhere

> End-state design. One typed graph representation (`VibeWorkflow`) is the *only*
> thing the agent pipeline sees: it is what every stage ingests, what research
> searches, what the model reads and edits (as Python), and what the judge
> grades against. Raw ComfyUI LiteGraph JSON becomes a wire format at the door —
> nothing past ingest touches it.

---

## 1. The problem this solves

The pipeline was built on the wrong substrate. Each stage read the raw LiteGraph
canvas dump (`request.graph`): positional link arrays `[id, src, src_slot, dst,
dst_slot, type]`, `widgets_values` positionally indexed, `linked(17)` link-ids
that look like node-ids, and `_ui` bloat carrying canvas positions and editor
state. Three concrete consequences, all measured in the failure analysis:

1. **The model confabulated against a truncated view.** The reply stage rendered
   `_build_text_summary`: first 5 widgets, first 6 inputs, first 20 edges as bare
   `15 -> 16` with no link id — while the judge scored the *complete* UI. The
   "orphaned ControlNet" hallucination (3c978e) was locally honest, globally false.
2. **Edits targeted positional indexes.** Widgets were `w4`, `w5` — not
   `strength`. The model wrote widget index 4 when the strength widget was index 5
   (8800a9), and tried to set a socket as if it were a widget (90a1d5).
3. **The IR that solved both existed and was deleted.** A `VibeWorkflow`-based
   edit path ran from `d4c80b5e` (2026-06-11) until the elegance run
   `bc433ece` (merged `0f515870`) removed it, leaving `VibeWorkflow` dormant as an
   input-shape normalizer that round-trips then discards.

This design restores the IR as the single representation and keeps it there.

---

## 2. The representation

### 2.1 The IR (`VibeWorkflow`)

`vibecomfy/workflow.py` — typed dataclasses, no positional anything:

```
VibeWorkflow
  id: str
  source: WorkflowSource          # provenance: where this graph came from
  nodes: dict[str, VibeNode]      # keyed by node id
  edges: list[VibeEdge]           # named endpoints, not positional arrays
  inputs: dict[str, VibeInput]    # graph-level inputs (named)
  outputs: list[VibeOutput]       # graph-level outputs (named, typed)
  requirements: WorkflowRequirements
  metadata: dict                  # opaque, round-trips verbatim
  groups: list[dict]              # LiteGraph groups, carried losslessly

VibeNode
  id: str, class_type: str, pack: str | None
  inputs: dict[str, Any]          # named input sockets (values or edge refs)
  widgets: dict[str, Any]         # NAMED widgets: {"strength": 0.8}, not [0.8]
  metadata: dict                  # opaque canvas extras, round-trips
  uid: str, mode: int
  pos: list[float] | None, size: list[float] | None
  raw_widgets: RawWidgetPayload | None
  provenance: str                 # security tag (S4)

VibeEdge
  from_node: str, from_output: str
  to_node: str,   to_input: str   # "N15.CONDITIONING -> N16.conditioning"
```

The IR is **lossless** over the canvas: `_normalize_ui_to_api` keeps the raw node
as `_ui` and `_raw_widgets`, and `from_ui` carries groups across. Nothing the
judge needs is dropped. But the *model-facing view* of the IR (below) shows only
the meaningful structure.

### 2.2 The doors in / out

```
raw LiteGraph JSON ──from_ui()──▶ VibeWorkflow ──compile("api")──▶ Comfy API dict
serialized envelope ─from_envelope()──▶ VibeWorkflow ──emit_ui_json(wf)──▶ UI JSON
Comfy API dict    ──from_api()──▶ VibeWorkflow ──to_envelope()──▶ versioned envelope
```

All in `vibecomfy/ingest/normalize.py` + `vibecomfy/porting/emit/ui.py`. These
are pure functions: same input, same output, testable without a server.

### 2.3 The clean view — the graph as Python

The model never sees the IR dump, the raw JSON, or a bespoke text projection.
It sees the workflow **as Python code** — rendered from the IR by
`emit_agent_edit_python` (`vibecomfy/porting/emit/emit_agent_edit.py`). This is
the actual representation the model reads *and writes*. Real output for the
3c978e graph:

```python
# vibecomfy: agent-edit
# Edit node assignments only; uid comments are the stable identity fallback.
checkpointloadersimple = CheckpointLoaderSimple(
    ckpt_name='sd1/toonyou_beta6.safetensors',
)  # uid:4 slots model='MODEL', clip='CLIP', vae='VAE'
vhs_loadvideo = VHS_LoadVideo(
    choose_video_to_upload='image',
    custom_height=512, custom_width=512, force_rate=0,
    force_size='Disabled', frame_load_cap=0, select_every_nth=1,
    skip_first_frames=0, video='diffuse.gif',
)  # uid:10 slots image='IMAGE'
vhs_loadvideo_2 = VHS_LoadVideo(
    video='open pose.gif', custom_height=512, custom_width=512, ...
)  # uid:13 slots image='IMAGE'
ksampler = KSampler(
    model=animatediff.MODEL,
    positive=controlnetapply_3.CONDITIONING,
    negative=clip_text_encode_2.CONDITIONING,
    latent_image=vae_encode.output_0,
    seed=902255461654498, control_after_generate='randomize',
    steps=20, cfg=8, sampler_name='euler', scheduler='normal', denoise=0.45,
)  # uid:3 slots LATENT='LATENT'
```

What this representation gives you:

- **Named everything.** `steps=20`, `strength=0.8`, `video='open pose.gif'` —
  never `w4`, never `widget_0`, never positional arrays.
- **Edges are code.** `positive=controlnetapply_3.CONDITIONING` — a wire is a
  Python assignment, read as "node.INPUT = src.SLOT". The chain
  `openpose → depth → canny → KSampler` reads as data flow, not `[17,26,0,3,1,""]`.
- **Stable identity.** `uid:4` comments anchor nodes across the round-trip;
  `slots` comments say what each node outputs.
- **No noise.** No `pos`, `size`, `_ui`, `flags`, `metadata`, `provenance` —
  the emitter renders only what an editor reasons about.
- **The same language for reading and editing.** The model edits this exact
  text; the harness re-parses it. No translation layer between "what I see" and
  "what I change."

**Why no imports / no `def build()`?** Deliberate, by security contract
(`docs/architecture/python_authoring_edit_surface.md` §3): `import` and `def`
are **forbidden from the surface grammar** because they "cross into runtime
evaluation." The class names (`KSampler`, `VHS_LoadVideo`) resolve through the
session's **typed node library** — a pre-bound name→uid table the harness injects
at interpret time, not through Python imports. The AST allow-list is
`{Module, Expr, Assign, Delete, For(bounded), Call, Name, Attribute, Constant,
List, Tuple, Dict, keyword, BinOp(const)}`; batches are capped (~50 statements /
~64 KiB). The model writes assignments; the interpreter — never `exec` — lowers
them to typed ops.

For **explain-only stages** (classify, reply, judge) the same Python view is the
shared text — plus a computed topology index appended for the answer path
(`orphans`, `out_degree`, `class_index`), derived in code so the model never
derives what code can state. One representation, one renderer, used by every
stage.

---

## 3. The pipeline (all stages on the IR)

```
        from_ui()
raw JSON ────────▶ VibeWorkflow
                      │
                      ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ classify │──▶│ research │──▶│ implement│──▶│  reply  │──▶│  judge  │
   └─────────┘   └─────────┘   └─────────┘   └─────────┘   └─────────┘
      reads          reads          edits        reads        reads
   Python census   Python-view    via Python   Python view  Python view
   + ref map       corpus         surface      + diff       + index
```

### 3.1 Classify — route the request

Sees: the query + a compact census of the IR (`N node(s): ClassA, ClassB, …` +
a 30-row `id=N: ClassType` reference map). Chooses route / intent from the locked
table. No widgets, no edges — classification needs shape, not wiring.

### 3.2 Research — search an IR-shaped corpus

Sees: the research brief (question, directions, source preferences) + the
evidence digest. The research agent calls `hivemind_search` / `hivemind_get` /
`registry_lookup` over the **Hivemind corpus, whose workflow records are
normalized to the same IR** before they are served. A search hit returns the
record's *Python view* (the same `emit_agent_edit_python` rendering), not a
blob of JSON — so
the agent reasons about precedents in the same representation it edits.

Two integrity rules (unchanged from the current design, now on the IR):

- **Attempt typing, not confidence.** Python derives `research_attempt` from the
  ledger: `never` (zero tool calls) / `empty` (tools ran, nothing found) /
  `thin` (artifacts, no fetched citations) / `grounded` (≥1 fetched citation).
  Semantic routes (inspect/respond/research-answer) **never gate the reply** —
  on `never`/`empty` the model answers from graph + knowledge instead of emitting
  "No supported conclusion".
- **Adapt implements on evidence existence.** `thin` or `grounded` → implement.
  Only `never`/`empty`/non-OK skip.

### 3.3 Implement — edit the Python, the harness interprets it

The implement stage is a **Python REPL over the IR**. Turn 0 renders the full
Python view (§2.3) plus the typed node library and the budget. Each turn the
agent replies with a fenced ```batch``` of Python; the harness interprets it
against the working IR, applies what's valid, and returns a diff + ✓/✗ report —
never a re-dump. `done()` commits. Detail in §4.

### 3.4 Reply — the same Python view

Sees: the Python view (what the graph *is*) + the executed-diff summary (what
changed). Prose may not contradict the diff; canned "was not applied" only with
`validation_issues[]`.

### 3.5 Judge — grade against the same view

The semantic judge gets the same Python view the model read (plus the rubric),
with the computed topology index appended so untokened topology claims
hard-fail. The edit judge compares pre-IR vs post-IR Python views — the diff is
the delta the interpreter logged, not positional text.

---

## 4. The edit tool — the Python surface

There is no JSON op tool. The edit tool **is** the Python surface: the agent
writes assignments; `EditSession.apply_batch(code)` (`vibecomfy/porting/edit/
_parse_execute.py`) parses them against a strict AST allow-list and lowers each
statement to a typed op on the ledger.

### 4.1 The grammar — the agent writes the SAME language it reads

| Surface (what the agent writes) | Internal op | Interpreter does |
|---|---|---|
| `node.field = literal` | `set_node_field` | `literal_eval` the RHS (const/list/dict, or a const-folded `BinOp`); reject names/calls |
| `var = Class(field=…, inp=src.SLOT, …)` | `add_node` (+ `upsert_link` per wired input) | mint uid, bind `var`, reject `vibecomfy.*` intent classes |
| `dst.field = src.SLOT` (bare `src` if unambiguous) | `upsert_link` | resolve slot name→index, type-check (`socket_types_compatible`) |
| `dst.field = None` | `remove_link` | |
| `del node` | `remove_node` | refuse substrate virtuals |
| `node.mode = "bypassed"\|"enabled"\|"muted"` | `set_mode` | |

(from `docs/architecture/python_authoring_edit_surface.md` §3 — the grammar is
already specified and the interpreter exists.)

**The agent passes objects and slot names — never a uid or a slot index.** A bare
node on the RHS resolves to its type-matching output; `.SLOT` is required only
when several outputs type-match. `for n in <search-result>: n.seed = 42`
macro-expands at parse time (bounded ~50). `import`, `def`, comprehensions,
conditionals, and arithmetic over names are **forbidden** — they cross into
runtime evaluation. The AST allow-list is
`{Module, Expr, Assign, Delete, For(bounded), Call, Name, Attribute, Constant,
List, Tuple, Dict, keyword, BinOp(const)}`; batches are capped (~50 statements /
~64 KiB).

Intra-batch forward references work because the interpreter walks statements in
order: `up = ImageUpscaleWithModel(...)` binds `up`, the next line's
`saveimage.images = up.IMAGE` resolves it — the agent writes code exactly as it
thinks.

### 4.2 The typed node library — why the surface needs no imports

`KSampler`, `VHS_LoadVideo`, … resolve through a **pre-bound typed node
library** — the session's name→uid table injected at interpret time — not
through Python imports. That is why the rendered Python carries no `import`
lines: the names are already in scope by contract, and `import` is banned from
the grammar for security (it would cross into runtime evaluation). The same
library powers `describe(node)` / `search(...)` helper calls the agent may use.

### 4.3 What the model sees vs what can be edited

The **EditableSurface** of each node (instance-hydrated from the IR, works even
when the class schema is missing) decides what's writable:

- Widgets and sockets come from the node's real `widgets` / `inputs` — named,
  never positional.
- Sockets are editable only as *wiring* (`dst.field = src.SLOT`), never as a
  value write. `TripoRefineNode.prompt` is a socket; `prompt = 5` is a
  `channel_mismatch`, not a guessed widget.
- Missing schema ≠ no surface: `schema_status: unknown` still yields the
  instance's real fields. `TripoRigNode` with zero widgets → nothing writable →
  typed `uneditable`, without asking the user for a field that doesn't exist.
- Roles come from a closed enum (`PARAMETER_TWEAK_TARGET_TERMS` + aliases):
  `strength|scale|weight|aggressiveness → strength`, `seed → seed`,
  `rows + cols → both-or-nothing` for N×M grids. No ontology, no learned catalog.

### 4.4 The deterministic apply guard

Every landed op passes the guard before it touches the IR (allowed: safety /
execution / evidence — judgment stays with the model):

1. Target node exists in the IR.
2. Channel matches the surface (`prompt` is a socket → refuse).
3. Name resolves via the typed library / compact resolver.
4. `old == current` (compare-and-swap — refuses stale edits).
5. New value matches `kind` / bounds / combo choices.

Rejections are per-statement ✓/✗ in the diff report, so the agent sees exactly
what landed and what failed, and can fix it next turn. Zero writable targets →
typed `uneditable` + inspected surface + reason (`clarify` only when ≥2 writable
rows match).

### 4.5 Emit — IR back to the world

After `done()`: the edited IR → `emit_ui_json(wf, guard_original_ui=…,
guard_resolved_ops=…)` (`vibecomfy/porting/emit/ui.py`) rebuilds the full
LiteGraph payload — node ids, link ids, widget values, positions — with
provenance carried. The agent never hand-writes JSON; it writes Python, and the
emit is deterministic. The op ledger (`ops.py`: `set_node_field`, `add_node`,
`upsert_link`, …) is the durable record of what changed.

### 4.6 What this fixes

| Live failure | Mechanism | Fix |
|---|---|---|
| 8800a9 wrote idx 4 instead of strength idx 5 | positional `widgets_values[i]` | write by name `strength`; guard checks name↔index |
| 90a1d5 tried to set `TripoRefineNode.prompt` (a socket) | sockets merged into editable previews | sockets are `writable: false`, separate channel |
| 2×2 set `rows=4` alone | single-field write | role rule: N×M declares both `rows` and `cols` |
| 352066 hedged "no knee control exists" | couldn't see the surface | `EditableSurface` shows zero widgets → typed `uneditable` |

---

## 5. The elegance principles

1. **One representation.** `VibeWorkflow` is the only graph the pipeline touches.
   JSON is a wire format at the door; it never enters a prompt, a tool, or a
   judge payload.
2. **Structure, not text.** The model reads and writes the graph as Python —
   named nodes, named fields, wires as assignments. Never raw arrays to parse
   mentally.
3. **Names everywhere.** Widgets and sockets are addressed by name at every
   boundary: surface, grammar, guard, reply, judge. Positional indexing exists
   only inside the emit, and only as a derivation.
4. **Compute, don't ask.** Topology facts (orphans, degrees, class index),
   research-attempt type, edit-target validity — all computed in code. The model
   is never asked to derive what code can state.
5. **Deterministic = safety / execution / evidence.** The interpreter parses an
   allow-listed grammar; the guard verifies every op; the emit is pure; the
   attempt type is ledger-derived. Choosing the query, the edit, and the meaning
   stays with the agent.
6. **Same facts for model and judge.** Whatever Python the model reasons from is
   the Python the judge grades against. Asymmetry is the root of the
   hallucination class; symmetry is the design.

---

## 6. Migration path (from the current batch_repl world)

| Step | Change | Lands |
|---|---|---|
| 1 | Ingest: `_frag_entrypoint` normalizes via `from_ui` once and *retains* the IR (it already constructs it, then discards) | `graph_normalization.py`, `_frag_entrypoint.py` |
| 2 | Python view everywhere: `emit_agent_edit_python` becomes the model-facing graph for reply + judge too (not just implement); wire `graph_inspection=` correctly; judge uses the same Python | `porting/emit/emit_agent_edit.py`, `core.py`, `prompts.py`, `intent_judge.py` |
| 3 | Edit via the Python surface: route implement through `EditSession.apply_batch` (the allow-listed interpreter) as the *product* path — it already exists, it's dev-gated; make it default. Add `EditableSurface` projection + the CAS guard on every landed op | `porting/edit/_parse_execute.py`, `session.py`, new `editable_surface.py` |
| 4 | Corpus: normalize Hivemind workflow records to the Python view at serve time | `hivemind_tools.py` |
| 5 | Research typing: `research_attempt` on the ledger; semantic replies never gated | `agent_research_stage.py`, `core.py`, `prompts.py` |
| 6 | Query shape: message scope phrase-only, no alias OR bomb, cheaper 57014 retry | `hivemind_clients.py` |
| 7 | Delete the raw-JSON-only paths once all stages consume the IR | `_frag_*` cleanup |

Steps 1–3 are the core of this design; 4–6 are the research half (they hold
regardless); 7 is the payoff — the raw-JSON mutation layer becomes dead code.

---

## 7. What "done" looks like

- `request.graph` is converted to `VibeWorkflow` exactly once, at the door.
- Every stage, tool, prompt, and judge consumes the IR (or its Python view).
- The Python surface (`EditSession.apply_batch`) is the only way the graph
  changes; it writes by name, through the guard, and emits deterministically.
- A live 100-scenario run shows the semantic-answer hallucination class and the
  edit-mistarget class collapse (the 3c978e / 9d28c6 / 8800a9 / 90a1d5 / 2×2
  families), with the remaining failures being the honest model-capability floor.
