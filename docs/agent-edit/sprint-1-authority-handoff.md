# Sprint 1: Authority Preservation and Canonical Candidate — Handoff

**Date**: 2026-07-14
**Sprint**: Sprint 1 — Authority Preservation and Canonical Candidate
**Status**: Complete (17 of 18 tasks; T18 deferred to Sprint 2)

---

## 1. Executive Summary

Sprint 1 closed six categories of authority leaks and established a fail-closed
server-side authority receipt before full browser preparation.  All existing
routes (`/vibecomfy/agent-edit`, `/vibecomfy/agent-executor`, `/agent/edit`) now
share a single canonical executor pipeline (`_handle_agent_executor_submit`) with
identical authority semantics.

The sprint shipped these new contracts:

| Contract | Schema Version | File |
|---|---|---|
| Delta Envelope | `2.0.0` | `vibecomfy/porting/edit/schemas/v2/delta_envelope.schema.json` |
| Authority Receipt | `authority_receipt_v1` | `vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json` |
| Obligation Ledger | `obligation_ledger_v1` | `vibecomfy/porting/edit/schemas/v2/obligation_ledger.schema.json` |
| Completion Proof | `completion_proof_v1` | `vibecomfy/comfy_nodes/agent/completion_proofs.py` |
| Execution Plan | `execution_plan_v1` | `vibecomfy/comfy_nodes/agent/execution_plan.py` |
| Turn Context | `agent_edit_turn_v2` | `vibecomfy/comfy_nodes/agent/contracts.py` |

---

## 2. Eligibility Ownership

Eligibility is owned exclusively by the server-side gate pipeline and is
never synthesized by compatibility serialization.

### 2.1 Owner module

`vibecomfy/comfy_nodes/agent/gates.py` — canonical gate evaluation.

### 2.2 Gate names (9 gates)

```python
DEFAULT_GATE_NAMES = (
    "python_load_ok",
    "lower_ok",
    "ir_validate_ok",
    "ui_emit_ok",
    "ui_fidelity_ok",
    "ui_load_safe_ok",
    "plan_validate_ok",      # Sprint 1: fail-closed absent-plan default
    "queue_validate_ok",     # Sprint 1: weak evidence blocks queue
    "state_match_ok",
)
```

### 2.3 ApplyEligibility reasons

```python
APPLY_ELIGIBILITY_REASONS = (
    "applyable",
    "no_candidate",
    "not_latest",
    "superseded",
    "server_blocked",
    "stale_canvas",
    "queue_blocked_warning",
)
```

### 2.4 Plan obligation states

```python
PLAN_STATE_NOT_REQUIRED         = "not_required"
PLAN_STATE_REQUIRED_SUPPORTED   = "required_supported"
PLAN_STATE_REQUIRED_UNSUPPORTED = "required_unsupported"
```

Only `not_required` may pass `plan_validate_ok` without an execution plan.
All absent-plan defaults serialize as `required_unsupported` with explicit
failing evidence (`ok=False`, `reason="required_unsupported"`).

### 2.5 Queue evidence-tier gating

Only `live_runtime_schema` and `object_info` tiers are strong enough for
Queue/runtime-readiness proof.  All other tiers (web, github, hivemind,
civitai, external_workflow, …) are weak and block Queue.  Weak
`runtime_availability` labels (`not_available`, `not_installed`,
`provisional`, `workflow_observed`, `stale`, `untrusted_source`) are
rejected regardless of tier.

---

## 3. Proof States

### 3.1 Four domains × four states

| Domain | Purpose |
|---|---|
| `transformation_safety` | Candidate graph is safe to apply (no forbidden nodes, no data loss) |
| `graph_validity` | Candidate graph is structurally valid (DAG, all links resolvable) |
| `task_satisfaction` | Candidate graph satisfies declared task obligations |
| `runtime_readiness` | All required node types are installed and compatible |

| State | Semantics |
|---|---|
| `pass` | Domain is satisfied |
| `fail` | Domain is not satisfied |
| `not_run` | Intentionally skipped (non-applyable route) |
| `unknown` | Expected but not available — **fail-closed default** |

