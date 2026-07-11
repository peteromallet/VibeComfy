# Corrective Verification Evidence — 2026-07-10

## Canonical corrective gate

The missing acceptance surface was restored and run from commit
`a9b2add2dbfa1485f06875323bb71b7a1e1c8a2a` plus the intentional gate repair
awaiting commit. The command was:

```text
make corrective-trust-gate
```

The locked inventory and complete quarantine hash set passed. The unified
manifest recorded:

- Python: 64 collected, 64 passed, exit 0.
- Node: 675 collected, 675 passed, exit 0.
- Playwright: one real Chromium test, one expected, zero skipped, unexpected,
  or flaky results, exit 0.
- Launcher: `E2E_PASSED` after real ComfyUI readiness, two real submits, geometry
  capture, and certain teardown.

The sanitized manifest is
`test-results/corrective-trust-gate/manifest.json` with SHA-256
`79da340e0594257f3071bfd7ec80d141d310b388dccc1f67a53debb050f6ff13`.
The locked inventory SHA-256 is
`7fdb5df649b80f0387e7951b867c9f12ff9bf3e6883eabcdb7da615b93430390`.
An exact repository-root search across the retained gate artifacts found no
absolute workspace path. Native Playwright `results.json` is recursively
sanitized before publication, and the bundled HTML viewer is retained only for
failed Playwright runs.

## Separate Corrective 2 boundary

The separate, intentionally non-gating Corrective 2 command was rerun after the
canonical gate:

```text
PATH="$PWD/.venv/bin:$PATH" python -m pytest -q --tb=short tests/test_comfy_nodes_agent_edit.py
```

It again collected 402 tests: 391 passed and the same 11 failed. Pytest reported
all 11 as new failures outside quarantine:

- `tests/test_comfy_nodes_agent_edit.py::test_agent_edit_batch_empty_model_response_retries_once_then_commits`
- `tests/test_comfy_nodes_agent_edit.py::test_batch_repl_code_task_prefetches_vibecomfy_exec_signature`
- `tests/test_comfy_nodes_agent_edit.py::test_flag_off_dev_delta_stage_order_and_prompt_unchanged`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_clarify_after_edit_returns_edit_and_clarify_outcome`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_runs_bounded_loop_with_turn0_render_then_diff_feedback`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_batch_repl_turn0_catalog_is_scoped_and_search_first`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_dev_delta_uses_delta_stage_sequence_without_authoring_pipeline`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_research_route_writes_agentic_messages_and_blocks_apply`
- `tests/test_comfy_nodes_agent_edit.py::test_handle_agent_edit_you_decide_pil_code_node_uses_classifier_summary_to_attempt_provider`
- `tests/test_comfy_nodes_agent_edit.py::test_rejected_terminal_clarify_after_partial_edit_fails_fast`
- `tests/test_comfy_nodes_agent_edit.py::test_rejected_terminal_clarify_is_durable_budget_failure`

These node IDs remain visibly reproducible and are neither quarantined nor
included in the passing corrective inventory.

## Cleanup and remediation behavior

The launcher removed its generated ComfyUI shim and runtime root. No ComfyUI,
Playwright, Chromium, or chain-runner process remained after the gate.
`make post-root-clean` and `git diff --check` passed. Wrong-runner inventory,
quarantine drift, missing tools/files, timeout, nonzero exit, zero collection,
malformed native output, skipped/unexpected/flaky Playwright results, and
unsanitizable Playwright JSON all fail the corrective gate with remediation in
the unified manifest.
