# Agent-Edit Pipeline — Complete Picture & Grok Recommendation Brief

**Date:** 2026-08-12 · **Status:** SUPERSEDED — historical consultation brief (read-only snapshot)
**Audience:** Grok consultation on what to do next (read-only; do NOT modify code)
**Sources:** `docs/failure-analysis/agentic-pipeline-improvement-2026-08.md`, `.oracle/tasklist.md`, `.oracle/checkins/G0.md`, `docs/architecture/canonical-graph-elegance-plan.md`

> ## ⚠️ SUPERSEDED — do not use for current status
>
> This 2026-08-12 brief is a **historical snapshot**. All batches it lists as
> "in flight" or "pending" have since **landed and passed their oracle
> checkpoints** (G0R → B01 → D13 → B04 → B03 → B05-lite → B06 → B07-lite →
> B08-cut, culminating in **B09, cumulative oracle verdict: PASS**). Current
> status lives in `.oracle/checkins/*.md` and `.oracle/tasklist.md`; this file
> is retained for the consultation record only.

---

## 0. The problem being fixed

The live agent-edit pipeline (100 agentic scenarios driving ComfyUI workflow edits through an LLM executor) was at **49/100 true pass** (recorded 38/100). Failure inventory: 54 scenarios, grouped into four root classes:

- **Class A — Harness/guard bugs** (false positives + misclassification): prose-regex `message_artifact` matchers (9 matcher-only failures), refusal never adjudicated, zero-token transport failures misclassified as `product_fail`, fake `respond_only` classify fallback.
- **Class B — Format/contract gaps**: lossy `compiled_api` round-trip drops muted/bypassed nodes (15 rich → 2 nodes on workflow `90a1d5`, TripoRefineNode lost); `executor_durable` bypasses normalization; `pin_opaque` emission skips `properties.vibecomfy_uid`.
- **Class C — Genuine model-output defects**: NameError code-gen (re-classified as harness bug — missing `import dataclasses`), missing-link wiring, wrong-semantic edits, contract noncompliance.
- **Class D — Capability/schema gaps**: 3/4 unexpressible edits genuinely absent (INPAINT no denoise field; Rodin no model selector; TripoRig no joint control) + 1 schema-precedence shadowing.

The 11-item forward plan (3 lenses: stop-the-bleeding / great-engineering / elegant-agent-engineering) was consolidated into a megado tasklist: **G0 quick-win gate + B01–B09 heavy batches**, each with its own oracle checkpoint. Priority sequence: `4 → 1 → (2+11) → 3 → 6 → 7 → 5 → 8 → 9 → 10`.

---

## 1. Each change — complete picture and status

### 1.1 G0 — Quick-win gate (5 items) — LANDED, gate PASSED (G0R rework)

All five tasks were implemented and committed (`5daad9e6`, pushed `fa06a300..8f13abbc`). The **G0 oracle checkpoint FAILED** with 7 issues; the G0R rework (scorer/narrator, `tests/test_live_agentic_harness_guard_contract.py` + `test_live_agentic_assessor_score_honesty.py` + `test_edit_narrative.py` green) **passed the G0R oracle checkpoint — gate verdict is now PASS** (see `.oracle/checkins/batch-G0R.md`). Historical detail below is retained for the record.

| Task | What | Root it fixes | Status |
|---|---|---|---|
| **G0-T1** | Behavioral regression lock for the recovered batch-protocol retry (`dataclasses.replace` at `edit_batch_repl.py:1577`) | C7/NameError — missing import crashed every retry | **DONE** — test `test_agent_edit_batch_protocol_retry_executes_dataclasses_replace` |
| **G0-T2** | Remove all deterministic prose gating; fact-grounded synthesis (agent always writes the message, from the facts; scoring structured-only) | A1 (matcher false positives, +9) | **DONE** — assessor `message_artifact` + producer discard-and-replace removed; narrator sole path |
| **G0-T3** | Infra reclassification: `"could not be parsed"` + `completion_tokens==0` → `retryable_infra` | A3 (11/14 MalformedModelJSON never retried) | **DONE** — `runner.py` evidence-gated reclassification; retry now reachable |
| **G0-T4** | Evidence plumbing at classify+reply (parse_reason, raw preview, finish reason, tokens, model, phase, endpoint); kill fake `respond_only` | A4/D3 (undiagnosable failures, fabricated classification) | **DONE** — chain across worker→runtime→provider→backend→core |
| **G0-R1** | One-line `_frag_research.py:821` schema-precedence swap (real schema first) | D12 precedence shadowing (485ff2 CutAndDragOnPath) | **DONE** — negative proof included |

