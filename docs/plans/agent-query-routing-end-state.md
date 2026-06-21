# Agent Query Routing End State

This document records the implemented route contract for the embedded
VibeComfy executor and the browser-facing agent submit surface.

## Public Route Vocabulary

Serialized executor output uses exactly four canonical routes:

- `clarify`: ask a clarifying question or respond without editing.
- `inspect`: inspect or explain the current graph without editing.
- `revise`: revise the current graph using local context only.
- `adapt`: research or adapt a precedent before revising the graph.

The empty route string remains an internal input sentinel for classifier results
that omit the route and should be derived from legacy booleans. It is not a
public output route. `AgentTurnResult` clamps any non-public output route to
`clarify`, so legacy labels are never serialized as response routes.

## Input-Only Legacy Aliases

During the migration window, classifier output may still contain legacy route
names. These names are accepted only as input aliases and are normalized before
serialization:

| Legacy input route | Canonical output route |
| --- | --- |
| `inspect_only` | `inspect` |
| `direct_edit` | `revise` |
| `diagnose_repair` | `revise` |
| `precedent_research` | `adapt` |
| `asset_lookup` with research and implementation | `adapt` |
| `asset_lookup` with implementation only | `revise` |
| `asset_lookup` without implementation | `clarify` |
| `subgraph_preview` with research and implementation | `adapt` |
| `subgraph_preview` with implementation only | `revise` |
| `subgraph_preview` without implementation | `clarify` |

Static aliases log an informational normalization event with the legacy route
and normalized route. Context-dependent aliases also log the legacy route,
normalized route, legacy intent, and task. The current policy is compatibility
without public-route leakage: aliases remain input-only, and future removal
should be handled by a separate sunset decision and release note.

## Unknown Explicit Routes

Unknown non-empty explicit routes fail closed to `clarify`. The implementation
logs a warning containing the requested route and normalized route, then proceeds
with the canonical `clarify` route. Unknown routes do not produce candidates,
do not become applyable, and serialize with `apply_eligible: false` and a stable
non-applyable/no-candidate reason.

This fail-closed behavior is intentional: the executor must not silently expose
new route vocabulary through public responses before the contract is updated.

## Response Envelope

The canonical executor response envelope includes:

- `route`
- `reply`
- `evidence`
- `candidate`
- `apply_eligible`
- `no_candidate_reason`

`apply_eligible` is computed by the backend. It is true only when the canonical
route is one of `revise` or `adapt` and a candidate graph exists. `clarify` and
`inspect` turns are never applyable, even if legacy booleans or compatibility
fields might otherwise suggest an edit path. The frontend must gate Apply/Reject
on `apply_eligible` plus candidate presence, not on route strings.

## Submit And Compatibility Paths

The canonical submit endpoint is:

- `POST /vibecomfy/agent-executor`

The browser submit flow posts to `/vibecomfy/agent-executor`. The legacy submit
endpoint remains available as a compatibility wrapper:

- `POST /vibecomfy/agent-edit`

Both submit endpoints delegate to the same executor adapter, so they share
request parsing, route normalization, response serialization, and apply
eligibility behavior. The legacy submit path should be treated as compatible
but not the preferred path for new browser code.

The existing action and session endpoints under `/vibecomfy/agent-edit/*` remain
stable and are not part of the submit-path replacement:

- `POST /vibecomfy/agent-edit/accept`
- `POST /vibecomfy/agent-edit/reject`
- `POST /vibecomfy/agent-edit/rebaseline`
- `GET /vibecomfy/agent-edit/chat`
- `GET /vibecomfy/agent-edit/session-bundle`
- `GET /vibecomfy/agent-edit/session-json`
- `POST /vibecomfy/agent-edit/rating`

These endpoints keep their action/session roles while query submit converges on
the executor endpoint.

## Deprecation Policy

Current implemented policy:

- Legacy route names are tolerated only as input aliases.
- Public serialized routes remain canonical.
- Alias use is logged.
- Unknown explicit routes fail closed instead of being passed through.
- `/vibecomfy/agent-edit` submit remains a compatibility wrapper for now.
- `/vibecomfy/agent-edit/*` action and session endpoints remain preserved.

Open sunset decisions remain outside this batch: when to remove individual
legacy route aliases, and whether `/vibecomfy/agent-edit` submit should begin
emitting a deprecation warning before removal. Until those decisions are made,
docs and tests should describe the implemented state above rather than imply a
removal date.