### 3.2 Owner module

`vibecomfy/comfy_nodes/agent/completion_proofs.py` (`CompletionProof` frozen
dataclass with `to_dict`/`from_dict`, aggregate queries `all_pass`,
`any_fail`, `is_success`).

---

## 4. Obligation Ledger

### 4.1 Vocabulary

| Kind | Description |
|---|---|
| `class_present` | A node of a given class-type must exist |
| `class_absent` | A node of a given class-type must NOT exist |
| `value_match` | A specific field/input value must equal an expected value |
| `edge_exists` | A directed edge between two node references must exist |
| `terminal_output_domain` | The terminal node must produce a specific output domain |
| `scope_preserved` | The scope/session graph must not lose pre-existing nodes/edges |
| `obligation_declared` | Meta-obligation: declared but not yet evaluated |

### 4.2 Statuses

`satisfied`, `unsatisfied`, `unknown`, `not_evaluated`, `unsupported`

### 4.3 Severities

`required`, `recommended`, `optional`

### 4.4 Satisfaction strategy (SD3)

Obligation satisfaction is **structural**, not semantic.  The server compares
declared obligations to landed delta/candidate evidence and marks ambiguous
cases `unknown` or `not_run`.  Incomplete required obligations block Apply.

### 4.5 Owner module

`vibecomfy/comfy_nodes/agent/obligation_ledger.py` (`Obligation`,
`StructuralTarget`, `ObligationLedger` frozen dataclasses with deterministic
SHA-256 hashable serialization).

---

## 5. Artifact Hashes

### 5.1 Authority receipt hashes

| Hash | Algorithm | Purpose |
|---|---|---|
| `submit_graph_hash` | SHA-256 | Immutable submit graph bytes |
| `cumulative_delta_hash` | SHA-256 | Cumulative V2 delta envelope |
| `candidate_hash` | SHA-256 | Replay-recomputed candidate |
| `candidate_match_hash` | SHA-256 | Equality check with persisted candidate |
| `response_digest` | SHA-256 | Response metadata payload hash |

### 5.2 Evidence content hashes

| Hash | Algorithm | Purpose |
|---|---|---|
| `content_hash` | SHA-256 | Deterministic hash of precedent evidence (excludes ephemeral score/relevance fields) |

### 5.3 Owner modules

- `vibecomfy/comfy_nodes/agent/authority_receipts.py` — `build_and_persist_authority_receipt`, `ReplayReceipt`, `AuthorityReceipt`
- `vibecomfy/comfy_nodes/agent/session.py` — `payload_hash`, `canonical_json_bytes`
- `vibecomfy/executor/research.py` — `_compute_content_hash`

---

## 6. Delta Envelope Contract

### 6.1 Canonical shape

```json
{
  "schema_version": "2.0.0",
  "ops": [
    { "op": "set_node_field", "target": {...}, "field": "...", "value": ... },
    { "op": "set_mode", ... },
    { "op": "add_node", ... },
    { "op": "upsert_link", ... },
    { "op": "remove_node", ... },
    { "op": "remove_link", ... }
  ]
}
```

### 6.2 Cumulative batch_repl assembly

`_build_cumulative_batch_repl_delta_envelope` in `edit_response_contract.py`
collects `delta_ops_envelope` ops from each batch turn in order, concatenates
them, and normalizes through `ensure_root_scoped_delta_envelope(strict=True)`.

`delta_ops` is derived as a **read-only** list from the canonical envelope ops
and must never be set independently.

### 6.3 Delta validation (fail-closed)

| Diagnostic Code | Condition |
|---|---|
| `delta_diagnostic_corrupted` | Envelope fails structural parse |
| `delta_diagnostic_truncated` | Ops list is empty when expected |
| `delta_diagnostic_absent` | No delta evidence present |
| `delta_diagnostic_replay_mismatch` | Replay produces different candidate |
| `delta_diagnostic_legacy_shape` | Legacy wrapped `{delta_ops: ...}` rejected |

### 6.4 Owner module

