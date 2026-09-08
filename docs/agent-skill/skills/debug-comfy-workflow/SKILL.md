---
name: debug-comfy-workflow
description: Diagnose a VibeComfy or ComfyUI workflow that fails validation, conversion, node/model resolution, runtime execution, or output production. Use when the user asks why a workflow does not run, has missing nodes/models, validation errors, bad wiring, failed RunPod/local runs, or confusing agent-edit failures.
---

# Debug Comfy Workflow

Debug from cheap static evidence toward expensive runtime evidence. Decide first whether the failure is the graph, dependencies, or the runtime.

## First Pass

```bash
vibecomfy inspect <workflow>
vibecomfy validate <workflow>
vibecomfy doctor <workflow> --json
vibecomfy analyze info <workflow>
```

For source JSON or conversion failures:

```bash
vibecomfy port check <workflow.json> --json
vibecomfy port doctor-all <workflow.json> --json
vibecomfy port widgets <workflow.json> --json
```

For runtime failures:

```bash
vibecomfy runtime doctor
vibecomfy logs tail
vibecomfy watchdog list
```

## Missing Nodes Or Models

```bash
vibecomfy nodes install-plan <workflow>
vibecomfy nodes spec <ClassType>
vibecomfy models ensure <workflow> --dry-run
vibecomfy models stage --select-phase core --dry-run
```

Install or download only after the evidence supports it and the user agrees.

## Discipline

- Keep graph errors separate from environment errors.
- If embedded ComfyUI is not discoverable, use `vibecomfy-setup`; that is not a workflow bug.
- Do not recommend arbitrary node packs. Require `nodes install-plan`, lockfile data, registry evidence, or a concrete precedent.
- If class/schema evidence is missing, use `search-comfy-workflows` before patching.
- Preserve report paths and cite the exact command output or file that supports the diagnosis.
