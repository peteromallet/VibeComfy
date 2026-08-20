I'll read the philosophy, the round-1 strategy, and every round-2 finding/result file before writing the RC list.Philosophy and the round-1 strategy are in. Next I’ll read the three batch findings and the round-2 result so the RCs are pinned to residual evidence.The batch docs name the residuals; next I’ll pin each one to the live artifacts and the current queue-gate, inspect-lens, and emit code so the RCs cite real mechanisms.I’ll pin the remaining residuals to live artifacts and the post-RC-2/3 code so the new list only includes high-confidence mechanisms.I'll gather the RC-3 notes, inspect residuals, lens code, and live artifacts for thoseI'llThe gather investigators the RC four scenarios. are on-2 writeI'll gather the Round the artifacts. I’ll inspectup, the-1 RC notes the two, shipped batch residual RC findings findings-,,1 live– live artifacts artifacts, and the current gate, and the claimed8 diffs and the predicates in RC parallel.-1/5 current queue//6 code pathsinspect surfaces so each so the new residual can be classified as list only miss names leftover vs different defect. mechanisms.Next I’ll locate the two scenario artifact trees and read the RC-2 gate code that still fires.RC-2’s unknown-class path is already in tree. Next I’ll read the schema-less queue-safe predicate and the RC commits in the vibecomfy repo.I have the exact scenario dirs. Next I’ll pull the live JSON gates and the RC-2 / schema-less predicates.The 30-v2 artifacts are on disk. I’ll pull the residual responses and the queue-stage / inspect-lens code next.Pulling lens dumps, model replies, and judge assessments from the four live artifacts.The assessments already name `schema_less_queue_blocker`. I’ll pull response/implementation artifacts and the queue-safety classifier next.The queue-gate hard-blocks any edited schema-less node before `schema_less_queue_safe` can apply. I’ll confirm that against the 485ff2 artifacts and the other residuals.Findings files aren’t at the obvious docs paths; I’ll search nearby artifacts and read the 30-v2 run summaries plus the claimed RC code.Both live rows cite `schema_less_inputs_changed`. I’ll compare original vs final node input shapes and read that signature helper.Oracle findings and round-1 strategy are located. Next I’ll read those plus the live artifacts and the RC-1/5/6 code.The 485ff2 seed edit landed and intent passed; queue still hard-blocked. I’ll pull the exact `schema_less_safety` reason and the other residual artifacts.Batch findings are in. Next I’ll pull live diagnostics and the RC-1/5/6 implementations to see whether each residual is a miss or a different defect.The inspect reply path uses `render_text`, not `render_inspect_markdown`. Checking that surface lens next.Checking R1 485ff2 outcome fields and whether `schema_less_widgets_and_connections_changed` would still fire after skipping the input-shape check.# Evidence brief — ROUND-2 residual “schema-less node queue-gate”

## Scenario dirs (30-v2 attempt_1)

- `/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/out/agentic/ir-everywhere-30-v2/attempts/video-video-inpainting-with-spline-based-cut-and-dra-485ff2/attempt_1/video-video-inpainting-with-spline-based-cut-and-dra-485ff2`
- `/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/out/agentic/ir-everywhere-30-v2/attempts/image-sd3-image-generation-with-controlnet-19d221/attempt_1/image-sd3-image-generation-with-controlnet-19d221`

## Verbatim R2 gates

| | **485ff2** | **19d221** |
|---|---|---|
| `queue_validate_ok` | `false` | `false` |
| `ui_emit_ok` | `true` | `true` |
| `outcome.kind` | `"candidate"` | `"candidate"` |
| `no_candidate_reason` | `null` | `null` |
| apply | `applyable=true`, `reason=queue_blocked_warning` | same |
| assessor | `gates: queue_validate_ok` + `hard_diagnostic` | same |
| intent_judge | **pass** | **pass** |

Hard diagnostic strings (verbatim):

- 485ff2: `Node 18 (INPAINT_InpaintWithModel) is schema-less and cannot be queued safely.`
- 19d221: `Node 60 (ACN_AdvancedControlNetApply) is schema-less and cannot be queued safely.`

Queue issue payload (same code + same safety on both):

- `code=schema_less_queue_blocker`
- `schema_less_safety=schema_less_inputs_changed`
- `diagnostic=schema-less: no schema provider evidence for node`

485ff2 also has a **warning** on untouched uid 17: `schema_less_queue_warning` / `connection_shape_unchanged` (`INPAINT_LoadInpaintModel`). That is the RC-2 bystander path working.

Contrast **03fced** (the other RC-2 target): 30-v2 `assessment.json` is **`passed: true`**. RC-2 flipped the “known-class widget Δ next to an unknown bystander” case.

## What the landed IR Δ actually was

Both are one `set_node_field` + `done()`, Gate A/B passed, `landed_operation_count=1`, persisted in `final.ui.json`.

**485ff2**

```
inpaint_inpaintwithmodel.widget_0 = 42
done()
```

`18.widget_0`: `534667941392889` → `42`. `widget_1` stays `'fixed'`. Topology not rewritten by the agent.

**19d221**

```
acn_advancedcontrolnetapply.widget_0 = 0.5
done()
```

`60.widget_0`: `0.6` → `0.5` (strength). `widget_1=0`, `widget_2=0.75` unchanged. Not a linked-slot collapse.

R1 vs R2 (why RC-2 looks like it “did something” on 485ff2 only):

- **R1 485ff2**: `outcome.kind=noop`, `no_candidate_reason=no_changes`, done-summary `Evidence: 2 unknown class type(s).`, seed **not** landed. That *is* the RC-2 unknown-class veto.
- **R2 485ff2**: that veto is gone; Δ persists; assessor now fails only the schema-less **queue** gate.
- **R1 19d221**: implement `Missing stable link to port` (RC-7), empty Δ. **Not** an unknown-class done() veto.
- **R2 19d221**: emit succeeded; same queue residual as 485ff2.

## Same mechanism or two?

**Same R2 mechanism.** Both are: widget-only Δ on the **edited schema-less node itself**, then emit’s best-effort input list ≠ original LiteGraph input list, then `_preexisting_schema_less_queue_safe` returns `schema_less_inputs_changed` **before** the RC-2 “widget values only” warning can fire.

They are **not** the same *R1* mechanism:

| | R1 | R2 residual |
|---|---|---|
| 485ff2 | unknown-class done() rollback (`has_blockers` / “2 unknown class type(s)”) | schema-less emit-projection queue gate |
| 19d221 | emit refuse (`Missing stable link to port`) | **same** schema-less emit-projection queue gate |

R1 RC-7 is **not** what still fails 19d221.

## Exact input-list Δ that trips the classifier

`_node_input_shape_signature` is an **ordered** `(name, type)` tuple of **all** inputs, including unlinked optionals (`_frag_transform_stages.py:299-308`).

**Node 18 INPAINT**