`vibecomfy/porting/edit/ops.py` — `normalize_delta_envelope`,
`ensure_root_scoped_delta_envelope`, `validate_delta_envelope_structure`,
`validate_apply_delta_evidence`, `validate_delta_replay_equality`.

---

## 7. Authority Receipt Lifecycle

1. **On response write** (scope=edit): `record_idempotent_response` in
   `session.py` calls `build_and_persist_authority_receipt` with the turn
   directory, request payload, and response.

2. **Replay**: `build_and_persist_authority_receipt` replays
   `apply(submit_graph, cumulative_delta)` and compares the recomputed
   candidate hash with the persisted candidate hash.

3. **Fail-closed stamping**: If `replay_ok=False` or `candidate_matches=False`,
   `stamp_response_with_authority` marks the response non-applyable.  **Only**
   applyable turns are stamped; non-applyable executor-only responses are
   left unchanged.

4. **Persistence**: Receipt written to `<turn_dir>/authority/authority_receipt.json`
   under a per-turn immutable `authority/` namespace (SD1).

### 7.1 Owner module

`vibecomfy/comfy_nodes/agent/authority_receipts.py` (578 lines).

---

## 8. Evidence Freshness and Precedence

### 8.1 Per-tier TTLs

| Tier | Default TTL | Env Override |
|---|---|---|
| Web search | 24h (86400s) | `VIBECOMFY_WEB_SEARCH_TTL` |
| GitHub | 7d (604800s) | `VIBECOMFY_GITHUB_TTL` |
| Hivemind | 7d (604800s) | `VIBECOMFY_HIVEMIND_TTL` |
| Civitai | 30d (2592000s) | `VIBECOMFY_CIVITAI_TTL` |
| External workflow | 30d (2592000s) | (inherits Civitai TTL) |
| Live runtime schema | 0 (no cache) | — |

### 8.2 SelectedPrecedent fields

`retrieval_time`, `content_hash` (SHA-256, deterministic, excludes ephemeral
fields), `query_transform_trace`, `tier`, `freshness_status`,
`selection_reasons`.

### 8.3 Owner modules

- `vibecomfy/executor/contracts.py` — `SelectedPrecedent` dataclass
- `vibecomfy/executor/research.py` — TTL constants, `_source_tier_for_source`,
  `_tier_ttl_seconds`, `_source_freshness_status`, `_compute_content_hash`

---

## 9. Durable Candidate Preservation on Narration Failure

When reply narration fails after a successful implementation:

1. `edit_narrator.py`: `_narrate_final_message` is wrapped in try/except;
   any unhandled exception returns `_deterministic_narrative_fallback` with
   `fallback_reason="narrator_unrecoverable_error"`.

2. `executor/core.py`: In the reply phase catch block, when
   `implementation_result.durable_response` is set and `result_graph` is
   available, the executor returns `ExecutorResult.success` with a
   deterministic fallback reply instead of `ExecutorResult.failure`.

Narration failure is **presentation-only** (SD1); durable edit work
(candidate, gates, proofs, receipts, eligibility) is preserved.

### 9.1 Owner modules

- `vibecomfy/comfy_nodes/agent/edit_narrator.py`
- `vibecomfy/executor/core.py`

---

## 10. Idempotency

### 10.1 Key stamping

Idempotency keys are stamped on durable executor responses (both executor-only
and applyable) via `executor_durable.py` and `edit_entrypoint.py`.  Replayed
responses include the cached key even if the original write predates the
stamping change.

### 10.2 Duplicate behavior

Duplicate idempotency keys return the cached response without allocating a new
turn or repeating provider/edit work.  Distinct keys allocate distinct turns.

### 10.3 Owner modules

- `vibecomfy/comfy_nodes/agent/executor_durable.py`
- `vibecomfy/comfy_nodes/agent/edit_entrypoint.py`
- `vibecomfy/comfy_nodes/agent/session.py` (`record_idempotent_response`)

---

## 11. Retained Bridges — Owner, Use Count, Deletion Criteria

