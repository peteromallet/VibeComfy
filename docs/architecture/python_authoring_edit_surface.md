# Python authoring surface for agent-edit (design note)

## The problem this solves

The v2 agent-edit path is **faithful** — the model returns a typed `delta` of ops
and we patch only the named nodes in the verbatim original graph, so every
untouched node stays byte-identical. That faithfulness is non-negotiable (it is
the entire reason v2 replaced the v1 "rewrite the whole Python and recompile"
path, which mangled positions, widget order, link ids, virtual wires, and
uninstalled custom nodes).

But empirically, **the model is good at Python and bad at emitting complex JSON
deltas.** Across real RuneXX LTX graphs:

- Simple ops (`set_node_field`, `set_mode`, single `add_node`) → reliable.
- Complex ops (`add_node` + `upsert_link`, multi-op edits) → the model
  hallucinates link endpoints, picks invalid mode values, or emits malformed /
  multi-object JSON ("Extra data" parse failures).

This is a **surface-syntax** problem: the model reasons fluently in Python
("add an UpscaleModelLoader, connect the VAE-decode IMAGE output to it") but
stumbles when forced to express that as precise nested JSON with exact
`[scope, uid, slot]` tuples.

## What we must NOT do (the v1 trap)

Do **not** go back to "model rewrites the whole graph-as-Python, then recompile
the Python back into a graph." Recompiling regenerates *every* node from a lossy
abstraction, so untouched nodes come back subtly different (reordered widgets,
renumbered links, resolved-away `Get/Set/Reroute` virtual wires, dropped
uninstalled custom nodes). That breaks byte-identity by construction. The Python
must drive **a delta applied over the original**, never a full regeneration.

## Why Python (the core intuition)

The fix is a **surface-syntax** change, not a new algorithm. The model already
reasons fluently about the edit in prose; it only stumbles when forced to
serialize that to `[scope, uid, slot]` JSON. A ComfyUI graph *is* a typed dataflow
DAG — i.e. already a Python program — so we let the model read and write it as one,
and translate its edits into the same faithful typed delta underneath. The model
writes code (its strength); the delta is produced for it (its weakness, removed).
The full, decided design is below.

## Making the view feel maximally NATIVE Python (not "nodes and wires")

The agent reasons best when the surface is *code*, not a node-graph description.
A ComfyUI graph is a typed DAG of function calls — i.e. already a Python dataflow
program. Render it as one:

```python
model, clip, vae = CheckpointLoaderSimple(ckpt_name="sd_xl.safetensors")
pos     = CLIPTextEncode(clip=clip, text="a glass teapot on basalt")
latent  = EmptyLatentImage(width=1024, height=1024, batch_size=1)
samples = KSampler(model=model, positive=pos, negative=neg, latent_image=latent,
                   seed=9, steps=20, cfg=8.0, sampler_name="euler",
                   scheduler="normal", denoise=1.0)
image   = VAEDecode(samples=samples, vae=vae)
SaveImage(images=image, filename_prefix="out")
```

Principles that make it native:

1. **Edges become variable bindings.** Wiring = "pass this variable to that
   argument" — no slot indices, no link ids. This is what fixes `add+wire`: you
   can't pass a LATENT-typed variable into an IMAGE argument.
2. **Fields become keyword arguments with their real names + values**
   (`RandomNoise(noise_seed=9)`). No guessing `seed` vs `noise_seed`. This is what
   fixes field-name misses.
3. **"Search node" = a typed Python API the model recalls like a library.** Don't
   dump 745 class names; expose available nodes as typed function signatures with
   docstrings, e.g.
   `def ImageUpscaleWithModel(upscale_model: UPSCALE_MODEL, image: IMAGE) -> IMAGE: ...`.
   The COMBO/socket types (IMAGE, LATENT, MODEL, …) let the model type-check its
   own wiring in-head. Filter by task relevance to keep the surface tight.
4. **The edit is editing the script** — add a statement, change a kwarg, rebind a
   variable. Each statement carries a stable node identity (`vibecomfy_uid`) so the
   change maps back to a node, and the change is emitted as the typed delta.

