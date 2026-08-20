# Maximal improvement from here

**Role:** strategy / philosophy audit after 3 rounds of the fixed-30 loop.
**Measured state:** R1 13/30 (`a779d762`) → R2 15/30 (`1328df11`) → R3 13/30 (`8d897528`). 13 RCs shipped. 7 durable flips. **13/30 rows wobble.**
**Do not** soften `grounded` / `correct`. Do not loosen `guard_emit` presence, `_guard_counter`, apply-gate, or widget-shape overflow. Do not raise 1200s. Do not propose a “smarter agent” rewrite as a primary lever.

---

## Diagnosis (read this before the ranked list)

The loop did what it is good at. Mechanical edit defects flipped and **held**: `cc0df7`, `3d-converts`, `d20410`, `03fced` (R2+), `19d221`, `1d414c`, `485ff2` (R3). Round-2 RC-1 (schema-less queue-gate) and RC-5 (terminal value beats direction-word) are the last clean edit-side wins.

R3 going 15 → 13 is **not a regression of those RCs**. R3 analysis (`.oracle/findings/30-v3-analysis.md`) says the four R2→R3 product regressions are VARIANCE. The 7 “regressed” rows in `run.md` are inspect-answer wobble, a reply-stage timeout (`71f825`, `432652`), a format flake (`d813fe`), and a model that picked a different wrong edit (`multi-i2v-2` after RC-2 actually landed).

The remaining surface is not “more queue-gate predicates.” It is:

| Bucket | n (approx) | What it is |
|---|---|---|
| Durable product-edit, already flipped | 7 | Keep as regression guards |
| Stable PASS (all 3 rounds) | 5 | Two of these are inspect (`7c8bb3`, `62682a`); three if you count `a7e2af` |
| **Inspect / semantic wobble** | **6–8** | `caae97`, `c9df19`, `1c7ad8`, `052e59`, `432652`, `71f825` (+ `kolors` format flake) |
| Philosophy-held / guard-correct FAIL | 6–8 | `99e2a9`, `b55994`, `a7ecc5`, `f65774`, `indextts-2`, `multi-i2v-llm`, often `f855de` |
| Incomplete envelope (almost a product RC) | 1 | `c80bbf` — kind now `requires_custom_nodes`, refusal judge still fails R2 |
| Infra never-start | 1 | `506ebd` × 3 rounds |

**12 of 30 scenarios are `apply: false`** (inspect / explain / diagnose). Of those 12: 3 stable PASS, 3 stable FAIL, **6 wobble**. That is a 50% inspect coin-flip. The 18 edit rows are where the 13 RCs spent their energy, and that energy is mostly spent.

R1 promised 18–20. R2 promised 17–18. We printed 15, then 13. The miss is not “we picked the wrong RCs.” It is that **a single 30-run cannot measure a 13-wobble set**, and the remaining product work is on the inspect/answer surface, where prompt-only fixes have already shipped twice (`prompts.py:512-519`, then RC-3 lens at `core.py:2635`) and `4eebf3` still invents `tile_size` / `overlap`.

Honest ceiling on this 30-set, philosophy intact: **~18–20 voted PASS**. The last 10–12 will not flip without loosening a guard or accepting invented fields. Another RC-list round that treats 13 → 18 as the target will reprint 13–15 and waste a week.

---

## 1. Highest-leverage moves

Ranked by \((\text{expected durable PASS gain} \times \text{probability}) / \text{effort}\). “Durable” means holds on a voted measurement, not a lucky single run.

### M1 — Vote the inspect rows; stop treating one 30-run as the score

**What.** Each “round” is two independent runs of the 12 `apply: false` scenarios (or 2-of-3 if a row disagrees). Edit rows stay single-run — they have been stable once the mechanical RC landed. Ledger a row PASS only on agreement. Print three numbers every time: **edit PASS / inspect voted PASS / infra**. Persist the inspect lens dump (`render_inspect_markdown` string) into the attempt dir; R2 strategy already flagged that `chat.json` only has the 218-char query.

