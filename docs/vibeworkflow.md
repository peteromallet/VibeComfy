# VibeWorkflow — one model, three views

`VibeWorkflow` (`vibecomfy/workflow.py`) is the only editable workflow IR. Python `build()` or an imported candidate loaded through `load_bundle()` supplies the semantic graph; UI/API JSON is evidence at an import or execution boundary.
The serialized envelope **is** the IR: rich `nodes` (keyed by node id) plus
`edges`, `inputs`, `outputs`, `requirements`, `metadata`, and
`vibecomfy_format_version`. The envelope is the interchange and corpus format.

Three views of the same graph, named by how they enter or leave:

| View | Shape | Role |
|---|---|---|
| **Envelope** (serialized IR) | rich `nodes` dict + version | Stored / interchanged form. `nodes` is the sole structural authority. |
| **UI** (LiteGraph) | `nodes` / `links` as lists | The browser panel; Agent Edit persist/apply. An importer, not the schema. |
| **API** (Comfy prompt) | `{node_id: {class_type, inputs}}` | Execution view, derived by `compile("api")` — a pure, lossy *function* of the IR, never stored next to it. |

Required flows:

```text
envelope -> VibeWorkflow   (VibeWorkflow.from_envelope; lossless; fail-closed)
UI JSON  -> VibeWorkflow   (list-node import)
API dict -> VibeWorkflow   (Comfy prompt import)
VibeWorkflow -> envelope   (VibeWorkflow.to_envelope; no compiled_api)
VibeWorkflow -> compile("api")   (execution view; drops helpers/muted/bypassed)
VibeWorkflow -> emit_ui_json()   (LiteGraph persist / apply)
```

Presentation and browser transaction boundary:

- A `.vibe.json` sidecar is optional presentation custody for positions, groups, canvas metadata, and links. Its workflow identity and semantic digest must match the Python bundle; it cannot add or replace nodes, widgets, modes, ports, or execution data.
- Browser capture/prepare uses `/vibecomfy/agent-edit`; canonical V2 Apply uses `/vibecomfy/agent-edit/prepare` followed by `/vibecomfy/agent-edit/finalize`. `/vibecomfy/agent-edit/accept` is a temporary compatibility bridge to finalize: it carries the same revision/API digest and transaction guards and has no independent authority-bypass path. Rollback and reconciliation use `/vibecomfy/agent-edit/rollback` and `/vibecomfy/agent-edit/reconcile`. The legacy `/agent/edit` alias is compatibility-only, carries its deprecation marker, and uses the same canonical adapter; stale or malformed candidates hard-fail with the reported remediation.
- Queueing is a later runtime boundary: only a finalized approved revision may queue. The queue gate checks the approved revision identity and matching fresh API digest; stale, unapproved, or revision/API-mismatched candidates are blocked. A browser candidate, sidecar, or raw API export is never itself a queue instruction.
- The H3 proof is structural and no-GPU: it covers full source IR custody, active compiled role wiring, public `load_bundle` parity, and negative mutations. It does not establish edit, sidecar, transaction, model, CUDA, media-quality, or RunPod execution success.

Loaders (`load_workflow_any`, `workflow_from_file`, `load_port_source`) decode
envelopes straight to the IR; they never compile-then-reingest. `compile()`
is a function, not stored data: old corpus files may carry a `compiled_api`
twin, and the decoder ignores it. New envelopes do not write it.

The IR is the schema source: adding a field means adding it to the dataclass.
UI and API stay named importers — collapsing all three into one stored JSON
shape is not this model.
