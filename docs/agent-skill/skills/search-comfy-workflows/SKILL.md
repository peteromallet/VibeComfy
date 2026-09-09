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

Use Hivemind for current ComfyUI practice, Banodoco workflows, Kijai/Ablejones node usage, settings, model notes, and workflow examples that are not in the local corpus.

Preferred when the Astrid executor is available:

```bash
python3 -m astrid executors run hivemind.search \
  --input 'query=wan animate workflow openpose' \
  --input 'limit=10'
```

Fallback raw HTTP:

```bash
curl -sS \
  -H 'apikey: sb_publishable_O38oPBafrBoFrpi_rlWJvA_UJrulFsx' \
  'https://ujlwuvkrxlvoswwkerdf.supabase.co/rest/v1/unified_feed?select=kind,item_id,title,body,context,url,created_at&or=(title.ilike.*wan%20animate*,body.ilike.*wan%20animate*)&order=created_at.desc&limit=20'
```

URL-encode spaces as `%20`. Favor topic-specific sources such as `wan_comfyui`, `wan_resources`, `ltx_chatter`, `ltx_resources`, `comfyui`, `resources`, and `daily_summaries`.

## Evidence Standard

- A broad message hit is not enough. Extract exact workflow, node class, field, socket, model, or pack evidence.
- Prefer local ready templates when the user wants something runnable immediately.
- Prefer Hivemind resources/workflows over chatter; use chatter for clues, not final wiring.
- If no precedent exists, say that directly and describe the next safest inspection step.
- Keep the handoff short: best candidates, match rationale, node/model requirements, and blockers.
