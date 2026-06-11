# Local Text-to-Graph Agent — Blockers Log

Status of every blocker hit while making the in-ComfyUI agent-edit panel work
end-to-end (see `docs/local_agent_text_to_graph_e2e.md` for the runbook). Ordered
**all blockers first as an index**, then full detail. Dates are 2026-06-01.

Legend: ✅ fixed · 🟡 partially fixed · 🔴 open · ⚪ pre-existing / out of scope.

## Index (all blockers)

| # | Blocker | Layer | Status | Severity |
|---|---|---|---|---|
| B1 | Agent runtime not wired (`_load_arnold_runtime` finds no module) | backend | ✅ | critical |
| B2 | `megaplan` editable install pointed at stale worktree | env | ✅ | critical |
| B3 | `utils` top-level module collision with ComfyUI (in-process) | backend | ✅ | critical |
| B4 | Browser "Apply" always fails `StaleStateMismatch` (hash mismatch) | backend/frontend | ✅ | critical |
| B5 | Agent panel undiscoverable (collapsed off-screen by default) | frontend | ✅ | high |
| B6 | `convert` dead-branch pruning silently drops user nodes | porting | ✅ | high |
| B7 | Emitter strips wired UI-only passthrough nodes (`PreviewAny`) | porting/emitter | ✅ | high |
| B8 | ~~v3 grouped/dotted inputs not modeled~~ (misdiagnosis) | porting/ingest | ⚪ | — |
| B9 | No verbatim/passthrough fidelity for unknown/v3 nodes (root design) | porting | 🟡 | medium |
| B12 | guard_emit no-ops on first edit of a user graph (no `vibecomfy_uid`) | porting | 🔴 | medium |
| B13 | Agent sometimes emits malformed Python (`from __future__` ordering) | provider | 🔴 | low |
| B10 | Subgraph-wrapped templates don't round-trip prompt into instance | porting/emitter | ⚪ | medium |
| B11 | Pre-existing known-red emitter/parity tests (7) | tests | ⚪ | low |

B1–B7 are resolved: the agent edit now works end-to-end on standard graphs **and**
on the reference Gemini→ByteDance/Seedance video pipeline (verified: faithful
round-trip `parity_ok=True`, PreviewAny + `model.prompt` preserved, prompt edited,
applied). B9/B12/B13 are residual robustness/safety follow-ups. B10–B11 are
pre-existing and out of scope.

---

## Resolved blockers

### B1 — Agent runtime not wired ✅
**Symptom:** `/vibecomfy/agent/status` → `provider_available: false`, error
`"Arnold/Hermes runtime is unavailable… Import attempts: arnold.hermes…; hermes_agent…; arnold…"`.
**Root cause:** `agent_provider._load_arnold_runtime()` imports one of
`arnold.hermes` / `hermes_agent` / `arnold` (or `$VIBECOMFY_ARNOLD_RUNTIME_MODULE`).
None were importable; the published harness installs as the **`megaplan`** package
(`github.com/peteromallet/arnold`) and exposes no `run_agent_turn`/`run`.
**Fix:** shipped adapter `vibecomfy/comfy_nodes/agent/runtime.py` (delegates one
tool-free `AIAgent` turn) + launcher sets
`VIBECOMFY_ARNOLD_RUNTIME_MODULE=vibecomfy.comfy_nodes.agent.runtime`.
Status route now: `ok:true, provider_available:true, backend:megaplan.agent.run_agent.AIAgent`.

### B2 — `megaplan` editable install pointed at a stale worktree ✅
**Symptom:** `import megaplan` → `ModuleNotFoundError`, yet `pip show megaplan-harness`
succeeded (v0.23.0).
**Root cause:** the editable `.pth` pointed at `~/Documents/.megaplan-worktrees/arnold-paf`
(stale) instead of the live checkout `~/Documents/megaplan`.
**Fix:** `pip install -e ~/Documents/megaplan --no-deps` into the ComfyUI python
(`~/.pyenv/versions/3.11.11`). Re-points the editable install.

### B3 — `utils` top-level module collision ✅
**Symptom:** agent turn failed with classified `ProviderError` whose detail was
`cannot import name 'atomic_json_write' from 'utils'` — only inside the ComfyUI process.
**Root cause:** `megaplan/agent/run_agent.py:347` does a bare `from utils import atomic_json_write`
(and `from model_tools import …`). ComfyUI caches its own `utils` package in
`sys.modules`, so megaplan's bare import resolves to ComfyUI's `utils`, which lacks
the name. Worked in a standalone CLI process (no ComfyUI `utils` loaded).
**Fix:** run each `AIAgent` turn in an **isolated subprocess**
(`vibecomfy/comfy_nodes/agent/worker.py`); the worker never imports ComfyUI, so
the bare imports resolve to megaplan's modules. Also isolates asyncio/HTTP state
from ComfyUI's aiohttp loop.

