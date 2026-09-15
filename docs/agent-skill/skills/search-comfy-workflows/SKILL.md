---
name: search-comfy-workflows
description: Search for ComfyUI workflow precedents, VibeComfy ready templates, node wiring examples, Banodoco/Hivemind community workflow knowledge, and concrete graph patterns before editing or adding a workflow. Use when the user asks to find workflows, examples, precedents, ComfyUI node combinations, Hivemind/Banodoco evidence, or which workflow to start from.
---

# Search Comfy Workflows

Use this to find evidence before editing or adding a graph. The result should tell the next agent what to open, why it matches, which node classes matter, and what is still uncertain. A found JSON workflow is a precedent to import and inspect; it is not itself an execution instruction.

## Fast Path

Start local. Escalate to Hivemind when local search does not have the precedent, or when the user asks for community/Banodoco practice.

```bash
vibecomfy workflows list --ready
vibecomfy workflows list
vibecomfy search "wan i2v controlnet" --task i2v --limit 10 --json
vibecomfy inspect <workflow_id_or_path>
vibecomfy analyze info <workflow_id_or_path>
```

Run `vibecomfy sources sync` only when indexes are stale and generated index updates are acceptable.

## Hivemind

Use Hivemind for current ComfyUI practice, Banodoco workflows, Kijai/Ablejones node usage, settings, model notes, and community workflow examples. Local search is for the selected imports and curated adapters already present in this checkout.

Use the deployed Hivemind pack through Astrid. This is the single supported
route; it pins the installed pack and applies the runtime's retry/error
handling:

```bash
python3 -m astrid hivemind search "wan animate workflow openpose" \
  --kinds workflow --limit 10 --json
```

Fetch the exact accepted resource/revision through the Astrid Hivemind SDK
(`hivemind.get_item`) after search. Do not call Hivemind's PostgREST tables or
the retired `unified_feed`/`contribute-resource` paths directly from a
workflow task.

Favor topic-specific sources such as `wan_comfyui`, `wan_resources`,
`ltx_chatter`, `ltx_resources`, `comfyui`, `resources`, and `daily_summaries`.

## One workflow lifecycle

Hivemind is the discovery and provenance layer. VibeComfy owns the local
workflow artifacts:

1. Search Hivemind and pin the accepted resource/revision.
2. Pull that one workflow on demand with the normal importer, for example
   `vibecomfy import hivemind:external_resources:<id>` or
   `vibecomfy import hivemind://resource/<id>[/revisions/<revision>]`. The importer writes the single
   local bundle under `workflows/<source-id>/` and retains the Hivemind
   evidence ID, any provider revision, and hash in bundle metadata; when the
   provider exposes no revision, the hash is recorded as the local snapshot
   pin.
3. Edit, validate, and run that local bundle (or copy it to `recipes/`).
4. Use `vibecomfy templates create ... --id ...` only when deliberately promoting a
   validated workflow into a curated `ready_templates/` adapter. Any source
   snapshot shipped with that adapter is generated from the pinned Hivemind
   input; it is not a second source of truth.

Do not bulk-mirror Hivemind into `external_workflows/`. Hivemind is the
canonical shared workflow catalogue; `workflows/` is the single local
on-demand ingestion/cache location. `ready_templates/` contains only curated
executable adapters.

## Evidence Standard

- A broad message hit is not enough. Extract exact workflow, node class, field, socket, model, or pack evidence.
- Prefer local ready templates when the user wants something runnable immediately.
- Prefer Hivemind resources/workflows over chatter; use chatter for clues, not final wiring.
- If no precedent exists, say that directly and describe the next safest inspection step.
- Keep the handoff short: best candidates, match rationale, node/model requirements, and blockers.
