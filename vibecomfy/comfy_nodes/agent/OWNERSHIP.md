# Backend Module Ownership Map

This document records the canonical owner for each backend boundary touched by
agent-edit turns.  It is the source of truth for where a responsibility lives,
which module is allowed to import it, and which modules are consumers only.

## 1. Boundaries

| Boundary | Canonical owner | What it owns | Consumers (read-only) |
|---|---|---|---|
| Response envelope | `contracts.py` | `turn_envelope`, `success_envelope`, `failure_envelope`, `build_legacy_agent_edit_v1`, `ensure_agent_edit_response_contract` | `edit.py`, `routes.py` |
| Chat artifacts | `edit.py` | `_write_turn_chat_artifact` | `routes.py` reads via `read_session_chat` |
| Session artifact iteration | `session.py` | `iter_turn_records` and raw turn-directory walking | `edit.py:read_session_chat`, CLI `_agent_edit_debug.py` |
| Accept / reject / idempotency | `session.py` | `accept_turn`, `reject_turn`, `_mutate_turn_state` | `routes.py` thin `*args` / `**kwargs` wrappers |
| Field-change type | `porting/edit/types.py` | `FieldChange` frozen dataclass | `contracts.py`, `edit.py` |
| Field-change repair | `contracts.py` | `repair_field_changes` | `edit.py` |
| Diagnostics contract | `contracts.py` | `DiagnosticRecord` | `audit.py` (writer), `session.py:iter_turn_records` (reader/adapter) |
| Diagnostics persistence | `audit.py` | `write_audit` | `edit.py`, `routes.py` |
| Typed transaction projections | `projection_registry_v1.py` | field rules, canonical-UI normalization, stable identity, UTF-16-compatible ordering, projection hashing, typed references, and v2 authority stages | `session.py` compatibility facades and lifecycle code |

## 2. Principles

1. **Canonical types live in `contracts.py` or `porting/edit/types.py`.**
   No other module may define a competing `FieldChange`, `FailureEnvelope`,
   `TurnOutcome`, or `DiagnosticRecord`.

2. **Server-side state mutation is owned by `session.py`.**
   `edit.py` orchestrates logic; `routes.py` only dispatches HTTP requests.
   Both delegate accept/reject/idempotency to `session.py`.

3. **Disk iteration is owned by `session.py`.**
   `iter_turn_records` is the only canonical reader that walks turn
   directories and joins `response.json` with `session_state.json` lifecycle
   data.  `edit.py:read_session_chat` may keep its own chat-specific display
   logic but should reuse `iter_turn_records` for the raw walk when practical.

4. **CLI debug is a consumer, not an owner.**
   `contracts.py` owns `DiagnosticRecord`.  `session.py` imports that contract
   and exposes `iter_turn_records()` as the canonical iterator that returns
   typed diagnostic records.  `_agent_edit_debug.py` imports
   `iter_turn_records()` from `session.py`, converts those records to its legacy
   CLI row shape, and applies its own text formatting.  It must not directly
   import `DiagnosticRecord`, redefine a diagnostic record shape, or
   re-implement the turn walk.

5. **Routes are HTTP adapters, not session owners.**
   `routes.py` may expose API functions for accept/reject, but those wrappers
   must delegate directly to the `session.py` implementations.  It must not
   define independent idempotency, state mutation, or turn-state persistence
   logic.

6. **The projection registry is the semantic authority.**
   `session.py` may retain only compatibility facades for old hash call sites;
   it must not introduce independent field selection, ordering, or identity
   rules for new transaction authority. Native node IDs may be used only as
   registry-local locators while converting native links to stable UID/port
   endpoint tuples; they are never emitted as typed authority identity.

## 3. Exceptions / compatibility notes

- `edit.py:read_session_chat` retains chat-specific fallback logic (reading
  `chat.json`, building display messages, bounding message count).  The
  underlying turn iteration is delegated to `session.py:iter_turn_records`.
- `audit.py:normalize_agent_edit_v2_metadata` stays in `audit.py` because it
  normalizes audit-specific metadata shapes and is not duplicated elsewhere.
- `_agent_edit_debug.py` continues to format output columns, colors, and
  summary widths locally.  That formatting is a presentation-layer concern, not
  a backend boundary.

## 4. Agent-judgment rework ownership (V02)

The agent-judgment rework (F01 → V01, landed at `4358aaa6`) re-homed agent
research and tools out of this directory. The rules:

1. **Agent judgment lives in `vibecomfy/executor/`, not here.**
   The classify → research → implement → reply spine is orchestrated by
   `vibecomfy/executor/core.py`; this directory owns the durable session /
   apply / queue machinery that executes and records the agent's work.

2. **Agent-invoked tools are owned by `vibecomfy/executor/` modules.**
   `hivemind_search`/`hivemind_get` → `hivemind_tools.py`; `registry_lookup`,
   `node_schema`, `ready_template_list`/`ready_template_load` →
   `lookup_tools.py`; `web_search` → `web_tools.py`; `rank_edit_targets` and
   `suggest_seed_nodes` → `edit_suggestion_tools.py`; `layout_hints` →
   `layout_hints.py`. Tool result statuses are typed in `tool_contracts.py`;
   stage handoffs (goal / priority brief / package) are typed in
   `stage_contracts.py` + `evidence_pack.py`.

3. **Research is agent-owned and phase-partitioned.**
   `agent_research_stage.py` is the single research entry point; the legacy
   prefetch path is a fail-closed stub in `core.py`
   (`run_research_phase`/`_run_research`/`_default_hivemind_client`, kept only
   for `assert_not_called()` tests). Implement-phase code must not call
   research tools.

4. **Queue readiness consumes probe receipts.**
   `gates.py` verifies `live_runtime_schema_probe()` receipts from
   `vibecomfy/runtime/schema_probe.py`; a bare tier label never satisfies the
   gate. Emitted edges are never dropped (`RefusedEmit` in `porting/emit`).

5. **Deleted machinery must not return.**
   The deterministic research engine (`executor/research.py`,
   `research_sources.py`, `execution_plan_builder.py`), the `ResearchResult`
   class and precedent contracts, the keyword classifiers
   (`_task_looks_like_parameter_tweak` / `_task_looks_like_additive`,
   `_should_prefetch_research`, `_delegated_clarification_plan`,
   `_headless_clarify_research_plan`, `_targeted_edit_hardening_feedback`),
   queue-time schema sanitization (`sanitize_api_against_schema`,
   `SCHEMA_VALIDATION_SKIP_CLASSES`), and the prompt-injection surface were
   deleted in Waves C/D. New code must not reintroduce deterministic
   decision-making or prompt rewriting (see
   `docs/agent-judgment-pipeline.md` §6, §9). The single exception: the
   low-level `_existing_parameter_tweak_targets_from_graph` ranking in
   `_frag_batch_memory.py` survives solely as the parity oracle for
   `diagnose_existing_tweak_ranking` in `edit_suggestion_tools.py`
   (`tests/test_executor_edit_suggestion_tools.py` asserts output equality);
   it is not wired into any prompt directive.