### B4 — Browser "Apply" always fails `StaleStateMismatch` ✅
**Symptom:** in the panel, **Apply Candidate** always errored
`StaleStateMismatch @ accept` ("Client graph hash does not match the graph submitted")
even with an untouched canvas.
**Root cause:** `agent_session.py:_mutate_turn_state` compared the incoming
`client_graph_hash` against the backend's **canonical** `submit_graph_hash`
(`sha256(canonical_json_bytes(graph))`). The frontend computes a *different*
serialization (`sha256HexUtf8(JSON.stringify(serialize()))`), stored separately as
`submitted_client_graph_hash` but never used by the gate → never matches.
**Fix:** accept a match against **either** `submit_graph_hash` *or*
`submitted_client_graph_hash` (both are submit-time fingerprints, so staleness is
still detected). Regression test:
`tests/test_comfy_nodes_agent_edit.py::test_agent_edit_accept_matches_browser_client_graph_hash`.

### B5 — Agent panel undiscoverable ✅
**Symptom:** opening `:8190` showed the canvas but no usable agent panel → "nothing works".
**Root cause:** the panel defaults to `dataset.open="0"` / `transform: translateX(432px)`
(collapsed off the right edge); the only opener was a buried right-click /
Extensions-menu command (`openAgentEdit`).
**Fix:** added an always-visible "✨ VibeComfy Agent" edge tab
(`ensureAgentLauncher()` in `vibecomfy_roundtrip.js`, called from `setup()`) that
toggles the panel open.

---

## Resolved API-node blockers (B6, B7) + the B8 correction

Reference workflow: 9 nodes — `LoadImage×2 → ImageStitch → GeminiNode → PreviewAny →
ByteDance2ReferenceNode (Seedance) → SaveVideo`, plus `PreviewImage`, `MarkdownNote`.
It originally failed `ValidationError @ convert`. **It now round-trips faithfully
(`parity_ok=True`) and edits successfully** — fixed by B6 + B7 together. The strict
convert parity gate is KEPT (no relaxation needed): with the two fixes a faithful
canvas passes it, and a genuinely-lossy conversion still fails honestly.

### B6 — `convert` dead-branch pruning drops user nodes ✅ fixed
**Symptom:** parity diff `class_types only in A: {'GeminiNode': 1}` — GeminiNode
present in source, absent from the round-tripped graph.
**Root cause:** the agent-edit `convert` stage reused the authoring-grade
`port_convert_and_write`, whose emit path runs
`emitter.py:_prune_dead_branches_for_emit` — a backward walk from recognized output
nodes that prunes anything not feeding an output. GeminiNode's only consumer is a
`PreviewAny` (not an output), so it was pruned.
**Fix applied:** added opt-in `prune_dead_branches` flag
(`emitter.emit_scratchpad_python` / `_prepare_workflow_for_emit`,
`convert.port_convert_workflow`); agent-edit (`agent_edit.py:_stage_convert`) passes
`prune_dead_branches=False`. Combined with B7 the graph round-trips with
`parity_ok=True`.
**Evidence:** 288 focused tests pass; the 7 `test_porting_emitter.py` failures are
pre-existing (B11), confirmed by stashing the change.

### B7 — Emitter strips wired UI-only passthrough nodes (`PreviewAny`) ✅ fixed
**Symptom:** even with pruning disabled, the emitted scratchpad had no `PreviewAny`
(`'PreviewAny' in text == False`); the compiled emitted API was missing node `361`
and the `model.prompt` link.
**Root cause (pinned):** `emitter.py:_prepare_workflow_for_emit` stripped a hardcoded
`UI_ONLY_CLASS_TYPES = {"Note","MarkdownNote","Label (rgthree)","PreviewAny","easy showAnything"}`
**unconditionally, before** pruning. But here `PreviewAny` is a functional
**passthrough** (schema `outputs=[STRING]`) carrying GeminiNode's output into
`ByteDance.model.prompt`. Stripping it severed that edge.
**Fix applied:** in fidelity mode (`prune_dead_branches=False`), keep a
`UI_ONLY_CLASS_TYPES` node when it has an output edge into a **non**-UI-only node
(a live passthrough). Authoring (`prune_dead_branches=True`) is unchanged — Note/
MarkdownNote (no outputs) are still stripped.
**Verified:** the reference graph now emits with `parity_ok=True`; PreviewAny and the
`model.prompt` edge are preserved; full agent-edit turn returns a candidate with all
8 nodes intact, `model.prompt` wired, and the GeminiNode prompt edited. No new test
regressions (288 pass; emitter 7 pre-existing unchanged).

