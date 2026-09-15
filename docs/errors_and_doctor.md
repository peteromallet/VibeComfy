# Errors and Doctor

`vibecomfy doctor` reports the failing layer:

- Python scratchpad import/build errors.
- VibeWorkflow validation errors.
- Missing model errors.
- Missing node errors.
- Comfy runtime errors.
- Device or VRAM profile errors.

For imported workflow failures, start with the canonical bundle diagnostics:

```bash
python -m vibecomfy.cli validate <workflow> --json
python -m vibecomfy.cli doctor <workflow> --json
```

Use `validate` and `doctor` before manual template editing or RunPod validation when you see:

- unknown or missing runtime classes;
- missing required inputs, invalid link shapes, or schema type mismatches;
- unresolved `SetNode` / `GetNode` broadcasts or UI-only helper nodes;
- model asset warnings, missing URLs, duplicate URL targets, 404s, or license-gated URLs;
- positional `widget_N` aliases that need a real widget name.

`doctor` is the runtime-readiness command for authored bundles and ready templates. Use `validate` for schema/structure checks, `nodes install-plan` for custom-node pack plans, and `fetch` for declared model downloads.

Normal `doctor`, `validate`, `fetch`, and `run` behavior stays offline unless you explicitly request network checks through the relevant dependency tooling.