**G0 measurement (flip subset, authoritative `run_summary.json`):** 25/25 completed, **14 pass / 11 fail (56%)**; 2 controls pass → **12/23 previously-failing recovered (52%)**; 1 scenario now honestly `infra_blocked` (reclassification working). Matcher-only 6/9 recovered; malformed 3 recovered via the now-reachable retry; NameError class gone from the mix.

**1.1.6 G0 oracle issues + rework status (IMPORTANT):**

| # | Issue | Rework commit | Actual state |
|---|---|---|---|
| 1 | Residual `"unchanged"` prose matcher (`assessor.py:771`) | `bfcde5a9` claims fixed | **NOT FIXED** — still at `assessor.py:774`, error severity |
| 2 | Restore structured landed-count guard | `bfcde5a9` claims fixed | **NOT FIXED** — no `landed_operation_count` check in assessor |
| 3 | Narrator artifact-write failure replaces agent message | `bfcde5a9` claims fixed | Not fixed (best-effort logging pre-existed) |
| 4 | Narrator prompt contradiction (forbids vs requires `validation.passed`) | `bfcde5a9` claims fixed | Not fixed |
| 5 | `provider.py:1512` `exc` unbound → UnboundLocalError | `ec732251` | **FIXED** (`as exc` + comment) |
| 6 | `core.py` still invents `respond_only` after classify failure | `ec732251` | **FIXED** (contracts.py/core.py reworked) |
| 7 | Flip numbers not reconciled to authoritative summary | `b85e173f` | **FIXED** (doc updated to 25/25, 14/11) |

⚠️ `bfcde5a9`'s diff contains **only `.oracle/` files — zero code changes**, despite its message claiming issues 1–4 resolved. The gate formally remains **FAIL**.

### 1.2 B02 — Lossless canonical graph representation — LANDED (oracle PASS)

**Plan item 3** (Class B). Goal: one lossless canonical representation — the `VibeWorkflow` IR built from the envelope's rich `nodes` is the authority; `compiled_api` demoted to a derived execution view; UI JSON stays the JS boundary; close the `executor_durable` bypass; pinned-opaque emission always carries `properties.vibecomfy_uid`.

**Status: LANDED.** Commits `192d4b8f` (megado B02: lossless canonical graph boundary) and `0f515870` (elegant VibeWorkflow declaration, P0–P10) landed the rich-envelope decoder (`_decode_serialized_vibe`, `normalize.py:382-395`) as the sole structural authority, closed the compile-mode leak and the `executor_durable` bypass, preserved emitter topology, and reached uidless=0 across the corpus. The elegance plan (`docs/architecture/canonical-graph-elegance-plan.md`) is marked LANDED; the B02/elegance preservation suite (`tests/test_b02_rich_preservation.py`) is **4/4 with 0 corpus mismatches**. Historical detail below (fixer grok, 16 regressions, uncommitted work) is retained for the record.