### 11.1 `build_legacy_agent_edit_v1`

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/comfy_nodes/agent/contracts.py` (line 446) |
| **Callers** | `executor_durable.py`, `reorganise.py`, `edit_response_contract.py`, `routes.py`, `edit_state.py` |
| **Observable call sites** | 6 modules, ~10 call sites |
| **Purpose** | Wraps a canonical V2 response dict with legacy aliases (`canvas_apply_allowed`, `queue_allowed`, `apply_allowed`, `candidate_graph`, `graph_unchanged`) for backward-compatible UI consumption |
| **Deletion condition** | When all browser/frontend consumers have migrated to the canonical V2 response contract and no caller references the legacy alias keys.  The JS `agent_edit_response_contract_generated.js` must be updated first. |
| **Deletion checklist** | 1. Audit all callers (6 modules). 2. Verify no browser code reads `canvas_apply_allowed`/`queue_allowed`/`apply_allowed` keys. 3. Remove the function and the `__all__` export. 4. Replace callers with direct canonical dict usage. |

### 11.2 `allow_legacy_list` (in `normalize_delta_envelope` / `ensure_root_scoped_delta_envelope`)

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/porting/edit/ops.py` (lines 645, 716, 724) |
| **Callers** | `test_porting_edit_session.py` (2 call sites), `test_agent_edit_artifact_replay.py` (1 call site) |
| **Observable call sites** | 3 test-only call sites (no production callers) |
| **Purpose** | Accepts flat V2 op arrays (without `{schema_version, ops}` wrapper) as a temporary migration bridge; stamps `legacy_bridge="flat_v2_ops"` on the resulting envelope |
| **Deletion condition** | When all persisted/stored delta artifacts have been migrated to the canonical `{schema_version: "2.0.0", ops: [...]}` shape.  Production code never passes `allow_legacy_list=True`. |
| **Deletion checklist** | 1. Migrate any legacy flat-op artifacts in storage. 2. Remove the parameter from `normalize_delta_envelope`, `normalize_delta_ops`, and `ensure_root_scoped_delta_envelope`. 3. Update the three test call sites. 4. Remove the `legacy_bridge` field from `CanonicalDeltaEnvelope` and the schema. |

### 11.3 `_normalize_link_wire_names`

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/porting/edit/ops.py` (line 455) |
| **Callers** | `parse_edit_op` (line 467, private caller within same module) |
| **Observable call sites** | 1 (private, within `ops.py`) |
| **Purpose** | Normalizes legacy wire names for upsert_link ops: `source→from`, `target→to`, `link_id→id`.  This is a compatibility shim for model-generated JSON that uses non-canonical field names. |
| **Deletion condition** | When the model no longer generates `source`/`target`/`link_id` field names and exclusively uses the canonical `from`/`to`/`id`.  Track via incidence counter on model output parsing. |
| **Deletion checklist** | 1. Confirm model output exclusively uses canonical field names over a 2-week observation window. 2. Remove `_normalize_link_wire_names` and inline the canonical parse. 3. Run full edit-ops test suite. |

### 11.4 Legacy `/agent/edit` route marker

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/comfy_nodes/agent/routes.py` (line 1795, `_legacy_agent_edit_route`) |
| **Callers** | External HTTP clients posting to `POST /agent/edit` |
| **Observable use count** | Tracked via `X-VibeComfy-Legacy-Route: true` response header |
| **Purpose** | Wraps the legacy `/agent/edit` endpoint through the canonical `_handle_agent_executor_submit` pipeline, preserving payload normalization and client-id behavior.  Returns the deprecation header `X-VibeComfy-Legacy-Route: true`. |
| **Deletion condition** | When all external clients have migrated to `POST /vibecomfy/agent-edit` or `POST /vibecomfy/agent-executor`.  Monitor the `X-VibeComfy-Legacy-Route` header emission rate; delete when it drops to zero over a 30-day window. |
| **Deletion checklist** | 1. Confirm zero legacy route hits over 30 days. 2. Remove the `_legacy_agent_edit_route` handler. 3. Remove the `@app.routes.post("/agent/edit")` registration. 4. Update route coverage tests. |

