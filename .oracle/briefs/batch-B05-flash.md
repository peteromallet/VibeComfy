# B05 — Profiles, report, profiler, events (Flash)

Worktree: /private/tmp/vc-twostep (branch two-step-megado). Python: `PYENV_VERSION=3.11.11`, venv at /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv, `PYTHONPATH=$PWD` if needed.

You are implementing batch B05 (Flash, no XHARD). B01–B04 land before you start; verify
with `git log --oneline -6` that B01 (f5a45561) is present and B02–B04 commits exist
before you begin. Do not start B06.

## Tasks

1. `vibecomfy/executor/profiles.py`:
   - Split `DECLARED_STAGES` into `REQUIRED_STAGES` (classify, research, implement, reply)
     and `ALLOWED_STAGES` (+ execute) — see profiles.py:28/108/225. Validation currently
     requires exact equality; change to: all required present, extras must be in ALLOWED.
   - Add typed `MissingProfileStageError`.
   - Resolve `execute` ONLY for two-step mode; NEVER fall back to `implement`.
   - `core._resolve_spec()` must preserve the typed error (currently wraps profile failures
     in generic ValueError — fix so MissingProfileStageError survives).
   - Fix stale Arnold comments in `profiles.py` + `profile_data/__init__.py` (packaged
     TOMLs are the sole runtime authority; no external Arnold mirror in this batch).

2. Add explicit `execute` specs to `profile_data/{default,openai,openrouter,anthropic,
   opensource}.toml` (same provider/model family as `implement` for each profile, or a
   sensible two-step default).

3. `Report` (`executor/contracts.py`):
   - Always serialize resolved `pipeline_mode` (including `"full"`) — intentional additive
     schema change; update report fixtures intentionally.
   - Add optional `execute` report ONLY for two-step: session identity, route, budget
     usage, tool/evidence IDs, accepted delta IDs, claim validation, replacement use,
     self-assessment.
   - Top-level executor envelope unchanged.

4. Profiler (`executor/profiler.py` + core request/result records):
   - Add `pipeline_mode` to request/result records.
   - One `phase="execute"` span with continuation/tool/budget counters.
   - Preserve existing full-mode phase spans.

5. Events:
   - Add `execute` start/working/done/error/skipped for two-step (use canonical
     `done`/`error` statuses, NOT completed/failed).
   - Frontend `comfy_nodes/web/executor_progress.js:29` — add `execute` to the phase list;
     keep existing statuses.
   - Backend event payload construction at `core.py:1663` — add execute events without
     touching full-mode payload bytes.
   - `tests/browser/payload_contracts.test.mjs:1177` — add the execute phase to fixture
     enumeration.
   - New fixture `tests/fixtures/payload_contracts/websocket_executor_phase_execute.json`.
   - **Full-mode websocket event payloads must be byte-identical** — assert with a
     fixture-level comparison against the pre-change JSON.

6. Tests:
   - `tests/test_executor_profiles.py`
   - `tests/test_executor_two_step_reporting.py`
   - Event cases in `tests/test_executor_flows.py`
   - Response fixture coverage in `tests/test_agent_executor_response.py`

## Acceptance gate

```bash
python -m pytest -q \
  tests/test_executor_profiles.py \
  tests/test_executor_two_step_reporting.py \
  tests/test_executor_flows.py \
  tests/test_agent_executor_response.py \
  tests/test_agent_executor_durable.py
node --test tests/browser/...   # or make browser-contracts if that's the repo convention
```

Fixture-level assertion: full-mode phase events byte-identical to pre-change JSON.

## Constraints
- Commit ONLY this batch's scope: `git add -A && git commit -m "B05: profiles/report/profiler/events for two-step"`.
- Do not start B06 work.
- Report: files changed, gate output, deviations.