Build on what exists: VibeComfy already renders workflows as Python (the
porting/emitter, the `VibeWorkflow` IR, the v1 scratchpad). The work is pointing
that rendering at the *edit* surface, making it typed + dataflow-shaped, and
mapping statement edits → delta ops.

## The design (definitive)

The whole architecture rests on **two invariants and one surface.** Everything
below is a consequence of these three commitments, not a separate feature — if a
detail doesn't serve one of them, it isn't in the design.

> **Invariant A — Faithfulness.** The committed graph is exactly
> `apply_delta(verbatim_original, ops)`. Every node not named by an op is
> byte-identical to the original. (Enforced by the existing `guard_full_ui`.)
>
> **Invariant B — Correctness.** The committed graph is *what the agent saw and
> acted on* — the touched region is structurally isomorphic to the last Python
> preview the agent edited against. (Enforced by an independent compile oracle,
> below — *not* by `guard_full_ui`, which cannot see a semantically-wrong edit.)
>
> **The Surface.** A stable-identity Python *view* the agent reads, an
> AST-*interpreted* op grammar it writes, and a teaching feedback loop. The Python
> is parsed, never executed; it is a view and a syntax, never the source of truth.

### 1. Identity: the uid is the truth; the variable is a stable alias

This is the beam the whole thing stands on. "Identity = variable name" only works
if a name means the *same node every turn*. The emitter's `_compute_variable_names`
(emitter.py:3559) derives names from downstream topology — so adding or rewiring a
node silently renames *existing* variables (`positive` → `positive_1`,
`vaedecode` → `vae_decode_1`). If that happens, the agent's mental map is
invalidated on every edit and the surface collapses.

So the rule is precise: **the `vibecomfy_uid` is identity; the variable name is a
deterministic, session-locked alias for it.** The session holds a write-once
`uid → name` table. The first time a node is rendered it gets a name; every later
re-render is *forced* to that name (via a `var_name_overrides` map handed to the
emitter), overriding the emitter's topology-driven choice. A node added by the
model takes the model's own binding (`up = ImageUpscaleWithModel(...)`) as its durable alias. The
`# uid:` comment carries the fully-qualified uid as the always-valid fallback the
agent can use when a name is ambiguous across scopes. Slot names render as **valid
Python identifiers** (ComfyUI slots may contain spaces/dots: `MODEL (Positive)`
would be a syntax error in `src.MODEL (Positive)`) — the raw name lives in the
comment.

### 2. The view the agent reads

One in-memory working ledger per session, rendered via the existing emitter
(`keep_virtual_wires=True`, `prune_dead_branches=False`) as a dataflow program:

- Function calls binding variables; edges are variable references passed as kwargs;
  widgets are kwargs. `positive = CLIPTextEncode(text=prompt, clip=cliploader)  # uid:b91e`
- **Virtual Get/Set/Reroute are the immovable substrate** — rendered, tagged
  `[virtual]`. (See §6 for why this framing, not "never touch.")
- **Subgraphs render as scoped nested functions**; variables are scope-local, the
  comment carries the scope-qualified uid for disambiguation.
- **The node library is a typed Python API** —
  `def ImageUpscaleWithModel(upscale_model: UPSCALE_MODEL, image: IMAGE) -> IMAGE: ...`
  — filtered by socket-compatibility and task relevance, top-N with `search(...)`
  for more. "Find a node" is recalling a library, not browsing 745 names.
- Coordinates are not rendered in the agent-edit surface: placement is automatic;
  the only spatial hint available is the optional `near=anchor_var` keyword in
  `add` statements (§7).

### 3. The grammar — the agent writes the SAME language it reads

The deepest native-feel win: **the edit surface is the view's own syntax.** The
agent reads `image = VAEDecode(samples=samples, vae=vae)`; to edit, it writes in
exactly that language — there is no second command vocabulary (`connect(...)`,
`set(...)`) to translate the view into. Write == read.

- **Add a node = construct it** — identical to how the view renders one:
  `up = ImageUpscaleWithModel(upscale_model=loader, image=image)`. The kwargs *are*
  the input wiring, exactly as in the view.
