# M6: Backend Module Boundary Hardening

## Outcome

Clarify backend ownership so orchestration, graph mutation, normalization, session persistence, audit/reporting, and CLI diagnostics do not keep reimplementing the same concepts. The goal is stability and readability, not churn.

Overall plan difficulty: 5/5; selected profile: partnered-5; because backend boundary mistakes can corrupt persisted sessions, graph edits, diagnostics, or public contracts while looking like internal refactors.

## Scope

In scope:

- Target exact backend ownership points:
  - one `response_envelope(...)` owner for canonical outcome, eligibility, hashes, audit refs, and legacy compatibility aliases
  - one `write_chat_artifact(...)` owner for applyable and executor-only chat artifacts
  - one `read_session_artifacts(...)` iterator with formatters for chat, JSON metadata, bundle, CLI, and diagnostics
  - one shared accept/reject/rebaseline action route helper where route validation and idempotency are duplicated
  - one field-change normalizer aligned with the canonical `FieldChange` contract
  - one diagnostics record/status contract for CLI and web consumers
- Consolidate low-level normalizers that encode the same schema in multiple places.
- Align graph edit field-change construction with the canonical `FieldChange` contract from earlier milestones.
- Separate workflow/executor lifecycle from UI/session payload construction.
- Clarify CLI/debug contracts versus browser API contracts.
- Add small tests around extracted boundaries.

Out of scope:

- Replacing the execution engine wholesale.
- Changing Comfy graph mutation behavior.
- Changing model/provider routing.
- Large package moves unless the planner proves they reduce concrete coupling and can be reviewed safely.

## Locked Decisions

- Backend extraction should follow existing domain boundaries, not invent a generic framework.
- Public/session/browser contracts remain backward compatible unless a compatibility path is explicitly removed and tested.
- Audit/debug code may retain richer data than browser payloads, but the boundary must be named.

## Execution Defaults

- Work only on the six named ownership points unless prep proves a seventh is required to complete one of those six. Do not generalize this into package-wide backend cleanup.
- Shared schema constants are hand-written in the canonical contract module unless there is already an active generator for the exact contract. Do not introduce a new generator in this milestone.
- CLI diagnostics use the same durable artifact iterator as audit/reporting, with developer-facing formatting at the final output boundary.
- If extraction is riskier than leaving a duplicate in place, record the exception with caller evidence and a follow-up; do not perform aesthetic extraction.

## Constraints

- Preserve current tests and add focused coverage for moved behavior.
- Keep changes incremental enough for review.
- Do not hide behavior changes inside file moves.

## Done Criteria

- The six targeted backend ownership points have clear owners or documented exceptions.
- Any exception explains why extraction would create more coupling than it removes.
- Duplicate serialization/normalization paths are removed or explicitly documented.
- Session, audit, browser, and CLI contracts have named entry points listed in the backend ownership map.
- Tests prove graph edit, session, audit, and CLI/debug behavior stayed stable.

## Handoff Artifacts

- Backend ownership map for response envelopes, chat artifacts, session artifacts, actions, field changes, and diagnostics.
- Removed duplicate builder/normalizer list.
- Remaining backend compatibility/deletion ledger, if any.

## Touchpoints

- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/comfy_nodes/agent/contracts.py`
- `vibecomfy/comfy_nodes/agent/session_store.py`
- `vibecomfy/comfy_nodes/agent/audit.py`
- `vibecomfy/comfy_nodes/agent/workflow.py`
- `vibecomfy/comfy_nodes/agent/ingest/normalize.py`
- `vibecomfy/comfy_nodes/agent/executor/core.py`
- `vibecomfy/commands/_agent_edit_debug.py`
- Relevant Python tests
