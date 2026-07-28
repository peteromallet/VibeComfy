# Proposal: Fixing VibeComfy additive restore

The campaign did not expose a missing-capability problem. It exposed a broken evidence path. Three cases were invalid fixtures; of the six runnable failures, four either lost the exact precedent or reached the oracle with values that the exact precedent already contained. The highest-leverage response is therefore an additive-specific evidence contract, not a larger model and not a looser oracle.

## 1. Per-failure verdict

| Case | Feature | Verdict | Primary root | One-line evidence | Single highest-leverage fix |
|---|---|---|---|---|---|
| 01 | `refinement_pass` / `ManualSigmas` | `rejected` | **REFERENCE** | Research found the exact two-stage template, but flattened `key_values` conveyed only the first-stage 9-value schedule; the fixer correctly wired that wrong value into the second sampler. | Pass a role-aware slice containing **every** target-type instance, its local peers, and widgets; do not reduce duplicate nodes to one key/value. |
| 02 | `controlnet` | `skipped_no_feature_node` | **PAIRING** | The golden contains LTX ICLoRA guidance, not a ControlNet application/loader; the matcher correctly found nothing (`run_campaign.py:61`). | Re-pair with `video/wanvideo_wrapper_22_5b_i2v_controlnet`. |
| 03 | `audio_merge` | `baseline_rejected` | **INFRA** | Baseline failed on three IAMCCS “unknown class” errors before the agent ran; the campaign never enabled the resolver, so `baseline.py:93-94` never added `--resolve-on-demand`. | Enable on-demand schemas for campaign baseline, fixer, and candidate check; add a regression proving IAMCCS resolves through the public-source ladder. |
| 04 | `face_detailer` | `skipped_no_feature_node` | **PAIRING** | The Flux.2 Klein golden has no face/detailer node at any level (`run_campaign.py:65`). | Promote/source a real FaceDetailer golden, then generate the removal fault from it. |
| 05 | `lora_loader` / `WanVideoLoraSelect` | `fixer_failed` | **SEARCH** | Attempts 1–2 missed the workflow’s own `prior_path` and asked for a LoRA filename that is literal in that template; attempt 3 finally found it, then timed out. | Search the workflow’s exact provenance before similarity/hivemind results. |
| 06 | `upscale` / `ResizeImageMaskNode` | `fixer_failed` | **FIXER** | A surviving identical sibling was already in the broken graph, yet attempts produced a timeout and two `Missing stable link from port` validation failures. | Add a deterministic “clone sibling and splice into bypass edge” edit primitive. |
| 07 | `lora_loader` | `skipped_no_feature_node` | **PAIRING** | `image/flux2_klein_4b_t2i` contains no LoRA node; the conservative matcher is correct (`run_campaign.py:70`). | Re-pair with `image/qwen_image_2512` or a deliberately materialized Flux+LoRA golden. |
| 08 | `refinement_pass` / `WanVideoSampler` | `fixer_failed` (attempt 1: `rejected`) | **VALUE** | Attempt 1 restored the exact node topology but used steps/cfg/seed/scheduler `20/6/42/unipc` instead of `4/1/1057359483639287/dpm++_sde`; attempts 2–3 were timeout/parse failures. | Copy functional values from the exact source workflow, not a loosely related Ovi-audio sampler. |
| 09 | `upscale` / `ImageScaleToTotalPixels` | `fixer_failed` (attempts 1–2: `rejected`) | **VALUE** | The node and branch were correct, but `lanczos` replaced golden `nearest-exact`; all classifications used `research:false` although the exact ready template contains the answer. | Force additive evidence lookup and require provenance for non-default widget choices. |

Classification rule used here: **REFERENCE** means the correct precedent was retrieved and then degraded (case 01); **SEARCH** means the correct precedent did not reach the fixer before it failed (case 05); **VALUE** means a structurally valid candidate reached the oracle with functionally wrong parameters (cases 08–09). That keeps causes distinct without hiding the immediate semantic defect.

## 2. Where the process breaks

Counts across all nine failures:

| Root class | Count | Cases |
|---|---:|---|
| SEARCH | 1 | 05 |
| REFERENCE | 1 | 01 |
| FIXER | 1 | 06 |
| VALUE | 2 | 08, 09 |
| INFRA | 1 | 03 |
| PAIRING | 3 | 02, 04, 07 |

The largest literal bucket is **PAIRING (3/9)**: 30% of the canonical campaign never tested the agent. The dominant product failure is one coherent **precedent-to-values cluster (4/9: SEARCH + REFERENCE + VALUE)**. Its two forms are:

1. `revise` hard-disables research. `ClassifyDecision` canonicalizes `revise` to `research=False` (`executor/contracts.py:437-449`), and runtime behavior explicitly says “without research” (`executor/core.py:240-253`). Cases 06 and 09 were routed this way on every attempt.
2. `adapt` research is not provenance-directed or role-preserving. VibeComfy writes `source_template` and `prior_path` breadcrumbs (`porting/emit/ui.py:384-390`), but `executor/research.py` does not consume either. Cases 01, 05, and 08 therefore received incomplete, late, or alien evidence.