**Why it works.** `ledger-30.md`: 13/30 wobble. `1d414c` was a **byte-identical** candidate (`0e7610`) judged both ways before RC-5. `c9df19` is “switch at 20” vs “handoff at 20” on the same `end_at_step=20` / `start_at_step=20` widgets. `1c7ad8` passed R2 (one active branch) and failed R3 (claimed 3 videos). Principle 11: you cannot improve what a single run cannot distinguish from noise. R3’s net −2 is the measurement screaming.

**Expected flips.** **+0 product.** Converts the flip table from a confounder into the audit instrument. Unlocks every move below. Without this, M2–M5 have unmeasurable EV.

**Effort / risk.** Low. Harness-only (`runner.py` / ledger). Risk is cost (12 extra inspect runs, ~1 hour on a quiet machine) and the temptation to “vote until pass.” Vote a fixed N, then stop.

**Philosophy.** Upholds **8, 11, 12**. Would bend 11 if we dropped disagreeing rows from the denominator.

---

### M2 — Mechanical inspect-claim guard + one retry (not a prompt, not a judge rewrite)

**What.** After the inspect reply, extract claimed **node-field names**, **link ids**, and **active-vs-bypass** assertions. Allowed set = named widgets + slot names + display titles + link ids actually present in the `render_inspect_markdown` evidence the model was given (`graph_inspection.py:844-866` already prints `name=value`, `unlabeled_count=N`, `slot=linked(id)`). Also apply the existing `mode_labels` table (judge prompt already has `0=enabled, 2=muted, 4=bypassed`).

- Claimed field/widget not in that set (`tile_size`, `overlap`, `codec=H.264` as a setting) → fail-closed `grounded=false` **and retry the reply once** with a one-line “those names are not in the inspection lens.”
- Claimed link id not in the lens (`99e2a9` init_image=19 vs actual 24; `4eebf3` links 48/49/50 vs 35/36/34) → same.
- Behavior attributed to a `mode=4` node as if it were active (`052e59` nodes 17/19; `1c7ad8` bypass) → same.

Implement next to the existing intent pre-grade (`intent_judge.py:560-627`, `_apply_parameter_identity_pregrade`). Do **not** change `semantic_answer_judge.prompt.md` groundedness. Do **not** strip `widget_N` from the **edit** surface (`emit_prepare.py` is π_edit).

**Why it works.** Prompt-only already failed (`prompts.py:512-519`). RC-3 **did** land the live lens (`core.py:2635-2637` now calls `render_inspect_markdown`; `_run_reply` at `:1904-1911` already skips the Python edit surface on inspect). R3 `4eebf3` still mapped node 265’s unlabeled `[1.2, ease in-out, concat, 0, 1, 0, V only]` to `tile_size` / `overlap` (`.oracle/findings/30-v3-batch-2.md`). The model does not obey the sentence. A detector + one boring retry is principle 10. A detector **without** retry only makes `4eebf3` a stable FAIL — honest, but not a PASS.

**Expected flips.** **+1–2** if the retry produces a lens-bound answer (`4eebf3` high if it already points at uid 265; `052e59` / `1c7ad8` partial). `99e2a9` **+0** (when grounded, it is still `correct=false` on seed/randomize — keep failing). `f855de` **+0** on causal H.264-from-`auto`; maybe +1 if R3’s connectivity misread of node 5012 is a link-id miss the retry can correct. Probability ~0.5 on the retry actually landing. **Do not budget this as +3 deterministic PASSes** — that is the proposal’s oversell.

**Effort / risk.** Medium (extractor + allowed-set + one retry in `_run_reply`). Risk: over-broad jargon matching (`ESRGAN` as a family name). Scope to “claimed node field / widget / link id / mode.” Risk: retry costs one inspect turn; bound it to one.

**Philosophy.** Upholds **1, 9, 10, 12**. Would bend 12 if the guard were used to *accept* paraphrases of invented fields. Would bend 10 if we added a third inspect prompt instead of the detector.

---

### M3 — Inspect-rubric honesty: stop scoring fields the graph does not have

**What.** Audit the 12 `apply: false` `answer_rubric.expected_criteria` against the live lens. Delete or rewrite any criterion that **requires the agent to name a field/behavior that is not in the evidence**.

