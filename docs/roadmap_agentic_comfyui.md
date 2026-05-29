# Roadmap v2: from PoC to Agentic ComfyUI

**Status:** holistic plan, **revised after a 10-agent red-team** of the v1 roadmap.
Companion to `docs/python_on_the_graph.md` (design + verified findings) and the
scratchpad-emitter epic (the round-trip engine). v1 framed this as a lossless *bijection*;
the red-team showed that framing is the single most dangerous thing in the plan. v2 keeps
the spine (oracle-backed gates, foundation-first, "never grade your own homework") and fixes
the framing and the mechanisms.

> **If you just want the work plan, jump to [§0 — What we need to do](#0-what-we-need-to-do-the-concrete-build-plan).**
> It is a five-step, file-level porting job whose hard parts are already proven in
> `scripts/roundtrip_fidelity_spike.py`. Everything below §0 is the *why* behind it.

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

## 0. What we need to do (the concrete build plan)

**Read this section first.** §1–§13 are the *why* (the reframed goal, the robustness theory,
the red-team findings). This section is the *what*: the next, ordered, file-level work — and
it is no longer speculative. The hard part (does the architecture actually round-trip?) is
**already proven in a committed harness** (`scripts/roundtrip_fidelity_spike.py` →
`ALL PASS: True`, see §11.5). The remaining work is **wiring the proven mechanisms from the
spike into the real `ingest/` + `porting/` code, behind the same oracle gate.** That is a
porting job, not a research job.

**The one-sentence bet (LOCKED — refined 2026-05-30, see §11):** VibeComfy's Python/IR stays the
source of truth; we make Python → ComfyUI-JSON *non-fragile* by **regenerating structure from the IR
through one schema-derived codec and gating every emit against ComfyUI's own `convert_ui_to_api`,
with a runtime refusal-spine that aborts rather than ship an unintended change** — furniture
(pos/size/groups/…) is restored verbatim from a uid-keyed store. *Byte-for-byte replay of untouched
nodes is an available optimization/fallback, NOT the foundation* (see the reconciliation note in §11).

> **Why the refinement (3-model sense-check of the running epic, 2026-05-30).** The original bet
> crowned *replay* ("emit untouched nodes verbatim, codec only on the delta") as the foundation. The
> sweep showed that conflates the *safety property* (never silent corruption) with one *mechanism*.
> Replay has its own corruption class — a node that's "untouched" but whose upstream/links changed,
> replayed verbatim, carries **stale references** — and it freezes old-format node blobs that drift as
> ComfyUI evolves. The **semantic oracle gate + refusal-spine** deliver the safety property for *any*
> emit strategy, and the IR-as-source-of-truth means regenerating is internally consistent by
> construction. So the load-bearing trio is **schema-codec + oracle-gate + refusal**; replay is a
> bounded fallback for node classes the codec can't yet round-trip 100%. This matches what the running
> `scratchpad-emitter` epic already builds (m3 emitter regenerates every node; m5 preserves furniture).

**What is already true (proven in the spike, not yet in the product):**
- Preserve-replay of captured UI (per-node `_ui` + the envelope) is **lossless vs ComfyUI's
  own converter** on z_image, qwen_image_edit, wan_t2v, and a 44-node community LTX graph —
  *including recovering the subgraph bodies emit drops today.*
- Editing an existing node lands **exactly** the intended widget change, nothing else moves.
- The created-node widget bug (6-element `widgets_values`) and its fix (the injection-aware
  7-element form) are both **measured** against the oracle.
- The "never silently corrupt" detector **ALLOWs** a clean edit and **REFUSEs** a corrupting one.

So the steps below are not "figure out if this works" — they are "move this exact, verified
behavior out of the clean-room harness and into `normalize.py` / `ui_emitter.py` / `tests/`."

> **Honest caveat (from a 3-model review of this plan — Codex + Claude + DeepSeek, all
> independently).** The spike proves the *architecture*, but it proves it in a **clean room**:
> its `capture()/replay()` (`scripts/roundtrip_fidelity_spike.py:71-81`) grab the raw UI dict
> directly and never run `normalize.py → IR → ui_emitter.py`. Wiring into the real pipeline
> surfaces two things the spike sidestepped, so the steps below are a *porting job with two real
> design decisions in it*, not a pure copy-paste:
> - **The replay data is not always captured today.** On the comfy-converter ingest path (the one
>   z_image / qwen / wan_t2v take), `_merge_slim_ui` (`normalize.py:156-165`) stores a **slim
>   `_ui`** — `id/pos/size/properties/mode/flags/color/bgcolor`, **no `widgets_values`/`outputs`/
>   `title`**. §11.5's "`_ui` holds the full raw node for 100% of nodes" is true only on the
>   *fallback* path (unknown-widget graphs like the 44-node LTX). So **Step 1 must broaden capture
>   to the full raw node on the comfy-converter path** before replay (Step 2) has anything to
>   replay on the official graphs.
> - **The "touched vs untouched" signal does not exist.** See Step 0 — three of the five steps
>   silently depend on it.

### Step 0 — the Replay & Delta Contract (write this first; the other steps depend on it)

Steps 2, 3, and 5 all assume emit can answer *"did the agent change this node, and if so what?"*
**That signal does not exist in the code today** — `VibeWorkflow` setters mutate the IR in place,
there is no dirty-bit, and `emit_ui_json` has no notion of a change-set. So define it once, as
data, before building anything that consumes it:

- **`touched_uids` / intended-delta is system-computed, never agent-declared.** Derive it by
  diffing each node's current IR projection against its captured-on-ingest snapshot, keyed by
  durable `vibecomfy_uid` (an agent-declared delta can be made over-broad, which turns the
  corruption-detector in Step 5 into a no-op). A node is *touched* iff its projection differs from
  its snapshot; the *intended API delta* is the set of `(uid, field)` pairs that differ.
- **One source of truth feeds both replay (Step 2) and refusal (Step 5).** `emit_ui_json` takes a
  `touched_uids: set[str]` (or the IR carries a per-node dirty set); the corruption-detector's
  "intended delta" is the *same* computed set, not a second hand-authored one.
- **Replay has preconditions — it is not a binary touched/untouched switch.** Replay a node only
  when (a) a *full* raw `_ui` exists for it, (b) no upstream structural change alters its
  inputs/outputs, and (c) its `vibecomfy_uid` is present; otherwise regenerate through the codec
  *with the detector guarding it*. Without (b), an "untouched but structurally affected" node
  replayed verbatim becomes its own silent-corruption vector.

| # | Step | Where (file) | What it does | Done when |
|---|---|---|---|---|
| **1** | **Envelope-aware capture on ingest** *(top priority — closes the one foundation hole)* | `vibecomfy/ingest/normalize.py` | Capture, verbatim, the workflow **envelope** — `definitions` (subgraph bodies), `groups`, `extra`, `config`, `version`, link table — into workflow-level metadata. **AND** broaden per-node capture: today `_merge_slim_ui` (`normalize.py:156-165`) stores a *slim* `_ui` (no `widgets_values`) on the comfy-converter path the official graphs take, so the per-node replay data is NOT actually captured for them — capture the full raw node before `convert_ui_to_api` discards it. The `definitions` block has no capture site at all today (it lives only in the raw UI JSON, gone after the API conversion at `normalize.py:59`), so modern official graphs (z_image/flux/qwen) round-trip with a vanished subgraph body (§11.5). Name the exact hook: grab `raw['definitions']` + the full raw `nodes` in `normalize_to_api` *before* line 59. | A loaded→emitted graph contains the `definitions` block byte-identical to source; spike **T1** passes through the *real* ingest path, not the harness's clean-room `capture()`. |
| **2** | **Replay-from-`_ui` on emit** | `vibecomfy/porting/ui_emitter.py` (`emit_ui_json`) | For any node whose `vibecomfy_uid` was ingested and the agent did **not** touch, emit its captured `_ui` verbatim instead of regenerating it; replay the captured envelope verbatim. Only agent-created/edited nodes go through the regeneration codec. (Mechanism #1 — highest leverage.) | `convert_ui_to_api(original) == convert_ui_to_api(emit(ingest(original)))` for an **unmodified** graph across the corpus families (spike T1, through real code). |
| **3** | **Injection-aware widget emit for *touched* nodes** | `vibecomfy/porting/ui_emitter.py` (widget-values builder / `_compacted_widget_names`) | When emitting a node that *was* changed (so it can't be replayed), build `widgets_values` in the editor's true order **including** frontend-injected control widgets (e.g. `control_after_generate` after a seed). Derive the order from the node schema + the injection rule, matching ComfyUI's frontend. **Note (review):** this is a *fork* in the widget-values builder, not a one-liner — `_compacted_widget_names` (`ui_emitter.py:624`) deliberately *strips* the slot for replay parity, so the builder needs two modes (`compacted` for replayed nodes, `injection_aware` for touched ones). Pick the authoritative widget-order provider explicitly (schema precedence: `node_index.json` vs live `object_info`, `schema/provider.py:374-389`). This is the proven 6→7-element fix; it affects ~19% (141/742) of node classes. | Spike **T3** passes through the real emit path: a freshly created/edited KSampler is read back by the oracle with `steps`/`cfg`/etc. correct. |
| **4** | **Promote the oracle gate to a real pytest** | `tests/parity/` (new test, behind the existing `comfy` marker) | Lift the four spike assertions into a marked, opt-in test: per-family differential `convert_ui_to_api(original) == convert_ui_to_api(emit(ingest(original)))`, existing-edit-exact, created-node-correct, corruption-detector. Runs against the *vendored, pinned* ComfyUI (§8) for reproducible numbers. | The test is in the suite, green on the pinned ComfyUI, runnable in CI behind `VIBECOMFY_COMFY_SMOKE=1`. The falsification numbers stop being a script and become a gate. |
| **5** | **Corruption-detector as a runtime guard (the refusal spine)** | small new module on the emit/apply path | Before any APPLIED commit, diff the candidate's API output vs the original on **untouched** regions; abort to a typed **REFUSED** on any change outside the intended delta. The intended delta is the **system-computed** set from Step 0 — *never* agent-declared (an over-broad declaration turns the detector into a no-op). Proven in spike T4 (which hand-passed the delta; production derives it). Makes "never silently corrupt" a mechanism, not a hope. | Clean edit → ALLOW; corrupting edit (e.g. dropped control slot) → REFUSE, with a machine-readable reason (§3). |

**Sequencing:** 1 → 2 unlock the foundation (lossless on everything untouched, subgraphs
included); 3 makes the agent's *own* edits correct; 4 turns the spike into a standing gate so
the above can't regress; 5 is the safety net that holds on graphs we've never seen. Do **1+2+4
together first** — that is the "lossless on everything the agent didn't touch + a gate that
proves it" milestone (§11 "highest-leverage first build"), and it moves the measured baseline
(§13) off single digits immediately.

**Explicitly NOT now (kept out of scope on purpose):** the schema-derived *unified* codec
(§11.2 — replay sidesteps it for the common case), the property-based/fuzz coverage harness
(§7), the version-matrix + saved-graph migration (§8 — just pin one ComfyUI version), the Ops
canary/flywheel (§4), and the L3–L5 agent/control-flow/UX layers. Those come after the codec
actually works on real families.

**One known minor cleanup (not blocking, currently shimmed):** `pyproject.toml` registers
`vibecomfy.comfy_nodes` as a `comfyui.custom_nodes` *package*, but `comfy_nodes.py` is a
*module* — so ComfyUI's catalog walk trips on the missing `__path__`. The spike works around
it with a `__path__=[]` shim; the real oracle path (step 4) should not need the shim, so
either drop the entry point or make `comfy_nodes` a package. Low risk, do it when wiring step 4.

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

> **⚠ RECONCILIATION (2026-05-30 sense-check of the running epic — re-ranks the four below).** Mechanism
> #1 (replay) was originally crowned "highest leverage / the foundation." A 3-model review of the
> `scratchpad-emitter` epic demoted it: the **load-bearing safety mechanism is #3 (oracle gate) + a
> runtime refusal-spine** (§3), which deliver "never silent corruption" for *any* emit strategy. The
> primary emit strategy is **regenerate structure from the IR through the one schema-codec (#2)** —
> the IR is the source of truth, so regeneration is internally consistent and naturally correct when
> a node's upstream changed (which verbatim replay gets *wrong* — stale links). **#1 replay is retained
> only as a bounded OPTIMIZATION/FALLBACK:** emit a node verbatim *only* when the codec can't yet
> round-trip its class 100% **and** the node + its inputs are untouched. Read #1 below in that light.

1. **Preserve-don't-regenerate — replay untouched nodes verbatim.** *(DEMOTED to optional fallback —
   see reconciliation above)* When kept, it captures every node verbatim keyed by `vibecomfy_uid` on
   ingest and, on emit, replays untouched nodes byte-for-byte so codec bugs (e.g. the KSampler shift)
   can't touch them. **The catch the review surfaced:** it requires full raw capture (the shipped
   `_merge_slim_ui` stores furniture only — no `widgets_values`), and a node whose *upstream* changed
   but is itself "untouched" becomes a silent-corruption vector if replayed verbatim (§0 Step 0
   precondition b). Use it surgically for codec-incomplete classes, not as the whole-graph strategy.
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

**Highest-leverage first build (revised 2026-05-30):** mechanisms **#3 + the refusal-spine + #2** —
the `convert_ui_to_api`-gated property test as a *semantic* gate over the regenerated output, the
runtime detector that aborts to REFUSED on any unintended change, and the schema-derived codec that
makes regeneration correct. That trio delivers the safety contract (§1/§3) regardless of emit
strategy. **#1 replay is layered on afterward, only for codec-incomplete node classes** — it is an
optimization on top of a correct, gated codec, not the thing the foundation rests on.

### 11.5 Empirical status (falsification spike, run against the live setup)

Probes run against the installed package + live ComfyUI, designed to *break* the mechanisms:

**VERIFIED — mechanism #1 works, confirmed by ComfyUI's own converter.** A clean-room
envelope-aware replay prototype (capture per-node `_ui` + the envelope `definitions`/`groups`
verbatim, replay them) achieves **lossless round-trip on z_image, qwen_image_edit, wan_t2v, and
a 44-node community LTX graph** — including **recovering the subgraph bodies** that `emit_ui_json`
drops (z_image 10 nodes/18 links, qwen 20/35). Confirmed *both* by structural diff *and* the
external oracle: `convert_ui_to_api(original) == convert_ui_to_api(replay)` returned **True on
all four** (custom LTX nodes the oracle doesn't know still matched — replay preserves them
verbatim). A delta-edit touched **only the edited node**. So the foundation — lossless on
*untouched/replayed* content — is **measured, not argued**, and the subgraph hole is closed by
envelope capture. This is a clean-room prototype; the real work is wiring envelope-capture into
`normalize.py` + replay-from-`_ui` into `ui_emitter.py`. (The run also confirmed the `pyproject`
`comfy_nodes` packaging bug live; a `__path__=[]` shim worked around it — fix it for real per §12.)

**Two follow-up spikes closed the remaining L0 unknowns (oracle-verified):**
- **Editing an EXISTING node — ✅ works.** Setting KSampler `steps` 30→25 (widget located via the
  schema+injection-derived index, rest preserve-replayed) produced an oracle diff of *exactly*
  `{steps:(30,25)}` — change landed, nothing else moved. The common agent operation is proven
  end-to-end.
- **CREATING a new node through the current codec — ❌ broken (measured), fix proven.** A fresh
  KSampler emits a **6-element** `widgets_values` (`emit_ui_json`/`_compacted_widget_names` strips
  the `control_after_generate` slot); ComfyUI's own converter then reads it **shifted**
  (`steps=4.5, cfg='dpmpp_2m'`). The 19%-injection-class bug, now confirmed on the *create* path.
  **Fix verified directly on the create path:** injecting the `control_after_generate` slot at the
  schema-derived index produces the **7-element** form `[999, 'randomize', 30, 4.5, …]`, which the
  oracle reads correctly (`steps=30, cfg=4.5, …`). So the codec fix is "emit the injection-aware
  7-element form" — confirmed working, not new research.
- **The "never silently corrupt" spine — ✅ demonstrated.** An oracle-diff corruption-detector
  (diff the candidate's API vs the original on untouched regions; refuse on any change outside the
  intended delta) **ALLOWs** a clean edit (`{steps}` only) and **REFUSEs** a corrupting one (the
  control-slot-drop shift — it catches the unintended `cfg`/`sampler_name`/`scheduler` changes).
  The safety contract is mechanism, not aspiration.

**Net after spikes:** the substrate (preserve-replay + editing existing nodes) is oracle-proven;
the created-node codec is fixed-and-verified; and the refusal spine that makes the whole system
trustworthy is demonstrated. **L0's *architectural* risk is falsified** — but L0 is NOT "closed"
as a product: every result above was measured in the spike's clean room, which bypasses
`normalize.py`/`ui_emitter.py` (its `capture()`/`replay()` operate on the raw UI dict, not the IR).
*Product* L0 closes when these same results hold *through the real pipeline* — i.e. when §0's
Steps 0–4 land (notably the slim-`_ui` capture gap and the touched/untouched signal, neither of
which the spike exercised). The committed architecture holds; the engineering is the open part.

**Reproducible:** all of the above re-runs on demand via `scripts/roundtrip_fidelity_spike.py`
(`PYENV_VERSION=3.11.11 python scripts/roundtrip_fidelity_spike.py` → `ALL PASS: True`) — the
falsification harness is committed, not a chat rumor, and is the seed of the §11.3 oracle-gated
property test.

**De-risked (measured):**
- **The replay data exists on the FALLBACK ingest path.** `metadata["_ui"]` holds the *full* raw
  node (incl. `widgets_values`) for **100% of nodes** on graphs that take the unknown-widget
  fallback (`_normalize_ui_to_api`, `normalize.py:110` stores the whole node) — including the
  44-node custom-node-heavy community LTX workflow (44/44) — and it **survives emit→re-ingest**.
  **CORRECTION (3-model review):** this does *not* hold on the **comfy-converter path** that the
  official graphs (z_image / qwen / wan_t2v) take — there `_merge_slim_ui` (`normalize.py:156-165`)
  stores a *slim* `_ui` with **no `widgets_values`**. So "#1 is well-fed" is true for unknown-widget
  graphs and **false for the official ones** until Step 1 broadens capture. The spike's clean-room
  `capture()` masked this by grabbing raw nodes directly. This is the highest-value correction the
  review surfaced.
- **Top-level edges round-trip well on flat graphs** (1/1, 3/3, 11/11, 59/60). The "edges
  vanish" fear was localized, not pervasive.

**New / refined wrinkles (these update the mechanisms):**
- **[FOUNDATION HOLE] Subgraph definitions are dropped entirely.** z_image's subgraph body
  (**10 internal nodes + 18 links**) is captured *nowhere* in the IR (`wf.metadata` is empty,
  the instance node's `_ui` doesn't contain it) and is **absent from the emitted UI** (no
  `definitions` key). A round-trip yields a subgraph *instance* pointing at a vanished
  definition. Modern official workflows (z_image, flux, qwen) all use subgraphs. **→ Mechanism
  #1 must capture-and-replay at the ENVELOPE level (`definitions`, `groups`, `extra`), not just
  per-node `_ui`.** Same preserve-don't-regenerate principle, one level up: capture the
  `definitions` block verbatim, replay it on emit — subgraph workflows then round-trip as
  opaque blobs (not editable *inside* yet, but never lost). **This is the #1 priority fix.**
- **The injection-rule wrinkle is 19% wide — 141 of 742 node classes** carry a
  `control_after_generate`-flagged input (it's a *flag on the seed spec*, not an input, so it's
  frontend-injected and absent from `object_info`'s input list). So mechanism #2 must replicate
  ComfyUI's widget-injection rules or it mis-maps ~1 in 5 classes — which *reinforces #1 as the
  workhorse* (replay sidesteps injection for every ingested node; #2's wrinkle is contained to
  agent-*created* nodes of those classes).
- **Oracle (#3) bootstrap:** `convert_ui_to_api` is reached via
  `comfy_backend.ensure_nodes()` (puts `vendor/ComfyUI` on `sys.path`) → `import
  comfy.component_model.workflow_convert`. Standable, but requires the vendored submodule
  initialized (+ the `pyproject` entry-point fix from `python_on_the_graph.md` §12). Real but
  bounded setup.

**Net:** the failure surface is **localized and fixable**, not pervasive — the single-digit
baseline is dominated by (a) widget re-derivation (replay fixes), and (b) dropped subgraph
definitions (envelope-level capture fixes). The committed architecture holds; #1's scope just
grew from "per-node" to "per-node + envelope-level definitions/groups."

## 12. Phases (revised)

- **Phase 0 — The non-fragile foundation (decision §11 is locked).** Build the two highest-
  leverage mechanisms together: **capture-and-replay untouched content (§11.1) — at BOTH the
  per-node `_ui` level AND the envelope level (`definitions`/`groups`), since dropped subgraph
  definitions are the top foundation hole (§11.5)** — plus the **`convert_ui_to_api`-gated
  property test (§11.3)**. This is the not-fragile foundation and the scoreboard in one.
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

The plan is now legible: the order is forced by the stack + the fork, every layer has an
*external-truth* gate, "done" is a *set* of per-family numbers, and an Ops track watches
production from day one. The risk has moved from "we don't know what's wrong" to "make the
fork decision, then hold execution discipline against un-bypassable gates."
