---
name: reorganise-comfy-workflow
description: Reorganise an existing ComfyUI workflow layout without changing runtime behavior. Use when the user asks to clean up a messy graph, make it readable, regroup or align nodes, or run the explicit `/reorganise_comfy_workflow` agent route.
---

# Reorganise Comfy Workflow

Use this when the graph should become easier to review, share, or maintain, but the workflow semantics must stay unchanged. This is a layout-only path: it may move, resize, group, color, flag, or annotate UI furniture, but it must not edit topology, node classes, links, widget values, prompts, runtime payloads, or generated graph state.

## CLI Path

Start with deterministic offline evidence:

```bash
vibecomfy reorganise workflow.json --assess
```

Create a preview candidate before any write to the source workflow:

```bash
vibecomfy reorganise workflow.json --preview --out cleaned.json
```

Preview writes sibling artifacts next to `cleaned.json`:

- `reorganisation_plan.json`
- `reorganisation_report.md`
- `reorganisation_metrics.json`
- `structural_noop_evidence.json`
- `reorganisation_preview_manifest.json`

Apply only an existing preview manifest:

```bash
vibecomfy reorganise workflow.json --apply --manifest reorganisation_preview_manifest.json --out cleaned.json
```

Omit `--out` only when the user explicitly wants to update the source file in place. In-place apply preserves a sibling `.bak`. Apply refuses stale source graphs by checking the preview manifest source hashes and writes the exact previewed candidate instead of recomputing a new layout.

Useful options:

```bash
vibecomfy reorganise workflow.json --preview --out cleaned.json --spacing compact
vibecomfy reorganise workflow.json --preview --out cleaned.json --existing-group-policy preserve
vibecomfy reorganise workflow.json --preview --out cleaned.json --force-regroup
vibecomfy reorganise workflow.json --preview --out cleaned.json --sidecar workflow.layout.json
```

## Agent Route

For Comfy app agent turns, use the explicit route:

```text
/reorganise_comfy_workflow
```

or send `route="reorganise"`.

The route runs after normal durable turn allocation. It should produce a reviewable layout candidate, report, metrics, structural no-op evidence, and candidate UI artifact when gates pass. It must use the existing candidate, idempotency, accept/reject, and apply-eligibility flow; do not introduce a parallel apply path.

## Review Discipline

- Treat the result as a candidate, not an applied edit.
- Confirm `layout_only_structural_noop` is true before presenting an apply path.
- Use `reorganisation_report.md` for the user-facing summary and `structural_noop_evidence.json` for safety evidence.
- If parse, validation, compile, stale-source, invalid-ref, duplicate-ownership, or structural-drift checks fail, report that no candidate is available.
- Do not call semantic providers for CLI assessment or default preview. Provider-backed planning is an explicitly injected orchestration path, not the default skill behavior.
- If the user asks for functional graph changes after layout cleanup, hand off to `edit-comfy-workflow`.