The smoking gun is `4eebf3` (`scen30/video-animatediff-video-with-ipadapter-and-controlne-4eebf3.json:47-51`): expected criterion 2 is *“Test the tiling hypothesis against IPAdapterTiled and its tile/weight/application settings”*, and `_tags.author_rationale` says *“targeting overlap or tile size misconfiguration.”* Node 265 has no such widgets. The scenario author planted the hallucination the judge then punishes as `grounded=false`. `1c7ad8`’s **query** plants “saves three separate video outputs”; R2’s passing answer identified one active branch (mode=4 bypass). The query and the graph disagree.

This is **not** softening `grounded`/`correct`. It is stopping the corpus from demanding a bar violation. Keep fail_conditions that already say “hallucinated nodes, settings, connections.”

**Why it works.** The semantic judge is instructed to use `expected_criteria` (`intent_judge.py:1313-1314`, `semantic_answer_judge.prompt.md:10`). A criterion that names `tile_size` makes a *grounded* answer (“unlabeled_count=7; I will not name them”) look incomplete, and an *inventing* answer look on-rubric until groundedness catches it. That is a measurement defect (principle 11), and it is why RC-3 + a louder prompt cannot flip `4eebf3`.

**Expected flips.** **+0–2** (`4eebf3` only if M2’s retry is also honest; `1c7ad8` if the query/rubric stop requiring three videos). Probability ~0.6 that rubric contradiction is load-bearing on at least one row.

**Effort / risk.** Low (read 12 rubrics, diff against `original.ui.json` widgets). Risk: someone “helpfully” loosens `correct` while they are in the file. Diff-review against principle 12: only remove demands for **absent** fields, never lower the groundedness sentence.

**Philosophy.** Upholds **1, 9, 11, 12**. The current `4eebf3` rubric *bends 12* by scoring a diagnosis the evidence cannot support.

---

### M4 — Refusal-judge mechanical pre-grade for a query-named missing class

**What.** Mirror `_apply_parameter_identity_pregrade` onto `judge_grounded_refusal` (`intent_judge.py:1124-1256`). If all of:

1. the query names class C (`AudioLDM2` in `c80bbf`),
2. C is absent from schema / `compiled_api` / node inventory,
3. `outcome.kind ∈ {clarify, requires_custom_nodes}` and `outcome.missing_classes` contains C,
4. persisted graph is unchanged,

then force `no_representable_edit=true`. A *different* available audio class is not a representable satisfaction of “replace X with AudioLDM2.” Also require the envelope to name a next action (install C / pick an available class) so `specific_next_action` is a product of the envelope, not of judge mood — this is the `f65774` R3 miss (`specific_next_action=False`, `.oracle/findings/30-v3-batch-1.md`).

Do **not** default the allowlist onto every edit scenario. Do **not** force R2 true when the query is “add some audio” and a local class exists (that would bend 5).

**Why it works.** Round-1 RC-5 / round-2 RC-4 partially landed: R3 `c80bbf` is now `requires_custom_nodes` (kind changed) and still fails `grounded_refusal` on `no_representable_edit=False`. The remaining hole is the **LLM refusal judge**, not the envelope gate. Same shape as RC-5’s “`to 16` beats ‘increase’.”

**Expected flips.** **`c80bbf` +0–1** (high if R2 is the only failing criterion). `f65774` **+0–1** only if the guard-fired refusal already has a real blocker and we add a named next action; do **not** loosen `guard_emit` presence to buy this. Probability ~0.7 on `c80bbf`.

**Effort / risk.** Low. Risk: treating any missing-class search hit as R2-true when a same-socket swap exists (`d813fe` / face-style). Gate on **query-named** class.

**Philosophy.** Upholds **7, 8, 11**. Would bend **5** if we accepted a refuse that had a graph-local move matching the *named* request. Would bend **12** if we forced the whole `pass_` true without R1/R4.

---

### M5 — Split the scoreboard (edit vs inspect vs infra) and persist the lens

**What.** `run.md` / `ledger-30.md` grow three columns. Infra stays infra (`506ebd`, reply-stage `TimeoutError` on `71f825` / `432652`). Inspect lens dump written next to `response.json`. Cheap enough to ship in the same commit as M1.