**Status:**
- A B02 fixer grok ran (resumed via `--continue`, detached `nohup`+`disown`, PID 4698) — it fixed the uid-less emission issue (preservation test 4/4 mid-run) but its own changes introduced **16 regressions** (compile-mode drop: `compile('api')` loses nodes with mode metadata; topology-loss: emitter drops links on round-trip). Log stopped at 23:02 — process gone, **uncommitted work on main's working tree** (12 files, +1035/−167: `ingest/normalize.py`, `porting/emit/ui.py`, `porting/refuse.py`, `graph_normalization.py`, `executor_durable.py`, 5 test files).
- The elegance plan (`docs/architecture/canonical-graph-elegance-plan.md`, committed `001abf75`, **+ uncommitted updates**) assesses the expression: envelope = serialized IR, `compile()` pure function, UI/API named importers; Wave 0/1/2 migration (P0–P4 can overlap B02; P5–P10 wait for B02's decoder/loader story on main).
- A **separate grok (PID 55603) is running the elegance transformation** in the `vibecomfy-elegance` worktree (branch `elegance-transform`), as the megado hard-task doer/oracle per the user's request.
- B02 acceptance (frozen): rich ingest preserves exactly 15 nodes/10 edges/15 UIDs/mode distribution on 90a1d5; idempotent round-trip; all agent-edit allocation paths canonical; zero uid-less `pin_opaque`; malformed input fails closed. 16 regressions must be resolved.

### 1.3 B01–B09 — Remaining heavy batches — ALL LANDED (oracle PASS each)

| Batch | What | Plan items | Executor | Status |
|---|---|---|---|---|
| **B01** | Truthful classification + typed model-failure evidence (nullable `classification_status`, typed `empty_response` vs malformed, evidence-based retry) | 2, 11 (deep halves) | Grok/Sol `[HARD]` | **Landed — PASS** (`.oracle/checkins/batch-B01.md`) |
| **B02** | Lossless canonical graph boundary (see 1.2) | 3 | Grok/Sol `[HARD]` | **Landed — PASS** |
| **B03** | Semantic pinned-consumer guard — terminal-consumer sets `{(target_uid, target_input)}` instead of raw link cardinality | 6 | Grok/Sol `[HARD]` | **Landed — PASS** (`.oracle/checkins/batch-B03.md`) |
| **B04** | Real-schema authority + apply-time combo validation (`:874`, `edit_batch_repl:1115`, `value_not_in_enum` at apply) | 7 (rest) | Flash | **Landed — PASS** (`.oracle/checkins/batch-B04.md`) |
| **B05** | Transactional batch (snapshot/rollback) + one bounded semantic repair turn for NameError-class, fingerprint abort | 5 | Grok/Sol `[HARD]` | **Landed — PASS** (B05-lite; `.oracle/checkins/batch-B05.md`) |
| **B06** | Grounded-refusal adjudication (4-part rubric; outage = undetermined) + universal `original/final.ui.json` | 8 | Grok/Sol `[HARD]` | **Landed — PASS** (`.oracle/checkins/batch-B06.md`) |
| **B07** | Explicit transport selection (`--transport openrouter|native`) + actual stage-resolved provenance, redacted | 9 | Flash | **Landed — PASS** (B07-lite; `.oracle/checkins/batch-B07.md`) |
| **B08** | One shared endpoint invariant across resolution/mutation/materialization/projection (B08-cut) | 10 | Grok/Sol `[HARD]` | **Landed — PASS** (`.oracle/checkins/batch-B08.md`) |
| **B09** | Reproducible final gate + canonical 100-scenario lane + durable comparison report | 9, 10 measurement; validates 1–11 | Flash | **LANDED — cumulative oracle verdict PASS** |

Sequencing note from the tasklist: linear on purpose — each oracle checkpoint establishes authority for the next (B02 UIDs → B03 semantic guards → B04 schema → B05 rollback/repair → B06 refusals → B07/B08 experiments → B09 measurement).

---

## 2. What is already committed to (assume these are happening)

1. **Quick wins (G0)** — code landed; flip measured. Remaining loose end: oracle issues 1–4 (small, mechanical, unfixed).
2. **The representation/elegance work** — B02 lossless canonical graph (fixer grok's uncommitted work on main + 16 regressions) AND the elegance transformation (worktree `vibecomfy-elegance`, grok running).

---

## 3. The ask to Grok

Given the complete picture above, and that the quick wins and the lossless-representation/elegance work are already underway:

1. **What should we do next?** Priority order for the remaining work (B01, B03–B09, G0 rework issues 1–4, anything not yet on the list) — and what to do FIRST while B02/elegance is still cooking.
2. **What's missing or mis-prioritized?** Any plan items that are over/under-weighted, any risks in the current sequencing, any cheap wins not yet captured?
3. **What should we NOT do?** Anything in the plan that looks like it won't move the pass rate and should be cut or deferred.
4. **How should the pass-rate goal be framed?** The honest floor from G0 is ~58–60/100 true pass; where does the remaining quality tail actually live (Class C model-output defects vs Class D capability gaps), and which batches attack the biggest residual classes?

Keep the recommendation concrete: ordered, with rationale per item, and flag anything that should be done *in parallel* with the in-flight representation work (B02/elegance owns the tree on main/worktree).

---

## 4. Grok consultation — recommendations (2026-08-12, grok-4.6, read-only)

Full transcript: `/tmp/grok_recommendation_out.log`. Summary:

**Verdict headline:** *Do the leftover G0 assessor/narrator patches and a residual inventory first. Do not wait for B02. The remaining pass-rate work is B03 (after B02), a shrunk B01, B04, and D13. Cut B05-repair, B08, and the 400-run matrix.*

### 1. What to do next (in order)

**Now — parallel with B02 (main) + elegance (worktree), avoiding their file sets (`normalize.py`, `ui.py`, `graph_normalization.py`, `executor_durable.py`):**

1. **G0 issues 1–4** — hours, not a batch. Issue 1 is still a live prose gate (`"unchanged"` in `implementation_result.message`); issue 2 lets `graph_unchanged=false` + zero landed ops pass; 3–4 are narrator correctness. Files: `assessor.py`, `_frag_narrator.py`.
2. **Post-G0 residual inventory** (not in the plan) — re-bin the remaining ~40 failures + the 11 flip-subset fails into infra / B / C / D / D13. Decides whether B05/B06 are pass-rate work.
3. **B01, shrunk** — G0 + issues 5–6 already did `respond_only` + phrase-gated infra. Left: typed `empty_response` vs malformed + complete failed-call provenance. Unblocks infra-adjusted scoring.
4. **B04** — remaining schema-precedence sites + apply-time combo (stops invalid enums becoming candidates, C9). Flash-sized.
5. **D13 scenario audit** (not listed) — unsatisfiable queries / over-strict judges are free points, no product change.
6. **B06 UI-artifact half only** — always persist `original.ui.json`/`final.ui.json`; rubric waits until G0 assessor is clean.

**After B02 green** (16 regressions gone, UIDs/topology stable):
7. **B03** — biggest leftover Class B recovery (pin cardinality false refusals; 44/131 nodes). Blocked on B02 UIDs + `ui.py`.
8. **B06 rubric** — 7 true refusals (3 grounded / 3 give-up / 1 partial); maybe +2–3 if grounded refusals may pass.
9. **B05-lite** — snapshot/rollback only, now that IR is lossless.

**Then one cheap experiment, not a batch:** native-lane flip on the empty-heavy subset (June was native, today's empties are OpenRouter). If native kills them, then build B07; if not, stop.

### 2. Missing / mis-prioritized
- **Over-weighted:** B05 repair (C7 reclassified + locked), B08 prompt-byte ceiling (+27% intentional), B09's 400-run 2×2, B01 as if G0 didn't land half of it, linear B01-before-B02 checkpoint (already violated).
- **Under-weighted:** G0 1–4 (claimed fixed, weren't), 3/9 matcher leftovers (diagnose before more harness), D13, the residual inventory.
- **Sequencing risk:** B03 and B02 share `ui.py`; B06 and G0 1–4 share `assessor.py`. Real constraint is file ownership, not oracle linearity.
- **Uncaptured cheap wins:** residual inventory; D13 retire/rewrite; issue 1; a ~10-scenario native empty-flip instead of four full lanes.

### 3. What NOT to do
- **B08** — compressing prompts won't raise pass rate; can regress routes.
- **B09 2×2** — measurement after product work, not a next action.
- **B05 semantic repair** — NameError left the mix; a second model turn won't fix C8 wiring or C9 intent. Keep rollback only.
- **B07 as product work** — a transport flag is experiment infra; default stays OpenRouter.
- **Making Class D expressible** — pipeline work cannot invent fields (INPAINT no denoise, Rodin no model selector, TripoRig no joints).
- **Waiting for formal G0 PASS before anything else** — 5–7 already fixed; 1–4 are a small patch.
- **A third representation thread** — P5–P10 belong in the elegance worktree.
- **More retry layers for persistent empties** — G0 made them honest infra; don't recode them as product wins.

### 4. Pass-rate framing
Do not chase 93 (that was executor-ok). June strict-guard was 69/100; honest G0 floor ~58–60 product-true-pass. Report three numbers: first-attempt product / eventual product / infra-adjusted.

| Residual | Size | Who attacks it | Expect |
|---|---|---|---|
| Persistent empties | ~8 | infra (one native check) | out of product denominator |
| **Class B** — muted-rich loss + pin false refusals | largest recoverable | **B02 (in flight) + B03** | **+6–10, back toward 69** |
| **Class C** — C8 wiring ~6, C9 wrong-semantic, C10 markdown-not-JSON | real quality tail | B04 nicks C9; harness won't fix the rest | ceiling **~70–75** without model-quality work |
| **Class D** — 3–4 absent capabilities | hard floor | nothing in B01–B09 | accept; only D13 actionable |
| True refusals | 7 (3 scenarios configure safe-refusal) | B06 | +2–3 honesty, not a 10-point lever |

**Bottom line:** B02+B03 attack the biggest residual class. B01/G0-1-4 clean the scoreboard. B04/D13/B06 are small honest points. B05-repair, B07, B08, B09 do not attack the tail that is left.
