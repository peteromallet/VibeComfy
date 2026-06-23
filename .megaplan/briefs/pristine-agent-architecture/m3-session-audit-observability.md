# M3: Session, Audit, And Observability Boundary

## Outcome

Make raw evidence explicit. Normal chat/session payloads contain only safe transcript, details, stage, and candidate data; raw diagnostics, artifact paths, model traces, audit JSON, provider payloads, and issue-report evidence are available only through explicit audit/debug surfaces.

Overall plan difficulty: 5/5; selected profile: partnered-5; because privacy, path leakage, and diagnostic leakage can regress without obvious test failures.

## Scope

In scope:

- Trace session store reads/writes, chat rehydrate payloads, issue report generation, audit downloads, diagnostics reporting, and CLI debug commands.
- Strip host filesystem paths and raw artifact locations from normal UI-facing payloads.
- Preserve explicit audit/debug/download flows with stable identifiers or relative bundle paths.
- Define a clear boundary between:
  - `TranscriptMessage`
  - `ResponseDetail`
  - `ExecutionEvent`
  - `AuditArtifact`
- Sanitize user-facing error/failure messages while retaining raw diagnostic context in audit surfaces.
- Add an explicit schema version to issue report bundles.
- Add regression tests for session rehydrate and report/debug boundaries.

Out of scope:

- Removing audit artifacts.
- Changing the agent execution engine.
- Replacing the full session storage format.

## Locked Decisions

- Raw audit details are allowed only through explicit debug/report/download actions.
- Normal browser payloads use stable ids and safe summaries, not absolute paths.
- User-facing failures are concise and sanitized; diagnostic detail is attached separately.

## Execution Defaults

- Existing session JSON is handled by read-time projection first. Add a migration only if a read-time projection cannot preserve replay behavior or produces untestable branching.
- CLI outputs may keep raw paths only for local developer commands explicitly documented as developer-facing. Browser payloads and shareable reports never expose absolute host paths.
- Issue report bundles get an explicit schema version in this milestone, even if the rest of the structure remains compatible.

## Constraints

- Existing debug and audit workflows must keep working.
- Do not make evidence harder to retrieve for developer investigations.
- Do not break current saved-session replay where compatibility can be maintained with projections.

## Done Criteria

- Normal chat/session rehydrate payloads do not expose raw execution internals or absolute local paths.
- Audit/download/report paths still expose necessary evidence through explicit actions.
- Tests use sentinel internal strings and path-like values to prove the boundary.
- Any compatibility behavior is documented with a deletion path.
- Issue report bundle schema versioning is implemented and covered by tests.

## Touchpoints

- `vibecomfy/comfy_nodes/agent/session_store.py`
- `vibecomfy/comfy_nodes/agent/audit.py`
- `vibecomfy/comfy_nodes/agent/edit.py`
- `vibecomfy/commands/_agent_edit_debug.py`
- `vibecomfy/comfy_nodes/web/diagnostics_reporting.js`
- `vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js`
- Browser and Python tests for chat/session/debug flows