**Why it works.** R3’s “13/30, net zero” buries “7 durable edit flips, inspect coin-flip ate them.” Operators will keep authorizing RC lists until the number is split.

**Expected flips.** +0. Required instrumentation for M1.

**Effort / risk.** Trivial.

**Philosophy.** Upholds **8, 11**.

---

### M6 — Inspect answers become a closed evidence pack (architecture, not a prompt)

**What.** The inspect route today: free-text essay over a markdown dump, then an LLM judges the essay (`judge_semantic_answer`, `deepseek-v4-pro`). That is two wandering models. Change the *product contract*:

1. Inspect reply must emit a structured `claims[]` (node id, class, field-or-`unlabeled`, value, link id) **plus** prose.
2. Mechanical checker grades every claim against the lens (M2, but as the authority, not a sidecar).
3. The LLM judge scores only residual causal inference (`correct`), and only over claims that survived (1). Prose that introduces a new field name is not evidence; it is a fail.

This is principle 1 applied to inspect: *the accepted Δ is the edit; the accepted claim list is the answer.*

**Why it works.** `4eebf3` / `99e2a9` / `f855de` / `052e59` are the same class: the model writes an essay, then we ask another model whether the essay is grounded. RC-3 changed the wallpaper. The door is still prose. Every inspect wobble in the ledger is this architecture.

**Expected flips.** **+3–5 inspect over two rounds** if claims are mandatory and fail-closed — `4eebf3`, `052e59`, `1c7ad8`, maybe `caae97` (hivemind:3166) and the connectivity half of `f855de`. Causal-only misses (`f855de` H.264-from-`auto`, `99e2a9` seed/randomize when grounded) stay FAIL. Probability ~0.6 that this is the real inspect ceiling-raiser; 0.3 that the model then refuses to answer (vacuous `claims=[]`) and we have to fail those as empty.

**Effort / risk.** High (executor reply schema, assessor, 12-scenario fixtures, one retry on empty claims). Do **not** do this in the same week as M2–M4. M2 is the 20% version; M6 is the 80% version. Shipping both at once double-spends.

**Philosophy.** Upholds **1, 2, 9, 12**. Would bend **2** if we kept the markdown essay as a second authority “beside” `claims[]`. The essay becomes commentary; claims are the product.

---

### M7 — Profile `506ebd` (then one infra RC, or officially isolate it)

**What.** Three rounds, `killed_before_first_attempt=true`, `model_attempts=[]`, 1200s, stderr `emit_ready.py:1574` arity warning that **already continues**. Round-2 was right: the warning is not a crash. Round-3 proves we still do not know the hang. Profile the worker (import time, first-token classify, graph size) **before** writing code. If it is a huge-graph import wedging the worker, the RC is “fail named-infra at T≪1200 when classify has not started,” not “raise the wall.” If it is load, isolate the row from the 30 and stop spending 40 minutes per round on a corpse.

**Why it works.** Principle 8: infra ≠ product. A 1200s silent stall is the most expensive zero-information row in the set.

**Expected flips.** **+0 PASS.** +1 measured (product-fail or named-infra). Probability 0.8 we can at least stop the silent stall.

**Effort / risk.** Medium for a real profile; low if we just isolate. Risk: shipping an arity “fix” from the warning text (round-2 already rejected this).

**Philosophy.** Upholds **8, 10, 11**. Raising 1200s would bend 10.

---

### M8 — Semantic-judge paraphrase consistency (narrow, after M1)

**What.** Teach `semantic_answer_judge.prompt.md` that a paraphrase of **widget facts already in the payload** stays `grounded` (`end_at_step=20` + `start_at_step=20` ≡ “switch/handoff at 20”). Still fail invented fields, missing nodes, unsourced providers. This is the `c9df19` class. RC-5 already did the edit-side analog for `1d414c`.

**Why it works.** Same widgets, opposite verdict, two rounds (`30-v2-batch-a.md`). But **M1 (voting) already contains this variance**. Calibrating the judge is worth it only after voting shows `c9df19`-class still flipping the *voted* bit.

