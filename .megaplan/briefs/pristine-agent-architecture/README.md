# Pristine Agent Architecture Epic

Last updated: 2026-06-23

This epic turns the current cleanup findings into an ordered Megaplan chain. It is deliberately aggressive: the target is not only to remove the visible `Turn 1 / working` leak, but to make the underlying agent panel architecture structurally unable to confuse user-facing transcript, progress, preview/apply state, and internal audit data.

## Prep Decision

Overall plan difficulty: 5/5; selected profile: partnered-5; because a bad plan can preserve leaky internal/user-facing boundaries while still passing local UI tests.

Planning complexity: full for each milestone, with prep enabled. Each sprint has enough cross-module surface area that a visible prep phase is worth the cost, but the risk does not justify `thorough` unless a milestone struggles.

Depth: high for each milestone. The planner needs substantial repository reading and structural reasoning across frontend state, backend contracts, session persistence, audit paths, and tests.

## Existing Prepared Plan

The already-prepared Megaplan is:

- `.megaplan/briefs/messaging-boundary-cleanup.md`
- initialized plan state in the worktree: `/Users/peteromalley/Documents/.megaplan-worktrees/messaging-boundary-cleanup/.megaplan/plans/messaging-boundary-cleanup/state.json`
- worktree: `/Users/peteromalley/Documents/.megaplan-worktrees/messaging-boundary-cleanup`
- status from that worktree: `initialized`, next step `plan`, lock file present but not held

This epic makes that work milestone 2 rather than replacing it. The existing brief is still the source for the messaging-boundary sprint.

## Source Material

The cleanup backlog is `cleanup.md`. It consolidates the Codex review, the DeepSeek swarm findings, redundancy waves, and system-level smell domains. The milestone briefs below are derived from that backlog and the existing messaging-boundary brief.

Related existing epics that should be treated as context, not substitutes:

- `.megaplan/briefs/agent-routing-end-state/chain.yaml`
- `.megaplan/briefs/gremlin-cleanup/chain.yaml`
- `.megaplan/briefs/structural-decomposition/chain.yaml`

## Canonical Vocabulary

Use this vocabulary throughout the epic. Do not introduce parallel names. If existing code already uses another term, keep it behind an adapter or compatibility ledger entry with an owner and deletion trigger.

- `TranscriptMessage`: durable user-visible conversation entry.
- `ResponseDetail`: safe expandable details for a user-visible response.
- `ExecutionEvent`: internal progress/debug/audit event; never normal renderer input.
- `AuditArtifact`: explicit debug/download/report evidence.
- `StageSnapshot`: user-facing progress/stage projection derived from execution state.
- `ApplyCandidate`: preview/apply proposal, diff summary, eligibility, and lifecycle.
- `FieldChange`: canonical typed graph/content change.
- `ProviderStatus` and `RouteStatus`: provider availability and UI route readiness, kept distinct.
- `FailureEnvelope`: sanitized user-facing failure plus structured diagnostic references.
- `SessionArtifact`: durable storage artifact with explicit formatter/projection boundaries.

## Data-Flow Law

Normal renderers may consume only safe view models and selectors. Raw `batch_turns`, `debug`, `audit`, `canonical_activity.details`, raw provider payloads, exception text, absolute paths, model prompts/responses, and session JSON must cross a named projection, boundary normalizer, or explicit audit/debug adapter before any UI sees them.

Compatibility aliases are output-only. They may be emitted by named legacy adapters and consumed by boundary normalizers, but they must not become new canonical inputs for renderers, reducers, or backend business logic.

## Ambiguity Rules

- If a brief says to choose a canonical owner, the default is to create the smallest named owner module/function that can be tested directly. Do not leave ownership implicit in comments.
- If compatibility is retained, it must be listed in the compatibility ledger with owner, caller evidence, fixture coverage, and deletion trigger in the same milestone.
- If an old path cannot be deleted safely, add a failing-when-removed fixture or explicit caller evidence. Otherwise delete it.
- If a renderer needs data not present in a safe view model, extend the view model. Do not let the renderer read raw wire/session/debug fields.
- If prep discovers a milestone exceeds two weeks, stop at the declared handoff artifact and record the remaining work as a follow-up brief rather than expanding scope.

## Fixed Implementation Defaults

- Backend canonical contract builders start in `vibecomfy/comfy_nodes/agent/contracts.py`. Create a new narrow backend module only if using `contracts.py` would create a real import cycle or mix browser/session/audit ownership.
- Frontend wire normalization lives in `vibecomfy/comfy_nodes/web/agent_contracts.js`. Render modules consume selectors/view models from this boundary, not raw wire payloads.
- The final architecture note lives at `docs/architecture/agent_panel.md`.
- The artifact manifest lives at `docs/architecture/ARTIFACTS.md`.
- The compatibility ledger lives at `docs/architecture/compatibility-ledger.md`.
- `cleanup.md` is planning scratch. M7 must fold still-relevant content into the architecture note, artifact manifest, or compatibility ledger, then remove or relocate the root file.
- Issue report bundles get an explicit schema version in M3, even if their structure otherwise remains compatible.

## Milestones

1. Canonical contracts and view models: lock `StageSnapshot`, `ApplyCandidate`, `FieldChange`, identity, compatibility adapters, and failure/provider surfaces.
2. Messaging boundary cleanup: split durable chat from internal execution events using the canonical contracts.
3. Session, audit, and observability boundary: keep raw evidence explicit and out of normal UI payloads.
4. Frontend selector and render boundary: make thread/detail/candidate rendering selector-driven and raw-data-blind.
5. Frontend module and poller decomposition: make `vibecomfy_roundtrip.js` an orchestration shell and remove duplicated renderers/pollers.
6. Backend/module boundary hardening: create concrete owners for response envelopes, chat artifacts, session iteration, action routes, field-change normalization, and diagnostics contracts.
7. Guardrails, tests, and artifact hygiene: add regression coverage, cleanup policies, architecture notes, and artifact policy.

## Start Command

Do not start this automatically just because the files exist. When ready:

```bash
python -m arnold.pipelines.megaplan chain start --spec .megaplan/briefs/pristine-agent-architecture/chain.yaml
```

For a single inspected step:

```bash
python -m arnold.pipelines.megaplan chain start --spec .megaplan/briefs/pristine-agent-architecture/chain.yaml --one
```
