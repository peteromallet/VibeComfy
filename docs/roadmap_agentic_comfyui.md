# Roadmap v2: from PoC to Agentic ComfyUI

**Status:** holistic plan, **revised after a 10-agent red-team** of the v1 roadmap.
Companion to `docs/python_on_the_graph.md` (design + verified findings) and the
scratchpad-emitter epic (the round-trip engine). v1 framed this as a lossless *bijection*;
the red-team showed that framing is the single most dangerous thing in the plan. v2 keeps
the spine (oracle-backed gates, foundation-first, "never grade your own homework") and fixes
the framing and the mechanisms.

> **Scope discipline (read first).** The red-team was calibrated to "FULL robustness," so it
> returned a lot of *production-grade machinery*. This is still a prototype at single-digit-%
> fidelity with no users. So **not all of §1–§13 is "now."** Load-bearing now: the bijection
> reframe (§2), **the not-fragile Python→JSON architecture (§11 — decision LOCKED: IR-canonical)**,
> the never-silent-corruption contract (§3, as a principle), the two repro'd fixes + an
> oracle-backed gate (§13), and the vertical-slice/per-family sequencing (§9). **Deferred until there are real users / the codec
> actually works:** the Ops layer + prod canary + data flywheel (§4 Ops row), the version-matrix
> + saved-workflow migration (§8 — just *pin one ComfyUI version* now), the property/fuzz
> coverage harness (§7 — differential corpus gate now, fuzzing later), and the full metric
> taxonomy + execution ceremony (§5/§10 — keep the ratcheted CI gate + findings-as-tests, skip
> the org process). The rest is the catalog of where robustness *eventually* lives, not a day-one
> mandate.

---

## 1. North star + the HONEST goal

A user in the ComfyUI editor asks, in plain language, for something complex; an agent edits
the workflow, and the change appears faithfully on the canvas — runnable, diff-previewed,
undoable, trusted.

But "FULL robustness" is not "100% byte-fidelity on every workflow" — that is *provably
impossible* (the formats are lossy and the community node space is unbounded). The honest,
falsifiable goal is a **total function with an honest refusal branch**:

> **For any workflow a user can open in their ComfyUI, on any request, the system ends in
> exactly one state: (A) APPLIED — edited as asked, with zero execution-graph loss, faithful
> UI furniture, preserved identity, previewable + one-step-undoable; or (B) REFUSED — nothing
> reaches the canvas, with a precise machine-readable reason. The forbidden third state —
> SILENT CORRUPTION — must be impossible by construction.**

"Full" = **full fidelity on the round-trippable subset + graceful-partial edits everywhere
else + never silent corruption.** Naming that ceiling honestly is itself part of robustness.

## 2. The keystone, reframed: it is NOT a bijection

