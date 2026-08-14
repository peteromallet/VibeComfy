# Agent-Judgment Pipeline — End-State Design

Status: **DELIVERED** — the rework described below is fully landed at
`4358aaa6` (main). F01 → V01 are merged; the legacy machinery is deleted; the
eight V01 evidence scenarios validate 8/8 under the structural harness; V02 is
this release proof. The migration table in §8 is a record of what shipped, not
an open task list. See §10 for the delivered-vs-design mapping.
Applies to: the VibeComfy headless agent pipeline (classify → research → implement →
apply/validate → reply) and the live-agentic harness that scores it.

---

## 1. The one principle

> **Deterministic code does safety, execution, and evidence. The agent does judgment.**

Everything else in this document is a consequence of that line:

- Code may **refuse** (fail-closed guards), **verify** (transactions, replay, evidence
  capture), and **execute** (apply ops, tool transport) — never **decide** what a
  workflow means, never **rewrite** the agent's work, never **preempt** a question the
  agent should answer.
- The agent owns: intent (what the user wants), approach (how to edit), research
  (what evidence it needs), and the enough-check (when to stop).

The pipeline is a chain of **agent stages with typed handoffs**. Each stage receives
(a) a **goal** (what the user wants), (b) a **priority brief** (our guidance — what
matters, which the agent weighs, not a directive), and (c) the **package** from the
previous stage. It works, and delivers the **package** for the next stage. Packages
are compact and schema'd — ledger entries and evidence IDs, never source dumps.

## 2. The phases

| Phase | Specific goal | Its tools (only these) | Package delivered |
|---|---|---|---|
| **Classify** | Understand intent; pick route; state priorities | — | Goal + priorities + route |
| **Research** (only on adapt/research routes) | Resolve the *specific open question(s)* blocking the edit | `hivemind_search`, `hivemind_get`, `registry_lookup`, `web_search` (last resort, disabled by default) | Evidence ledger: Decision / Conclusion / Evidence IDs / Uncertainty |
| **Implement** | Produce the edit delta for that goal | `node_schema`, `rank_edit_targets`, `suggest_seed_nodes`, `layout_hints`, `ready_template_load` | Edit ops + attribution (evidence pack) |
| **Apply + Validate** (deterministic) | Execute + report | — | Replayed delta / issue report |
| **Reply** | Answer the user | — | Final response + evidence pack |

Notes:

- Research is a **distinct phase with a narrow goal** — not something every phase
  does, not a blob of "one agent with all tools." Tools are partitioned by phase:
  the implement agent does **not** have `hivemind_search`.
- The research phase runs **only when classify decides the request needs evidence**
  (adapt/research routes). There is no prefetch; nothing runs ahead of the agent.
- The only interleaving is an explicit feedback edge: validate may discover a new
  question and hand back to research — a real phase transition with a new goal, not
  the agent improvising.

### The spine

```text
user request
  → classify        (goal + priorities + route)
  → [research]      (only if route needs evidence; lazy, effort-budgeted)
  → implement       (edit delta)
  → apply           (transactional; compare-and-swap, replay, authority receipts)
  → validate        (non-raising issue report; may loop back to research)
  → queue gate      (fresh probe receipt required)
  → reply           (response + evidence pack)
```

## 3. The paths

| Path (route) | What happens | Research? | Output |
|---|---|---|---|
| **revise** | Agent inspects graph (`node_schema`, optional `rank_edit_targets`), makes the parameter edit, apply → validate → queue | No | Edit delta, fast path, zero network |
| **adapt** | Structural change / new capability; agent enters research only on genuine questions; ledger feeds implement | Yes, lazy | Edit delta + evidence ledger |
| **research / explain** | Agent produces a bounded decision memo | Yes (agent-owned) | Memo: question, conclusion, 2–6 inspected citations, conflicts/uncertainty, next action |
| **inspect** | Read-only report on what the graph is/does | No | Report |
| **clarify / needs_input** | Agent emits typed `needs_input` at decision-critical gaps (never forced through phrase lists); headless may record a bounded assumption | — | Typed ambiguity package |

## 4. The tools (all agent-invoked, partitioned by phase)

| Tool | Answers | Source | Phase |
|---|---|---|---|
| `hivemind_search(query, filters, cursor, limit≤20)` | What precedents / community knowledge exist | Hivemind corpus (Discord + external_resources + curated distillations) | Research |
| `hivemind_get(evidence_id)` | What exactly a result contains | Full Hivemind record | Research |
| `registry_lookup(node_class)` | Which pack owns an unknown node | comfy.org / Manager registry | Research |
| `web_search(query)` | Last-resort external fallback (disabled by default) | Public web | Research |
| `node_schema(node_class)` | Is this node available; what inputs can be emitted | Runtime/local definitions | Implement |
| `rank_edit_targets(graph, intent)` | Candidate edit targets with scores + reasons (never "must edit") | Graph evidence | Implement |
| `suggest_seed_nodes(intent, constraints)` | Candidate starting nodes on empty graphs (visible alternatives) | Schema-aware | Implement |
| `layout_hints(graph, operation, anchors?)` | Candidate positions/groups with reasons | Geometry | Implement |
| `ready_template_list / ready_template_load` | Direct-load shipping assets (explicitly NOT research evidence) | Local ready templates | Implement |

