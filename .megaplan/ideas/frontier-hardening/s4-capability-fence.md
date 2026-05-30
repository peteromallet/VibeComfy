# S4 — capability-fence: the existential gate #2 (confused-deputy security)

## Outcome
The agent cannot be a confused deputy: graph-borne text is treated as **data, never instructions**, and
adding a node with side effects (filesystem write / network / code execution) from untrusted provenance
**requires explicit user confirmation**. Faithfulness becomes *faithfulness within a capability fence*.

## Why (the gremlin)
Roadmap §14 lens 5 (verdict: existential on write). The strategy treats the graph as pure data, but it is
also untrusted input AND executable code. Confirmed by the 5×2 sweep, code-cited: graph text (titles,
widget strings, `properties`) survives ingest verbatim and is re-served to the agent as context
(`analysis/graph.py`) = an injection channel (stripping `MarkdownNote` only hides one channel). `add_node`
(`workflow.py`) has **no class allowlist**. Three unsandboxed exec paths: `scratchpad_loader.py:24`,
`registry/ready.py:97`, `node_packs_install.py` (`git clone` + `pip install`). The refusal-spine guards
*corruption*, not *malice* — a faithfully-applied malicious edit passes every gate.

## Scope — IN
- **Provenance/taint tags on IR node values**: `untrusted_source` (ingested) vs `agent_authored` vs
  `user_confirmed`, carried in node `metadata`.
- A **side-effect allowlist**: classify node classes by capability (filesystem-write / network / code-exec),
  sourced from `node_packs.py` + a curated list.
- **Gate the dangerous verbs**: `add_node` of a side-effecting class, `install_pack`, and scratchpad-exec
  require explicit confirmation when provenance is untrusted (or are refused in headless mode).
- **Quarantine graph-text-as-agent-context**: the agent-facing dump treats titles/notes/widget strings as
  data, never as instructions (a clear data/instruction boundary).

## Scope — OUT
- Sandboxing custom-node EXECUTION (a large, separate effort — this fence is about *additions* + *context*,
  not runtime isolation of arbitrary node code).
- The full parse-don't-exec AST rewrite of the scratchpad loader (its own sprint; here, gate it).

## Locked decisions
- This is a **capability/taint layer on the IR**, not a content filter (string-matching injection text is a
  losing game). Tag provenance; gate by capability.
- Confirmation is required for untrusted-provenance side effects; defaults are deny in unattended contexts.

## Open questions (resolve in planning / prep)
- The capability taxonomy source-of-truth and how new/unknown classes default (deny? quarantine?).
- The confirmation UX boundary (CLI prompt now; editor-surface later).

## Constraints
- Must not break legitimate flows for `user_confirmed` / `agent_authored` provenance.
- Behind S1's oracle gate; coordinates with s2's per-node verdict map (capability is another verdict axis).

## Done criteria
- **Injection probe**: a workflow with an instruction embedded in a node title/widget → the agent-facing
  surface presents it as data; the agent does not act on it.
- **Confused-deputy probe**: `add_node("SaveImage", filename_prefix="../../etc/x")` (or a DownloadAndLoad
  pointed off-host) from `untrusted_source` provenance is **blocked / requires confirmation**, not silently applied.
- `install_pack` + scratchpad-exec from untrusted provenance require confirmation (verified by test).

## Touchpoints
- `vibecomfy/workflow.py` (`add_node`), `vibecomfy/node_packs.py` + `node_packs_install.py`,
  `vibecomfy/scratchpad_loader.py`, `vibecomfy/registry/ready.py`, `vibecomfy/analysis/graph.py`
  (agent-facing dumps), IR `metadata` (provenance tags), `tests/`.

## Anti-scope
- No runtime sandbox for custom-node execution. No AST rewrite of the loader. No string-based injection filter.

## Handoff artifact
The capability taxonomy + provenance model — the second prerequisite (with s3) that the future
write-enable milestone must satisfy before any edit reaches a user's canvas.
