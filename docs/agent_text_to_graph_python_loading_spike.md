# Python-Loading Spike: Keep/Kill Decision

**Status:** KEEP — agent-edited Python loading through the AST-gated restricted path.

**Date:** 2026-06-01
**Decision owner:** S0 Contract Freeze
**Linked from:** [`agent_text_to_graph_mvp.md`](./agent_text_to_graph_mvp.md#python-loading-derisk-spike)

## Summary

A focused derisking spike was run against the S0 model-authored Python boundary. The
spike implemented a restricted loader that AST-parses agent-generated Python before
execution, fed it 12 hostile bypass fixtures and one representative benign scratchpad
fixture, wired it into the `agent_edit.py` proof path, and proved that the 64
checked-in ready templates all pass the same scan. The spike answered its kill
criterion decisively: **useful generated templates load through the AST-gated path
without opening a broad Python execution surface.**

## Evidence

### Fixture Coverage

**15 hostile/corner-case fixtures** were created under
`tests/fixtures/agent_generated_loader/`. Each hostile fixture was tested through
both `scan_agent_generated_python()` (pure scan) and
`load_agent_generated_scratchpad()` (full load path including gate interaction).
Every rejection stayed in the `load_python` phase, produced zero gate audit entries,
and the module-level file-write canary was never created.

| Fixture | Bypass class | Expected rejection code(s) | Rejected pre-execution |
|---|---|---|---|
| `command_execution.py` | `__import__("os").system("true")` | `forbidden_call` | ✓ |
| `hidden_import.py` | `from os import system` through a hidden alias | `forbidden_import` | ✓ |
| `encoded_import_trick.py` | `getattr(__builtins__, "__import__")("os")` | `forbidden_call`, `forbidden_name` | ✓ |
| `dunder_traversal.py` | `(1).__class__.__mro__` dunder traversal | `dunder_access` | ✓ |
| `file_read.py` | `open("/etc/passwd")` file read | `forbidden_call` | ✓ |
| `network_call.py` | `import urllib.request` network import | `forbidden_import` | ✓ |
| `socket_call.py` | `import socket` socket import | `forbidden_import` | ✓ |
| `subprocess_call.py` | `import subprocess` subprocess import | `forbidden_import` | ✓ |
| `env_read.py` | `import os.environ` environment import | `forbidden_import` | ✓ |
| `dynamic_attribute_access.py` | `getattr(obj, attr_name)` dynamic access | `forbidden_call` | ✓ |
| `huge_payload.py` | Oversized source (131KB+ with 128B limit) | `source_too_large` | ✓ |
| `malformed_syntax.txt` | Invalid Python syntax | `syntax_error` | ✓ |
| `module_side_effect_canary.py` | Module-level `open().write()` | `forbidden_call` | ✓ |

All 13 hostile fixtures were tested through `load_agent_generated_scratchpad()`
(not just scan), confirming no execution occurs before rejection.

### Benign-Template Coverage

**One representative benign fixture:** `tests/fixtures/agent_generated_loader/benign_scratchpad.py`
matching the generated template style (header comment, `_node` helper, three
connected nodes: LoadImage → PreviewImage / SaveImage). The fixture:

- Passes `scan_agent_generated_python()` with zero failures.
- Loads through `load_agent_generated_scratchpad()` into a validating `VibeWorkflow`.
- Every created node carries `agent_generated` provenance.
- `VibeWorkflow.confirm_node()` is a no-op for every node (provenance stays `agent_generated`).
- The gate audit log shows `scratchpad_exec` with `agent_generated` provenance and `add_node` entries also carrying `agent_generated`.

**Ready-template bulk scan:** All 64 checked-in `ready_templates/*.py` files were
scanned with `scan_agent_generated_python()`. Result: **0 failures.** Every current
generated template passes the AST policy.

### Agent-Edit Path Proof

The `agent_edit.py` proof path was updated (T6) to call
`load_agent_generated_scratchpad()` instead of the old
`load_scratchpad(..., provenance_override="user_confirmed")` bypass. Focused tests
(T7) prove:

- Model-edited Python loaded through the agent-edit path carries `agent_generated`
  provenance on every node, never `user_confirmed`.
- `confirm()` and `confirm_node()` are no-ops on agent-generated nodes.
- Hostile model output (command execution via `os.system`) raises
  `AgentGeneratedLoadError` in the `load_python` phase.
- Hostile module-level canary file-write is rejected before execution; the canary
  file is never created.
- All 9 hostile bypass classes (file_read, hidden_import, dunder_traversal,
  encoded_import_trick, network_call, socket_call, subprocess_call, env_read,
  dynamic_attribute_access) are rejected through the agent-edit path.
- Malformed Python syntax from the model is caught in `load_python` with
  `syntax_error` code.

### Provenance Contract

The `agent_generated` provenance literal (T1/T2) is:

- **Non-promotable:** `confirm()` and `VibeWorkflow.confirm_node()` keep it as `agent_generated`.
- **Gate-allowed:** The headless gate accepts `agent_generated` for all side-effecting
  capability sets (same as `agent_authored` and `user_confirmed`).
- **Restricted minting:** Only `agent_generated_loader.py` may mint this provenance.
  No other loader (scratchpad, ready-template, workflow_from_file, ingest) exposes a
  path to `agent_generated`.

23 parametrized provenance/gate tests prove these invariants. A deliberate
mutation test confirmed that a promotion regression or gate rejection would be
caught.

## AST Policy Summary

The restricted loader (`vibecomfy/security/agent_generated_loader.py`) applies
these checks before any `exec()`:

| Check | Mechanism |
|---|---|
| Source size | Max 1MB UTF-8 bytes before parsing |
| Syntax validity | `ast.parse()` with SyntaxError → `load_python` failure |
| AST node count | Max 50,000 nodes after parsing |
| Forbidden node types | No ClassDef, Lambda, Try, Raise, Yield, AsyncFunctionDef, Await, Global, Nonlocal, Delete |
| Import allow-list | Only `__future__`, `vibecomfy.handles`, `vibecomfy.templates`, `vibecomfy.workflow`, and specific `vibecomfy.patches.*` / `vibecomfy.nodes.*` |
| Forbidden module roots | `os`, `sys`, `subprocess`, `socket`, `importlib`, `inspect`, `ctypes`, `pathlib`, `shutil`, `tempfile`, `http`, `urllib`, `requests`, `ftplib`, `ssl`, `asyncio`, `multiprocessing`, `glob`, `builtins` |
| Forbidden names | `eval`, `exec`, `compile`, `__import__`, `open`, `getattr`, `setattr`, `delattr`, `globals`, `locals`, `vars`, `dir`, `breakpoint`, `__builtins__`, `input` |
| Forbidden call attrs | `run`, `spawn`, `open`, `read`, `write`, `download`, `send`, `request`, `exec_module`, `glob`, `iterdir`, `walk`, `mkdir`, `rmdir`, `remove`, `unlink`, `rename`, `replace`, `chmod`, `chown`, `exists`, `resolve`, `expanduser`, `read_text`, `write_text`, `read_bytes`, `write_bytes`, `delete` |
| Dunder access | No attribute starting with `__` except `__file__` and `__name__` |
| Relative imports | Rejected |
| Wildcard imports | Rejected |
| Dunder names in imports | Rejected |

After scanning, the loader calls `require_confirmation(operation="scratchpad_exec",
provenance="agent_generated", capabilities={"code_exec"})` through the gate, sets
`requesting_provenance` to `agent_generated`, and executes the scanned code in a
fresh module namespace. It then calls `build()` and verifies the result is a
`VibeWorkflow`.

## Residual Risk

The spike is definitive for the current bypass classes but acknowledges residual
risk that must be managed in S1 and beyond:

1. **Deny-list architecture.** The policy is largely deny-list based (forbidden
   modules, names, call attrs, node types). A novel bypass technique not covered
   by the current deny lists could slip through. The import allow-list is the
   primary structural defense; new `vibecomfy.nodes.*` modules could expose
   dangerous callables if not reviewed.

2. **Static analysis only.** There is no runtime sandbox (seccomp, restricted
   subinterpreter, or capability-dropping). The AST scan is the sole defense
   between model output and execution. A sufficiently sophisticated model output
   exploiting a parser-level ambiguity or a missed code path could execute.

3. **`vibecomfy.nodes.*` is prefix-allowed.** Any module under the
   `vibecomfy.nodes.` prefix can be imported. If a future package adds a
   dangerous importable symbol under that prefix, the policy would allow it.

4. **No behavioral analysis.** The policy does not analyze what the generated
   code *does* at runtime — only what it *imports and calls*. A generated
   template could, in theory, call `vibecomfy.templates.node()` a million times
   in a loop. Size limits provide partial defense.

5. **Model prompt injection.** The system prompt instructs the model to avoid
   dangerous operations, but a determined adversarial prompt embedded in the
   user's task could override this. The AST gate is the enforcement layer; the
   system prompt is guidance only.

6. **Narrow test coverage of generated template shapes.** The benign fixture
   covers the common 3-node pattern (LoadImage → PreviewImage / SaveImage).
   Complex generated templates with many nodes, custom helpers, or edge cases in
   `_node()` usage may exercise code paths not covered by the fixture.

## Mitigations in Place

- **Agent-edit path wired:** `agent_edit.py` now uses the restricted loader
  exclusively. There is no remaining path that loads model-edited Python as
  `user_confirmed`.
- **Gate audit trail:** Every `scratchpad_exec` and `add_node` operation is
  recorded with the `agent_generated` provenance tag, making the trust boundary
  auditable.
- **Canary test:** The module-level file-write canary test proves that hostile
  code is never executed; the rejection happens at the AST scan stage.
- **Bulk ready-template scan:** All 64 ready templates pass, confirming the
  policy is not too restrictive for real use.

## Decision: KEEP

**The spike proved that useful generated templates load through the AST-gated
path without opening a broad Python execution surface.**

The model-edited Python loading path is viable for S1. The restricted loader
rejects all 12 hostile bypass classes before execution, the benign template
fixture loads and validates, and all 64 checked-in ready templates pass the same
scan. The agent-edit proof path is correctly wired to the restricted loader, and
the provenance contract ensures model-authored code can never be silently promoted
to `user_confirmed`.

### What changes from the pre-spike design

- The old `load_scratchpad(..., provenance_override="user_confirmed")` bypass in
  `agent_edit.py` is **removed** and replaced with
  `load_agent_generated_scratchpad()`.
- Python remains the primary edit substrate for S1.
- The S1 fallback (structured IR patch/edit operations) is **not needed** for
  S0. The Python-loading path is proven safe enough to keep as the primary
  mutation contract.

### What must be monitored in S1

1. Add new hostile bypass classes as the agent model improves.
2. Review new `vibecomfy.nodes.*` imports for dangerous surface expansion.
3. Consider runtime sandboxing if the AST policy shows gaps in production.
4. Expand benign fixture coverage for complex multi-node generated templates.
5. Audit the system prompt for injection resistance.
