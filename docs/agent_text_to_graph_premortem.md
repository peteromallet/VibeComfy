# Text-to-Graph Agent Pre-Mortem

This review assumes the overall direction is right: the browser sends the
current ComfyUI graph plus a text request, the backend edits through VibeComfy
Python using DeepSeek, validates, returns candidate UI JSON, and the frontend
lets the user apply or reject it.

The failure story from the review panel is not "the idea is wrong." The failure
story is that the product ships before the contract is sharp enough at the
editor/runtime boundary.

## Kickoff Blockers

These must be folded into S0/S1/S2 before the epic starts.

1. **State primitives cannot wait for S3.** `baseline_turn_id`,
   `client_graph_hash`, `idempotency_key`, stale-response handling, and
   accepted/rejected/candidate state must be frozen in S0 and partially
   implemented in S1/S2. S3 can harden the protocol, but S1/S2 cannot ship
   against a different contract.
2. **Canvas Apply is not Queue.** The frontend must use
   `canvas_apply_allowed`, not legacy `apply_allowed`, as its Apply gate.
   `apply_allowed` is only a back-compat alias and must be tested explicitly.
3. **Validation must split into named gates.** A candidate is not apply-safe
   just because Python loads or `ValidationReport` passes. The gates are:
   `python_load_ok`, `ir_validate_ok`, `ui_emit_ok`, `ui_load_safe_ok`,
   `queue_validate_ok`, and `state_match_ok`.
4. **UI JSON fidelity is a product contract.** Positions, uids, groups, notes,
   reroutes, bypass/mute state, properties, custom metadata, widget payloads,
   and subgraph definitions need explicit preserve/drop/refuse rules.
5. **Generated Python loading needs a real safety boundary.** The loader must
   treat model output as `agent_generated`, not `user_confirmed`, and run an
   allowlist-style pre-load scan before import/load.
6. **S2 must show the candidate on the canvas.** A text diff is not enough.
   Users need canvas-level preview/highlights before Apply and confirmation
   after Apply.
7. **Queue blocking has to reach the native Queue path.** If a graph contains
   editor-only intent nodes, the panel and native ComfyUI Queue action must make
   queue blocking obvious.
8. **The audit schema must be typed and reconstructable.** Each turn needs full
   raw model request/response files, artifact hashes, redaction metadata,
   frontend action evidence, and acceptance state.

## Sprint Amendments

### S0

Freeze the UI-fidelity contract, named validation gates, closed failure enums,
`apply_allowed` alias semantics, state primitives, and audit schema before more
implementation. ~~S0 should also define whether editor-only `vibecomfy.*` nodes
are extension-owned UI nodes, normal custom nodes, or both.~~ **Resolved in S0
contract freeze:** Editor-only `vibecomfy.*` nodes are frozen as extension-owned
UI nodes registered in `NODE_CLASS_MAPPINGS` with `vibecomfy_editor_only=true`,
non-executable, Queue-blocked. See MVP doc: Editable Intent Nodes — Frozen
architecture block, with premortem traceability note.

### S1

Implement the backend spine with turn allocation, idempotency records,
`agent_generated` scratchpad loading, raw request/response audit files,
port-check-style diagnostics, and UI-load-safe derivation. S1 is allowed to
return `queue_allowed: false`; it must not overclaim queueability.

### S2

Implement the durable panel plus canvas diff/preview, apply-time dirty checks,
native Queue coordination, "Undo Last Apply", hash-mismatch UX, and browser
tests for stale Apply, double submit, reject/resubmit, audit download, and
failure non-mutation.

### S3

S3 becomes hardening: explicit accept/reject endpoints, backend conflict
policies, persistent session restore, audit transitions, and concurrency
coverage. It should not be the first time state primitives appear.

### S4

Intent nodes need more than a badge. Editor-only status must be visually
unmistakable, queue-blocking must reference the specific node, and the node
metadata must round-trip through UI JSON and audit.

### S5

Static lowering needs deterministic ids, original intent hash, lowered fragment
hash, source-to-lowered node map, layout policy, and post-lowering validation.

## Model Allocation

Use **Codex** for decisions where multiple systems interact and architectural
debt is easy to create:

- FE/BE protocol and state machine;
- validation gate semantics;
- UI JSON fidelity contract;
- generated-Python safety boundary;
- intent-node apply/queue model;
- sequencing changes and merge gates.

Use **DeepSeek** for breadth and adversarial enumeration:

- UX confusion states;
- audit-field completeness;
- stale-response/browser race cases;
- workflow corpus fixtures and custom-node weirdness;
- prompt/response edge cases once the contract is fixed.

The current plan should remain Codex-led for implementation. DeepSeek is useful
as a review/scanning layer, not as the final authority for the contract.

## S0 Incorporation Table

The eight kickoff blockers and five sprint amendments are addressed in the
S0 contract freeze as follows. Where the freeze is deferred, the rationale
and S1/S2 impact are noted.

### Kickoff Blockers

