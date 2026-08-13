# Capability Fence — Taxonomy & Design

**Status:** Accepted (S4 Step 1).  
**Version:** 1.0.  
**Audience:** Implementors of the capability gate, S1 oracle-gate harness authors, and future maintainers.

## 1. Capability Tags

Every node class in the VibeComfy IR carries exactly one **capability tag** (or the `quarantine` fallback for unknown classes). The tag describes the *worst side-effect* adding a node of that class could cause at edit time. It is **not** a runtime sandbox classification — `KSampler` “executes code” at inference time but is tagged `passthrough` because the gate fences additions, not execution.

| Tag | Meaning | Canonical examples |
|---|---|---|
| `filesystem_write` | Can write arbitrary paths on disk. | `SaveImage`, `VHS_VideoCombine`, `SaveLatent` |
| `network` | Can open sockets or make HTTP requests. | `VHS_LoadVideo`, `DownloadAndLoad*` loaders |
| `code_exec` | Can evaluate or execute arbitrary Python. | `eval()`, `exec()`, `subprocess` wrappers |
| `passthrough` | Pure graph node — no dangerous I/O or eval surface at add time. | `CLIPTextEncode`, `KSampler`, `VAEDecode`, `CheckpointLoaderSimple` |
| `quarantine` | **Policy default for unknown classes.** Treated as `code_exec`-suspect (see §3). | Any class not explicitly listed in the taxonomy |

**Anti-scope note:** The capability fence is a *static taxonomy + IR-side gate on additions and context*. It is not a runtime sandbox. Classes like `KSampler` are tagged `passthrough` because the gate exists to prevent a confused-deputy agent from *adding* a dangerous node, not from running existing nodes at inference time. Runtime sandboxing of custom-node execution is a separate, deferred effort.

## 2. Provenance Tags

Every `VibeNode` carries a provenance tag in `metadata['provenance']`. The tag records *how the node entered the IR* — who authored or supplied it.

| Tag | Meaning | Set by |
|---|---|---|
| `untrusted_source` | The node came from graph text supplied by an external source (JSON import, scratchpad from another agent, raw ComfyUI JSON payload). **This is the fail-closed default when provenance is missing or `None`.** | `from_api` / `from_ui` / `from_envelope`, scratchpad/ready loaders under untrusted scope |
| `agent_authored` | The node was created programmatically by the local agent at edit time (e.g., `wf.add_node(…)` during a recipe or a deliberate edit). **This is the safe default for direct CLI/user calls and for nodes created outside an `untrusted_scope()` block.** | `VibeWorkflow.add_node` (default), `node()`, `add_block_node()` |
| `user_confirmed` | A node that was originally `untrusted_source` but the user explicitly approved through the gate confirmation prompt. Monotonically promoted from `untrusted_source` by `provenance.confirm()`. | `provenance.confirm(node)` (idempotent on already-trusted) |

### Provenance promotion lattice

```
untrusted_source ──[confirm()]──▶ user_confirmed

agent_authored ─── already trusted (confirm() is a no-op)
user_confirmed ─── already trusted (confirm() is a no-op)
```

- `confirm()` **never demotes** — it is strictly monotonic in trust.
- `confirm()` **never raises** on legitimate confirmation requests — it is idempotent on `agent_authored` and `user_confirmed`.
- Missing or `None` `metadata['provenance']` is treated as `untrusted_source` everywhere it is consumed (gate, taint dump, doctor). This is fail-closed.

## 3. Gate Truth-Table

The gate fires on three verbs: `add_node` (including `node()` and `add_block_node()`), `install_pack`, and scratchpad exec. For each verb, the decision is a function of **(provenance × capability × gate context)**.

### 3.1 `add_node` gate

| Provenance | Capability | tty (interactive) | headless (`--non-interactive` or `!isatty()`) |
|---|---|---|---|
| `agent_authored` | any | ✅ allow | ✅ allow |
| `user_confirmed` | any | ✅ allow | ✅ allow |
| `untrusted_source` | `passthrough` | ✅ allow | ✅ allow |
| `untrusted_source` | `filesystem_write` | ⚠️ prompt → y=allow, n=deny | ❌ `CapabilityFenceError` (exit 42) |
| `untrusted_source` | `network` | ⚠️ prompt → y=allow, n=deny | ❌ `CapabilityFenceError` (exit 42) |
| `untrusted_source` | `code_exec` | ⚠️ prompt → y=allow, n=deny | ❌ `CapabilityFenceError` (exit 42) |
| `untrusted_source` | `quarantine` (unknown) | ⚠️ prompt (treated as `code_exec`-suspect) | ❌ `CapabilityFenceError` (exit 42) |
| any | any | `--yes` flag | ✅ allow (bypass all prompts) |

### 3.2 `install_pack` gate

`install_pack` is always side-effecting (it invokes `git clone` + `pip install`). The gate fires when the requesting provenance is `untrusted_source`.

