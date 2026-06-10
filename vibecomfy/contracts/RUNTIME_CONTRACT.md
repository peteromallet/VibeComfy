# S6 Runtime Contract — Settled Gate Decisions

**Go decision**: PROCEED (gate passed 2026-06-01, iteration 2).
**Plan**: `s6-runtime-backed-intent-nodes` (plan_v2.md).
**Updated**: 2026-06-10 — three-mode execution policy added (see `docs/runtime_code_modes.md`).

## In-scope

### Runtime-backed node kind

Exactly one: **`vibecomfy.code`**.

All other `vibecomfy.*` intent nodes (including `vibecomfy.loop`) remain editor-only or statically lowered.
Do not runtime-back additional node kinds without a new approval.

### Execution modes

Three active modes plus one legacy back-compat mode. See [`docs/runtime_code_modes.md`](../docs/runtime_code_modes.md) for the full per-mode capability table.

| Mode | Surface | Imports | Timeout | Source cap |
|---|---|---|---|---|
| `sandboxed_loose` *(default)* | exec, broad builtins | allowlisted: math, statistics, re, json, random, itertools, datetime | 10 s | 64 KiB |
| `sandboxed_strict` | exec, broad builtins | none (`__import__` always raises) | 10 s | 64 KiB |
| `unrestricted` | exec, full builtins | unrestricted | 10 s | 64 KiB |
| `expression_v1` *(legacy)* | eval single-expression, 16-name builtins | none | 1 s | 16 KiB |

**`expression_v1` back-compat**: The legacy eval branch is preserved byte-for-byte. It retains its 16-name builtin set (`abs`, `all`, `any`, `bool`, `dict`, `float`, `int`, `len`, `list`, `max`, `min`, `round`, `sorted`, `str`, `sum`, `tuple`), single-expression AST parse, 1-second timeout, and 16 KiB source cap. It is intentionally NOT aliased to `sandboxed_strict`; they are semantically distinct.

**`unrestricted` opt-in**: `unrestricted` mode requires `runtime.unrestricted_ack = true` in the contract payload as an explicit defense-in-depth check. The agent pipeline raises `ValueError("agent cannot emit unrestricted mode")` — this mode is human-only opt-in. The subprocess worker also inherits the parent env and skips rlimits for unrestricted mode only.

### IO contract

**JSON-compatible metadata computation only.**

Accepted output types: `str`, `int`, `float`, `bool`, `None`, `list`, `dict` (with JSON-serializable values).

Non-JSON transforms are explicitly out of scope: no image, latent, tensor, or conditioning objects may be returned or processed through the runtime path. The subprocess JSON protocol cannot safely transport ComfyUI internal objects in this sprint.

For the new exec-based modes (`sandboxed_loose`, `sandboxed_strict`, `unrestricted`) code writes results into an `outputs = {}` dict pre-initialized in the execution scope.

### Queue gate (multi-factor)

A runtime-backed `vibecomfy.code` node is allowed to queue only when **all** of the following agree:

1. Runtime contract validates (malformed/schema-less contracts fail before queue).
2. Local schema confidence is adequate.
3. `VIBECOMFY_RUNTIME_BACKED = True` is set on the class.
4. Executor readiness marker is present.

A single `runtime_backed=True` flag is not sufficient — the gate is multi-factor.

## Out of scope (deferred / non-go)

- Any transformed object types beyond JSON-compatible scalars/lists/dicts.
- `vibecomfy.loop` runtime backing (remains editor-only / static-lowered).
- Full OS sandboxing; the subprocess boundary is crash/resource containment, not a capability fence.
- Live ComfyUI queue smoke is opt-in/manual only (not a CI gate).

## Settled decisions

| ID   | Decision                                                                                         |
|------|--------------------------------------------------------------------------------------------------|
| SD1  | Runtime-back exactly one intent node kind: `vibecomfy.code`.                                     |
| SD2  | Three active execution modes (`sandboxed_loose`, `sandboxed_strict`, `unrestricted`) plus legacy `expression_v1`. `sandboxed_loose` is the default. `unrestricted` requires explicit `unrestricted_ack`. |
| SD3  | Runtime code is limited to JSON-compatible metadata computation.                                 |
| SD4  | Queue allow requires contract validation, schema confidence, class runtime flag, and executor readiness marker. |
| SD5  | `expression_v1` is kept as a byte-identical back-compat path; it is NOT aliased to `sandboxed_strict`. |
| SD6  | Per-mode caps (builtins, imports, timeout, source bytes) are re-derived at execution time from the resolved mode — never trusted from a stale agent-emitted snapshot. |

## Guardrails

- The AST policy scanner is the primary capability fence. Subprocess isolation is for crash/resource containment, timeout, environment scrubbing, and protocol enforcement — not a full OS sandbox.
- Do not widen beyond `vibecomfy.code` / JSON-compatible IO without a new approval.
- Recovery reports, queue diagnostics, and compile materialization must be updated together.
- `unrestricted` mode must never be emitted by the agent pipeline; any code path that does so is a policy violation.