**Expected flips.** **+0–1** voted (`c9df19`). Probability ~0.5, and much of it is redundant with M1.

**Effort / risk.** Low. Risk: this is the easiest place to accidentally soften `grounded`. Require a fixture: invented `tile_size` still fails; “handoff at 20” with `end_at_step=20` in the UI payload passes.

**Philosophy.** Upholds **11**. Would bend **12** if the sentence is “accept loose inspect language.” That is why this is M8, not M2.

---

### M9 — Model choice is a *secondary* inspect lever, not a strategy

**What.** Honest option, ranked last among things that could work: route **inspect-only** through a more constrained structured-output call (JSON `claims[]`), not a bigger chat model writing a better essay. Do not swap the whole agent to a frontier model. Do not swap the judge to a frontier model until M1 exists — you cannot tell if the new judge is better.

**Why it (might) work.** Inspect wobble is LLM variance. A smaller model forced onto `claims[]` (M6) beats a larger model on prose. Cost of “use GPT-5 for inspect” is high; residual variance remains; principle 10 says this is the wrong first move.

**Expected flips.** **+0–2** if paired with M6; **+0** if it is just a model swap on the current essay path (R3 already shows the same model passing and failing the same scenario).

**Effort / risk.** High cost, low structural gain without M6.

**Philosophy.** Principle 10 forbids this as the primary lever. Listed so nobody “discovers” it next week as if it were new.

---

## 2. Moves that are not worth it

Be blunt. These have been proposed, half-shipped, or are the obvious next itch. Do not do them.

| Move | Why not |
|---|---|
| **Another 5–8 incremental edit RCs** (primitive alias remainder, emit preserve unlinked optionals, more queue-gate predicates) | Edit-side mechanical EV is spent. `multi-i2v-2` R3 is **target-selection** after RC-2 landed (`30-v3-analysis.md`). More alias tables will not flip it. R1+R2 already over-promised 18–20 and the misses were inspect variance. |
| **“Smarter agent” / deeper research / two-step pipeline** | Principle 10. Explicitly out. ~60h venue, zero evidence it beats M2/M6. |
| **Prompt-only inspect pass #3** | `prompts.py:512-519` shipped. RC-3 lens shipped and is on the live path (`core.py:2635`). `4eebf3` still invented. The sentence is not the lever. |
| **Loosen `guard_emit` presence (`a7ecc5`, `f65774`)** | Nodes vanish (`presence [true,false]`). Principle 4/6. Round-1 and round-2 both skipped RC-15 for this reason. R3 `f65774` changing from RefusedEmit to grounded-refusal is **not** permission to let the delete through. |
| **Loosen `_guard_counter` (`b55994`, R3 `a7ecc5`)** | `last_node_id` 428→427 is a real LiteGraph defect. High-water-mark emit is correct semantics and **still does not promise a flip** (round-1 scoring miss was orphaned ChatterboxVC). Keep the guard. |
| **Loosen widget-shape (`indextts-2`)** | Guard correctly refused overflow 2 vs schema 1 on node 124. R1 passed by touching node 125. Variance of *which node*, not a bad guard. |
| **Task-specific rewire heuristic for `multi-i2v-llm`** | R1 rewired Florence2Run 176→185 (PASS). R2 cleared StringFunction 182 (FAIL). R3 `dunder_name_not_allowed`, nothing landed. Model-behavior. A Florence-specific rule bends 10/12 and will not generalize. |
| **Raise 1200s / chase `emit_ready` arity as a crash** | Warning continues (`emit_ready.py:1572-1585`). Three rounds of never-start is a profile problem (M7), not a timeout problem. |
| **Soften `grounded` / `correct` to buy `99e2a9` / `f855de`** | `99e2a9` has been `correct=false` on a grounded answer (seed vs `randomize`) and, separately, link-id hallucination. `f855de` H.264-from-`auto` is a reasoning miss the prompt already forbids. Shipping a pass here is principle 12. |
| **Expand to the 100-set or a new 30** | Adding scenarios before voting multiplies noise. The 30-set is fine; the *meter* is broken. |
| **Judge-model upgrade without voting** | Replaces one uncalibrated LLM with another. You will not know if the new judge is better. |
| **Full-30 double-run every round** | The 18 edit rows do not need it. Vote the 12 inspect rows. Spending 2× on `b55994` teaches nothing. |
| **Finish “RC-3 didn’t wire the lens” as if it were still true** | It is wired (`core.py:2635`). Flash’s “RC-3 did NOT reach this model turn” (`30-v3-batch-2.md`) is about the *model still inventing*, not a dead function. Do not re-implement the lens. |