- **Set a field = assignment:** `ksampler.steps = 30`
- **Rewire an input = rebind the kwarg:** `vaedecode.samples = up.IMAGE`
- **Disconnect = unbind:** `vaedecode.samples = None`
- **Bypass / mute = the mode attribute:** `ksampler.mode = "bypassed"`
- **Remove = `del ksampler`**
- **Query (no op):** `search(...)`, `python()`, and the named agent tool calls —
  side-effect-free catalog / research; no graph op.
- **Control (no op):** `done()` — commit the session.

Every statement is still **AST-parsed and interpreted, never executed.**
`vaedecode.samples = up.IMAGE` parses to
`Assign(target=Attribute(Name('vaedecode'),'samples'), value=Attribute(Name('up'),'IMAGE'))`
and dispatches to one `upsert_link`. This is emphatically **not** the Option-B
textual-diff trap: we never diff two graph-models; each *statement* is one typed op
applied over the verbatim original. The old `set`/`connect`/`remove` survive only
as the *internal* primitive names — the surface the agent touches is just Python.

<!-- grammar-doc-table:begin -->
| Surface (what the agent writes) | Internal op | Interpreter does |
|---|---|---|
| `node.field = literal` | `set_node_field` | fold the RHS as a literal (const/list/dict, or a const-folded `BinOp`); reject names/calls |
| `var = Class(field=…, inp=src.SLOT, near=…)` | `add_node` | mint uid, bind `var`, reject `vibecomfy.*` intent classes (those use `intent_node_properties()`); emit one `upsert_link` per wired input |
| `dst.field = src.SLOT` (or bare `src` if unambiguous) | `upsert_link` | resolve slot name→index, type-check (`socket_types_compatible`) |
| `dst.field = None` | `remove_link` | disconnect the named input |
| `del node` | `remove_node` | refuse substrate virtuals (§6) |
| `node.mode = "bypassed"|"enabled"|"muted"` | `set_mode` | assign the semantic mode |
| `for n in <list>: n.field = value` | `macro` | parse-time expansion to one assignment per element (hard cap ~50); `range(...)` is the constant-iterator form of the same macro |
<!-- grammar-doc-table:end -->

Resolution mirrors the view: a bare node on the RHS (`vaedecode.samples = ksampler`)
resolves to the node's type-matching output — exactly as the emitter elides an
unambiguous slot when *rendering* — and `.SLOT` is required only when more than one
output type-matches (`vaedecode.samples = ksampler.LATENT`). `node`/`src` resolve
through the session name→uid table; `.SLOT`/`.field` are attribute accesses on tiny
proxies whose `__getattr__` returns only the string name and hard-blocks every
dunder. The agent passes **objects and slot names — never a uid or a slot index.**

**Bounded native idioms — supported because a Python mind reaches for them:**
`for n in <search-result>: n.seed = 42` is *macro-expanded* at parse time (resolve
the iterable to a prior `search()`/list, emit one op per element, hard cap ~50, body
= a single assignment, no guards, no nesting); `node.steps = 20 + 5` constant-folds.
Both are parse-time expansion, not execution. Comprehensions, conditionals,
arithmetic over names, `import`, and `def` stay forbidden — they cross into runtime
evaluation. The AST allow-list is
<!-- grammar-ast-allow-list:begin -->
{Module, Assign, Attribute, Name, Constant, List, Tuple, Dict, BinOp(const), Call, keyword, Delete, For(bounded), Expr}
<!-- grammar-ast-allow-list:end -->
; batches are capped (~50 statements / ~64 KiB) so a confused model can't exhaust the
ledger.

Intra-batch forward references work because the interpreter walks statements in
order: `up = ImageUpscaleWithModel(...)` binds `up`, the next line's
`saveimage.images = up.IMAGE` resolves it — the agent writes code exactly as it
thinks.

### 4. The loop and the wire protocol — write → interpret → preview → teach

A REPL where a cell is a few lines of code. The session captures the verbatim
original ONCE, then each turn is one batch:

