# Runtime Code Execution Modes

`vibecomfy.code` nodes execute Python in a subprocess worker with one of four
execution modes.  The mode is set via the `execution_mode` widget on the node
(seeded by the frontend default) and is re-authoritative at execution time —
any agent-emitted snapshot of the per-mode caps is ignored.

See also: [`vibecomfy/contracts/RUNTIME_CONTRACT.md`](../vibecomfy/contracts/RUNTIME_CONTRACT.md)

## Per-mode capability table

| Capability | `sandboxed_loose` | `sandboxed_strict` | `unrestricted` | `expression_v1` (legacy) |
|---|---|---|---|---|
| **Execution style** | `exec` (statements) | `exec` (statements) | `exec` (statements) | `eval` (single expression) |
| **Builtins** | Broad (≈ 42 names) | Broad (≈ 42 names) | Full `builtins.__dict__` | 16-name safe set |
| **`__import__`** | Allowlisted roots only | Always raises `ImportError` | Unrestricted | Not available |
| **Allowed imports** | math, statistics, re, json, random, itertools, datetime | none | any | — |
| **Default timeout** | 10 000 ms | 10 000 ms | 10 000 ms | 1 000 ms |
| **Source size cap** | 64 KiB | 64 KiB | 64 KiB | 16 KiB |
| **Subprocess env** | Empty | Empty | Parent env inherited | Empty |
| **rlimits** | Yes (POSIX) | Yes (POSIX) | No | Yes (POSIX) |
| **outputs dict** | Pre-initialised in scope | Pre-initialised in scope | Pre-initialised in scope | Not present |
| **Agent-emittable** | Yes (default) | Yes | **No** — raises `ValueError` | Legacy only |

### Broad builtins (sandboxed_loose / sandboxed_strict)

`abs`, `all`, `any`, `bool`, `dict`, `float`, `int`, `len`, `list`, `max`,
`min`, `round`, `sorted`, `str`, `sum`, `tuple`, `print`, `range`,
`enumerate`, `zip`, `map`, `filter`, `set`, `frozenset`, `reversed`,
`divmod`, `pow`, `hex`, `oct`, `bin`, `ord`, `chr`, `repr`, `isinstance`,
`issubclass`, `type`, `hash`, `id`, `iter`, `next`.

### Legacy 16-name safe builtins (expression_v1)

`abs`, `all`, `any`, `bool`, `dict`, `float`, `int`, `len`, `list`, `max`,
`min`, `round`, `sorted`, `str`, `sum`, `tuple`.

## Mode selection

The frontend seeds the default mode from the `VibeComfy.DefaultExecutionMode`
setting (or `localStorage['vibecomfy.defaultExecutionMode']` as a fallback).
The node's `execution_mode` widget is the authoritative source at queue time.
Execution-time resolution order:

1. `properties.execution_mode` widget value
2. `properties.vibecomfy.execution_mode`
3. `properties.vibecomfy.runtime.execution_mode`
4. Default: `sandboxed_loose`

## `unrestricted` opt-in flow

`unrestricted` mode requires **both**:
- `execution_mode` widget set to `"unrestricted"` (labeled `DANGEROUS` in the
  frontend settings UI), AND
- `runtime.unrestricted_ack = true` in the contract payload.

The worker also inherits the parent process environment and skips rlimits so
user code can perform real I/O and import native extensions.  The agent
pipeline raises `ValueError("agent cannot emit unrestricted mode")` — this
mode is always a human-initiated, manual opt-in.

## Legacy `expression_v1` back-compat

`expression_v1` is preserved byte-for-byte for existing deployed payloads.
It uses `ast.parse(mode="eval")` and is intentionally **not** aliased to
`sandboxed_strict`; they are semantically distinct (single-expression vs
multi-statement, 16-name vs broad builtins, 1 s vs 10 s timeout, 16 KiB vs
64 KiB cap).  New code should use `sandboxed_loose` or `sandboxed_strict`.

## Contract constants

All policy constants are exported from `vibecomfy.contracts`:

| Constant | Value |
|---|---|
| `EXECUTION_MODE_SANDBOXED_LOOSE` | `"sandboxed_loose"` |
| `EXECUTION_MODE_SANDBOXED_STRICT` | `"sandboxed_strict"` |
| `EXECUTION_MODE_UNRESTRICTED` | `"unrestricted"` |
| `RUNTIME_CODE_EXECUTION_MODE` | `"expression_v1"` (legacy) |
| `RUNTIME_CODE_BROAD_BUILTINS` | frozenset of 42 builtin names |
| `RUNTIME_CODE_LOOSE_ALLOWED_IMPORTS` | frozenset of 7 module roots |
| `RUNTIME_CODE_MAX_SOURCE_BYTES_NEW` | `65536` (64 KiB) |
| `RUNTIME_CODE_TIMEOUT_MS_MAX` | `10000` (10 s) |
| `RUNTIME_CODE_UNRESTRICTED_ACK_ERROR` | `"runtime_unrestricted_requires_ack"` |
