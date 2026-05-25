# Errors and Doctor

## VibeComfyError hierarchy

All framework errors inherit from `VibeComfyError(RuntimeError)`. Every error
carries agent-facing structured metadata:

| Field | Description |
|---|---|
| `severity` | `"error"` (default), `"warning"`, or `"info"` |
| `next_action` | Remediation hint string (CLI command to run next) |
| `default_next_action` | Class-level fallback when no explicit `next_action` given |
| `to_dict()` | Returns `{"type", "message", "severity", "next_action"}` |

**Subclasses and their `default_next_action`:**

| Class | default_next_action |
|---|---|
| `ModelAssetError` | `vibecomfy doctor --models` |
| `SchemaValidationError` | `vibecomfy port validate-call <class_type> --kwargs '<dict>'` |
| `QueueError` | `vibecomfy runtime doctor` |
| `ContextVarBindingError` | `vibecomfy doctor` |
| `ConversionParityError` | `vibecomfy port convert <wf> --dry-run --diff` |
| `SubgraphFreshnessError` | `vibecomfy port --reconvert <template>` |
| `RuntimeNodeError` | `vibecomfy inspect <wf> --node <id>` |
| `DriftError` | `vibecomfy doctor --lockfile` |

The `next_action` kwarg on construction overrides the class default:

```python
raise ModelAssetError("model not found")              # uses default_next_action
raise ModelAssetError("model not found", next_action="custom fix")  # overrides
raise VibeComfyError("warning", severity="warning")    # non-error severity
```

## Doctor command

`vibecomfy doctor` reports the failing layer:

- Python scratchpad import/build errors.
- VibeWorkflow validation errors.
- Missing model errors.
- Missing node errors.
- Comfy runtime errors.
- Device or VRAM profile errors.

For template porting failures, start with the cheaper porting preflight:

```bash
python -m vibecomfy.cli port check <workflow> --json
```

Use `port check` before manual template editing or RunPod validation when you see:

- unknown or missing runtime classes;
- missing required inputs, invalid link shapes, or schema type mismatches;
- unresolved `SetNode` / `GetNode` broadcasts or UI-only helper nodes;
- model asset warnings, missing URLs, duplicate URL targets, 404s, or license-gated URLs;
- positional `widget_N` aliases that need a real widget name.

`doctor` remains the runtime-readiness command for authored scratchpads and ready templates. It may point you back to `port check` when a failure is better explained by the port report. Use `validate` for schema/structure checks, `nodes install-plan` for custom-node pack plans, and `fetch` for declared model downloads.

Model URL HEAD checks are opt-in:

```bash
python -m vibecomfy.cli port check <workflow> --head-check-models --json
```

That command records status, redirects, timeouts, and likely gated or missing URLs without downloading model bodies. Normal `doctor`, `validate`, `fetch`, and `run` behavior stays offline unless you explicitly request network checks.

## Readability diagnostics (`doctor --readability`)

`doctor --readability` adds a source-level readability report to the normal
`doctor` output. The same diagnostics are also available through
`port check --strict-ready-template --json`. Five first-wave checks flag
common anti-patterns in generated ready-template source at severity `warning`:

| Code | What it flags |
|---|---|
| `avoidable_positional_output` | `wf.finalize()` without an explicit `output_node=` kwarg — the output node is resolved by convention (last save node) but should be explicit. |
| `schema_backed_widget_alias_not_resolved` | `widget_N=` patterns in source where the object_info schema could resolve to a canonical widget name. |
| `uuid_class_type_in_ready_template` | A raw UUID used as `class_type` — subgraph nodes should be materialized as named Python functions rather than opaque UUIDs. |
| `model_filename_not_declared` | A bare model filename literal (`.safetensors`, `.ckpt`, `.pt`, `.gguf`, etc.) in a model-picker input without a `model_assets` declaration. |
| `generated_template_has_local_node_helper` | A local `_node()` helper function copy embedded in a generated template — prefer the shared `node()` from `vibecomfy.templates`. |

Use `--readability` when auditing generated template quality or before
promoting a template to strict-ready status:

```bash
python -m vibecomfy.cli doctor ready_templates/image/z_image.py --readability
python -m vibecomfy.cli doctor ready_templates/image/z_image.py --readability --json
python -m vibecomfy.cli port check ready_templates/image/z_image.py --strict-ready-template --json
```

The JSON output includes a `known_codes` catalog listing all five code names,
so even a clean template surfaces which codes were checked. Findings are
deterministically ordered (by code, then node_id, then field).