```
turn 0: render the FULL Python view + the typed node library + the budget
loop:
  agent replies: a ```batch``` fence (the code) + free prose (user-facing chat)
  runner extracts ONLY the fenced batch → interprets it (apply valid statements
      to the working ledger, log each op); done()/clarify() are just calls it sees
  reply to the agent = a DIFF + a structured ✓/✗ report (NOT a 200-line re-dump)
  agent reads what landed / what failed, writes the next batch
done() → commit (§5)
```

**The fence is the only stripping seam.** Everything outside the ` ```batch ` block
is the agent's natural-language explanation to the user; only the fenced code is
parsed. So the agent stays chatty and human-facing while the interpreter sees clean
code — no JSON envelope, no route field. Control flow is native: the batch simply
*contains* `done()` or `clarify("before or after the face restoration?")`, which the
runner recognizes. **Turn 0 sends the full view; every later turn sends only the
diff** (this is what keeps 100+ node graphs affordable); when the agent needs more
context it calls `search(...)`.

The feedback is the agent's entire window into reality, so it is precise. A
two-line batch where line 2 names a wrong slot returns:

```
--- diff -------------------------------------------------
~ samples = KSampler(... steps=20→30 ...)            # uid:b91e
--- report -----------------------------------------------
[1/2] ✓ ksampler.steps = 30        KSampler.steps: 20 → 30
[2/2] ✗ vaedecode.samples = up.LATENT
        ImageUpscaleWithModel has no output slot "LATENT"; available: IMAGE
        hint: did you mean up.IMAGE?