---

## 3. Measurement-level vs product-level

Keep these budgets separate. Mixing them is how R3 looked like a product regression.

### Measurement (do first; they do not raise honest PASS)

| Change | Where | What it buys |
|---|---|---|
| 2-run vote on 12 inspect rows | harness / ledger | Separates signal from the 13-wobble set |
| Split scoreboard: edit / inspect-voted / infra | `run.md`, `ledger-30.md` | Stops “13/30 net zero” from hiding 7 durable flips |
| Persist `render_inspect_markdown` dump | attempt dir | Makes the next Flash batch able to cite the lens, not reconstruct it |
| Named-infra if classify never starts | runner, ≪1200s | Turns `506ebd` into a typed row instead of a 40-minute hole |
| Judge 2-call agree on *disputed inspect only* | `judge_semantic_answer` | Optional, after M1; cheaper than a third full run |
| Mechanical `grounded=false` **without** retry | assessor | Converts `4eebf3` into a **stable FAIL**. Honest. Not a PASS. Ship this as a guard even if the retry (product) is delayed |

### Product (can raise voted PASS)

| Change | Target rows | Notes |
|---|---|---|
| Claim-guard + one inspect retry (M2) | `4eebf3`, `052e59`, `1c7ad8`, maybe `f855de` connectivity | Highest remaining product EV per hour |
| Rubric honesty (M3) | `4eebf3`, `1c7ad8` | Corpus, not agent |
| Refusal R2 pre-grade (M4) | `c80bbf` | Envelope already advanced |
| Named next-action on guard-fired refuse | `f65774` | Do not loosen the guard |
| Structured `claims[]` (M6) | the inspect 12 | Next architecture step, not this week |
| `506ebd` real hang fix (M7, if profile shows one) | 1 infra | Product-fail or named-infra, either is a win |

The existing intent pre-grade (`_apply_parameter_identity_pregrade`) is the pattern to copy. Do not invent a second judge.

---

## 4. Recommended 1-round plan

Minimal set. One implementation week. Then **one voted measurement**, not one lucky 30-run.

### Ship

1. **M5 + M1** — split scoreboard, persist lens dump, 2-run vote on the 12 `apply: false` rows. Edit rows single-run. Ledger rule: inspect PASS requires agreement.
2. **M2** — mechanical claim/link/mode=4 guard + **one** inspect retry. Fixture: `4eebf3` node-265 widgets must not accept `tile_size`/`overlap`; a retry that says `unlabeled_count=7` is allowed to proceed to the judge.
3. **M3** — rewrite `4eebf3` expected criterion 2 so it does not demand tile/overlap fields the node does not have. Check `1c7ad8` query/rubric against bypass. Touch no groundedness sentence.
4. **M4** — refusal R2 pre-grade for query-named missing class. Fixture: `c80bbf` + absent `AudioLDM2` + `kind=requires_custom_nodes` + `missing_classes` ⇒ `no_representable_edit` cannot be judged false. Negative fixture: unnamed “add audio” with a local class still fails R2 if the agent refuses.
5. **M7 profile only** — hang-profile `506ebd`. Ship a named-infra timeout-if-never-classified **only if** the profile shows classify never starts. Do not ship an arity patch from the warning.

### Do not ship this round

M6 (structured claims), M8 (judge paraphrase) unless M1+M2 still leave `c9df19` as a voted flip, M9 (model swap), any guard loosening, any `multi-i2v-*` heuristic.

### Target