- original `_ui.inputs`: `(inpaint_model, INPAINT_MODEL)`, `(image, IMAGE)`, `(mask, MASK)`, `(optional_upscale_model, UPSCALE_MODEL)` with `link=null`
- final emit: `(image, IMAGE)`, `(inpaint_model, UNKNOWN)`, `(mask, MASK)`
- dropped unused optional; reordered; `INPAINT_MODEL` → `UNKNOWN`

**Node 60 ACN**

- original: 10 sockets (5 linked + 5 unlinked optionals: `mask_optional`, `timestep_kf`, `latent_kf_override`, `weights_override`, `model_optional`)
- final: 5 linked only, reordered (`control_net`, `image`, `negative`, `positive`, `vae_optional`)
- every originally **linked** name is still present and still linked

This matches emit’s schema-less diagnostic: “emitting best-effort slots from link appearance order” (`porting/emit/ui.py:2052-2053`). Not an agent rewire.

## Predicate that still hard-blocks (file:line)

Classifier (first veto):

```526:527:/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/vibecomfy/comfy_nodes/agent/_frag_transform_stages.py
        if _node_input_shape_signature(original_node) != _node_input_shape_signature(candidate_node):
            return (False, "schema_less_inputs_changed")
```

This runs **before** the RC-2 widget-only success branch at `:537-543` (`preexisting_schema_less_widget_values_changed`).

Hard error (second veto): `diagnostics.py:365-400`. Because `safety != preexisting_schema_less_widget_values_changed` and `node_id in edited_node_ids`, `own_surface_changed=True` → `schema_less_queue_blocker`.

**Not firing on these R2 rows:**

- `TopologyFindings.has_blockers` (`contracts.py:1422-1436`) — RC-2 already documented this as inventory-only
- `_has_new_topology_blockers` (`revision_evidence.py:473-517`) + class_type identity (`:465-470`) — this is what flipped 03fced and unblocked 485ff2’s *done()*
- apply-gate

RC-2 fixture `tests/test_rc_preexisting_unknown_classes.py:47-73` uses `inputs: []` on both sides, so it never sees live emit projection. That is why the unit test is green and 485ff2 is not.

## Did RC-2 intend this?

**485ff2: intended product flip, incomplete implementation.**  
RC-2 item 3 explicitly said: widget-only Δ on a uid already unknown in `original_ui` → warning, not `queue_validate_ok=false`. The warning branch exists (`diagnostics.py:343-364`) but is unreachable when emit drops/reorders/UNKNOWN-remints inputs. Distinct **predicate**; same **intended row**.

**19d221: distinct R1 residual (RC-7), same R2 leftover as 485ff2.** RC-2 never listed it. After emit started succeeding, it fell into the hole RC-2 item 3 named but did not pin.

## Narrow fix (what to change / what not to)

**Change** `_preexisting_schema_less_queue_safe` so raw `_node_input_shape_signature` inequality is **not** immediately fatal. Add an earlier “emit projection of a preexisting schema-less node” classification:

Treat as **`preexisting_schema_less_widget_values_changed`** (already a warning) when **all** of:

1. class_type unchanged  
2. widget **shape** unchanged (list length / mapping keys)  
3. every originally **linked** input name is still present and still linked  
4. no **new** linked input names  
5. every dropped input was originally `link is null`  
6. linked endpoint identity (source uid + output slot, by input **name**) unchanged  
7. only widget **values** differ (already true for both live Δs)

Allow: reorder, drop of unused optionals, type remint `T → UNKNOWN` on the **same name**.

Keep **hard** `schema_less_inputs_changed` / `schema_less_widgets_and_connections_changed` when a linked name appears or disappears, or a previously-linked socket becomes unlinked (real rewire).

**Must also skip the later semantic-signature trap.** `_semantic_connection_signature` (`:355-407`) includes unlinked optionals and concrete types. If you only delete the early return, both rows become `schema_less_widgets_# ROUND-2 inspect residuals — evidenceand_connections_changed` (`:544`) brief

 and## ** RC-3 actuallystill fail changed (wrong**. The linked surface-endpoint check)

**Intent has** (` to win/. **before** bothoracle/improvement-strategy- the raw input30-round1.md`-shape return 94 **–and**107 the): emit `name=value `widgets` or `_changed &&unlabeled[i]=value !`; never treatsemantic_connection_shape_ `widget_N` asunchanged` return a field; one.

