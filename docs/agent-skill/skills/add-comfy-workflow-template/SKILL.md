---
name: add-comfy-workflow-template
description: Add a durable VibeComfy ready workflow/template from a ComfyUI source workflow. Use when the user asks to add a new ready template, promote a workflow into ready_templates, add a model family/capability, update coverage manifests, or make a workflow reusable by id.
---

# Add Comfy Workflow Template

Use this only for durable package templates. For a one-off user composition, create a gitignored `recipes/` file instead.

Read `docs/templates/adding_templates_models.md` before broad template or model-family work.

## Fast Path

1. Choose a stable id: `<media>/<lower_snake_model_capability>`.
2. Start from one selected Hivemind revision using the normal importer:

```bash
vibecomfy import hivemind:external_resources:<id>
```

For a durable package adapter, copy that pinned source as a build input close
to upstream. This checked-in snapshot supports deterministic regeneration; it
is not a second discovery catalogue or an ordinary import location.

3. Store the adapter build input close to upstream:

```text
ready_templates/sources/official/<media>/<id>.json
ready_templates/sources/community/<source>/<id>.json
ready_templates/sources/custom_nodes/<pack>/<source>/<id>.json
```

4. Add or update `ready_templates/sources/manifests/coverage.json`.
5. Declare custom-node packs in `vibecomfy/node_packs.py` or the relevant pack module; update `custom_nodes.lock` when needed.
6. Declare models in `vibecomfy/registry/models.yaml` when workflow metadata is not enough.
7. Validate and promote the imported bundle:

```bash
vibecomfy validate workflows/<source-id> --json
vibecomfy nodes reconcile --workflow workflows/<source-id> --json
vibecomfy templates create workflows/<source-id> --id <media>/<id> \
  --out ready_templates/<media>/<id>.py \
  --json
```

8. Validate:

```bash
vibecomfy validate ready_templates/<media>/<id>.py
vibecomfy doctor ready_templates/<media>/<id>.py --json
pytest -q tests/test_ready_templates.py tests/test_runpod_matrix.py tests/test_nodes_install.py tests/test_cli_misc.py tests/test_cli_sources_workflows_nodes.py
```

9. Run focused GPU validation only when environment and cost are acceptable:

```bash
VIBECOMFY_MATRIX_SCOPE=<family> uv run python scripts/runpod_corpus_matrix.py
```

## Rules

- Keep template additions narrow: source, manifest, node/model declarations, template, focused tests.
- Do not hand-edit generated templates unless you preserve converter markers and parity expectations.
- Do not hide known failures in chat or pod logs. Document incompatibilities in `docs/runtime/incompatibilities.md`, `docs/structural_issues.md`, or a family coverage doc.
- If the request is just "make this custom workflow for me", use `edit-comfy-workflow` and `recipes/`, not `ready_templates/`.