| Provenance | tty | headless |
|---|---|---|
| `agent_authored` | ✅ allow | ✅ allow |
| `user_confirmed` | ✅ allow | ✅ allow |
| `untrusted_source` | ⚠️ prompt → y=allow, n=deny | ❌ `CapabilityFenceError` (exit 42) |
| any | `--yes` | ✅ allow |

### 3.3 Scratchpad exec gate

Scratchpad paths classified as `untrusted_source` are refused in headless mode before `exec_module` runs. Trusted-directory paths (built-in ready templates, `out/scratchpads/` when loaded under agent scope) are classified `agent_authored` and allowed.

### 3.4 CLI flag summary

| Flag | Effect |
|---|---|
| `--yes` / `-y` | Bypass all prompts — all operations allowed |
| `--non-interactive` | Refuse all operations that would prompt (fail-closed) |
| `not sys.stdin.isatty()` | Defaults to `non_interactive=True` |

## 4. Unknown-Class Quarantine Default

**Policy:** Any node class not listed in the capability taxonomy is treated as `quarantine` — which behaves identically to `code_exec`.

**Rationale:**

- A class we cannot prove is `passthrough` may be a wrapper that shells out, writes files, or calls `eval()`. The surface area of custom-node packs is large and the taxonomy cannot be exhaustively pre-curated.
- **Pure allow** would make the gate trivially bypassable: rename `SaveImage` to `EvilSaveImage` and it falls through as passthrough.
- **Hard deny** would block every new node pack and force taxonomy updates before daily ingest runs — breaking the workflow *before* any security benefit materializes.
- **Quarantine** forces an explicit human acknowledge in tty mode and refuses in headless mode, matching the principle of least authority. It is overridable per-class once a human curator tags the class.

The quarantine default is flippable to `hard-deny` later without changing the gate surface — only the `unknown_class_policy()` helper return value changes.

## 5. Node-Level Granularity Decision

Provenance granularity is **node-level** for v1: `metadata['provenance']` is a single string per `VibeNode`. Every field on the node inherits the node's provenance tag.

**Why node-level:** A single node is the atomic unit of trust in the IR — it arrives via one path (ingest, agent authoring, or user confirmation). Per-field granularity would require tracking provenance on every widget value and title string, which adds complexity without evidence of a practical aliasing attack.

**Future escalation path:** If a probe later shows that an attacker can splice a clean `passthrough` node that references a tainted widget via `properties.title`, we will escalate to per-field granularity in `_node_values`. The door is kept open but deferred until evidence demands it.

**Schema-derived metadata exemption:** The schema-derived metadata fields (`output_names`, `output_types`, `input_aliases`, `schema_source`) are exempt from taint-marking in the agent-facing dump because they originate from the schema provider, not from graph text.

## 6. S2 Coordination Contract

The capability fence (S4) and the per-node verdict map (S2) are **loosely coupled** through parallel metadata keys. Capability is a separate verdict axis — it is never merged into S2's verdict object.

| Key | Axis | Written by | Read by |
|---|---|---|---|
| `metadata['capability']` | `frozenset[Capability]` | S4 (this plan) | S2 verdict map (reference-only) |
| `metadata['provenance']` | `ProvenanceTag` (string) | S4 (this plan) | S4 gate, S4 taint dump, S4 doctor warnings |

S2's per-node verdict map can **reference** `metadata['capability']` to make decisions (e.g., flagging nodes with `code_exec` capability from `untrusted_source` provenance), but capability semantics are defined exclusively by S4. If S2 later wants capability merged *into* its verdict object, the harmonization will happen through key renaming at that boundary — not by changing S4's axis.

The contract is deliberately loose: S4 writes keys, S2 reads them. No circular dependency, no merge.

## 7. Naming Collision: `WorkflowSource.provenance` vs `VibeNode.metadata['provenance']`

There are **two distinct provenance concepts** in the codebase, and they share the word “provenance” by coincidence, not by design.

### 7.1 `WorkflowSource.provenance` (pre-existing)

- **Location:** `vibecomfy/workflow.py:31` — `WorkflowSource` dataclass field.
- **Type:** `dict[str, Any]` (free-form metadata dict).
- **Purpose:** Records media-type metadata about the *workflow's origin file* (e.g., `{"media_type": "image", "source_path": "..."}` ). Populated by ingest/normalize at `vibecomfy/ingest/normalize.py:207`.
- **Consumer:** `_detect_media_type()` at `vibecomfy/analysis/graph.py:290` reads `workflow.source.provenance` and `workflow.metadata` to determine whether a workflow produces images, video, or audio.
- **Unchanged by S4.** This field continues to carry media-type and source-path metadata exactly as before.

### 7.2 `VibeNode.metadata['provenance']` (new in S4)

- **Location:** `VibeNode.metadata` dict — a free-form metadata bag on every IR node.
- **Type:** `str` — one of `'untrusted_source'`, `'agent_authored'`, or `'user_confirmed'`.
- **Purpose:** Records the trust provenance of a *single node* within the IR — who authored or supplied it. This is the tag the capability gate reads.
- **Consumers:** The capability gate (`add_node`, `install_pack`, scratchpad exec), the taint dump (`agent_dump_values()`), and the doctor extension (`_doctor_warning_findings`).
- **Introduced by S4.** This is a new key in the pre-existing `metadata` dict.