Optional reply: add the sentence; ** samedo not** touch judge safety string to the existing warning ` groundedness.

**What landedif**

| File | Change |
|---|---|` in `diagnostics.py:343` (no
| `vibecom newfy fail/vibecomfy/executor/graph_inspection-open).

Replace.py: the empty-input INPAINT fixture with the live258-261 4`→ |3 `_ inputnamed projection_or_none` drops any (and an name starting ` ACN 10→5widget_` |
 case| `…/). Keep `graph_inspection.py:268-274test_preexisting_unknown_slot_name_change` | `__remains_a_widgets_from_ir`hard_block`.

** usesDo not that change for list `**

- `apply_gate.py`
raw_widgets` |
- `new_schema_| `…/graph_less_node` / `inspection.py:848-851schema_less_class_` | Markdownchanged` / output: `{ **namename}={val}` else** changes
 `unlabeled[{index- `_has_new}]={_topologyval}`_ |
blockers| `` / unknown…/executor-class identity (already correct;/prompts.py:512 03fced)
-519` | “- `TopologyFindings.has_If the lens marks a widget `unlabeled`, say so; do not name it.blockers` inventory
- emit remap / “ Do not infer codec families…guess a from slot `”auto` (.” |
| `intentRC-7);/prompts/semantic_answer _judge.prompt.md`19d221 no | **Unchanged longer needs that for** (correct) this fail
- b55994- |

**Currentstyle rewire unlabeled format (retired of a schema-less node markdown only):** ` (unlinkedlabeled name[/3]=0` — neverendpoint change `widget_3 stays=0`. Tests: an `tests/test error)

Do_graph_inspection.py: **not** make983-996 “any`.

**That widget markdown is not what inspect edit on a schema replies- seeless.** node” ` arender warning. Bound_inspect_markdown` is it to unused only referenced from-optional drop + reorder `graph_inspection.py` + tests + UNKNOWN remint with linked endpoints. Live stable.

## Flip inspect reply:

 expectation

**+2```2637:2639 certain:v**ibe on acom rerfy/vibecomfy/un,executor/core.py
                if the only remaining scored graph_inspection=_render_ fail is `graph_text(effective_queue_validate_ok`graph)
                if route_ + this hardbehavior.reply_uses__diagnostic.graph_inspection
                else Both already None,
```

`_render have_ `intentgraph_text`_judge=pass`, ` → `porting.renderoutcome.kind.render_text` **=surfacecandidate+diff`, and+ the widgettopology in**. ` Comment at `final.ui.json`. No second judgecore.py:1905-surface after the-191 gate goes0`: compact inspect views are **retired**. green.

Not Surface is `emit_agent a stretch_edit_python` → / `_emit_agent_edit not “maybe_lines`, which ** RCkeeps**-7.” IR The `widget_N` keys:

 residual``` is one500:505:vibecomfy/v booleanibecomfy/porting in/emit the schema/emit_prepare.py
-less queue classifier            # Emit the IR field that RC name as stored.  Pos-2 nameditional widget_N keys are and then missed
 because            the # fixture had the actual envelope payload, not aliases — rewriting empty `inputs`. them to a
            # compact name (or collapsing them to widget_unknown) would hide
            # inequality from π_edit.
            alias = input_aliases.get(raw_key) or to_python_identifier(raw_key)
            kwargs.append((alias, _format_value(value, elide_strings_over=None), raw_key))
```

Resolver `_align_names` (`compact_resolver.py:255`) **fills holes with `widget_{index}`**. `IPAdapterTiled` is absent from `WIDGET_SCHEMA` and `out/cache/object_info.585da68a0620a37d.json`.

**RC-3 patched a dead lens. Live lens still prints `widget_N`.**

Artifacts only store `"graph_inspection": {"used_for_reply": true}` — no persisted dump.

---

## 4eebf3 — IPAdapterTiled uid 265

**UI widgets** (`original.ui.json`): `[1.2, "ease in-out", "concat", 0, 1, 0, "V only"]`. Slots include `tiles`/`masks` (images), **not** `tile_size`/`overlap`.

**What the live lens would print** (reconstructed; dump not persisted):

```text
… = IPAdapterTiled(widget_0=1.2, widget_1='ease in-out', widget_2='concat',
                   widget_3=0, widget_4=1, widget_5=0, widget_6='V only', …)
# uid:265
```

Retired RC-3 markdown (model never got this):  
`Widgets: unlabeled[0]=1.2, unlabeled[1]='ease in-out', unlabeled[2]='concat', unlabeled[3]=0, unlabeled[4]=1, unlabeled[5]=0, unlabeled[6]='V only'`

**Classify already invented the names** (`classification.json`):

> Analyze the attached workflow to explain that the tiling grid artifact … comes from the IPAdapterTiled node (node 265), **specifically its tile_size/tile_overlap settings**

Classify sees **census only** (`core.py:334-338`) — no widgets. Plan is injected as `Executor plan:` (`prompts.py:609-610`).

**Model reply** (`response.json`):

> The tiling grid artifact … is almost certainly caused by the **IPAdapterTiled** node (node 265).
>
> - **`widget_3=0`** — This is the **tile_size** setting. A value of 0 uses a default size (typically 256×256 or 224×224…)
> - **`widget_4=1`** — This is the **tile_overlap/stride** … A value of 1 means minimal overlap (1 pixel…)
> - **`widget_1='ease in-out'`** — The easing mode…
> - **`widget_6='V only'`** — Applies the IP-Adapter only to the Value (V) attention projections…
>
> **Likely fix:** Increase `widget_4` (tile overlap) … and/or increase `widget_3` (tile size) to 512 or 640…

Judge: `grounded=False, correct=False`. Round 1 was `correct=True` (same invention class).

**Why it still mapped unlabeled[i] → invented names:** it did **not** see `unlabeled[i]`. It copied live `widget_3=0` / `widget_4=1`, then bound those to `tile_size`/`overlap` from (1) class name `*Tiled`, (2) classify plan, (3) training. Prompt rule is about `unlabeled`, a token the reply lens never emits.

---

## Stronger guard (do not soften groundedness)

**Do not rewrite `emit_prepare` widget_N.** That is the π_edit payload (`emit_prepare.py:500-503`). Display-only.

| Option | Verdict |
|---|---|
| **(a) strip unlabeled values; print only `unlabeled count=N; do not name them`** | Useful **only on an inspect-only overlay**, not emit. Hiding `1.2` / `concat` / `V only` loses real evidence; class name + classify plan still invent `tile_size`. Prefer **relabel** `widget_N` → `unlabeled[i]=value` on the **inspect reply text**, keep values. |
| **(b) post-answer name-invention detector** | **Strongest complement.** Allowed set = named surface fields + slot names + titles. If reply attributes a param (`tile_size`, `overlap`, `codec=H.264` as a widget) not in that set → fail `grounded` mechanically. Does not change the judge prompt. Scope to “claimed node field/widget,” not all jargon (ESRGAN). |
| **(c) prompt-only** | **Weak.** Already shipped (`prompts.py:512-519`). Model still named `widget_3`/`tile_size`. Classify plan bypasses it. |

**Recommended RC (not prompt-only):**
1. **Inspect-route reply must use `render_inspect_markdown` (or a display transform of surface)** so `widget_N` never appears as a field. Wire it in `core.py:2637` / `_run_reply`. Leave emit/π_edit alone.
2. **(b)** as a fail-closed groundedness check after reply.
3. **Sanitize inspect `plan_summary`** before reply: census-only classify must not inject invented field names (`tile_size`/`tile_overlap`).

---

## f855de — lens vs judge vs miss

**Round 1:** `grounded=False` — invented 8-bit VAE + `codec=auto`→H.264.  
**Round 2:** `grounded=True, correct=False`.

**Reply (key sentences):**

> **SaveVideo (4852) uses `codec='auto'` and `format_='auto'`.** In ComfyUI, `auto` typically picks H.264 at default CRF/bitrate, which is notoriously lossy for 8-bit video.
>
> **The upscaling pipeline uses latent upscalers (5001 → 5012).** `2x Upscale` and `4x Upscale` each take a latent upscale model and apply it in latent space.

**Graph facts:** SaveVideo widgets `["output","auto","auto"]`. Nodes 5001/5012 are UUID classes, titles `2x Upscale` / `4x Upscale`, input `upscale_model: LATENT_UPSCALE_MODEL`.

**Split the judge rationale:**

| Claim | What it is |
|---|---|
| `auto` → H.264 / 8-bit encoder | **Real reasoning miss.** Forbidden by RC-3 prompt; still happened. Judge filed under `correct`, not `grounded` — **leniency vs r1**, not a lens bug. |
| “Uses latent-space upscalers” | **Supported** by `LATENT_UPSCALE_MODEL` + titles. Judge says the type “expects LATENT_UPSCALE_MODEL, not pixel-space, so the claim is unsubstantiated” — **internally contradictory**. **Judge-strictness / confused causal bar**, not a lens defect. |

**RC?** Small, only if you still want the `auto` expansion killed: same inspect overlay + (b) treating inferred codec-as-setting as ungrounded. **Do not** open an RC to “fix” the latent-upscaler sentence. **Do not** weaken `correct`/`grounded`.

---

## 99e2a9 — KEEP FAILING

KSampler **70** widgets: `[537206407769123, "randomize", 12, 2.5, "dpm_2", "karras", 1]`.

Reply: *“The fixed seed means the same bad frames will appear every run.”*

Judge: `grounded=True, correct=False` — `control_after_generate='randomize'`.

R1 fail was a different wrong SVD-denoise claim; r2 is seed/randomize. Same class: **technically wrong, grounded**. Philosophy (`strategy` L17, L47, RC-3 L103): **+0, keep failing.** Reply still says `widget_3` / `widget_0` — extra proof live lens is still `widget_N`.

---

## c9df19 — judge calibration without softening groundedness

**Widgets (not invented):**
- Base **10** `KSamplerAdvanced`: `steps=25`, `start_at=0`, `end_at=20`, leftover `enable`
- Refiner **11**: `steps=25`, `start_at=20`, `end_at=10000`, leftover `disable`
- Primitive **47** titled `end_at_step` = **20**

**R1 (PASS):** “`25` total steps, switch at step `20`” → grounded=True.  
**R2 (FAIL):** “25 total steps, **handoff at step 20**” / “node 11, steps 20–25” → grounded=False, **correct=True**.

Judge treated “handoff at step 20” as a single-run hallucination and “20–25” as false because `end_at_step=10000`. That is the **standard two-sampler XL schedule** (base ends 20, refiner starts 20, `steps=25`). Same widget facts as r1.

**Calibration that does not soften groundedness:** instruct the judge that **paraphrases of widget facts already in evidence stay grounded** — `end_at_step=20` + `start_at_step=20` ≡ “switch/handoff at 20”; refiner `start=20` + `steps=25` + leftover off ≡ “last 5 of 25.” Still fail invented fields, missing nodes, unsourced providers. That **tightens consistency** (equivalent support ⇒ grounded), it does not lower the bar.

`c9df19` is route=research, not inspect; variance is judge phrasing, not RC-3.

---

## One-line disposition

| ID | Disposition |
|---|---|
| **4eebf3** | RC-3 miss: dead lens. New RC = inspect **display** overlay + (b) + classify-plan sanitization. |
| **f855de** | Mixed: `auto`→H.264 still a miss; latent-upscaler fail is judge confusion. Tiny RC at most. |
| **99e2a9** | **Keep fail.** |
| **c9df19** | Judge paraphrase calibration only; do not touch groundedness definition. |# ROUND-2 residual brief (RC vs skip)

Round-1 RCs 1/5/6 **did land in tree**. Residuals below are either **over-gated implementations**, **a new defect after the named one**, or **explicit skip**. Do not loosen apply-gate / `_guard_counter` / orphaned-wiring. Do not raise 1200s.

---

### 1. `3d-3d-model-generation-and-retargeting-f65774`
**vs RC:** RC-8 (infra bound) **landed** (now has a product packet). Failure is **RC-15 presence-flip**, **explicitly not this pass**.

**Diagnostic:** `guard_emit refused re-emit: 4 uid-matched node(s) changed outside snapshot_delta` with `presence [false,true]` on 23/26/33 and `[true,false]` on 32.

**Decision: SKIP.** Loosening `guard_emit` presence reintroduces unattributed node re-adds. No mechanical product RC.

---

### 2. `audio-audio-processing-chatterbox-b55994`
**vs RC:** Round-1 **explicit skip** (litegraph counter). Same gate still fires; orphaned-VC never reached.

**Diagnostic:** `full_ui_counter_changed_unattributed` `last_node_id` **428→427** after replacing SaveAudioMP3 (id 428). `_wire_counter` (`emit/ui.py:210-216`) is supposed to keep captured ≥ computed; candidate still emitted 427.

**Decision: SKIP as product RC** (do not relax `_guard_counter` at `emit/ui.py:3894`). Optional emit high-water-mark (`max(captured, computed)`, never decrement) is correct LiteGraph semantics but **does not promise a flip** — round-1 scoring miss was orphaned ChatterboxVC.

---

### 3. `audio-ltx-c80bbf` — **why RC-5 did not flip**
**vs RC:** RC-5 **landed but over-gated**. Not a different product defect.

**Live envelope:**
- search: `missing_classes: ["AudioLDM2"]` (named in the query)
- `clarify("AudioLDM2 is absent…")`, `exit_mode=edit_clarify`
- `outcome.kind="candidate"` (internal `edit+clarify` → public `candidate` via `contracts.py:133-136`)
- **`outcome.missing_classes` absent**
- `no_candidate_reason=no_changes`, `graph_unchanged=true`
- assessor never enters `judge_grounded_refusal` (needs `kind in {clarify, requires_custom_nodes}`)

**Why `_record_named_schema_absence_blocker` (`_frag_response_contract.py:569-597`) returned `()`:**
1. `has_candidate=True` (4 MelBand deletes landed first) → early return.
2. `_clarification_has_question_and_options` requires `?` **and** ≥2 `(a)`/`1.` markers (`:557-566`). The live clarify string has **neither**.
3. `promote_requires_custom_nodes_outcome` therefore never rewrites kind.

Secondary: litegraph-counter hard_diagnostic (keep).

**Mechanical fix (high confidence, does not loosen gates):**
- File: `_frag_response_contract.py:569-597` + `1162-1256`.
- If `_batch_named_schema_absences` is non-empty **and** product `graph_unchanged`, set public `kind=clarify` **or** `requires_custom_nodes` and copy `missing_classes`, **even when** `exit_mode=edit_clarify` and the prose lacks option markers.
- Expected flip: **c80bbf PASS** via existing allowlist `clarify` / `requires_custom_nodes` + grounded-refusal (skip intent_judge on the rolled-back 4 deletes).

Do **not** default the allowlist on every edit scenario.

---

### 4. `image-wan2-2-chroma-a7ecc5` — **why RC-6 did not flip**
**vs RC:** RC-6 **landed**. **Different defect now.**

**Evidence:** v2 artifacts have **no** `Unknown graph name 'cliptextencode_4'` / `batch_identity_rejected`. `_refresh_bindings` uid-anchor is in `_interpret.py:1232-1287` and unit-tested.

**Now:** `RefusedEmit` snapshot-delta **presence `[true,false]`** on uids **10, 24, 26, 29** (delete existing t2v chain). That is RC-15, explicitly skipped. Round-1 already budgeted a7ecc5 **+0–1**.

**Decision: SKIP.** Stable names unblocked the batch; the rewire still destroys snapshot-present nodes.

---

### 5. `multi-image-to-video-generation-with-2` — **why RC-1 did not flip**
**vs RC:** RC-1 **partially landed**. **Still dual-channel, now visible as Law-3 replay fail — not a new mismatch class.**

**What RC-1 did:**
- Python: `Float(widget_0='25')` → `Float(value=24)` (no longer both keys on one line).
- Session **candidate.ui.json** `widgets_values: [24]` vs original `["25"]`.
- Internal `delta_evidence_valid=true`, all emit/queue gates green.

**What still fails:**
- Session `authority/receipt.json`: `"error": "interpret_failed"`, `"replay_ok": false`, `"candidate_matches": false`.
- Stamped `no_candidate_reason=authority_replay_mismatch` (`authority_receipts.py:696-720`) → `apply_eligible=false`, `graph_unchanged=true`.
- Harness assessor: `no_candidate_reason=no_changes` + **judge** `delta replay mismatch: 4 leftover op(s)`.
- Applied API still `"218": {"inputs": {"widget_0": "25"}}` — live carrier is **`widget_0` only**; unit test started with **both** `inputs.value` and `widgets.widget_0`.

Alias write (`_ir_utils.py:35-76`) updates `inputs["value"]` + `widgets["widget_0"]` when schema names `value`. Authority/judge `interpret(pre, Δ)` on a **single** `set_node_field(value=24)` does not reconstruct the 4-channel post (value / widget_0 / raw / `_ui.widgets_values`). Fail-closed drops the otherwise-correct 24.

**Mechanical fix (high confidence):**
- File: `_ir_utils.py:35-76` + authority replay path (`authority_receipts.py` interpret) so **one** primitive write is what replay diffs.
- Treat live API `widget_0` as the same field as `value` even when the node only has `widget_0`.
- Fixture: live Float 25→24 must have `replay_ok=true`, `widgets_values[0]==24`, **and** `diff(interpret(pre, Δ), post)==()`.
- Expected flip: **+1 certain**.

Do not invent aliases for schema-less custom nodes.

---

### 6. `multi-image-to-video-with-llm`
**vs RC:** none. **REGRESSION-REAL / model-behavior.**

**R1 PASS:** rewired Florence2Run **176** ← LoadImage **185**.
**R2 FAIL:** cleared StringFunction **182** `widget_4`/`widget_5` to `""`. Judge: wrong parameter, intent not addressed. Edit **did apply** (`apply_eligible=true`).

**Decision: SKIP.** No mechanical lever without a task-specific rewire heuristic (bends 10/12).

---

### 7. `multi-animatediff-face-swap-506ebd`
**vs RC:** RC-8 infra. Still `killed_before_first_attempt=true` ×2, `model_attempts=[]`, 1200s.

**Diagnostic:** stderr `emit_ready.py:1574: UserWarning: output arity disagreement for ImageListToImageBatch: cached snapshot declares 0 outputs but UI declares 1. **continuing with the UI output count**`.

**That is load/import noise, not a crash.** The warn path already continues (`emit_ready.py:1572-1585`). No first-token classify.

**Decision: SKIP.** Do not raise 1200s. Chasing arity warnings will not start the model.

---

### 8. `audio-tts-narration-indextts-2`
**VARIANCE / correct refusal.** `widget_shape` overflow node **124** `QwenEmotionNode` candidate 2 vs schema 1. R1 passed by editing node **125** (matching shape).

**Decision: SKIP.** Keep the guard.

---

### 9. `image-inpainting-1d414c`
**VARIANCE / judge flip.** Feathering set to 16; prior 40. Candidate hash **0e7610 byte-identical** to R1 PASS. Judge: “increase blur” vs literal 16.

**Decision: SKIP.** Do not soften `value_semantically_matches_intent`.

---

## Direct answers

| Question | Answer |
|---|---|
| Why RC-1 missed multi-i2v-2 | **Still dual-channel.** UI 24 is emitted, then **authority replay `interpret_failed`** fail-closes apply. Judge leftover-4 is the same Law-3 hole. Not a new mismatch family. |
| Why RC-5 missed c80bbf | **kind still `candidate`.** `missing_classes` never reaches outcome. Blocker requires `has_candidate=False` + `?` + numbered options. Search already proved AudioLDM2 absent. Assessor never takes grounded-refusal. |
| Why RC-6 missed a7ecc5 | **Name-renumber is gone.** Now snapshot-delta **deletes** 10/24/26/29. RC-15 skip. |
| 506ebd emit_ready arity | **Warning, not a pre-model crash.** Hang is still 1200s never-start. |
| multi-i2v-llm | **SKIP model-behavior.** |

## Round-3 RC candidates (only these)

1. **RC-1 remainder** — primitive alias must round-trip authority/judge interpret → **multi-i2v-2 +1**.
2. **RC-5 remainder** — proven named-class absence + unchanged graph → `clarify`/`requires_custom_nodes` + `missing_classes` → **c80bbf +1**.

Everything else: **SKIP**.I have the leftover mechanisms. Writing the round-3 strategy to the same `.oracle` path as round 1.# Improvement strategy 2 — ir-everywhere-30-v2 (fixed-30 loop, round 3)

**Role:** strategy / philosophy audit for the 15 round-2 residuals.
**Measured baseline:** 15 PASS / 15 FAIL at `1328df11` (RC1–RC8 applied).
**Prior art:** RC-1…RC-8 shipped. Six flips (cc0df7, 3d-converts, d20410, kolors, 1c7ad8, 03fced). This pass is the *leftover mechanism*, not a second coat.
**Do not** soften groundedness or correctness. Do not loosen apply-gate, LiteGraph counter, orphaned-wiring, or `guard_emit` presence. Do not raise the 1200s outer kill.

---

## What the 15 rows actually are

| Class | n | Scenarios | Judge correct? |
|---|---|---|---|
| Schema-less queue-gate of a **landed** widget-only Δ | 2 | `485ff2`, `19d221` | Yes on the gate; intent **passed**; product has the new widget |
| Primitive alias hole (`inputs["widget_0"]` left stale) | 1 | `multi-image-to-video-generation-with-2` | Yes — IR Δ claimed `value`; emit/candidate did not move |
| Inspect still sees `widget_N` (RC-3 lens never reached the model) | 1 | `4eebf3` | Yes — grounded=false on invented `tile_size`/`overlap` |
| Clarify envelope still `kind=candidate` after empty Δ | 1 | `c80bbf` | Yes on empty Δ; the reply *is* a class-absence clarify |
| Inspect `correct=false` on a grounded seed/randomize miss | 1 | `99e2a9` | Yes — **keep failing** |
| Inspect new-mode: grounded=true, wrong causal claim | 1 | `f855de` | Yes on H.264-from-`auto`; latent-upscaler is disputed |
| Snapshot-delta / presence flip (nodes vanish) | 2 | `a7ecc5`, `f65774` | Yes — **keep** `guard_emit` |
| LiteGraph counter | 1 | `b55994` | Yes — **keep** |
| Model chose the wrong edit | 1 | `multi-i2v-llm` | Yes — REGRESSION-REAL, not code |
| Judge/luck variance | 3 | `indextts-2`, `c9df19`, `1d414c` | `indextts-2` guard is correct; other two are judge-strictness |
| Infra never-start | 1 | `506ebd` | n/a (principle 8) |

`19d221` is **not** still RC-7. RC-7 landed the strength 0.6→0.5 write (`final.ui.json` widgets `[0.5, 0, 0.75]`, `ui_emit_ok=true`, `outcome.kind=candidate`). The residual is the same schema-less queue-gate as `485ff2`.

`4eebf3` is **not** “the model ignored unlabeled[i]”. The inspect reply never received `graph_inspection.render_inspect_markdown`. It received `emit_agent_edit_python` (`widget_3=0`).

---

## Answers to the residual classes

### 1. Schema-less node queue-gate — one mechanism, two rows

`485ff2`: seed 534667941392889→42 on `INPAINT_InpaintWithModel` uid 18. `intent_judge` **passed**. `final.ui.json` widgets `[42, 'fixed']`. `queue_validate_ok=false`. Hard diagnostic: “Node 18 … cannot be queued safely.” `schema_less_safety=schema_less_inputs_changed`.

`19d221`: strength 0.6→0.5 on `ACN_AdvancedControlNetApply` uid 60. Same gate pattern. Same safety reason.

What actually changed in emit (not in the IR Δ):

| Node | Original `_ui` inputs | Emitted inputs |
|---|---|---|
| 18 INPAINT | 4: `inpaint_model:INPAINT_MODEL`, `image`, `mask`, **unlinked** `optional_upscale_model` | 3: `image`, `inpaint_model:UNKNOWN`, `mask` |
| 60 ACN | 10, including 5 unlinked optionals | 5 linked sockets only |

`_preexisting_schema_less_queue_safe` (`_frag_transform_stages.py:526-527`) compares `_node_input_shape_signature` = `(name, type)` over **all** sockets. Schema-less emit drops unlinked optionals and remaps unknown types → `schema_less_inputs_changed`. Then `queue_stage_diagnostics` (`diagnostics.py:365-399`) hard-blocks because the node is in `edited_node_ids`, **before** `schema_less_queue_safe` can save it. The only warn-shortcut is `safety == "preexisting_schema_less_widget_values_changed"` (`diagnostics.py:343-364`) — which never fires here.

RC-2 covered **unknown-class identity**. It did not cover this emit-churn input-signature path. Distinct residual.

### 2. Inspect hallucinated widget semantics — RC-3 missed the live lens

`core.py:2637` sets `graph_inspection=_render_graph_text(effective_graph)`. `_render_graph_text` (`core.py:310-331`) is `porting.render.render_text` → `_render_surface` → `emit_agent_edit_python`. That surface still prints `widget_N=` (`emit_prepare.py:452, 463-471`).

RC-3 changed `graph_inspection.py:851` (`unlabeled[i]=value`) and `prompts.py:517-519`. `used_for_reply=true` only means the inspect *flag* was set; the string the model saw was the Python edit surface. The model then mapped `widget_3=0` / `widget_4=1` to `tile_size` / `overlap`. Classifier `plan_summary` also planted those names — secondary.

Do **not** strip `widget_N` from the **edit** surface (schema-less authoring still needs it — `485ff2` seed is `widget_0`). Inspect must use a different lens.

### 3. f855de new-mode — no RC

Round-1: grounded=false (invented 8-bit VAE). Round-2: grounded=true, correct=false. Reply still infers H.264 from `codec='auto'` (prompt already forbids this) and asserts latent-upscalers; the judge rejects the causal claim. Softening `correct` violates 12. A louder “do not expand `auto`” sentence is prompt grandstanding (10). **+0.**

### 4. 99e2a9 seed claim — no RC

grounded=true, correct=false: “fixed seed” vs `KSampler(70).control_after_generate='randomize'`. Keep failing.

### 5. multi-i2v-llm REGRESSION-REAL — no RC

Round-1 rewired Florence2Run 176 → LoadImage 185. Round-2 cleared StringFunction 182 widgets. Model-behavior. Principle 10: no “smarter agent” rewrite.

### 6. 506ebd infra — no product RC

Both attempts `killed_before_first_attempt`, 1200.0s, `agent_exercised=false`. `stderr_tail` is a **UserWarning** from `emit_ready.py:1574-1584`: arity disagreement on `ImageListToImageBatch`, “continuing with the UI output count”. Not a crash. Do not raise 1200s. Keep in the infra ledger. **+0.**

### 7. Variance — calibrate one, accept two

| Row | Product | Verdict |
|---|---|---|
| `indextts-2` | Guard refused widget-shape overflow on node 124 (2 vs schema 1). Round-1 edited node 125 (matching shape). | **Accept.** Guard is correct. |
| `c9df19` | Answer cites `end_at_step=20` / “handoff at step 20”; judge splits hairs on timing phrasing. | **Accept.** Calibrating this would soften groundedness. |
| `1d414c` | Candidate hash `0e7610` **byte-identical** to round-1 PASS. Δ: feathering 40→16, padding→32. Query: “increase the mask blur **to 16** and reduce the padding to 32”. Judge failed because 40→16 is a numeric decrease. | **Calibrate.** The request names a terminal value. Direction words do not override `to 16`. |

---

## Prioritized RCs

Order is expected flips per unit of implementation risk.

### RC-1 — Schema-less queue-gate: emit-churn inputs are not a new topology

**Targets.** Schema-less queue-gate: `485ff2` (seed 42), `19d221` (ACN strength 0.5).

**Evidence.** Both: `ui_emit_ok=true`, `outcome.kind=candidate`, `graph_unchanged=false`, `intent_judge` passed, `queue_validate_ok=false`, `schema_less_safety=schema_less_inputs_changed`. Landed widgets persist in `final.ui.json`. The input-signature Δ is dropped unlinked optionals + type `INPAINT_MODEL`→`UNKNOWN`.

**Fix.**
1. `_preexisting_schema_less_queue_safe` (`_frag_transform_stages.py:526-544`): for a preexisting same-class node, compare **linked** `(name, destination_uid)` only. Dropping a previously-unlinked optional, or remapping a remaining type to `UNKNOWN`, is not `schema_less_inputs_changed`. If widgets changed and linked semantic connections are unchanged, return `(True, "preexisting_schema_less_widget_values_changed")`.
2. `queue_stage_diagnostics` (`diagnostics.py:341-399`): if `schema_less_queue_safe is True` **or** safety is `preexisting_schema_less_widget_values_changed`, warn-not-block **even when** the node is in `edited_node_ids`. The current “edited ⇒ own_surface_changed ⇒ hard block” runs first and makes the existing shortcut dead for the actual Δ.
3. Still hard-block: `new_schema_less_node`, `schema_less_class_changed`, `schema_less_widget_shape_changed`, linked-input name set **adds**, linked destinations removed without a transitive path (`b55994`-class rewires).
4. Fixture: the live INPAINT seed-only graph (4 original inputs, one unlinked optional) must keep `queue_validate_ok=true` and persist `widgets_values[0]=42`. The live ACN strength 0.6→0.5 graph (10→5 sockets, unlinked optionals dropped) must persist 0.5 and pass the queue gate.

**Expected flips.** **+2 certain** (`485ff2`, `19d221`).
**Risk.** Medium if we warn on *added* linked names or a real slot rename. Bound to: preexisting, same class, same widget *count*, linked destinations unchanged, input-name Δ ⊆ original unlinked sockets.
**Philosophy.** Upholds **4** (attribute the emit rematerialization, not the widget Δ), **1** (grade the landed product), **5** (the agent acted). Does not bend 4 toward new schema-less nodes or rewires. Inverse-pair follow-up (emit preserving unlinked optionals) is *not* this RC — do not expand scope.

---

### RC-2 — Primitive `value` ≡ `inputs["widget_0"]` (RC-1 hole)

**Targets.** Dual-channel leftover: `multi-image-to-video-generation-with-2`.

**Evidence.** Live node 218 is `Float` with **only** `inputs={"widget_0": "25"}` — no `value`, no `widgets`. RC-1 `_apply_primitive_widget_alias_write` (`_ir_utils.py:59-60`) **returns False** when `named_field.startswith("widget_")`. The unit test constructed `inputs={"value": 25.0}, widgets={"widget_0": "25"}`, so it passed. Live: `landed_operation_count=1`, `field_path=value` 25→24, done-summary `Changed float.value from <object object at 0x…> to 24`, `candidate_graph is None`, `graph_unchanged=true`, `no_candidate_reason=no_changes`, intent_judge “4 leftover op(s)”. `queue_validate_ok=true` — this is not a queue-gate.

**Fix.**
1. `_apply_primitive_widget_alias_write` (`_ir_utils.py:35-76`): when the compact name *is* `widget_N` (or there is no schema name), still write every retained carrier that exists: `inputs["widget_0"]`, `inputs["value"]` if present, `widgets["widget_0"]`, `raw_widgets.values[0]`, `metadata._ui.widgets_values[0]`. Writing `value` on a node that only has `inputs["widget_0"]` updates `inputs["widget_0"]`. Never leave those disagreeing.
2. Update `tests/test_rc_primitive_widget_alias.py` with the **live** shape (`inputs={"widget_0": "25"}` only). Emit must produce `widgets_values[0] == 24` and a non-null candidate.
3. Stop printing the sentinel object in done-summary (`<object object at 0x…>` is `missing_widget_value_sentinel`). Display the pre-image the Δ already named (`"25"`).

**Expected flips.** **+1 certain** (`multi-image-to-video-generation-with-2`).
**Risk.** Low if the alias set stays closed (`Float` / `Int` / `Primitive*`). Do not invent aliases for schema-less custom nodes.
**Philosophy.** Upholds **2** (one authority), **1**, **3**. Completes RC-1; does not add a third representation.

---

### RC-3 — Inspect reply must use the named/unlabeled lens

**Targets.** Inspect invention: `4eebf3`. Not `99e2a9`. Not `f855de`.

**Evidence.** `core.py:2637` passes `_render_graph_text` (Python edit surface) as `graph_inspection`. `render.py:357-361` → `emit_agent_edit_python`. The model replied with `widget_3=0` / `widget_4=1` → `tile_size` / `overlap`. RC-3's `unlabeled[i]` string does not appear in the inspect turn. `assessment`: grounded=false, correct=false.

**Fix.**
1. Inspect-only reply (`core.py:2637` + `_run_reply` at `core.py:1913-1914`): when `route_behavior.reply_uses_graph_inspection`, pass `render_inspect_markdown(inspect_graph(effective_graph))` (`graph_inspection.py:637`, `:1011`). Do **not** pass `emit_agent_edit_python`. The edit surface keeps `widget_N` for authoring.
2. Strengthen unlabeled rendering (`graph_inspection.py:844-851`): if a widget has no schema/instance name, print `unlabeled_count=N` (and optionally the raw values as an unordered opaque list **without indices**). Do not print `unlabeled[3]=0` — that is still a mapping hook. Keep `name=value` when a real name exists (`effective_widget_names_for_class` / object_info).
3. Optional one retry (principle 10, boring): if the inspect reply matches `widget_\d` **or** a field name not in the lens's named set for a cited node, resubmit once with a one-line “those names are not in the inspection lens; do not name unlabeled widgets.”
4. Do **not** change `semantic_answer_judge.prompt.md` groundedness. Do not add an IPAdapter fact card.

**Expected flips.** **+1 high** (`4eebf3` — already points at uid 265; the miss is invented names). `99e2a9` **+0**. `f855de` **+0**.
**Risk.** Low. Switching the inspect window off the edit surface can make answers more cautious, not less grounded. Softening `grounded` would violate 12 — not done.
**Philosophy.** Upholds **9** (names over indices), **1**, **2** (one inspect lens, not two unused ones), **10** (wire the lens we already wrote). Does not bend 10 via prompt grandstanding.

---

### RC-4 — Promote empty-Δ class-absence to `outcome.kind=clarify`

**Targets.** Clarify envelope leftover: `c80bbf`.

**Evidence.** Scenario allowlists `clarify` / `requires_custom_nodes`. Query names `AudioLDM2`. Live `outcome.kind=candidate`, `changes=[]`, `graph_unchanged=true`, `no_candidate_reason=no_changes`, `missing_classes` absent. Sidecar `outcome.question` / `clarification` is a real class-absence + two alternatives (“keep the native joint AV path **or** name an available audio class”). Assessor never enters `judge_grounded_refusal`. LiteGraph-counter hard_diagnostic is secondary (the 4 MelBand removals were rolled back).

RC-5's `_record_named_schema_absence_blocker` (`_frag_response_contract.py:569-576`) returns `()` if `has_candidate` **or** if `_clarification_has_question_and_options` fails. That helper (`:557-566`) requires a `?` **and** two `(a)` / `1.` markers. The live message has neither.

**Fix.**
1. Treat persisted-empty Δ (`changes=[]` / `no_candidate_reason=no_changes`) as `has_candidate=False` for this blocker, even if a rolled-back batch existed.
2. Recognise prose alternatives (`either A or B`, `keep X or name Y`) as options; do not require `(a)` / `1.` / `?`.
3. Populate `outcome.kind=clarify` (or `requires_custom_nodes` if that is the typed blocker) and `outcome.missing_classes=["AudioLDM2"]` so `_response_proves_class_absence` is true. Reuse the RC-5 envelope tests in `test_improvement_rc_fixes.py`.
4. Do **not** default the allowlist on every edit scenario. Do **not** emit clarify for a representable same-socket swap. `kolors` / face stay out.

**Expected flips.** **+1 high** (`c80bbf`).
**Risk.** Low if gated on named-class exact miss + empty persisted Δ + a real alternative. Blanket “any failed implement → clarify” would bend 5 and 6 — not done.
**Philosophy.** Upholds **7** and **8**. Completes RC-5. Would bend **5** if we allowed a refuse that had a graph-local move.

---

### RC-5 — Intent judge: explicit terminal value beats direction-word

**Targets.** Judge variance: `1d414c` only.

**Evidence.** Candidate hash `0e7610` identical to round-1 PASS. Query: “increase the mask blur **to 16** and reduce the padding to 32”. Δ: `feathering` 40→16, `left/right/top/bottom` → 32. Round-2 judge: `value_semantically_matches_intent=false` because 40→16 is a decrease. The request named the terminal number.

**Fix.** Intent-judge prompt / rubric (`intent` judge, not `semantic_answer_judge`): when the request contains an explicit terminal numeric target (`to N`, `= N`, `set … N`) and the landed `new` equals that N on the targeted field, `value_semantically_matches_intent` is true. Direction verbs (`increase`/`decrease`) do not override the named target. Do **not** touch groundedness. Do **not** apply this to `c9df19` phrasing.

**Expected flips.** **+0–1** (`1d414c` if the judge is the only fail).
**Risk.** Low if scoped to explicit numeric targets. A blanket “accept decreases when the user said increase” would be wrong — not done.
**Philosophy.** Upholds **11** (same product must not flip) and **12** (we are not softening the bar; we are reading the request). Would bend 12 if we told the semantic-answer judge to accept loose inspect language — that is why `c9df19` is out.

---

## Explicitly not this pass

| Residual | Why skipped |
|---|---|
| `99e2a9` seed/randomize | `correct=false` on a grounded answer. Softening violates 12. |
| `f855de` H.264 / latent-upscaler | New-mode reasoning miss. Prompt already forbids expanding `auto`. No mechanical flip. |
| `multi-i2v-llm` wrong edit | Model-behavior regression. Principle 10. |
| `a7ecc5`, `f65774` snapshot-delta | `guard_emit` presence `[true, false]` on uids 10/24/26/29 (and f65774 analog). Nodes would vanish. Keep. |
| `b55994` last_node_id 428→427 | Keep `_guard_counter`. |
| `indextts-2` widget-shape | Guard correctly refused overflow. Variance of *which* node the model touched. |
| `c9df19` “handoff at step 20” | Judge pedantry on a grounded widget fact. Calibrating this softens groundedness. Accept variance. |
| `506ebd` never-start | Warning continues; no crash; 1200s pre-model. Principle 8. Do not raise the wall. |
| Emit preserve unlinked optionals | Real inverse-pair (3) follow-up for RC-1. Out of scope this pass. |

---

## Philosophy audit (residuals → fixes)

| Residual | Violates | Fix upholds | Fix would bend if we… |
|---|---|---|---|
| Schema-less veto of landed widget Δ | **4, 5, 1** | 4, 5, 1 | Warned on new schema-less nodes or linked-slot rewires |
| `inputs["widget_0"]` ≠ `value` | **2, 1, 3** | 2, 1, 3 | Invented aliases for custom nodes |
| Inspect still sees `widget_N` | **9, 2** | 9, 1, 2, 10 | Softened `grounded` or stripped `widget_N` from the *edit* surface |
| Clarify kind not emitted (empty Δ) | **7, 8** | 7, 8 | Allowlisted every failed implement |
| Judge flip on byte-identical `to 16` | **11** | 11, 12 | Accepted `c9df19`-style loose inspect phrasing |
| Seed/randomize, H.264-from-auto, wrong edit | none — product holding | keep | Shipping a pass here |
| Snapshot-delta / counter / shape guard | none — product holding | keep | Loosening `guard_emit` / `_guard_counter` |
| 1200s never-start | **8** | 8 | Raised the wall |

---

## Round-3 target

| Package | PASS | What has to be true |
|---|---|---|
| 30-v2 now | **15 / 30** | 15 fail (incl. 3 variance + 1 infra + 1 model-regression) |
| Conservative | **18 / 30** | RC-1 +2, RC-2 +1. RC-3/4 miss or variance. Infra still 1. |
| **Target** | **17–18 / 30** | Conservative, allowing one of {RC-3, RC-4, RC-5} to miss. |
| Stretch | **19–20 / 30** | RC-3 `4eebf3` **and** RC-4 `c80bbf` **and/or** RC-5 `1d414c`. |
| Do not promise | 21+ | `99e2a9` + `f855de` + `multi-i2v-llm` + `a7ecc5` + `f65774` + `b55994` + `indextts-2` + `c9df19` + `506ebd` are the honest ceiling this pass. |

**Significant = the target row (17–18 PASS), +2–3 on 15.** Measured by a fresh 30-v2→v3 rerun on a clean HEAD, idle machine, `max-workers` 2–3. Count `assessment.json.passed` on the terminal attempt. Keep `1c7ad8` and the two wan inspect guards in the manifest so RC-3 cannot regress round-2 inspect flips.

Do not declare victory from unit tests.

---

## What this corpus is still missing

1. `506ebd` has no product packet and no hang profile — only a continuing arity warning + 1200s. Do not invent an emit_ready crash RC from the warning text.
2. `f855de` inspect prompt dump (the actual `render_text` surface for SaveVideo / upscale nodes) was not attached. The skip assumes the H.264 sentence is still ungrounded world knowledge; if the surface literally says “auto → H.264”, that is a lens bug and a new row.
3. `c80bbf` batch_turns `missing_classes` on the search statement were not dumped. RC-4 must still populate `missing_classes` from the named query class when the search statement omitted it.
4. `4eebf3` assembled reply user-message (the `_render_graph_text` string) is not persisted in `chat.json` (218-char query only). Confirm against a debug dump of `render_text` / `emit_agent_edit_python` for node 265 before calling the lens-switch certain. The `widget_3=` tokens in the *reply* are already sufficient to know the model numbered a positional surface.

---

## Implementation pointers

| RC | Files |
|---|---|
| RC-1 | `vibecomfy/comfy_nodes/agent/_frag_transform_stages.py:504-544` (`_preexisting_schema_less_queue_safe`); `vibecomfy/comfy_nodes/agent/diagnostics.py:341-399` (stop hard-blocking edited + queue-safe) |
| RC-2 | `vibecomfy/porting/edit/_ir_utils.py:30-76`; `tests/test_rc_primitive_widget_alias.py` (add the live `inputs={"widget_0": "25"}` fixture) |
| RC-3 | `vibecomfy/executor/core.py:2637, 1913-1914`; `vibecomfy/executor/graph_inspection.py:637-670, 844-851`; do **not** change `porting/emit/emit_prepare.py` widget_N on the edit surface; `intent/prompts/semantic_answer_judge.prompt.md` untouched |
| RC-4 | `vibecomfy/comfy_nodes/agent/_frag_response_contract.py:557-597, 1162-1164`; `assessor.py` grounded-refusal path (already correct once `kind=clarify` + `missing_classes`) |
| RC-5 | Intent-judge prompt / rubric only (the `edit_intent` judge, not semantic-answer groundedness) |
| Do not touch | `porting/edit/apply_gate.py`; `emit/ui.py` `_guard_counter`; `guard_emit` presence; `DEFAULT_PER_SCENARIO_TIMEOUT`; semantic-answer `grounded`/`correct` bars |
