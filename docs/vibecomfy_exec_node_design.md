# `vibecomfy.exec` — full-power in-graph code node (design, v3.1)

**Status:** design draft, hardened by a second 6-agent implementation pre-mortem
(Codex build-risk + 5 DeepSeek slices: frontend / backend / agent-emission /
IR-roundtrip / UX). The strategy is fixed; this revision records the **binding
model decision**, the **one spike to run first**, and the concrete work each
layer needs. Load-bearing claims below were re-verified against the source.

A normal ComfyUI node that holds inline Python, takes dynamic typed inputs
(incl. IMAGE/tensors), runs in-process at full power. No sandbox, no trust
apparatus — running foreign code is already the ComfyUI model (you install the
node packs a downloaded graph needs). Coexists with the unchanged sandboxed
`vibecomfy.code`.

## 0. Spike — RESOLVED (the one empirical unknown)

**Q: Does ComfyUI's backend deliver an input key to `execute()` that is not
declared in `INPUT_TYPES`?** **A: YES (for linked inputs), and validation does
not reject it.** Verified by reading this fork's execution path, not a black-box
queue:
- `validate_inputs` loops only over the node's *declared* `required`+`optional`
  keys (`vendor/ComfyUI/comfy/cmd/execution.py:1037`) — an undeclared prompt key
  is never examined → never rejected.
- `get_input_data`'s `is_link` branch (`execution.py:204-212`) delivers a wired
  input regardless of declaration (`get_input_info` returns `(None,None,None)`
  for an unknown key → `not input_info` is True → link resolved and passed).

**Consequence:** Codex's "riskiest assumption" is NOT a hard blocker — both
binding models are runtime-viable. The choice is now a VibeComfy-layer tradeoff,
decided on the v3 minimal-shared-logic principle:
- **Option A (`in_N`, CHOSEN):** additive schema entry only; no shared apply
  changes. Agent wires `in_0=`; UI shows the semantic label from `io`.
- Option C (semantic named slots): cleaner agent syntax but needs a carve-out in
  the shared apply gate (`edit_apply.py:1325`). Rejected to avoid shared-logic
  surgery; documented fallback if `in_0=` proves too awkward in practice.

## 1. Binding model — fixed `in_N` wire keys, semantic UI labels (Option A)

The design uses **fixed wildcard input/output slots on the wire, relabeled to
semantic names in the UI, dispatched via the `io` map in the backend.** This is
the only model consistent across all four layers:

| Layer | What it sees |
|---|---|
| ComfyUI runtime (`INPUT_TYPES`) | declares `in_0..in_15` optional `("*",{"forceInput":True})`, `RETURN_TYPES=("*",)*16` |
| Compile (`workflow.py`) | edges target `in_3`; carried through verbatim (verified `workflow.py:1021-1030,1250-1303`) |
| VibeComfy schema / apply | schema declares `in_0..in_15` as valid inputs → no `unknown_add_node_input` |
| UI (LiteGraph) | slot `in_0` **relabeled** to "image" from `io`; only the label changes, never the wire key |

Why not DS_C's "named slots, no mapping": `_ensure_input_slot`
(`edit_apply.py:2675-2685`) *does* create a slot by name, but apply rejects any
input name absent from the static schema (`edit_apply.py:1325-1333`,
`unknown_add_node_input`), and a static schema cannot enumerate arbitrary
user-chosen names. Fixed `in_N` keys are declarable; semantic names are not.
Option A also defuses the rename-breaks-the-key risk: the wire key is always
`in_3`, the rename is cosmetic.

**`io` is the single source of truth** for the semantic name↔slot mapping:
`io.inputs[k]` describes slot `in_k`, `io.outputs[k]` describes `out_k`/return
index k. Stored as the **`io` widget value** (not duplicated into
`properties.vibecomfy`, which drifts — DS_D); the frontend falls back to the
widget value when `properties.vibecomfy.io` is absent (e.g. API-format reload).

## 2. The node (backend)

`VibeComfyExec`, class_type `vibecomfy.exec`, **ordinary node**
(`VIBECOMFY_INTENT_NODE = False`) registered in `NODE_CLASS_MAPPINGS`. Verified
not stripped at compile (`workflow.py:1063-1065` only strips intent classes), so
no runtime-backed flag needed — a reason to keep it a normal node.

- `INPUT_TYPES`: widgets `source` (multiline STRING), `io` (JSON) + optional
  `{f"in_{i}": ("*", {"forceInput": True}) for i in range(16)}`.