landed 1/2 · failed 1/2 · batches left: 11
```

**Batch semantics are partial-success, dependency-aware** — the right choice
*because* this is a REPL whose power is the agent seeing what happened and fixing
it. Each valid statement applies; a failed one is skipped and *its dependents fail
with it* (`up = …` fails → `saveimage.images = up.IMAGE` reports "`up` unbound").
Independent statements still land. Warnings never block. Rollback would be worse:
it hides the successful edit, so the model re-issues it and duplicates. The diff
shows *only* what changed; the ✗ line **teaches** (available slots, closest-class
match). A `max_batches` / `max_consecutive_errors` budget — surfaced every turn —
bails instead of doom-looping, classifying the exit (`model_mistake` /
`unrepresentable` / `schema_gap`) so an impossible request stops with a clear reason.

Capturing the original once means the sequential-edit `StaleStateMismatch` ("broken
when I change on top of changes") never arises intra-session; the optimistic lock
survives only as a *cross-session* guard, plus a cheap graph-hash check at `done()`
that refuses if the canvas changed underneath us.

### 5. `done()` — two machine invariants and one human-legible truth

`done()` is not "stop"; it is "prove the edit, or refuse to return." It applies the
accumulated ops over the *verbatim original* and then asserts three things:

- **A — Faithfulness (machine):** `guard_full_ui` — nothing untouched changed
  (byte-identical), with value normalization so a touched `30` vs original `30.0`
  is canonicalized rather than counted as churn.
- **B — Correctness (machine, independent):** compile *both* the original and the
  candidate to API (`compile("api")`) and assert the touched region is isomorphic
  to the working ledger the agent last saw. `guard_full_ui` judges equality through
  a normalizer that *shares the emitter's assumptions* — it grades its own homework
  and is blind to a right-bytes/wrong-slot edit. The compile oracle is the
  independent check that catches a bad name→index resolution.
- **C — Intent (human-legible):** A and B can BOTH pass while the edit is still
  semantically wrong — the agent wired a MODEL output to the wrong but
  MODEL-typed input, so the bytes are clean and the graph compiles. Nothing
  mechanical can catch this, so `done()` emits a **plain-language change summary** —
  every added/removed/rewired edge and changed field, with socket types, *new* edges
  flagged, and same-type adjacent slots noted ("`CLIPLoader.MODEL → KSampler.model`
  — new; adjacent MODEL input `KSampler.positive` unchanged"). The agent reconciles
  it against the request; the human approves from it. It is the third leg precisely
  because it is the only one a machine invariant cannot be.

If A or B fails, `done()` raises with structured diagnostics rather than returning a
wrong graph; C is the surface a human signs off on.

### 6. Virtuals, structural edits, and multi-node placement

The rule isn't "never touch virtuals" — it's the same principle as everywhere
else: **the original graph is immovable; your edits are additive.** Original
Get/Set/Reroute nodes are substrate (the ledger marks them immutable; `del` and
field edits on them are refused). But rebinding an input is a *replacing* upsert, so
multi-consumer fan-out genuinely *requires* a Reroute — and a reroute the session
*creates* is the agent's own, fully mutable. Substrate immutable; session-created
virtuals mutable. No special case — the additive principle applied to virtuals.

**A splice is now just two natural lines**, not a new verb: construct the node from
the upstream, rebind the downstream to it.

```python
up = ImageUpscaleWithModel(upscale_model=loader, image=vaedecode.IMAGE)
saveimage.images = up.IMAGE          # was fed by vaedecode.IMAGE; now by up
```

The runtime *recognizes the splice pattern* (a new node whose output rebinds an
input that the new node itself consumed the prior source of) and places the new node
**on the wire it interrupts** — between source and target — instead of off to the
side. So "splice" survives as a *placement inference*, not extra surface vocabulary.

**Adding many nodes at once must look hand-arranged, not dumped.** When a batch
constructs N chained nodes, the interpreter infers their dataflow order *from the
kwargs the agent already wrote* (the wiring is the order) — it does not need an
explicit `near=` on each. It then lays them out as a left-to-right lane using real
`estimate_node_size` per class (today `_place_add_node` uses a blind
`_STUB_NODE_SIZE`, which is why a naive multi-add staircases), scanning horizontally
around existing nodes rather than diagonally nudging each, and puts the cluster in
one shared group. The feedback annotates the cluster: `✓ placed 5-node pipeline
(1600–3360, 400) right of vaedecode`. Layout follows the wiring the agent expressed.

### 7. Layout — the agent expresses intent in nodes; the runtime owns pixels

The agent reasons over a coordinate-free dataflow view, so its spatial vocabulary is
minimal and *relational*, never absolute: placement is **inferred from the wiring**
by default; `near=node`, `relation="right_of"|"below"`, and `group="Name"` are
optional overrides. It never writes raw `(x, y)` — pixel coordinates would be
hallucinated badly and break across zoom/window. The runtime resolves `near=` to a
coordinate, infers group membership from the anchor, sizes nodes with
`estimate_node_size`, and dodges collisions. The agent receives no coordinate feedback
in the re-render; it can notice layout issues from the diff description and adjust via
`near=` next turn, without
ever owning coordinates. Untouched-node positions are already protected by Invariant A.

### 8. Worked example — "add an upscaling step after the decode"

What the whole surface looks like in motion (LTX/SDXL-style graph):

```python
# turn 0 — the agent is shown the view (excerpt) + the typed library:
#   image = VAEDecode(samples=samples, vae=vae)        # uid:f55i
#   SaveImage(images=image, filename_prefix=\"out\")     # uid:g46j

# turn 1 — the agent explores, then writes one batch:
search("upscale", accepts=["IMAGE"], returns=["IMAGE"])
# ← report: ImageUpscaleWithModel(upscale_model: UPSCALE_MODEL, image: IMAGE) -> IMAGE ; UpscaleModelLoader(...) ...

```batch
loader = UpscaleModelLoader(model_name="4x-UltraSharp.pth")
up     = ImageUpscaleWithModel(upscale_model=loader.UPSCALE_MODEL, image=image.IMAGE)
saveimage.images = up.IMAGE          # rebind: splices `up` onto the wire it interrupts
```
# ← diff shows +loader +up and SaveImage(images=up); runtime places loader/up between
#   VAEDecode and SaveImage (splice-pattern inference, §6); report: 3/3 ✓

