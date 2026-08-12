# VibeWorkflow — one model, three views

`VibeWorkflow` (`vibecomfy/workflow.py`) is the only editable workflow IR.
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
envelope -> VibeWorkflow   (lossless; rich nodes decode)
UI JSON  -> VibeWorkflow   (list-node import)
API dict -> VibeWorkflow   (Comfy prompt import)
VibeWorkflow -> compile("api")   (execution view; drops helpers/muted/bypassed)
VibeWorkflow -> emit_ui_json()   (LiteGraph persist / apply)
```

Loaders (`load_workflow_any`, `workflow_from_file`, `load_port_source`) decode
envelopes straight to the IR; they never compile-then-reingest. `compile()`
is a function, not stored data: old corpus files may carry a `compiled_api`
twin, and the decoder ignores it. New envelopes do not write it.

The IR is the schema source: adding a field means adding it to the dataclass.
UI and API stay named importers — collapsing all three into one stored JSON
shape is not this model.
