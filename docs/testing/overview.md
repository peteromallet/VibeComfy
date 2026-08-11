# Testing

The VibeComfy test suite has three layers: fast unit tests that run on every push, opt-in RunPod GPU smoke tests, and a snapshot regression channel for the canonical ready-templates. This document is the contract — what runs when, where the gates live, and how to interact with each piece.

## Fast-suite contract

- Runs on every push and pull request via `.github/workflows/ci.yml`.
- Target wall time: under 60 seconds on a fresh GitHub-hosted runner.
- Local equivalent: `uv run pytest -q --tb=no`.
- The CI job fails the merge if any test fails, errors, or unexpectedly passes (`xpassed`).
- No GPU markers run on this path. `-m 'not gpu'` is the default in `pyproject.toml::[tool.pytest.ini_options]`.

## Test-suite scope and the real coverage gap

The repository contains **347** `test_*.py` files (`find tests -name 'test_*.py' | wc -l`). The `make check` gate selects only **20 distinct files** — the 19 files listed in `FAST_PYTEST` plus one oracle node in `tests/test_porting_ui_emitter.py` (`test_layer3_corpus_wide_convert_ui_to_api_gate`) — roughly **5.8%** of the suite. This is the real gap: the fast path is a smoke floor, not full coverage, and the remaining ~94% of test files only run on demand.

- **`make full-pytest`** — the full-suite gate outside `make check`. Runs every collected test (GPU tests excluded via the default `-m 'not gpu'` addopts) parallelized across **8 pytest-xdist workers** (`-n 8 -q -p no:cacheprovider`).
- **Quarantine behavior** — failures whose nodeids are listed in `tests/quarantine/*.txt` (plus the legacy known-failures file) are tolerated baseline failures. The plugin prints `TOLERATED QUARANTINED FAILURES` for them and resets the exit status to 0 when **every** failure is a known-baseline failure. **New failures always gate**: any failed nodeid absent from the quarantine index forces a non-zero exit. The quarantine index is a scoped, owned record — not a skip mechanism — and the full suite is expected to exit 0 modulo that recorded baseline.

## Coverage floor

- Coverage is measured by `pytest-cov` and pinned in `pyproject.toml::[tool.coverage.report] fail_under`.
- **Baseline at the time of this sprint:** 80.21% (`uv run pytest --cov=vibecomfy --cov-report=term -q` reports `TOTAL  10842 stmts / 2146 missed`).
- **Current floor:** **70%** — pinned via `min(70, floor(baseline - 1))`. Because the baseline is already above 70, the floor is capped at the brief's upper bound of 70 rather than tracking `floor(baseline - 1) = 79`.
- **Lift policy:** visibility, not gaming. Raise the floor deliberately when the team is ready to defend the new number; don't fabricate tests to chase a percentage point.
- The gate triggers **only when `--cov` is passed.** `uv run pytest -q` does not enforce coverage; `uv run pytest --cov=vibecomfy -q` does.
- CI runs both: the fast suite for speed, the coverage variant for the gate.

## Snapshot regeneration

- Script: `python -m tools.regenerate_snapshots`. Default mode is `--write`.
- Modes:
  - `--check` — diff committed snapshots against current ready-template output; exit non-zero with a unified diff on drift.
  - `--write` (default) — atomically rewrite the snapshot JSON via `tmp file → os.fsync → Path.replace`.
  - `--filter <glob>` — only act on snapshots whose stem matches the glob.
- CI runs `--check` and **fails on drift** unless the PR opts in to a snapshot update via any of three channels:
  - The commit message contains `snapshots:`
  - The pull-request title contains `snapshots:`
  - The pull-request carries the `snapshots` label
- This three-channel bypass exists so a reviewer can land a legitimate template change without a manual `--check` round-trip but cannot land one accidentally.
- The 9 committed snapshot stems live under `tests/snapshots/<stem>.{api,class_types,widget_values}.json`. `STEM_TO_READY_ID` inside the regenerator carries the `image/`, `edit/`, `video/` prefixes for each stem — auto-inferring from stem is not safe (e.g. `qwen_image_edit` and `flux2_klein_4b_image_edit_distilled` both need the `edit/` prefix).

## RunPod budget cap

- Env var: `VIBECOMFY_RUNPOD_BUDGET_USD` (float). Defaults: **$2** when `--runpod` is passed, **$15** when `--runpod-full` is passed.
- Implementation: `tests/smoke/_runpod_helpers.py::precharge_budget` decrements running cost against the cap before each pod provision. Going over the cap raises `pytest.fail(...)` with the running tally.
- Tally at session end: each `pytest --runpod[ --full]` invocation prints a line of the shape `RunPod spend: $X / $Y` via the `pytest_sessionfinish` hook in `tests/conftest.py`. This is the canonical place to see actual spend after a run.

## Flake retry

- Only the `runpod` and `runpod_full` marker classes retry. The retry policy is one rerun via `pytest-rerunfailures` (declared as a dev dependency in `pyproject.toml`).
- All other tests (the fast suite, parity, snapshot, schema, porting, ready-template, CLI splits, runtime-session splits) **do not retry**. A red unit test is a red unit test.
- Implementation lives in `tests/conftest.py::pytest_collection_modifyitems`: GPU markers get an automatic `pytest.mark.flaky(reruns=1, reruns_delay=10)`. If `pytest-rerunfailures` is not installed, a `warnings.warn(...)` fires and the markers are skipped.

## File-size guidance

The CLI and runtime-session test surfaces grew into god-files mirroring their god-source counterparts; this sprint split them by behaviour.

- `tests/test_cli_*.py` — each file < 500 LOC. The six siblings are:
  - `test_cli_doctor_contract_validate.py`
  - `test_cli_loader.py`
  - `test_cli_misc.py`
  - `test_cli_models_fetch.py`
  - `test_cli_port.py`
  - `test_cli_sources_workflows_nodes.py`
- `tests/test_runtime_session_*.py` — each file < 700 LOC. The five siblings are:
  - `test_runtime_session_config.py`
  - `test_runtime_session_embedded.py`
  - `test_runtime_session_run_untracked.py`
  - `test_runtime_session_server.py`
  - `test_runtime_session_validation.py`
- Shared fixtures and helpers live in `tests/_cli_helpers.py` and `tests/_runtime_session_helpers.py`. New tests should reuse these rather than re-inlining setup.
- When adding behaviour, prefer extending a sibling that already owns that behaviour to inflating any single file past these caps.

## Follow-up — `object_info` snapshot kind (parked)

Real output-spec extraction — i.e. teaching the local schema provider to know not just inputs but also outputs per node class — is the natural next step for richer schema validation. It does not belong in the three existing per-template snapshot kinds (`.api.json`, `.class_types.json`, `.widget_values.json`). Track it as a new fourth snapshot kind sourced from a ComfyUI `/object_info` dump and gate the regenerator behind a `--with-object-info` flag when it lands. Not in scope this sprint; deliberately parked so the existing three-channel snapshot contract stays focused.

## Where snapshots live

- `tests/snapshots/<stem>.{api,class_types,widget_values}.json` — the curated 9-template registry, driven by `STEM_TO_READY_ID` in `tools.regenerate_snapshots`.
- Sibling `<recipe>.snapshot.json` — frozen compile output for user recipes (one file per recipe, next to the recipe).
- Both routes use the same canonicalizer (`vibecomfy.testing.snapshot.canonicalize_api`). One source of truth; users and the in-repo regenerator share the contract.
- For the user-facing walkthrough, see [`user_code.md`](user_code.md).