done()
# ← A byte-identity ✓ (5 untouched nodes identical) · B compile-isomorphism ✓
#   C summary: "added UpscaleModelLoader+ImageUpscaleWithModel; SaveImage.images
#   rewired vaedecode.IMAGE → up.IMAGE (new edge)." Human approves.
```

The agent never wrote a uid, a slot index, or a line of JSON — it wrote the same
Python it was shown. The **Reroute-into-subgraph variant** is the same moves: the
view shows both consumers explicitly, and rebinding the reroute's input
(`reroute.input = up.IMAGE`) replaces the link feeding the subgraph; trying
`del reroute` is refused with the teaching message "reroute is substrate; rebind
its input instead, or construct a new Reroute for fan-out."

### 9. What this deliberately does NOT do

Owned scope decisions, not omissions: no `session_rebase()` op-replay for
concurrent canvas edits (the `done()` hash-check is enough); no
`duplicate`/`clone_branch` (the agent constructs explicitly); no raw `(x, y)` /
`reposition()` coordinate API (relational placement only, §7); no unification of the
two placement constant sets until overlap proves to be a real problem; no
comprehensions/conditionals/user-`def`s in batches (they cross into runtime eval —
bounded `for` over a search result is the one iteration idiom we expand, §3). The
token cost of 100+ node graphs is handled by full-view-on-turn-0-then-diffs plus
`describe()`/`search()` windowing, not a new summarization mechanism.

### Build plan

**Reuse unchanged:** `edit_ops.py`, `edit_apply.py` (`apply_delta`,
`guard_full_ui`), `edit_ledger.py` (uid/link minting, scope indexing), schema
providers, `socket_types_compatible` / `_resolve_*_endpoint`, the emitter's
var-name / section-group / subgraph internals.

- **P0 — the offline-provable core (no LLM yet).**
  (a) Emitter: `emit_agent_edit_python(workflow, ledger, var_name_overrides)` —
  session-locked names (§1), valid-identifier slots, `[virtual]` tags, scoped
  subgraphs, placement annotations; `emit_available_node_signatures(...)`.
  (b) `porting/edit_session.py` — working ledger; the **assignment-syntax AST
  interpreter** (§3: construct/assign/`del`/`.mode`, bare-or-`.SLOT` RHS resolution,
  allow-list incl. bounded-`for`/const-fold, `literal_eval` values, dunder-blocked
  proxies, batch caps, intent-class refusal); name→uid table; slot resolver; uid
  minter; `describe()`/`search()`; multi-node cluster + splice-pattern placement;
  delta accumulator; partial-success dependency-aware executor with teaching
  diagnostics.
  (c) `done()` triple gate (§5: guard_full_ui + compile-isomorphism + the C summary).
  (d) **The gate that proves it before any model runs:** `tests/test_porting_edit_session.py`
  — per-statement round-trip for each surface form (`node.f=v`, `var=Class(...)`,
  `dst.f=src.SLOT`, `dst.f=None`, `del`, `.mode`) → delta → `apply_delta`, asserting
  *both* `guard_full_ui` and compile-isomorphism; the splice two-liner; a 5-node
  cluster placement; partial-batch semantics; bounded-`for` expansion; empty-delta
  no-op; plus a seeded property-fuzz over random 1–10-statement sequences. **And a
  dedicated cross-turn identity-stability test** (render → edit → re-render, assert no
  existing node's variable name changed) — the identity model is the highest-risk
  piece *precisely because its failure is invisible to the byte-identity and compile
  gates* (they check the committed graph, never the agent's cross-turn view), so it
  needs its own assertion. Pass on the flat fixture + corpus schema provider ⇒ the
  translator is sound, no LLM needed.

- **P1 — the loop + wire protocol, behind a flag.** The ` ```batch ` fence extractor
  (chat outside, code inside); full-view-on-turn-0-then-diffs; the diff + ✓/✗
  teaching report; `done()`/`clarify()` as in-batch calls; budget surfaced each turn;
  the C change-summary surfaced for human sign-off. The faithful apply layer is
  untouched.

- **P2 — polish.** Const-fold/bounded-`for` ergonomics, diff-render refinement,
  `describe()` formatting, group-inference edge cases.

- **P3 — proof on the real corpus.** The RuneXX LTX byte-identity harness: the
  canonical "add an ImageUpscaleWithModel after VAEDecode and wire it in" green where
  blind-JSON failed, plus the splice, a 5-node add, a subgraph-internal edit, and the
  Reroute-into-subgraph variant — every case satisfying A, B, and a clean C summary.

The smallest thing that proves the approach is P0(d): the executor proven correct
offline, with the *independent* oracle, before a single model token is spent.