### B8 — ~~v3 grouped/dotted inputs not modeled~~ ⚪ misdiagnosis
**What I thought:** the destination node's input dict lacked the `model.prompt` slot
an edge targeted, plus misaligned widget values — so I suspected dotted v3 inputs
weren't round-tripped.
**Actual finding:** the dotted edge round-trips **fine** once its source node isn't
stripped. The sibling `model.reference_images.image_1/2` links always round-tripped;
`model.prompt` only failed because its source (`PreviewAny`) was removed by B7. With
B7 fixed, `model.prompt` is preserved and `parity_ok=True`. The widget-value
"misalignment" (`auth_token_comfy_org="9:16"`, etc.) is **consistent on both parity
sides**, so it doesn't break the round-trip — it's cosmetic naming in the scratchpad,
not a fidelity bug. No fix needed for the reference workflow.
**Residual (cosmetic):** the positional `widget_N` / odd alias names in the emitted
*scratchpad* are ugly but harmless; improving v3 nested-name aliasing
(`ingest/normalize.py`) would make the generated Python more readable. Low priority.

### B9 — No verbatim/passthrough fidelity for unknown/v3 nodes 🔴 open (root design)
**Symptom:** the converter is schema-canonicalization-driven, so any node whose UI
inputs/widgets don't map cleanly to a known flat schema (v3 API nodes, custom packs)
gets dropped or misaligned rather than preserved.
**Root cause:** round-trip fidelity depends on rebuilding nodes from the schema. For
agent-edit, where the goal is to faithfully reproduce the user's exact canvas, that
is the wrong default.
**Proposed fix (Tier 3, several days):** add a "high-fidelity passthrough" mode for
agent-edit — preserve the UI graph's node set, input/slot names, and widget values
**verbatim** for any node that doesn't cleanly canonicalize, instead of dropping it.
Differentiate per node by *whether each UI input/widget maps cleanly to a schema
input*; if not, preserve verbatim. This generalizes B7 + B8 and future-proofs new
node packs without per-node code. With B6/B7 fixed, B9 is no longer blocking any
known workflow — it's the durable generalization, not an active bug.