### 11.5 Historical V1 read-only support

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/comfy_nodes/agent/session.py` (`agent_edit_protocol` field, line 1413) |
| **Callers** | Session rehydration, chat display, replay viewer |
| **Observable counter** | `agent_edit_protocol` field: `"v1"` vs `"v2_delta"` |
| **Purpose** | Marks turns as `"v1"` (no `delta_ops`) or `"v2_delta"` (with `delta_ops`).  V1 turns are read-only; they can be displayed and replayed but cannot be used as authority for new applyable turns. |
| **Deletion condition** | When no V1 turns exist in any production session.  This is a long-term migration target; V1 read-only support may persist indefinitely for historical sessions. |
| **Deletion checklist** | 1. Audit all production sessions for `agent_edit_protocol: "v1"`.  2. Migrate or archive historical sessions.  3. Remove the V1 protocol branch. |

### 11.6 Sprint 1 server-side authority receipt before full browser preparation

| Attribute | Value |
|---|---|
| **Owner** | `vibecomfy/comfy_nodes/agent/authority_receipts.py` |
| **Status** | Sprint 1 delivers server-side receipt verification only.  Browser-side authority receipt consumption (redacted audit views, apply-button gating based on receipt) is deferred to Sprint 2 (T18). |
| **Purpose** | The server now produces and verifies authority receipts for every applyable turn.  The receipt is persisted under the per-turn `authority/` namespace.  Browser-side contract parity tests exist (`tests/browser/agent_edit_response_contract.test.mjs`, `tests/browser/canonical_delta.test.mjs`) but browser code does not yet gate apply actions on receipt verification. |
| **Deletion condition** | Not a bridge to delete — this is a feature completeness note.  The "before full browser preparation" qualifier is resolved when Sprint 2 lands browser-side receipt gating. |

---

## 12. Browser Contract Parity (T16)

The generated JS contract (`vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js`)
was extended with:

- Constants: `COMPLETION_PROOF_STATES`, `COMPLETION_PROOF_DOMAINS`,
  `OBLIGATION_KINDS`, `OBLIGATION_STATUSES`, `OBLIGATION_SEVERITIES`,
  `DELTA_DIAGNOSTIC_CODES`, `PLAN_OBLIGATION_STATES`
- Validators: `isValidProofState`, `isValidProofDomain`, `isValidObligationKind`,
  `isValidObligationStatus`, `isValidObligationSeverity`
- Consumer helpers: `readDeltaEnvelope`, `readIdempotencyKey`,
  `readObligationArtifacts`, `isNonApplyableClarify`

Browser tests (`tests/browser/agent_edit_response_contract.test.mjs`,
`tests/browser/canonical_delta.test.mjs`) were updated with extended
expectations for cumulative delta envelope, proof states, obligation ledger,
authority receipt hashes, idempotency key, malformed delta, and non-applyable
clarify obligations.

---

## 13. Exact Test Commands

### 13.1 Core contract and gate tests

```bash
python -m pytest tests/test_comfy_nodes_agent_contracts.py -v --tb=short
python -m pytest tests/test_comfy_nodes_agent_backend_spine.py -v --tb=short
python -m pytest tests/test_agent_executor_response.py -v --tb=short
```

### 13.2 Obligation ledger tests

```bash
python -m pytest tests/test_agent_obligation_ledger.py -v --tb=short
```

### 13.3 Execution plan tests

```bash
python -m pytest tests/test_execution_plan_contracts.py tests/test_execution_plan_evaluator.py tests/test_execution_plan_builder.py tests/test_agent_execution_plan_hydration.py -v --tb=short
```

### 13.4 Authority receipt and replay tests

```bash
python -m pytest tests/test_comfy_nodes_agent_backend_spine.py -k authority_receipt -v --tb=short
python -m pytest tests/test_agent_edit_artifact_replay.py -v --tb=short
```

### 13.5 Route parity and idempotency tests

```bash
python -m pytest tests/test_agent_executor_routes.py -v --tb=short
python -m pytest tests/test_agent_executor_durable.py -v --tb=short
```

### 13.6 Edit response contract tests

```bash
python -m pytest tests/test_comfy_nodes_agent_edit.py -v --tb=short
```

### 13.7 Evidence freshness and research tests

```bash
python -m pytest tests/test_executor_research.py -v --tb=short
```

### 13.8 Delta contract and ops tests

```bash
python -m pytest tests/test_porting_edit_delta_contract.py tests/test_porting_edit_ops.py -v --tb=short
```

### 13.9 Narration failure preservation tests

```bash
python -m pytest tests/test_edit_narrative.py -v --tb=short
python -m pytest tests/test_executor_flows.py -v --tb=short
```

### 13.10 Browser contract parity tests

```bash
node --test tests/browser/agent_edit_response_contract.test.mjs
node --test tests/browser/canonical_delta.test.mjs
```

### 13.11 Full Sprint 1 regression suite

```bash
python -m pytest \
  tests/test_comfy_nodes_agent_contracts.py \
  tests/test_comfy_nodes_agent_backend_spine.py \
  tests/test_comfy_nodes_agent_edit.py \
  tests/test_agent_executor_response.py \
  tests/test_agent_executor_routes.py \
  tests/test_agent_executor_durable.py \
  tests/test_agent_obligation_ledger.py \
  tests/test_agent_edit_artifact_replay.py \
  tests/test_execution_plan_contracts.py \
  tests/test_execution_plan_evaluator.py \
  tests/test_execution_plan_builder.py \
  tests/test_agent_execution_plan_hydration.py \
  tests/test_executor_research.py \
  tests/test_porting_edit_delta_contract.py \
  tests/test_porting_edit_ops.py \
  tests/test_edit_narrative.py \
  tests/test_executor_flows.py \
  tests/test_reorganise_skill.py \
  tests/test_routes_session_sanitization.py \
  --tb=line -q
