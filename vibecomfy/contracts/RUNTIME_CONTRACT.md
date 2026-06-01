# S6 Runtime Contract — Settled Gate Decisions

**Go decision**: PROCEED (gate passed 2026-06-01, iteration 2).
**Plan**: `s6-runtime-backed-intent-nodes` (plan_v2.md).

## In-scope

### Runtime-backed node kind

Exactly one: **`vibecomfy.code`**.

All other `vibecomfy.*` intent nodes (including `vibecomfy.loop`) remain editor-only or statically lowered.
Do not runtime-back additional node kinds without a new approval.

### Execution mode

**`expression_v1`** only.

- A single expression that evaluates to a JSON-compatible value.
- No function bodies, statements, imports, modules, or broader Python language surface.

### IO contract

**JSON-compatible metadata computation only.**

Accepted output types: `str`, `int`, `float`, `bool`, `None`, `list`, `dict` (with JSON-serializable values).

Non-JSON transforms are explicitly out of scope: no image, latent, tensor, or conditioning objects may be returned or processed through the runtime path. The subprocess JSON protocol cannot safely transport ComfyUI internal objects in this sprint.

### Queue gate (multi-factor)

A runtime-backed `vibecomfy.code` node is allowed to queue only when **all** of the following agree:

1. Runtime contract validates (malformed/schema-less contracts fail before queue).
2. Local schema confidence is adequate.
3. `VIBECOMFY_RUNTIME_BACKED = True` is set on the class.
4. Executor readiness marker is present.

A single `runtime_backed=True` flag is not sufficient — the gate is multi-factor.

## Out of scope (deferred / non-go)

- Function bodies, multiple statements, code blocks (`execution_mode` beyond `expression_v1`).
- Module imports, `import`, `from ... import`.
- Any transformed object types beyond JSON-compatible scalars/lists/dicts.
- `vibecomfy.loop` runtime backing (remains editor-only / static-lowered).
- Full OS sandboxing; the subprocess boundary is crash/resource containment, not a capability fence.
- Live ComfyUI queue smoke is opt-in/manual only (not a CI gate).

## Settled decisions

| ID   | Decision                                                                                         |
|------|--------------------------------------------------------------------------------------------------|
| SD1  | Runtime-back exactly one intent node kind: `vibecomfy.code`.                                     |
| SD2  | Use expression-only `execution_mode="expression_v1"` for the first runtime contract.             |
| SD3  | Runtime code is limited to JSON-compatible metadata computation.                                 |
| SD4  | Queue allow requires contract validation, schema confidence, class runtime flag, and executor readiness marker. |

## Guardrails

- The AST policy scanner is the primary capability fence. Subprocess isolation is for crash/resource containment, timeout, environment scrubbing, and protocol enforcement — not a full OS sandbox.
- Do not widen beyond `vibecomfy.code` / `expression_v1` / JSON-compatible IO without a new approval.
- Recovery reports, queue diagnostics, and compile materialization must be updated together.