### Collision handling

- These two concepts live in different objects (`WorkflowSource` vs `VibeNode.metadata`) and different layers (workflow-level media metadata vs node-level trust provenance).
- No code conflates them. Consumers that read provenance explicitly qualify which object they read from.
- This section exists to prevent a future maintainer from confusing the two — if you see `provenance` in code, check whether it refers to `workflow.source.provenance` (media-type metadata) or `node.metadata['provenance']` (trust provenance).

## 8. Out-of-Scope: Ungated `exec_module` Callers

Several call sites in the codebase use `spec.loader.exec_module()` to load and execute Python code at runtime. These are **not gated** in the S4 sprint because they load repo-internal trusted code, not user-supplied paths. They are documented here so a future reviewer does not mistakenly try to gate them in isolation.

> **Gated callers (S4 Step 10).** Two `exec_module` sites *are* gated because they load paths supplied at agent / user request time: `vibecomfy/scratchpad_loader.py:24` and `vibecomfy/registry/ready.py:97`. Provenance is decided by `vibecomfy/security/loader_provenance.py::_provenance_for_path`, which classifies a resolved path as `agent_authored` only if it is `is_relative_to` the resolved `repo_root/out/scratchpads` or the resolved built-in `ready_templates/` directory — anything else is `untrusted_source`. The classifier never uses prefix-string matching, so traversal attempts such as `out/scratchpads/../../tmp/attacker.py` resolve outside the trusted root and refuse in headless mode (exit 42).

| File | Line(s) | What it loads | Why ungated |
|---|---|---|---|
| `vibecomfy/porting/loader.py` | 25 | Ready-template `.py` files during template inspection/build | Templates live inside the repo under version control; they are trusted code written by the project authors |
| `vibecomfy/porting/convert.py` | 397 | Emitted parity-check module (temp file inside the codemod's own output) | The parity check loads code the codemod itself just wrote to verify roundtrip fidelity |
| `vibecomfy/porting/convert.py` | 530 | Emitted strict-ready validation module | Same codemod-owned output; not user-supplied |
| `vibecomfy/porting/convert.py` | 553 | Emitted convert validation module | Same codemod-owned output; not user-supplied |
| `vibecomfy/testing/snapshot.py` | 282 | Recipe build function for snapshot testing | Loads known recipe files from the repo's `recipes/` directory for test infrastructure |
| `vibecomfy/commands/test.py` | 34 | `tools/regenerate_snapshots.py` stem-to-ready-id mapping | Loads the repo-owned snapshot helper, not user input |
| `vibecomfy/commands/test.py` | 46 | Recipe module under test | Loads known recipe files from `recipes/` for CLI test infrastructure |
| `vibecomfy/extras.py` | 89 | Plugin modules from `vibecomfy_extras/` and installed entry points | Plugin discovery loads local, project-authorized extensions, not user-supplied input |
| `tools/*` (various scripts) | — | Repo-internal tooling scripts | These are developer tools in a sibling `tools/` directory; they are invoked manually by repo maintainers, not by ingested graph text |

**Comprehensive fix:** The future **parse-don't-exec AST rewrite** will replace `exec_module`-based loading with AST-level inspection for all of these callers, eliminating the inherent trust-in-code assumption. That work is tracked separately and is out of scope for S4.

## 9. Anti-Scope (What This Fence Is Not)

- **Not a content filter.** The capability gate does not inspect prompt text, widget values, node titles, or any string content. Those are data, and the taint dump makes them visible to the agent with `_taint` markers — but the gate itself does not read them.
- **Not a runtime sandbox.** Custom-node execution at inference time is out of scope. The gate fences *additions to the IR*, not *execution of existing nodes*.
- **Not a class allowlist for compilation.** The compile path at `workflow.py:740` uses `GraphBuilder.node` (external) and is intentionally not gated — the IR `add_node` is the gated edit-time surface. This is noted in code so a future reviewer does not “fix” it.
- **Not an agent-system-prompt guard.** The data/instruction boundary is a separate document (`docs/security/agent_data_boundary.md`) that the system prompt quotes directly.

## 10. Future Integration Points

- **AST parse-don't-exec rewrite:** Will replace all `exec_module` callers in §8 with AST-level inspection, removing the trust-in-code assumption.
- **Per-field provenance escalation:** If a probe demonstrates a practical aliasing attack through `properties.title` or widget references, per-field granularity will replace the current node-level approach.
- **S2 verdict map merge:** If S2 decides capability should be merged into its verdict object rather than referenced as a parallel key, the harmonization will happen at the S2 boundary without changing S4's axis.
- **Hard-deny flip:** If quarantine proves too permissive, the unknown-class default can be flipped to `hard-deny` by changing one return value in `unknown_class_policy()` — no gate surface change needed.