```

---

## 14. Module Inventory

### 14.1 New modules created in Sprint 1

| Module | Lines | Purpose |
|---|---|---|
| `vibecomfy/comfy_nodes/agent/completion_proofs.py` | 342 | Independent four-domain completion proof artifacts |
| `vibecomfy/comfy_nodes/agent/obligation_ledger.py` | 814 | Obligation vocabulary, ledger, deterministic serialization |
| `vibecomfy/comfy_nodes/agent/authority_receipts.py` | 578 | Authority receipt persistence and replay verification |

### 14.2 New schemas created in Sprint 1

| Schema | Purpose |
|---|---|
| `vibecomfy/porting/edit/schemas/v2/authority_receipt.schema.json` | Authority receipt JSON Schema |
| `vibecomfy/porting/edit/schemas/v2/obligation_ledger.schema.json` | Obligation ledger JSON Schema |
| `vibecomfy/porting/edit/schemas/v2/delta_envelope.schema.json` | Updated with `legacy_bridge` field |

### 14.3 Modules modified in Sprint 1

| Module | Changes |
|---|---|
| `vibecomfy/comfy_nodes/agent/contracts.py` | Plan obligation states, legacy bridge, fail-closed TurnContext rehydration |
| `vibecomfy/comfy_nodes/agent/gates.py` | Evidence-tier gating for Queue, plan_state pass-through, weak evidence blocking |
| `vibecomfy/comfy_nodes/agent/execution_plan.py` | Proof domain integration, plan state constants, runtime evidence tier collection |
| `vibecomfy/comfy_nodes/agent/edit_response_contract.py` | Cumulative delta envelope, obligation gating, delta evidence validation, legacy bridge integration |
| `vibecomfy/comfy_nodes/agent/executor_response.py` | Removal of authority synthesis from `_executor_compatibility_fields` |
| `vibecomfy/comfy_nodes/agent/executor_durable.py` | Idempotency key stamping, defensive replay key stamping |
| `vibecomfy/comfy_nodes/agent/edit_entrypoint.py` | Idempotency key stamping on all response paths |
| `vibecomfy/comfy_nodes/agent/routes.py` | Legacy `/agent/edit` wrapping, `X-VibeComfy-Legacy-Route` header |
| `vibecomfy/comfy_nodes/agent/session.py` | Authority receipt integration in `record_idempotent_response` |
| `vibecomfy/comfy_nodes/agent/edit_narrator.py` | try/except wrapper, `_deterministic_narrative_fallback` on unrecoverable error |
| `vibecomfy/executor/core.py` | Preserve durable candidate on reply narration failure |
| `vibecomfy/executor/contracts.py` | `SelectedPrecedent` freshness/evidence metadata fields |
| `vibecomfy/executor/research.py` | TTL constants, content hashes, query transform traces, freshness status |
| `vibecomfy/porting/edit/ops.py` | Delta validation diagnostics, `allow_legacy_list` bridge, `_normalize_link_wire_names`, `legacy_bridge` field |
| `vibecomfy/comfy_nodes/web/agent_edit_response_contract_generated.js` | Extended constants, validators, consumer helpers |

### 14.4 Test files created or extended in Sprint 1

| Test File | Changes |
|---|---|
| `tests/test_comfy_nodes_agent_contracts.py` | Authority leak containment tests, legacy bridge tests |
| `tests/test_agent_executor_response.py` | Non-durable authority synthesis prohibition tests |
| `tests/test_agent_executor_routes.py` | Legacy route parity, composed route authority parity |
| `tests/test_agent_executor_durable.py` | Idempotency tests, duplicate key behavior |
| `tests/test_agent_obligation_ledger.py` | Full obligation vocabulary, serialization, schema tests |
| `tests/test_agent_edit_artifact_replay.py` | Delta validation, replay mismatch, cumulative/empty/malformed delta |
| `tests/test_executor_research.py` | Freshness, content hash, TTL enforcement |
| `tests/test_edit_narrative.py` | Narration failure preservation |
| `tests/test_executor_flows.py` | Durable candidate preservation on reply failure |
| `tests/browser/agent_edit_response_contract.test.mjs` | Extended expectations for Sprint 1 contracts |
| `tests/browser/canonical_delta.test.mjs` | Extended expectations for Sprint 1 contracts |

---

## 15. Deferred to Sprint 2 (T18)

- **Browser-side authority receipt gating**: The browser does not yet gate
  apply-button availability on server-side receipt verification.  Contract
  parity tests exist, but the browser apply flow uses server-returned
  `apply_eligible`/`apply_allowed` fields directly without consulting the
  authority receipt.

- **Redacted audit views**: No browser-side rendering of authority receipt
  hashes or replay verdicts.

- **Full authority receipt roundtrip**: Browser preparation → server
  verification → browser confirmation flow.

---

## 16. Sprint 1 Task Summary

| Task | Kind | Complexity | Status |
|---|---|---|---|
| T1 | test | 3 | done — Authority leak containment tests |
| T2 | code | 4 | done — Remove authority synthesis from executor serialization |
| T3 | code | 5 | done — Fail-closed absent-plan defaults |
| T4 | code | 5 | done — Wrap legacy `/agent/edit` through canonical executor |
| T5 | code | 4 | done — Idempotency key stamping |
| T6 | code | 4 | done — Completion proof artifacts |
| T7 | code | 5 | done — Obligation ledger vocabulary and schema |
| T8 | code | 6 | done — Gate edit+clarify on structural obligations |
| T9 | code | 6 | done — Evidence freshness and precedence |
| T10 | code | 5 | done — Queue evidence-tier gating |
| T11 | code | 5 | done — Cumulative normalized V2 delta envelope |
| T12 | code | 7 | done — Authority receipt persistence and replay |
| T13 | code | 5 | done — Fail-closed delta evidence validation |
| T14 | code | 5 | done — Preserve durable candidate on narration failure |
| T15 | test | 5 | done — Composed route, durable idempotency, artifact replay tests |
| T16 | test | 5 | done — Browser/generated response contract parity |
| T17 | docs | 3 | done — This handoff document |
| T18 | — | — | deferred — Browser-side authority receipt gating |
