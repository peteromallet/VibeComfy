# Corrective Verification Evidence — 2026-07-10

## Final independent validation

Commit under test: `9bc855e` with the three intentional E2E implementation
edits listed by `git status`.

The corrective acceptance surface was not available in this checkout:
`make corrective-trust-gate`, `tests/corrective_gate_inventory.json`, the gate
driver, and a unified manifest do not exist. Therefore this note does not claim
canonical-gate acceptance.

The separate Corrective 2 command was run once:

```text
PATH="$PWD/.venv/bin:$PATH" python -m pytest -q --tb=short tests/test_comfy_nodes_agent_edit.py
```

It collected 402 tests: 391 passed and the following 11 failed. Pytest reported
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

No passing corrective inventory exists, and a temporary exact-ID audit found
none of these nodes in `tests/quarantine/*.txt`. The audit script was deleted
after execution.

`make check` failed at its initial `root-clean` guard because the earlier E2E
launcher left `vendor/ComfyUI`. `make clean` removed ordinary artifacts but not
that runtime root. After explicitly removing the generated `vendor/` root,
`make post-root-clean` and `git diff --check` passed; no ComfyUI, Playwright, or
Chromium process or generated runtime root remained.

The three earlier E2E result sets each contained one expected Chromium test,
zero skipped/unexpected/flaky tests, and two parseable geometry attachments.
However, every native `results.json` contained six absolute workspace-path
references. Those artifacts were removed by `make clean`, but their sanitation
failure prevents a trust-gate pass.

Remediation: implement the missing locked inventory, fail-closed driver, Make
target, and unified manifest; sanitize native Playwright result paths before
publication; make launcher/cleanup ownership of generated `vendor/ComfyUI`
certain; then rerun the canonical gate and this independent validation.