| # | Blocker | S0 Resolution | Location in MVP doc | S1/S2 impact |
|---|---|---|---|---|
| 1 | State primitives (`baseline_turn_id`, `client_graph_hash`, `idempotency_key`, stale-response, accepted/rejected/candidate state) | Frozen in S0; partial implementation in S1/S2 | API shape (request fields, response envelope), Baseline and Concurrency, Accept/Reject, Per-Turn Audit (acceptance state). Sprint 3 hardens. | S1 ships request fields + accept/reject endpoints + audit state; S2 adds frontend serialization; S3 hardens backend enforcement. No S1/S2 contract divergence. |
| 2 | Canvas Apply is not Queue; use `canvas_apply_allowed` not `apply_allowed` | Committed. `canvas_apply_allowed` is primary; `apply_allowed` is back-compat alias only | API shape (response fields, Canvas Apply / Queue distinction), Apply-Safety Gates (named gates + derivation) | S1 derives both fields; S2 uses `canvas_apply_allowed` as Apply gate. Alias tested explicitly. |
| 3 | Validation must split into named gates | Frozen. Seven named gates: `python_load_ok`, `ir_validate_ok`, `ui_emit_ok`, `ui_fidelity_ok`, `ui_load_safe_ok`, `queue_validate_ok`, `state_match_ok` | Apply-Safety Gates table, response semantics, `canvas_apply_allowed` / `queue_allowed` derivation | S1 implements gate derivation; S2 surfaces gate status in frontend. |
| 4 | UI JSON fidelity is a product contract | Frozen. Positions, uids, groups, notes, reroutes, bypass/mute, properties, custom metadata, widget payloads, subgraphs | UI Fidelity Contract (protected surface list), Frontend decisions (Apply semantics with snapshot/restore), Closed Failure Enum (`RefusedEmit`, `EditorAheadConflict`) | S1 implements fidelity diagnostics; S2 adds canvas-level preview/highlights. |
| 5 | Generated Python loading needs real safety boundary (`agent_generated` not `user_confirmed`, allowlist scan) | **Resolved.** Restricted AST-gated `agent_generated_loader` built (S0 T3–T5); `agent_edit.py` wired to it (S0 T6–T7). Hostile fixtures prove pre-execution rejection. | Python Loading Derisk Spike (spike result: KEEP), backend loop (provenance contract), Safety constraints (restricted loader described) | No S1/S2 impact: the loader is integrated and the proof path uses it. |
| 6 | S2 must show candidate on canvas (not just text diff) | Committed for S2. S0 freezes the visual language. | Frontend decisions (Pre-Apply preview: structured diff only for v1; explicit "Preview on canvas" deferred), Node highlight visual values table | S1: structured diff only. S2: canvas preview with snapshot/restore. No S1 impact. |
| 7 | Queue blocking must reach native Queue path | **Resolved.** Frozen architecture: editor-only `vibecomfy.*` nodes are non-executable, Queue blocked; native Queue intercept/warn/block policy frozen. | Editable Intent Nodes (Frozen architecture block + premortem traceability note), Frontend decisions (Native Queue coordination), Closed Failure Enum (`EditorOnlyNodeQueueBlocker`) | S1 blocks Queue via `queue_allowed: false`; S2 adds native Queue intercept. No contract divergence. |
| 8 | Audit schema must be typed and reconstructable | Frozen. Schema v1 with staged fields, bounded embedding, redaction categories, full raw request/response artifact references by hash. | Per-Turn Audit (canonical `audit.json` shape, field list, bounded-embedding rules), Audit Download Route | S1 writes per-turn audit files; S2 adds audit download UI. Schema versioned for forward compatibility. |

### Sprint Amendments

| Sprint | Amendment | S0 Freeze Status | Rationale |
|---|---|---|---|
| S0 | Freeze UI-fidelity contract, named validation gates, closed failure enums, `apply_allowed` alias, state primitives, audit schema; define editor-only `vibecomfy.*` classification | **Done.** All items frozen in this doc. | See kickoff blockers 2–8 above for specific locations. |
| S1 | Implement backend spine: turn allocation, idempotency, `agent_generated` loading, raw request/response audit files, port-check-style diagnostics, UI-load-safe derivation; return `queue_allowed: false`; must not overclaim queueability | **Contract frozen.** Implementation deferred to S1. | Contract surfaces defined: Closed Failure Enum (retry/action semantics), Apply-Safety Gates, API shape (success/failure envelopes), Agent Decision Policy. S1 implements against these. No S1/S2 impact — this is the S1 plan. |
| S2 | Durable panel, canvas diff/preview, apply-time dirty checks, native Queue coordination, Undo Last Apply, hash-mismatch UX, browser tests | **Contract frozen.** Implementation deferred to S2. | Contract surfaces defined: Frontend work (16 required capabilities), Frontend decisions (persistent panel, turn history, keyboard, small-window), Node highlight visual values, Closed Failure Enum (`StaleStateMismatch`, `EditorAheadConflict`). No S1/S2 impact — this is the S2 plan. |
| S3 | Hardening: explicit accept/reject endpoints, conflict policies, persistent session restore, audit transitions, concurrency coverage | **Contract frozen.** Implementation deferred to S3. | Contract surfaces defined: Accept/Reject endpoints, Baseline and Concurrency (idempotency, dedup, serialization), Per-Turn Audit (acceptance state transitions). S1/S2 ship request primitives; S3 hardens backend enforcement. |
| S4 | Intent nodes: editor-only status visually unmistakable, queue-blocking references specific node, metadata round-trips through UI JSON and audit | **Contract frozen.** Implementation deferred to S4. | Contract surfaces defined: Intent Node Frontend (status badges, CSS classes, inline edit labels, typed socket labels, intent-level diffing, `properties.vibecomfy` preservation, audit inclusion), Intent Validation and Queueability table. No S1/S2 impact — this is the S4 plan. |