- `RETURN_TYPES = ("*",) * 16`, `RETURN_NAMES = tuple(f"out_{i}" ...)`.
- A **separate class** from `VibeComfyCodeIntent` — do not touch its subprocess
  path (DS_B).

### Execution (verified sketch)

```python
def execute(self, source, io, **kwargs):
    io = json.loads(io) if isinstance(io, str) else (io or {})        # io is a JSON string
    in_names  = [e[0] for e in io.get("inputs", [])]
    out_names = [e[0] for e in io.get("outputs", [])]
    scope = {in_names[i]: _clone_tensors(kwargs.get(f"in_{i}"))        # rule: clone tensors
             for i in range(len(in_names))}                            # unconnected slots → None
    ns = {}
    body = textwrap.dedent(source)
    exec(compile(f"def __run({', '.join(in_names)}):\n" + textwrap.indent(body, "    "),
                 "<exec>", "exec"), {"__builtins__": __builtins__, **PREINJECT}, ns)
    try:
        result = ns["__run"](**scope)
    except Exception as exc:
        raise RuntimeError(_format_body_error(exc, source))           # line-adjusted (UX)
    if not isinstance(result, dict):
        raise RuntimeError("exec body must `return {output_name: value, ...}`")
    missing = [n for n in out_names if n not in result]
    if missing:
        raise RuntimeError(f"body must return keys {out_names}; missing {missing}")
    out = [result[n] for n in out_names]
    out += [None] * (16 - len(out))                                   # pad to RETURN_TYPES arity (DS_B)
    return tuple(out[:16])
```

Verified gotchas folded in:
- **`io` arrives as a JSON string** — parse it (DS_B).
- **Unconnected optional slots are omitted from kwargs** — `.get`, default None (DS_B).
- **Output arity:** ComfyUI requires `len(return) == len(RETURN_TYPES)` — **pad
  to 16 with None** (DS_B). None outputs are harmless (downstream just unfired).
- **Clone tensors** (`torch.Tensor`; LATENT = shallow-copy dict + clone
  `samples`; MASK is a tensor; pass through CONDITIONING/scalars) — else in-place
  mutation corrupts other branches (DS_B/DS_3).
- **`PREINJECT`** = `{"torch": torch, "np": numpy, "Image": PIL.Image}` so bodies
  stay concise; documented (DS_E). Explicit `import` in the body also works.
- **No timeout** (honest): optional `signal.alarm` catches pure-Python infinite
  loops only; cannot interrupt a CUDA/C op. UI freezes on a hung body until the
  server is killed — badge + help text say so (DS_E).
- **Crash isolation:** a segfault/OOM kills ComfyUI, same as any custom node;
  documented, not engineered around.

## 3. Frontend — dynamic sockets (parallel patch, NOT the intent path)

`decorateIntentNode` returns early for non-intent nodes
(`vibecomfy_roundtrip.js:469-473`); intent classes are hardcoded (`:264-268`).
So `vibecomfy.exec` needs a **parallel patch** in `beforeRegisterNodeDef`
(`:9474`), not reuse of the intent decorator. The existing helper only relabels
(`:450-467`) — we need add/remove/reconcile.

`reconcileExecSockets(node)` (new), hooked on `onNodeCreated` + `onConfigure`:
1. Read `io` (widget value, fallback `properties.vibecomfy.io`).
2. Managed slots = `node.inputs` whose name matches `in_\d+` (skip the `source`/
   `io` widget slots — DS_A gotcha).
3. Remove excess **tail-first** (`removeInput`/`removeOutput` auto-clear links —
   DS_A); add missing (`addInput(name,type)`); then relabel.
4. Idempotent so reload (`configure` restores sockets, then `onConfigure` fires)
   doesn't double-add.

Verified-safe: the agent-edit **structural projection reads live serialized
socket names** (`vibecomfy_roundtrip.js:1860,1847`), so the panel/LLM see the
real dynamic sockets — no static-schema confusion. **Watch:** the structural
**hash** records socket names (`:1847-1902`); confirm a relabel doesn't trip the
agent-edit stale/rebaseline guard (Codex). Batch socket mutations to avoid
resize flicker (DS_A).

## 4. Agent emission — the secretly-biggest piece (Codex)

The doc's "confirm multiline widget handling" was wrong on cost. `_fold_constant`
**already** handles multiline strings + dict/list literals
(`edit_session.py:2927,2931-2937`, verified) — that part is free. The real work
is that the interpreter **blanket-blocks `vibecomfy.*` construction**:

- Guard A (`edit_session.py:2045-2052`): rejects `vibecomfy.X(...)` dotted calls.
- Guard B (`:2056-2063`): rejects any `class_type.startswith("vibecomfy.")`.
- Same guard in `_validate_call` (`:2786`).

Concrete changes (DS_C, ranked):
1. **Builtin schema entry** for `vibecomfy.exec` (`schema/provider.py:~119`)
   declaring `source` (STRING), `io` (JSON/DICT), `in_0..in_15` (optional, `*`),
   outputs `out_0..out_15`. Without it: `unknown_add_node_class_type`
   (`edit_apply.py:1256`) and every input rejected (`:1325`).
2. **Allowlist carve-out** for `vibecomfy.exec` at Guards A/B and `_validate_call`
   (small, surgical — do not open all `vibecomfy.*`).
3. **`_widget_aliases.py`** entry so `source`/`io` are recognized widgets.
4. **Prompt:** one "Custom code" section in `build_batch_messages`
   (`agent_provider.py:210-254`) + worked example. Teach: wire `in_0=..`, declare
   `io`, return a dict, imports pre-injected, plain strings only (no f-strings).
5. **Discovery:** ensure `search(focus_types=["vibecomfy.exec"])` returns the
   schema (signature rows are static — `emitter.py:4846`; add an example/usage
   line for the dynamic-IO contract).

Agent-facing syntax:
```python
e = vibecomfy.exec(
    source="result = {'image': torch.clamp(image * strength, 0, 1)}",
    io={"inputs": [["image","IMAGE"],["strength","FLOAT"]], "outputs": [["image","IMAGE"]]},
    in_0=decode.IMAGE, in_1=0.8)
save.images = e.out_0
```
Deferred (scope-creep, Codex+DS_C agree): unifying the three prompt protocols.
Wire the live batch path only.

## 5. IR / round-trip (DS_D)

- Single source of truth = `node.widgets["io"]`; don't dual-store in
  `properties.vibecomfy` (drift). Frontend falls back to widget value.
- **API-format reload loses `properties.vibecomfy.io`** (no `_ui`) — reconstruct
  it from the `io` widget value in `normalize.py`.
- `normalize` routes non-`widget_`-prefixed keys to `node.inputs` not
  `node.widgets` — ensure `source`/`io` keep a stable home (widget prefix or a
  special-case) so they survive round-trips.
- `finalize_metadata` won't enumerate dynamic inputs — `VibeComfyExec` should
  self-report `io.inputs` names if any IR consumer needs the effective input set.
- **Source byte cap** at ingest (`normalize.py`): ~48 KiB to leave headroom under
  the 1 MB scratchpad/AST cap (`agent_generated_loader.py:23`) when emitted via
  `repr()` (DS_D).

## 6. UX must-haves for a non-miserable v1 (DS_E)

Ship-blocking: (1) line-adjusted traceback (the `def __run` wrap offsets line
numbers — strip the frame, correct the number); (2) clear messages for
non-dict-return and wrong/missing output key; (3) pre-injected namespace +
docs; (4) `signal.alarm` best-effort + "⚡ no timeout — save first" badge + help
text; (5) node help covering no-timeout/namespace/return-contract; (6) the agent
prompt section. Nice-to-have (v1.1): capture body `print()`; "copy source"
affordance; io/source consistency lint; shipped example presets; source shown as
a diff in the panel.

Ship 4 example bodies: brightness/contrast, PIL resize, mask-from-luminance,
debug-shape passthrough.

## 7. Build sequencing (Codex)

1. **Spike §0.** 2. Register `VibeComfyExec` (static `INPUT_TYPES`); confirm it
appears in `/object_info`. 3. Executor (§2) — independently testable.
4. IR/compile passthrough + round-trip (§5). 5. Frontend dynamic sockets (§3).
6. Agent emission (§4) **last** — it's the biggest, and depends on the schema
from step 2/4. Each step independently testable; the seams that bite are
frontend↔wire-key contract and agent↔schema.

## 8. Coexistence

`vibecomfy.code` (sandboxed subprocess, JSON scalars, expression-only) unchanged
— portable/deterministic. `vibecomfy.exec` — local full-power compute, normal
node. No shared contract changes; no intent-node queue/compile surgery.

Sizing: one sprint, `partnered`/`full`. The §0 spike de-risks the estimate; the
agent-emission layer is the long pole.