Typed tool results: `ok | no_results | rate_limited | timeout | unavailable |
invalid_request | refused`. A rate limit is never "nothing exists"; tool outages never
masquerade as absence of evidence.

## 5. The deterministic rails (stay, by design)

- **Apply**: compare-and-swap transaction; stale state → rebaseline; authority
  receipts replay the declared delta; candidate marked `rejected` on mismatch.
- **Emit**: fail-closed — `RefusedEmit` with socket evidence; an edge is emitted,
  remapped, or refused — never silently dropped.
- **Queue gate**: requires a **fresh `live_runtime_schema_probe()` receipt**
  (runtime identity, timestamp, schema digest, readiness). No bare "research said
  it's fine" tier label satisfies it. The agent can now *produce* this evidence
  itself (previously it was blocked by evidence it couldn't obtain).
- **Validation**: typed, field-level compatibility policy. No class-wide
  suppression. Queue preparation never silently deletes inputs or coerces choices —
  normalization is a typed proposal the agent must approve.
- **Scoring (harness)**: evidence-over-narrative. Question-before-search, query
  relevance, Hivemind invoked when required, citations resolvable to returned IDs,
  no local-search research path, evidence-pack capture. Effects are scored, never
  implementation paths or prose. "Prose never gates."
- **Safety primitives**: rate-limit circuit (403/429 cooldown, `Retry-After`,
  single-flight), per-call timeouts, provenance, evidence capture — all stay inside
  the agent-invoked clients.

## 6. What gets deleted (the machinery that impersonates the agent)

- Deterministic research engine: local-corpus tier (the 38-row stub), Hivemind
  prefetch, registry/web fan-out, deterministic ranking/adaptation plans, the
  22,978-line `ResearchResult` prompt injection.
- Keyword classifiers: `_task_looks_like_parameter_tweak` / `_additive`, the
  "Stop searching, do not add or replace nodes" injection, target-node ranking
  injection, hardcoded edit recipes ("insert vibecomfy.exec frame extractor").
- Code-forced routing: `_revise_research_uncertainty_triggers` prefetch gate,
  phrase-based `clarify` overrides, silent source-preferences filtering, the
  enforced `execution_plan` (done()-refusal gate).
- Silent mutation: `sanitize_api_against_schema` queue-time rewrite, emit link
  drops, `SCHEMA_VALIDATION_SKIP_CLASSES` fail-open suppression.
- Scoring prejudice: shared-source-edit errors, `forbid_model_request_substrings`
  / `max_model_request_bytes`.

## 7. Research, end to end (the agent-owned loop)

1. Identify the unresolved decision (narrow: "which node chain produces
   audio-conditioned Wan video?" — not "research Wan").
2. Form the question; record it (scored: question-before-search).
3. Choose the cheapest authoritative source (Hivemind first).
4. `hivemind_search` with filters; inspect promising hits via `hivemind_get`.
5. Synthesize against the current graph; record Decision / Conclusion / Evidence
   IDs / Uncertainty.
6. Enough-check: "can I edit safely now?" Yes → stop. No → refine or escalate.
7. Effort budgets: 3 searches / 6 fetches / 1 registry batch / ~90s. Budget
   exhaustion is typed and preserves gathered evidence.

The ledger, not the sources, crosses into implement. The evidence pack (tool
inputs, result IDs, fetched records, ledger, final graph diff) is captured for
scoring — the grader reconstructs grounding from the pack, not the prose.

## 8. Task map (how we get there)

Task list is frozen from the planner; waves fork from the same SHA with disjoint
file ownership and merge back (see merge sequence in the plan). Serial barriers:
F01 first; A07 before behavior flips; tools + I01 before shadow mode; shadow passes
before cutover; cutover before deletion; V02 last.

| End-state element | Tasks that deliver it |
|---|---|
| Typed stage packages + evidence ledger + tool statuses | **F01** (foundation) |
| Hivemind research tools | **A01** |
| Registry / schema / ready-template lookups | **A02** |
| Live runtime schema probe | **A03** (+ **H02** wires it into the queue gate) |
| Target/seed suggestion tools | **A04** |
| Layout hints | **A05** |
| Last-resort web tool | **A06** |
| Evidence-over-narrative scoring (shared-source OK, no prose gates, research assertions) | **A07** |
| Tool surface integrated + effort budgets + ledger persistence | **I01** |
| Fail-closed queue normalization + field-level compatibility | **S01** |
| Never drop an emitted edge (RefusedEmit) | **S02** |
| Agent-owned research in shadow mode | **H01** |
| Queue gate consumes probe receipts | **H02** |
| Advisory, agent-authored, revisable plans | **H03** |
| Cutover: routing/research/headless ambiguity to agent judgment | **C01** |
| Delete keyword classifiers + hardcoded recipes | **C02** |
| Delete legacy research engine | **D01** |
| Remove `ResearchResult` + legacy contracts | **D02** |
| Remove giant prompt/payload injection | **D03** |
| Eight end-to-end evidence scenarios | **V01** |
| Release proof + contract documentation (this doc) | **V02** |

## 9. What stays (explicitly not deleted)

Transaction integrity (apply/authority/replay), fail-closed guards (emit fence,
queue readiness, validation), typed contracts, rate-limit circuits, provenance,
evidence capture, and all harness scoring. The line: **code may refuse, verify, and
record — it may not decide, rewrite, or preempt.**

## 10. Delivered — what landed vs this design

Landed at `4358aaa6` (main). Ownership and module locations are pinned in
`vibecomfy/comfy_nodes/agent/OWNERSHIP.md`; verification evidence is in the V02
release proof.

| Design element | Delivered as |
|---|---|
| Goal / priority brief / package handoffs (§1, §2) | Typed stage requests + packages in `vibecomfy/executor/stage_contracts.py`; the classify stage emits goal + priorities + route; `core.py` owns phase orchestration (`_ROUTE_BEHAVIORS`, typed `needs_input` routing). |
| Evidence ledger + evidence pack (§2, §7) | `vibecomfy/executor/evidence_pack.py` — ledger entries carry conclusions + evidence IDs only; source bodies live in `EvidenceArtifact` values resolved by `evidence_id`. |
| Research phase, agent-owned (§2, §7) | `vibecomfy/executor/agent_research_stage.py` — question-first loop with I01 effort budgets (3 searches / 6 fetches / 1 registry / ~90s), typed shadow result, never raises. |
| Research tools (§4) | `hivemind_search`/`hivemind_get` → `vibecomfy/executor/hivemind_tools.py` (rate-limit circuit, single-flight, `Retry-After`); `registry_lookup` → `lookup_tools.py`; `web_search` → `web_tools.py` (last resort, disabled by default). |
| Implement tools (§4) | `node_schema`/`ready_template_list`/`ready_template_load` → `lookup_tools.py`; `rank_edit_targets`/`suggest_seed_nodes` → `edit_suggestion_tools.py`; `layout_hints` → `layout_hints.py`. Typed statuses (`ok | no_results | rate_limited | …`) in `tool_contracts.py`. |
| Apply + validate rails (§5) | Compare-and-swap candidate transaction + authority receipts (`candidate_transaction.py`, `authority_receipts.py`); `RefusedEmit` never drops an edge (`porting/emit`); field-level compatibility policy, no class-wide suppression (`schema/validate.py`, `graph_normalization.py`); queue normalization is a typed proposal. |
| Queue gate consumes probe receipts (§5) | `vibecomfy/comfy_nodes/agent/gates.py` verifies `live_runtime_schema_probe()` receipts (`vibecomfy/runtime/schema_probe.py`); a bare tier label no longer satisfies readiness. |
| Advisory, agent-authored, revisable plans (H03) | `execution_plan.py`/`execution_plan_runtime.py` — executor-built plans are advisory diagnostics; the done()-refusal gate is gone. |
| Evidence-over-narrative scoring (§5) | `tests/live_agentic_harness/assessor.py` + `research_assessment.py` — question-before-search, query relevance, Hivemind required, citations resolvable to returned evidence IDs, no-local-search path, evidence-pack capture; shared-source edits are fine; prose never gates. |
| Deleted machinery (§6) | `vibecomfy/executor/research.py` (6,412 lines), `research_sources.py`, `execution_plan_builder.py`, the `ResearchResult` class + precedent contracts, the giant prompt-injection path — all removed in Wave C/D; keyword classifiers and hardcoded recipes deleted. Verified by the V02 banned-symbol audit (zero hits in live code). |
| Eight evidence scenarios (V01) | `tests/structural_harness/actors_agent_judgment.py` + eight scenario YAMLs/briefs; 8/8 validate under `--mode structural --actor fake`, proof level `validated` (evidence-pack citation resolver: zero dangling IDs). |

The one principle (§1) is unchanged and enforced: the agent owns intent,
approach, research, and the enough-check; deterministic code refuses, verifies,
and records.