Schema resolution is a separate infrastructure defect. `AuthoringSchemaProvider` appends the on-demand provider only under `VIBECOMFY_ON_DEMAND_SCHEMAS=1` (`schema/provider.py:591-610`); the campaign did not set it. This fully explains case 03’s pre-agent rejection under the stated premise that public nodes are resolvable.

The stored L7 artifacts do **not** attribute any of these nine historical outcomes to `New candidate authority requires explicit v2_delta evidence`: case 05 is clarify/timeout, case 06 timeout/validation, case 08 value/timeout/parse, and case 09 value/no-change. That exception is a real uncommitted-tree **rerun confound**: any fresh attempt carrying it must be marked INFRA and rerun after the unrelated authority/evidence work, not counted as an agent capability failure. It does not justify reclassifying the persisted failures.

## 3. Concrete fixes for the dominant modes

### A. Additive restore evidence contract — generalizable product improvement

Before implementation, unconditionally build one compact `RestoreEvidence` packet:

- exact provenance source first (`prior_path`, then `source_template`);
- all instances of the named class, not the first match;
- for each instance: widgets by schema field name, incoming/outgoing peer class + socket, and a short role label inferred from its neighborhood;
- the on-demand-resolved schema, invoked automatically on cache miss;
- an explicit confidence/source field; no guessed functional value may outrank exact provenance.

Then pass that packet verbatim to the fixer. Additive requests should bypass the classifier’s research veto: either force `adapt`, or make this preflight independent of route. This is medium effort (roughly 1–3 days including tests), not capability research. It is a sure fix for case 01, high-confidence for 09, and high-confidence evidence correction for 05 and 08; timeouts still make those latter two less than guaranteed. Expected impact: **+3 passes likely, +4 plausible**.

### B. Campaign pairing preflight — test-fixture fix

Resolve the target feature node before scheduling a case and fail campaign construction if it is absent. Replace cases 02, 04, and 07 with goldens that actually contain the feature. This is small and a sure thing, but it creates **three runnable tests**, not three passes. No model/capability work is involved.

### C. Resolver activation — infrastructure/test-fixture fix

Make on-demand schema resolution the campaign default and propagate it to baseline, fixer authoring, and candidate `port check`; log which ladder rung/source resolved each missing class. Add an IAMCCS integration test and, if class-to-source discovery is the missing hop, fix that routing rather than declaring the class unsupported. Small-to-medium effort; **certain to remove case 03’s unknown-class baseline failure**, but the subsequent repair result is unproven.

### D. Deterministic sibling splice — generalizable product improvement

For a named additive node with an in-graph sibling, offer a graph operation that clones its typed widgets and inserts it into the detected bypass edge while minting stable link identities. This directly addresses case 06’s failure after the LLM already formed the correct plan. Medium effort; **high confidence for +1 pass**.

No capability research is justified by this dataset. The examples, values, schemas, and required graph patterns already exist.

## 4. The biggest lever

Change one thing: **make additive restoration start with the mandatory, provenance-first `RestoreEvidence` packet and forbid implementation without it.**

Merely forcing `research:true` is insufficient: cases 01 and 08 already researched and still received bad evidence. Merely forcing the on-demand resolver is also insufficient: schemas describe valid fields and defaults, not the workflow-specific sigma schedule, sampler settings, LoRA filename, or interpolation choice. The packet joins exact precedent, role, values, wiring, and resolved schema at the boundary the fixer actually consumes. It directly targets cases 01, 05, 08, and 09 and gives case 06 a cleaner deterministic path.

The oracle is not the lever. Its exact widget check (`demo_factory/predicates.py:91-104`) correctly rejected all current candidates: even ignoring case 08’s seed, steps/cfg/scheduler remain wrong. Relaxing it turns **zero** current failures into legitimate passes. It should eventually normalize field names and tolerate extra trailing schema-default slots, but that is future false-negative prevention, not a campaign rescue.

## 5. Ordered path to “way more”

1. **Preflight and re-pair the campaign** — cases 02/04/07 become testable. Impact: +3 runnable, not passes. Confidence: certain.
2. **Ship `RestoreEvidence` and force it for additive requests** — rerun 01/05/08/09. Impact: +3 likely, +4 plausible. Confidence: high for 01/09; medium-high for 05/08 because executor reliability remains.
3. **Enable and verify on-demand schemas end-to-end** — rerun 03. Impact: +1 runnable; likely repair opportunity. Confidence: certain on removing the baseline blocker, unknown on final oracle.
4. **Add deterministic sibling splice/stable-link support** — rerun 06. Impact: +1 likely pass. Confidence: high.
5. **Harden retries separately** — isolate v2-delta authority failures, increase/stream implementation timeout, and retry malformed batch output without discarding good research. Impact: protects 05/08 and future cases; incremental pass impact depends on step 2.
6. **Normalize oracle widgets by schema field** — ignore only non-semantic serialization differences, never wrong functional values. Impact on these nine: 0; confidence: high as preventive hardening.

For the six currently runnable failures, this roadmap should move from zero passes to **four or five additional passes with high confidence**, with the sixth becoming a real test instead of an unknown-class baseline failure. The three invalid slots then need to earn their own results after re-pairing.