v1 said "round-trip fidelity is the foundation; build one canonical codec so `emit =
ingest⁻¹`." The red-team's deepest finding: **a true inverse is impossible.** Ingest is
deliberately *many-to-one* (it normalizes reroutes, inlines primitives, collapses Get/Set),
so a canonicalizing codec *cannot* also be invertible — the v1 cure was internally
contradictory. The achievable, correct target is:

- **(a) Semantic isomorphism** — the edited graph's API JSON equals ComfyUI's *own*
  `convert_ui_to_api` output, node-for-node / edge-for-edge / widget-for-widget. (the
  execution-graph core)
- **(b) Presentation fidelity** — UI furniture (pos / size / groups / color / title / `mode`)
  is *preserved via a `vibecomfy_uid`-keyed sidecar*, **restored on emit, not regenerated**.

This matters because the v1 keystone metric compares against an *API-JSON* oracle and is
therefore **furniture-blind**: a workflow can score 100% while emitting every node grey,
untitled, ungrouped, bypass-reset (`python_on_the_graph.md` §12 — `ui_emitter.py` hardcodes
`groups:[]`, `mode:0`, stubs layout). v2 splits the keystone into **two gates** — semantic
fidelity (a) and presentation fidelity (b) — and renames "lossless" → "semantic fidelity."

## 3. The robustness contract (the total function)

Three mechanisms v1 lacked, required to make §1's contract real:

1. **Runtime corruption-detector (oracle as a circuit-breaker, not just a CI scoreboard).**
   Before any APPLIED commit, dry-run the candidate through `convert_ui_to_api` and diff the
   *untouched* regions against the pre-edit graph; any divergence outside the intended delta
   → abort to REFUSED. Fencing is a *whitelist*; this is the *detector* that makes "never
   silent corruption" hold on graphs you've never seen.
2. **Refusal as a first-class, typed output** — `RefusalReason{scope, class, remediation}`,
   deterministic, with its own gate ("does the stated cause match the real one?"). Today
   refusal is an exception that happens to fire (33% of the corpus), not a designed surface.
3. **Independent semantic judge for "did the edit do what was asked"** — execution-diff or an
   LLM-judge panel against the NL intent, *not* VibeComfy's own compile (else L3 inherits the
   self-reference §6.1 condemns).

## 4. The dependency stack — now with an OPERATIONS column

v1 was a *construction* plan with no *operations* plan; its own "never grade your own
homework" principle was violated at the system level because **the production system grades
itself** (every gate measures a corpus we hold; a real user's graph is invisible). v2 adds an
**Ops track that runs parallel to L0 from day one:**

| Layer | What | Gate |
|---|---|---|
| **L0** Semantic codec | ingest↔emit semantic isomorphism vs `convert_ui_to_api` | semantic-fidelity %, per-family |
| **L0b** Presentation | furniture preserved via uid-keyed sidecar | presentation-fidelity % |
| **L1** Identity | durable `vibecomfy_uid`: mint-on-create, rename-stable | identity-stability % |
| **L2** Editor surface | diff/patch, atomic rollback, undo, `vibecomfy.*` render | surface integrity, live |
| **L3** Agent loop | parse-don't-exec, IR-tools, grounded, doctor-gated | edit-correctness % (indep. judge) |
| **L4** Control-flow | loops/branches/code/multi-wf | intent-equivalence parity |
| **L5** UX | NL → trusted graph update | end-to-end task-success % |
| **Ops** *(parallel to all)* | prod canary + telemetry; saved-workflow migration; ComfyUI version-matrix; the data flywheel | corruption-detected-in-field = 0; matrix green |

## 5. The metric is PLURAL — and shaped, never averaged

A single average % is Goodhart-bait (you can raise it by narrowing the corpus or normalizing
real diffs away). v2's gate is a *taxonomy*, each with a threshold **shape** of
**"100% on the fenced core + provably-safe refusal everywhere else,"** reported **per-family,
never blended**:

| Gate | Truth source | Shape |
|---|---|---|
| Semantic fidelity | `convert_ui_to_api`, per-family | 100% on fenced set; else refuse/passthrough, never corrupt |
| Presentation fidelity | uid-keyed sidecar | 100% furniture restored for ingested nodes |
| Edit-correctness | held-out NL tasks, **independent** judge | high; **0 silent-wrong** (wrong-but-compiles is the cardinal sin) |
| Run-success | HiddenSwitch `queue_prompt_api` | every *committed* edit runs, or is doctor-blocked pre-commit |
| Refusal-precision | adversarial + long-tail + malformed | provably-safe everywhere out-of-fence; 0 corruption-without-warning |
| Perf / atomicity | live editor, large graphs | rollback never leaves a broken canvas; node-count latency budget |

Goodhart guards: oracle side must be `convert_ui_to_api(original)` (a tripwire test asserts
the two operands aren't both VibeComfy compiles); corpus is append-only/versioned; any
diff-normalization needs a written semantic-equivalence justification.

## 6. The fence is a RUNTIME per-node verdict + per-region degradation

v1's "fence to families that pass L0" is a static allowlist — unsound, because failures are
*topological* (a node safe in z_image corrupts inside a renamed subgraph). v2:

- **Fence = an oracle-backed dry-run round-trip on *this* input**, producing a **per-node
  verdict map** (not a whole-graph boolean), enforced on both the input *and* the post-edit
  output. Static registry is a fast pre-filter only.
- **Per-region graceful degradation** (the highest-leverage missing decision): **edit the
  proven region, pin the rest as opaque** (reuse the existing `opaque()` carrier — validation
  already tolerates unknown class_types), **refuse-with-reason** on what you won't touch. This
  is the difference between "works on the curated corpus" and "works on any user graph,
  partially." One weird community node no longer locks the agent out of the whole workflow.

## 7. Coverage: property-based + differential + fuzz, not a fixed corpus

A 48-workflow pass-rate is a *regression smoke test*, not a robustness claim — it says nothing
about the 49th graph. Robustness over an unbounded space = a **coverage guarantee + a
safe-refusal boundary**, established by (prior art: QuickCheck/Hypothesis, differential
testing, coverage-guided compiler fuzzing):

- **Property-based:** generate valid graphs from the live `object_info` and assert the
  fixpoint law `ingest(emit(ingest(x))) ≡ ingest(x)`, shrinking counterexamples.
- **Differential:** every generated graph — `VibeComfy_roundtrip(x) ≡ convert_ui_to_api(x)`
  (the external-truth gate v1's self-referential parity gate never was).
- **Fuzz/mutation:** the corpus seeds structure-aware mutations (rewire, add random registered
  node, perturb widgets, wrap/unwrap subgraph, toggle bypass); coverage instrumentation on
  `ingest/` + `porting/` drives exploration; real-user graphs (opt-in) become new seeds.

## 8. The oracle is a VERSIONED dependency, not ambient truth

ComfyUI ships ~biweekly; the V3 node-schema migration is ongoing; `object_info` is
**installation-specific** (depends on the user's pack versions). So "fidelity % vs ComfyUI's
converter" is *non-reproducible across users* unless pinned — which would re-introduce the
frozen-snapshot problem one layer up. Resolution (the ecosystem already does this; the repo
already has `docs/comfy_version_support.md` + `migration_v25_to_v27.md`):

- **Pin a ComfyUI version per VibeComfy release** (`supported_comfyui_version`); the CI gate
  runs against the *vendored* pin → reproducible numbers.
- **Oracle-upgrade gate:** bumping the vendored ComfyUI re-runs the full corpus and diffs vs
  the prior pin; a fidelity drop blocks the bump until the codec adapts.
- **Version matrix** (committed JSON): fidelity per supported ComfyUI version; at startup
  VibeComfy compares the user's live version and fences to known-safe families on skew.
- **Format-migration at the ingest boundary:** one format-version-gated adapter in
  `normalize.py`, activated by the *detected* workflow format; emit targets the pinned format.
- **Saved-workflow migration:** the `vibecomfy` metadata blob carries `schema_version`; every
  codec/uid change ships a forward-migration + an "old saved graphs still round-trip" CI test
  — else our *own* version bumps orphan the identity of every previously-saved graph.

## 9. Sequencing: a vertical thin-slice + a horizontal pour, gated PER-FAMILY

Strict foundation-up ("no layer starts until the one below is globally green") is a trap: you
can't calibrate L0's "done" without a peek at L3/L5 (7/48 "failures" are a *benign* convention
diff), and L0⇄L1, L0⇄L4, L2⇄security are hard cycles that must co-develop. v2:

- **Track H (horizontal):** unify the semantic codec, anchor on live `object_info`, land the
  repro'd fixes. Gate **per-family** (`L_n may proceed on any family where L_{n-1} is green`),
  not whole-corpus.
- **Track V (vertical, in parallel, on `image/z_image` alone):** drive that one family
  L0→L5 — identity → live diff/patch/rollback → one structured agent edit → Tier-A unroll →
  docked NL panel, behind a flag. Track V is the oracle that tells Track H *which* fidelity
  actually matters and forces the L0⇄L1 / L3-security decisions to be made together, while
  they're still a one-file fix — converting "multi-month pour with zero shippable value" into
  "one trustworthy family in weeks, widening as the fence grows."

## 10. Execution hardening (the weakest layer is the process)

A correct design dies if the foundation never gets poured. Concrete mechanisms:

- **Named L0 owner + protected budget** (a fixed fraction of each sprint, not "remaining
  capacity"); L0 is the epic chain's first non-skippable link.
- **Un-bypassable, ratcheted CI gate:** the fidelity gate is a *required status check* on the
  protected branch; a PR that *lowers* any per-family number fails; threshold changes need a
  **separate approver** from the implementer ("independent oracle" applied to the process).
- **Per-family, per-defect-class trend artifact** committed each run — regression in any cell
  fails CI even if the headline rises; this is also what makes the runtime fence (§6)
  computable from live data.
- **Threshold + ticketed-exception** so an unreachable family doesn't deadlock a milestone:
  complete on threshold *within declared scope*, every exclusion carrying a ticket + reason.
- **File findings as failing-test tickets NOW** — each `[verified]` defect (Get/Set, KSampler
  shift, sg_key rename, subgraph edge-loss, atomic rollback, exec/RCE) as a megaplan ticket
  whose repro is a committed failing test. *A repro that isn't a test is a rumor.*

## 11. DECISION (LOCKED): IR-canonical Python → JSON, made non-fragile

**The decision:** VibeComfy's Python/IR is the source of truth; it translates to ComfyUI JSON.
We do **not** pivot to live-graph-canonical. This commits to the founding thesis — workflows
*are* Python, one IR, agents reason in Python — so the job is to make **Python → JSON not
fragile**.

The fragility is **not inherent** to "Python → JSON." It comes from VibeComfy being a *second,
independent implementation* of ComfyUI's serialization that drifts from the real one. Every
place VibeComfy hand-maintains knowledge ComfyUI already owns (widget orders, link formats,
node input shapes) is a place it can disagree with reality. Kill the drift via four mechanisms,
in leverage order:

1. **Preserve-don't-regenerate — run only CHANGED nodes through the codec.** *(highest leverage)*
   On ingest, capture every node verbatim keyed by `vibecomfy_uid`. On emit, **replay untouched
   nodes byte-for-byte** and send only agent-created/edited nodes through Python→JSON. A
   round-trip of an *unmodified* workflow becomes the **identity function**; most of the 3.2%
   baseline failures (untouched nodes mangled on re-emit — e.g. the KSampler shift on nodes the
   agent never touched) become *structurally impossible*. The fragility surface collapses from
   "every node of every workflow" to "just the delta the agent made."
2. **One codec, derived from the node SCHEMA, used in both directions.** The widget-shift and
   Get/Set bugs exist because ingest-read and emit-write are *separate hand-written functions*
   over a *frozen* `WIDGET_SCHEMA` table. Replace that table with a mapping **derived from live
   `object_info`** (what ComfyUI itself uses to order widgets), and have *both* directions call
   the *one* derivation. They then literally cannot disagree — this kills the entire bug class,
   not the instances.
3. **Anchor "correct" on ComfyUI's own converter; gate continuously.** The defining property of
   non-fragile: `convert_ui_to_api(emit(ir)) == compile_api(ir)` — the UI JSON we emit, fed to
   ComfyUI's *own* UI→API converter, yields exactly the API graph the IR says. Property-test it
   over *generated* graphs every commit, not a fixed corpus. Never self-grade.
4. **uid-keyed sidecar for everything non-semantic** — pos/groups/mode/color/title captured on
   ingest, restored *verbatim* on emit (not stubbed/regenerated). Anything the codec can't
   reproduce is carried opaquely, never guessed.

**Honest bound:** a *perfect bijection over all of ComfyUI* is impossible (formats are lossy /
many-to-one) — but "not fragile" doesn't require it. Preserve-untouched (1) + codec-only-on-the-
delta (2) + oracle-gating (3) gives **effective losslessness**: the untouched majority is
byte-preserved, the small delta is provably-correct-vs-ComfyUI, and the rare construct the codec
can't handle is refused/passed-through (§3 contract) — never silently corrupted. Worst case is
"I couldn't change that one node," never "I broke your graph."

**Highest-leverage first build:** mechanisms **#1 + #3 together** — capture-and-replay untouched
nodes, plus the `convert_ui_to_api`-gated property test. That alone moves the round-trip from
single-digit % to *lossless on everything the agent didn't touch* (most of every workflow), and
directly de-risks the committed Python→JSON path before any larger codec work.

## 12. Phases (revised)

- **Phase 0 — The non-fragile foundation (decision §11 is locked).** Build the two highest-
  leverage mechanisms together: **capture-and-replay untouched nodes (§11.1)** + the
  **`convert_ui_to_api`-gated property test (§11.3)**. This is the not-fragile foundation and
  the scoreboard in one.
- **Phase 1 — Pour the codec per-family.** The three repro'd emit fixes (subgraph edge-loss,
  Get/Set, KSampler), then the **schema-derived one-codec (§11.2)** + presentation sidecar
  (§11.4) + the runtime fence/refusal contract. Track V (z_image) goes vertical in parallel.
- **Phase 2–3 — L1 identity + L2 surface** on the families Track H has greened.
- **Phase 4–5 — L3 agent loop (parse-don't-exec, indep. judge) + L4 control-flow.**
- **Phase 6 — Widen the fence via the data flywheel; the UX.**
- **Ops — runs throughout:** canary, telemetry, version-matrix, migration, flywheel.

## 13. Measured baseline + honest framing

**L0 baseline (48-workflow corpus, vs ComfyUI's `convert_ui_to_api`):** 17/48 fail ingest
(Get/Set); of 31, **1 round-trips perfectly, 0 fully agree**; ~50%/68.6% of nodes; top sinks =
subgraph edge-loss (z_image 10→0) + KSampler widget-shift. Presentation fidelity is currently
~0% and was *untracked*. This is the gap — and the number is *only* meaningful as "vs the
pinned ComfyUI," per §8.

The plan is now legible: the order is forced by the stack, every layer has an *external-truth*
gate, "done" is a *set* of per-family numbers, and an Ops track watches production from day one.
The decision (§11) is locked; the risk has moved from "we don't know what's wrong" to "hold
execution discipline against un-bypassable gates."

## 14. Compatibility with the in-flight epic (6-way conflict check)

A 6-agent investigation checked each not-fragile mechanism against the scratchpad-emitter epic
+ shipped code. **No blockers — the decision sits on the epic's grain.** Two mechanisms are
already COMPATIBLE; the rest are REFACTOR-NEEDED, and for three of those **the epic's own
milestone idea files already prescribe the fix** — the conflict is shipped code lagging the
plan, not the plan.

| Mechanism | Verdict | Epic already plans it? | What must change |
|---|---|---|---|
| Readable Python ⟂ verbatim | **COMPATIBLE** | yes — 3 emit paths / 2 planes; narrate codemod retired | nothing |
| #4 furniture sidecar | **COMPATIBLE** | yes — M2 `layout_store` captures all furniture uid-keyed; M4 = new-nodes-only | wire `read_store` into emit; stop hardcoding `mode:0`/`groups:[]`/`flags:{}` (M3/M5) |
| #2 one object_info-derived codec | REFACTOR | **yes — M3 mandates `object_info_widget_order` as the authoritative model** | invert precedence (live schema beats frozen `WIDGET_SCHEMA`); collapse the Layer-1 duplicate. (ingest+emit already share one function) |
| #3 oracle-gated parity | REFACTOR | **yes — M3 makes `convert_ui_to_api` the gate of record + a property/fuzz clause** | retire `test_parity_gate_never_imports_comfy`; stop swallowing the oracle's exceptions at ingest |
| #1 keying for replay (uid) | REFACTOR | partly — M2 identity | mint uid in `add_node` + assert uniqueness; make `sg_key` name-independent (`scope.py:99`) |

**The TWO genuinely-new items (beyond the epic's current scope):**

1. **Delta-replay of node BODIES + edit-provenance.** The epic's M5 "preserve" is *furniture-only*
   (`Δpos==0 ∧ Δsize==0`); replaying untouched node **bodies** verbatim, and a per-node
   "untouched vs changed" signal (a uid-keyed structural diff vs the captured original, or a
   dirty-bit through the mutators), **do not exist** and must be added. This is the core of
   mechanism #1.
2. **The one real DIRECTIONAL conflict — slim `_ui` capture.** The epic doubles down on the
   comfy-converter ingest path (oracle-back), which stores a *slim* `_ui`
   (`{id,pos,size,properties,mode,flags,color,bgcolor}`) — dropping `widgets_values`/`inputs`/
   `outputs`/`title`, exactly the data verbatim body-replay needs. Mechanism #1 requires
   `_merge_slim_ui` (`normalize.py`) to **retain the full raw node** (uid-keyed). This is the one
   place the locked decision asks the epic to do something *different* from its current direction.
   (Also: the parity gate proves *equivalence*, not *identity* — a canonicalized byte-identity
   check on untouched nodes is needed to enforce "round-trip = identity.")

**Bottom line:** buildable on the existing epic with **no redesign**. Four mechanisms are already
on the epic's roadmap (just unshipped); the real net-new work is **delta-replay-of-bodies +
edit-provenance + un-slimming `_ui`**.
