# Migrating Ready Templates from v2.3 to v2.4

v2.4 keeps the Python graph-authoring style but moves public contract and reproducibility data out of imperative helper calls.

## Old Shape

Older generated templates typically ended with:

```python
apply_ready_template_policy(wf, READY_METADATA, source_path=__file__, requirements=READY_REQUIREMENTS)
bind_input(wf, "prompt", "6", "text", default="...")
bind_output(wf, "9", output_type="SaveImage", name="image")
return wf
```

These helpers still work for compatibility, but generated templates should not use them.

## New Shape

Declare the contract at module scope:

```python
MODELS = {"main": ModelAsset(filename="model.safetensors", url="https://...", subdir="checkpoints")}
PUBLIC_INPUTS = {"prompt": InputSpec(node="6", field="text", default="", type="STRING", required=True)}
READY_METADATA = ReadyMetadata.build(
    template_id="image/example",
    capability="text_to_image",
    inputs=PUBLIC_INPUTS,
    models=MODELS,
    requirements={"custom_nodes": ["ComfyUI-Example"], "custom_node_refs": [...]},
    vibecomfy_version="0.1.0",
    comfy_core={"version": "unknown", "commit": "unknown", "tested_at": "..."},
)
```

Then finalize once:

```python
return finalize(wf, PUBLIC_INPUTS, READY_METADATA, output_node="9", output_type="SaveImage")
```

## Migration Steps

1. Run `python -m vibecomfy.cli port check <template> --strict-ready-template --json`.
2. Run `python -m tools.refresh_comfy_metadata`.
3. Run `python -m tools.fetch_hf_metadata` when network access is available.
4. Run `python -m tools.convert_ready_templates <template> --write` (or use `vibecomfy.porting.emitter`).
5. Inspect `MODELS`, `PUBLIC_INPUTS`, `READY_METADATA.requirements`, `hardware`, and `python_env`.
6. Run `python -m tools.refresh_template_index`.
7. Run the three gates: strict ready templates, templates against packs, and traceability.

If the narrator cannot safely migrate a hand-authored or composition template, migrate it by hand using the same data shape and keep graph edits scoped.