| Number | Value | How counted |
|---|---|---|
| Single-run PASS (will still print) | **13–16 / 30** | Ignore this as the victory number |
| **Voted PASS (the target)** | **16–17 / 30** | Edit terminal-attempt + inspect 2-agree |
| Inspect wobble (of 12) | **≤ 3** | Down from 6 |
| Durable edit flips | **7/7 hold** | `cc0df7`, `3d-converts`, `d20410`, `03fced`, `19d221`, `1d414c`, `485ff2` |
| Philosophy-held still FAIL | `99e2a9`, `b55994`, `a7ecc5`, `indextts-2` (when it hits the overflow), `multi-i2v-llm` | If any of these PASS, investigate contamination |

**Significant = the voted row (16–17) and wobble ≤ 3**, not “18 on one run.” If voted lands at 14–15 with wobble ≤ 3, the round **still succeeded** as measurement: we finally know the product is stuck and M6 is the next venue. If voted lands at 13 with wobble still 6, M2/M3 did not work — do not “try more RCs”; inspect the claim-guard fixtures.

Conservative math: M4 `c80bbf` +0.7, M2 retry +1.0 expected, M3 enabling that retry +0.3, variance no longer stealing 3–5. That is 13 + ~2 durable, plus 2–3 inspect rows that used to fail-by-coin now agreeing PASS. Ceiling for *this* week is 17 voted. Stretch 18 if `052e59` and `1c7ad8` both retry-clean.

---

## 5. Three-round trajectory, and when to stop

Assume the user wants to keep going after the 1-round plan.

### Round A (this plan) — make the meter honest, take the last cheap product

M1, M2, M3, M4, M7-profile. Target **16–17 voted**. Cost: ~1 week implementation + 2 inspect passes.

**Stop after A if:** voted PASS is ≤ 15 **and** the remaining fails are the philosophy-held set plus model-behavior (`99e2a9`, `b55994`, `a7ecc5`, `f65774`, `indextts-2`, `multi-i2v-llm`, `f855de` causal, `506ebd`). That means the inspect retry did not convert. Further RC lists will reprint the same 13–15.

**Continue if:** inspect wobble dropped and 1–3 inspect rows are now voted-PASS but still essay-fragile (pass wording varies, claims would have been cleaner). That is the M6 signal.

### Round B — inspect architecture (M6)

Mandatory `claims[]`, mechanical authority, judge only residual `correct`. Optionally M8 if `c9df19` is still a voted flip. Do **not** combine with a model swap.

Target **18–19 voted**. This is the last move with a realistic +3. If Round B ships and voted is still 16, the inspect tasks in this corpus are harder than a structured pack can save (causal diagnosis on unlabeled widgets: `4eebf3`, `99e2a9`) — **stop**. Those are principle-12 holds, not missing RCs.

### Round C — only leftover holes Round B created

Examples that would justify a third round: claim schema too tight (vacuous `claims=[]` on otherwise-good answers), or `506ebd` profile produced a real hang bug we deferred. No new strategy. No new 30-set. Target **19–20 voted**, then **stop for good**.

### When to stop (hard)

Stop the improvement loop when **any** of these is true:

1. Voted PASS is unchanged (±1) across two consecutive rounds.
2. Every remaining FAIL is in the philosophy-held set: self-loop / orphan / counter / presence-flip / widget-shape / grounded-but-wrong / model-chose-wrong-edit / infra-isolated.
3. Someone proposes softening `grounded` or `correct` to “get over 20.”
4. Someone proposes a smarter agent rewrite as the next RC.

The honest ceiling on this 30-set is **~20/30 voted**. The last 10 are not a pipeline-improvement problem. They are either correct fails or a different product (inspect as structured Q&A over a closed pack — that is Round B, once, not an infinite RC loop).

### What “winning” looks like

Not 25/30. Not “the agent is smarter.” Winning is:

- Edit rows that *can* land a named widget Δ, land it, and stay landed (already mostly true).
- Inspect rows that invent a field name **cannot pass**, and inspect rows that only restate lens facts **do not flip** run-to-run.
- Infra rows have names, not 1200s silences.
- The ledger’s “pending” is preferred to a fake “resolved.”

That is principles 1, 8, 11, and 12. The last three rounds proved the RC loop can deliver the first bullet. The next unit of work is the other three — measurement first, then one inspect-surface change, then stop.
