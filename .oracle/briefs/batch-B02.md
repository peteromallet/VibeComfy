# Megado B02 — `sources=` tier gating

Worktree: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-info-oracle
Branch: oracle-info-run. Python: 3.11.11; run tests with
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/.venv/bin/python -m pytest ...`
(the worktree `.venv` is incomplete; the oracle-worktree venv has arnold + pytest 9.0.3).

## Context

You are implementing batch B02 of the informational-research path. B01 (commit
`317a3cdf`) is done: `vibecomfy/executor/hivemind_clients.py` has
`_default_hivemind_messages_client` (returns `{"results": [...]}`) and
`_default_hivemind_client` (workflow, unchanged), plus `_run_hivemind_messages_research`,
`format_community_summary`, re-exports from `research.py`.

Read `docs/plans/agent-judgment-iteration.md` section "2. sources= tier gating"
and the B02 section of `.oracle/tasklist.md` before coding.

HARD CONSTRAINT (user ruling, 2026-08-12): NO deterministic loops or actions —
no term expansion, no scoring, no thresholds, no latches, no early-stop. This
batch only adds tier selection plumbing. Do NOT create `research_iteration.py`.

## Target (B02 tasks 1-6, from tasklist)

1. Extend `vibecomfy/executor/research.py::research` additively:
   `sources: tuple[str, ...] | None = None` and `hivemind_messages_client` param.
2. Implement `run_workflows`, `run_messages`, `run_web`, `run_registry` booleans
   exactly from `sources`:
   - `sources is None` (legacy public API) → messages OFF, keep today's behavior
     (workflows on, web on, registry on, local on — verify what research() does today).
   - `sources=("messages",)` → ONLY messages tier; local_limit=0, no workflow
     Hivemind, no web, no registry.
   - `sources=("workflows",)` → workflow Hivemind + local; no web/registry/messages
     (per tasklist: "null default web/registry unless listed" — explicit tuple
     nulls unlisted tiers).
   - `sources=("messages","web")` → messages + web only.
   - Verify exact semantics against the design doc; do NOT union.
3. Wire `_run_hivemind_messages_research` only when run_messages is True; pass the
   injectable `hivemind_messages_client` (default `_default_hivemind_messages_client`).
4. `VIBECOMFY_MESSAGES_RESEARCH=0` env kill switch: messages client skipped with
   warning "messages tier disabled".
5. `vibecomfy/porting/edit/_resolve.py::_resolve_query_statement`: split clients —
   `"messages"` in sources → `research_module._default_hivemind_messages_client`;
   `"workflows"` → `research_module._default_hivemind_client`. Omitted-source
   default STAYS `("workflows",)` in this batch (B03 changes it). Pass the resolved
   sources tuple into `research(..., sources=...)`.
6. Tests: extend `tests/test_executor_research.py` and
   `tests/test_porting_edit_resolve.py` for the tier matrix:
   - messages-only invokes the messages fake once with the unchanged user query,
     no workflow/web/registry/local.
   - public `research("Hotshot XL")` (sources=None) does not invoke messages client.
   - explicit messages/web combination runs exactly those tiers.
   - env kill switch test.
   - existing invalid-explicit-source diagnostics unchanged.

## Non-goals (do not touch)

- Omit-default change (B03) — `requested_sources or ("workflows",)` stays.
- Followup text, memory persistence, community_summary on ResearchResult (B03).
- Hoist / _run_reply (B04).
- No changes to `_default_hivemind_client` workflow behavior/URL.
- No deterministic-loop machinery.

## Acceptance (oracle will verify)

- Targeted: `pytest tests/test_executor_research.py tests/test_porting_edit_resolve.py -q` passes.
- `sources=("messages",)` invokes the messages fake once with the original query,
  and NO workflow/web/registry/local tier runs.
- Public `research("Hotshot XL")` never touches the messages client.
- REPL omission still resolves to `("workflows",)`.
- Invalid explicit sources diagnostics unchanged.
- No expansion, scoring, latch, retry-by-evidence, network-call-cap artifacts.

## Workflow

Implement, run targeted tests (use the oracle venv python above; targeted files
only — do NOT run the full suite, it takes ~1.5h), iterate until green, commit:
`git add -A && git commit -m "megado B02: sources= tier gating in research() + _resolve client split"`.
Report: files changed, test counts, deviations.