### B12 — guard_emit no-ops on the first edit of a user graph 🔴 open (safety)
**Finding:** `guard_emit(original_ui, candidate, snapshot_delta)` (refuse.py) is the
"preserve original, refuse divergence outside the delta" net. It scopes by
`vibecomfy_uid` (`_uid_to_litegraph_id` reads `properties.vibecomfy_uid`). A user's
hand-authored canvas has **none** (verified: 0/9 on the reference graph), so
`scope_uids` is empty and guard_emit **returns early (refuse.py:266) — no guarding**.
It only engages on the *second* edit onward (after VibeComfy has stamped uids).
**Why it didn't bite here:** B6/B7 make the convert round-trip faithful, and the
strict convert gate (kept) is the active safety net for first edits. guard_emit is a
*second* layer that's currently inert on first contact.
**Proposed fix:** stamp a stable `vibecomfy_uid` into the original UI at ingest (or
let guard_emit fall back to litegraph node-id matching, which the candidate already
preserves). Then guard_emit + pin-opaque engage on the first edit too — the safety
foundation for ever relaxing the convert gate (a graceful-degradation path for
graphs that don't fully round-trip).

### B13 — Agent occasionally emits malformed Python 🔴 open (robustness)
**Symptom:** ~1-in-N turns fail `ValidationError @ load_python`:
`"from __future__ imports must occur at the beginning of the file"` — DeepSeek
emitted a line before the `from __future__` header. Classified, graph untouched,
**retryable** (the re-run succeeded). Not corruption.
**Proposed fix:** harden the agent system prompt (`agent_provider.build_messages`)
to require the exact scratchpad header, and/or have the loader normalize a
misplaced `from __future__` before the AST scan. Low severity (retry works).

---

## Pre-existing / out of scope

### B10 — Subgraph-wrapped templates don't round-trip the prompt ⚪
For templates like `image/z_image`, the agent edits the Python correctly but the
prompt does not round-trip back into the emitted subgraph **instance** widgets
(it lives in the subgraph definition). Pre-existing UI-emission limitation; flat
graphs round-trip cleanly.

### B11 — Pre-existing known-red emitter/parity tests ⚪
7 failures in `tests/test_porting_emitter.py` (e.g.
`test_ready_template_keeps_dead_multi_output_node_as_bare_call`). Confirmed present
on the unmodified tree (stash test). These are the scratchpad-emitter epic's
by-design red parity tests; only a *rising* count is a regression. This effort adds
zero new failures.

---

## Differentiating node kinds (design notes for B7–B9)

Signals available per node class from `object_info` + the UI graph:

| Signal | Example | Meaning |
|---|---|---|
| `output_node == True` | SaveImage/SaveVideo | terminal output |
| `outputs == []` | PreviewImage | terminal sink |
| `outputs` non-empty | PreviewAny (STRING), GeminiNode (STRING) | passthrough — preserve if wired onward |
| flat input names | `text`, `seed` | canonicalizable today |
| dotted input names (UI only) | `model.prompt` | v3 grouped inputs — **not in schema** |

Principle: don't hardcode node names. Decide per node by whether each UI
input/widget maps cleanly to a schema input. Clean → canonicalize (current path);
not clean (dotted v3 names, unknown class) → preserve verbatim. Never drop a node
with a live downstream edge.

## Recommended next step
Spike **B7** (preserve live passthrough nodes) and re-run the reference graph
through the parity gate. Cheapest probe: it either unblocks the workflow or surfaces
B8 as the next concrete diff.

---

# Part 2 — Full round-trip map & strategic finding

Mapped end-to-end (four parallel reads of ingest, convert/emit, load/lower/validate/
emit-to-UI, and compile/parity). The conclusion: **B6–B9 are not isolated bugs —
they are instances of one architectural choice.**

## The pipeline (agent-edit turn)

```
UI JSON (canvas)
  │  ingest/normalize.convert_to_vibe_format          [A]
  ▼
VibeWorkflow IR ──► python_before  (convert.port_convert_workflow → emitter.emit_scratchpad_python)  [B]
  │                    │  + self-parity: compile("api") source  vs  emitted build().compile("api")   [E]
  │                    ▼
  │                 AGENT (DeepSeek) edits the Python → python_after
  │                    │  security AST scan + exec   (agent_generated_loader)                          [C]
  ▼                    ▼
  │                 VibeWorkflow IR' ──► lower (intent nodes) ──► validate                              [C]
  │                                                                  │
  └────────────────────────────────────────────────────────────────┼─► emit_ui_json → candidate UI    [D]
                                                                     ▼
                                              accept → app.loadGraphData(candidate)  → canvas
```

`[E]` parity gates `[B]`: if the emitted Python doesn't re-compile to a graph
canonically-equal to the source, `convert` hard-fails (`convert.py:859`,
`ConversionWriteError` → `ValidationError @ convert`). That is the user's error.

## The one root cause

Every stage **regenerates** the graph from a **schema-canonicalized IR** instead of
**preserving** the user's bytes. That is exactly right for the tool's original job —
*authoring clean, minimal, canonical templates from known nodes* — and exactly wrong
for *faithfully round-tripping an arbitrary user canvas*. The canonicalization is
pervasive and deliberate:

- strips "UI-only" classes (`emitter.py:1688`; `parity.py` UI_ONLY)
- prunes dead branches (`emitter.py:_prune_dead_branches_for_emit`)
- maps `widgets_values` **positionally** against the schema, falling back to
  `widget_{idx}` (`normalize.py:137`)
- drops link **types** and link ids (`normalize.py:99`), stringifies slots
- hoists constants and **strips schema-default values** (`emitter.py` `_is_schema_default`)
- renumbers node ids / reassigns `vibecomfy_id` (`ui_emitter.py:1876`)
- resolves helper nodes (Get/Set/Reroute/Primitive) away
- infers schema-less outputs from "link appearance order" (`ui_emitter.py:1813`)

For known, flat, standard graphs these all round-trip. For **ComfyUI v3 API/cloud
nodes** (Gemini, ByteDance/Seedance) with **dotted grouped inputs** (`model.prompt`,
`model.reference_images.image_1`) and **passthrough preview nodes**, they don't —
and parity correctly refuses.

## Consolidated loss-point inventory (by class)

| Class | Where | Effect | Hits user wf? |
|---|---|---|---|
| UI-only class strip | `emitter.py:1688`, `parity.py` UI_ONLY | drops Note/MarkdownNote/**PreviewAny**/Label/showAnything even if wired | ✅ (B7) |
| Dead-branch prune | `emitter.py:_prune_dead_branches_for_emit` | drops nodes not feeding an output | ✅ (B6, mitigated) |
| Output-class heuristic | `emitter.py:_is_output_class` (`save*`/`preview*`/`create*`) | custom outputs invisible → pruned | possible |
| Positional widget map | `normalize.py:137`, `widget_aliases` | values land on wrong names; `widget_N`/`unused_widget_N` | ✅ (B8) |
| Dotted v3 inputs | ingest + emitter (`_extras` bundling) | `model.prompt` not first-class; edge has no slot | ✅ (B8) |
| Link type/id dropped | `normalize.py:99` | `[id,…,type]` → only `(node,slot)`; types lost | latent |
| Schema-default strip | `emitter.py` `_is_schema_default` | values matching defaults omitted; wrong schema ⇒ loss | latent |
| Constant hoist prune | `emitter.py:860` | hoisted constant dropped if all refs stripped | latent |
| Helper resolution | `convert.py` resolver | Get/Set/Reroute/Primitive rewritten | per-graph |
| ID/identity reassign | `ui_emitter.py:1874-1876` | `ir_node_id` scrubbed, `vibecomfy_id` renumbered | cosmetic |
| Schema-less output infer | `ui_emitter.py:1813` | output slots guessed by link order | possible |
| Subgraph re-normalize | `emitter.py:2177` | inner ids remapped, structure re-derived | B10-adjacent |
| Emit-time refusals | `ui_emitter.py` pin_opaque / guard_emit / editor-ahead | hard `RefusedEmit`/`EditorAheadError` | situational |

Parity (the gate) tolerates: node-id renumbering, ordering, UI-only widgets,
schema defaults, None values (it's WL-canonical, `parity.py:200`+, `canonical.py`).
Parity flags: any **runtime node present in source but absent in emitted**, any
widget-literal change, any link-topology change. So *any* of the drops above on a
node parity does **not** also strip ⇒ hard `class_types/topology only in A` ⇒ block.

## What we should do (strategy)

Fixing loss points one-by-one is whack-a-mole across ~13 classes / ~40 sites, and
new node packs will keep adding more. Two real options:

### Strategy A — "Fidelity mode" through the existing pipeline (incremental)
Thread a `fidelity=True` (a.k.a. preserve-don't-canonicalize) flag through
convert+emit that, for agent-edit:
- doesn't strip UI-only classes that have live edges (fix B7),
- keeps `prune_dead_branches=False` (done, B6),
- preserves dotted/v3 input names + widget values **verbatim** (no positional
  schema remap) (fix B8),
- preserves node ids/identity,
- and relaxes the parity gate to the same fidelity baseline.
**Pros:** smaller diffs, reuses the pipeline. **Cons:** still chasing each class;
parity semantics get muddy; ongoing maintenance as new node types appear.

### Strategy B — Diff-over-original: stop regenerating the graph (durable) ✅ recommended
Invert the model. The agent reasons over the Python view as today, but the **applied
candidate UI = the original `original.ui.json` with a minimal patch** for only the
nodes/widgets/edges the agent actually changed. Unchanged nodes (GeminiNode,
PreviewAny, dotted inputs, custom packs, subgraphs) are **never regenerated**, so
they're preserved byte-for-byte and *cannot* hit any emit loss point. The parity/
guard check becomes "candidate == original except inside the intended delta" — which
the codebase already has scaffolding for (`guard_emit(original_ui, candidate_ui,
snapshot_delta)`, `editor-ahead`/`snapshot_delta`, the `layout_store` that already
preserves prior geometry).
**Pros:** eliminates the entire blocker class; robust to any node type forever;
matches the safety model ("only change what was intended"). **Cons:** larger
up-front change to how the candidate is produced (derive a structured diff from
`python_before` → `python_after` and apply it to the original UI, instead of
emitting a fresh UI from IR'). Best run as a scoped plan, parity-corpus guarded.

### Recommendation
Adopt **B** as the target architecture. Optionally land the cheap **A** wins first
(B7 UI-only-with-live-edge + the existing B6 prune-off) as an interim that may
unblock simpler API-node graphs — but treat them as stopgaps, not the fix.

### Immediate probe
Spike the B7 narrow fix (preserve UI-only nodes that have a live output edge),
re-run the reference graph through the parity gate, and report the next concrete
diff. It either unblocks this workflow or pinpoints the exact next loss point —
cheap signal either way, and informs how much of B is unavoidable.
