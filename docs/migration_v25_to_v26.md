# Migration: v2.5 To v2.6

v2.6 removes the explicit `wf` positional argument from checked-in ready-template
node calls. The active workflow is bound by `with new_workflow(...) as wf:` and
generated wrappers read it through a `ContextVar`.

Before:

```python
def build():
    wf = new_workflow(READY_METADATA, source_path=__file__)
    model = UNETLoader(wf, _id="1", unet_name=MODELS["main"])
    image = VAEDecode(wf, _id="8", samples=samples, vae=vae)
    SaveImage(wf, _id="9", images=image, filename_prefix="image/example")
    return finalize(wf, PUBLIC_INPUTS, READY_METADATA, output_node="9", output_type="SaveImage")
```

After:

```python
def build():
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
        model = UNETLoader(_id="1", unet_name=MODELS["main"])
        image = VAEDecode(_id="8", samples=samples, vae=vae)
        SaveImage(_id="9", images=image, filename_prefix="image/example")
        return wf.finalize(PUBLIC_INPUTS, output_node="9", output_type="SaveImage")
```

The explicit workflow form still works for external callers:

```python
wf = new_workflow(READY_METADATA, source_path=__file__)
model = UNETLoader(wf, unet_name="model.safetensors")
```

Repository templates should use the context form. The strict-ready gate fails
ready-template builds that keep explicit `Wrapper(wf, ...)` calls, wrapper-
eligible `node(wf, ...)` calls, schema-default kwargs, single-output `_outputs=`,
or single-output named `.out("NAME")`.

Use the active converter for bulk migration:

```bash
python -m tools.convert_ready_templates --all --dry-run --include-manual
python -m tools.convert_ready_templates --all --write --include-manual
python -m tools.refresh_template_index
python -m tools.refresh_template_index --check
python -m tools.check_strict_ready_templates --json
```

For a single source workflow, use:

```bash
python -m vibecomfy.cli port convert workflow_corpus/.../<id>.json \
  --ready-id <kind>/<id> \
  --out ready_templates/<kind>/<id>.py \
  --json
```

`tools.narrate_template` has been removed (M0 structural cleanup). Use `vibecomfy.porting.emitter` or `tools.convert_ready_templates` for all template emission and migration paths.
