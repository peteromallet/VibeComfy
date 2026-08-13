Reading additional input from stdin...
2026-08-13T20:24:14.110502Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/pipelines/epic-blitz/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T20:24:14.110599Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
2026-08-13T20:24:14.110613Z ERROR codex_core::session::session: failed to load skill /Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/planning/skills/planning/SKILL.md: missing YAML frontmatter delimited by ---
OpenAI Codex v0.147.0
--------
workdir: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: high
reasoning summaries: none
session id: 019ffccb-ef4e-7371-91e9-1235141440ed
--------
user
You are GPT-5.6 Sol (high reasoning), read-only ORACLE. Megado run 2, checkpoint 4 — review Batch C (First-class geometry, [XHARD]).

Repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2 (branch elegance-run2). Prior passed checkpoint SHA: 6e97450a (Batch D+E). Batch C commit: 2ddd1f06. Review `git diff 6e97450a..2ddd1f06`.

## Batch C tasks + acceptance gate (frozen tasklist.md)
(1) VibeNode.pos + .size as separate list[float] | None fields; present values = exactly two finite coords; absence None, never synthesize; versioned envelopes reject malformed present values; UI/API ingest tolerates absent/malformed (field absent, raw _ui retained). (2) UI/API ingest copies valid _ui.pos/_ui.size; envelope decode prefers node-level, falls back independently to legacy _ui; first-class wins conflicts. (3) Replace geometry descents: layout_store:184, lowering:354 (+ copy mode/pos/size in manual constructor), reconcile:283, convert:182, emit/ui.py:333. (4) Leave non-geometry _ui hash access in reconcile:505 unchanged. (5) No corpus regeneration.

Gate: live/offline UI ingest identical first-class geometry; old+new envelopes round-trip w/ first-class wins; copies deep + compile geometry-invariant; missing size still triggers stub-layout; lowering/virtual wires/reconcile/sidecars/coordinate canonicalization stable; focused tests exit 0 (baseline-relative); diff-check clean.

## Host-verified evidence
- workflow.py:129-130 pos/size list[float] | None fields present.
- git diff --check clean; 16 files changed (8 test files + code).
- Codex verification: 432 passed / 5 skipped / 2 baseline-corpus deselected / 11 quarantined baseline failures; reconcile add-on 48 passed; live/offline parity, round-trip precedence, deep-copy/compile invariance, sidecars/canonicalization verified.
- Environmental/baseline note (pre-existing, verified at main 0f515870): no corpus in worktree (2 FileNotFoundError tests), parity-gate failures on ready_templates starter set, corpus-wide timeouts — do not count.

## Your verdict
Binary PASS or concrete issues (file:line). Confirm: pos/size minted at ingest + decode precedence; all 6 descents actually read node.pos/node.size (grep for remaining metadata['_ui'] pos/size descents outside reconcile:505 + ingest retention); stub-layout preserved; compile geometry-invariant; no corpus regen. Do NOT edit. Read-only.
warning: Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest.
codex
I’ll review Batch C read-only against the frozen gate. I’m using the `vibecomfy` skill because this is a VibeComfy package change; I’ll inspect its instructions first, then audit the commit diff, remaining geometry descents, and focused behavior without editing anything.
exec
/bin/zsh -lc "sed -n '1,240p' /Users/peteromalley/.codex/skills/vibecomfy/SKILL.md" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
---
name: vibecomfy
description: 'Drive the VibeComfy package to discover ComfyUI workflows, load ready Python templates, edit and compose them in a `VibeWorkflow` IR, validate, and execute either embedded locally, against an existing ComfyUI server, or on RunPod. Use whenever the user wants to generate images/video/audio/edits from ComfyUI workflows, tweak templates, build recipes, compose graphs in Python, or run existing `ready_templates` end-to-end.'
---

# VibeComfy

VibeComfy is this package: a Python-first way to drive ComfyUI without hand-editing JSON. The center of gravity is `VibeWorkflow`: load a workflow, edit it in Python, validate it, then compile to ComfyUI API JSON and run it.

Use this umbrella skill for orientation and package rules. For real work, route to the smallest focused skill:

| User wants | Use |
|---|---|
| Configure ComfyUI paths, server URL, custom nodes, or models | `vibecomfy-setup` |
| Find a workflow, precedent, node wiring, or Hivemind evidence | `search-comfy-workflows` |
| Explain what a workflow does or answer questions about it | `explain-comfy-workflow` |
| Clean up, regroup, or align a ComfyUI workflow layout without changing runtime behavior | `reorganise-comfy-workflow` |
| Tweak or rewrite a workflow without running it | `edit-comfy-workflow` |
| Execute a ready template, recipe, scratchpad, server run, or RunPod smoke | `run-comfy-workflow` |
| Diagnose validation, conversion, node/model, or runtime failures | `debug-comfy-workflow` |
| Add a durable package ready template | `add-comfy-workflow-template` |

The operating path is:

```text
discover -> load -> edit/compose -> validate -> run -> collect outputs
```

## First Moves

Work from the repo root. Prefer the `vibecomfy ...` console entrypoint; if an editable checkout has no console script, use `python -m vibecomfy.cli ...`.

For a runnable starting point:

```bash
vibecomfy workflows list --ready
vibecomfy inspect image/z_image
vibecomfy copy-to-recipe image/z_image --out recipes/my_run.py
vibecomfy validate recipes/my_run.py
vibecomfy run recipes/my_run.py --runtime server --server-url http://127.0.0.1:8188
```

For raw JSON:

```bash
vibecomfy port check workflow.json --json
vibecomfy port convert workflow.json --out out/scratchpads/workflow.py --json
vibecomfy validate out/scratchpads/workflow.py
```

For setup trouble:

```bash
vibecomfy config show --json
vibecomfy runtime doctor
```

## Authoring Model

Use one loader by default:

```python
from vibecomfy import load_workflow_any

def build():
    wf = load_workflow_any("image/z_image")
    wf.set_prompt("a glass teapot on basalt")
    wf.set_seed(42)
    wf.set_steps(20)
    return wf.finalize_metadata()
```

Choose the lightest edit shape:

| Shape | Use when |
|---|---|
| `VibeWorkflow` setters/direct methods | You are changing existing prompt, seed, steps, widgets, edges, or metadata. |
| Patches | You are decorating an existing graph without changing the public handle shape. |
| Blocks | You are adding graph structure that produces new handles. |
| Recipes | You are making a user-specific composition or chaining logic. |
| Ready templates | You are adding a durable package starting point by id. |

Keep ComfyUI's terms precise: a **workflow** is any graph; a **template** is a curated starting-point workflow under `ready_templates/`.

## Rules

- Treat the worktree as shared. Do not revert, overwrite, or clean up edits you did not make.
- Keep changes scoped to the requested workflow, command, template, or doc surface.
- Do not change runtime behavior, workflow corpus files, generated snapshots, or template manifests unless the task explicitly covers them.
- Never invent node class names, sockets, widget fields, or model layouts. Use `inspect`, `analyze info`, `nodes spec`, local precedents, or `search-comfy-workflows`.
- Sync indexes only when needed: `vibecomfy sources sync`.
- Add focused tests when changing command routing, parser behavior, conversion, validation, search, runtime-facing code, or template coverage.
- Keep tests deterministic; avoid requiring ComfyUI, RunPod, network, or local model files unless the test is explicitly marked for that environment.

## Agent-Edit Policy

- Prefer normal static graph edits first.
- Use `vibecomfy.loop` only for bounded visible sweeps that cannot lower cleanly to ordinary nodes. Keep iteration counts bounded and metadata typed.
- Use `vibecomfy.code` only for inspectable typed logic when no shipped shape fits. Default to sandboxed modes. Never emit unrestricted execution from agent-authored code.
- Reject side-effecting, unbounded, runtime-only, external-I/O, or otherwise unrepresentable requests at policy level.
- Editor-only intent nodes may be valid for Canvas Apply, but they are Queue blockers until lowered to normal runtime nodes.
- When emitting an intent node programmatically, build metadata with `intent_node_properties(...)`.

## When You Need More Detail

Read [REFERENCE.md](REFERENCE.md) for the API surface, layer model, command catalog, plugin hooks, known limitations, RunPod environment, and durable-template checklist.

In-repo references:

- `docs/authoring.md` — blocks, patches, handles, opaque subgraphs, recipes
- `docs/vibeworkflow.md` — IR contract
- `docs/api/m6-public-api.md` — public imports and compatibility aliases
- `docs/custom_nodes.md` — node packs, install/lock/restore
- `docs/runtime/lifecycle.md`, `docs/runtime/surface.md` — embedded vs server runtime
- `docs/errors_and_doctor.md` — what `doctor` flags and how to fix it
- `docs/templates/adding_templates_models.md` — full ready-template addition process

When in doubt, stay in Python and descend only as far as needed:

```text
op -> Artifact -> preview_workflow -> VibeWorkflow -> compile("api") -> run
```

exec
/bin/zsh -lc 'git diff --check 6e97450a..2ddd1f06' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git diff --stat 6e97450a..2ddd1f06 && git diff --name-status 6e97450a..2ddd1f06' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git status --short --branch && git rev-parse --verify 6e97450a''^{commit} && git rev-parse --verify 2ddd1f06''^{commit} && git log -1 --oneline 2ddd1f06' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 2 in 104ms:
.oracle/checkins/batch-3-rev.md:236: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:238: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:240: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:242: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:244: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:246: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:248: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:250: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:252: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:254: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:256: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:258: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:260: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:262: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:264: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:266: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:268: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:270: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:272: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:274: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:276: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:278: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:280: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:282: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:284: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:286: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:288: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:290: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:292: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:294: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:296: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:298: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:300: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:302: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:304: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:306: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:308: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:310: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:312: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:314: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:316: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:318: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:320: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:322: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:324: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:326: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:328: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:330: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:332: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:334: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:336: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:338: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:340: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:342: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:344: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:346: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:348: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:350: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:352: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:354: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:356: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:358: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:360: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:362: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:364: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:366: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:368: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:370: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:372: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:374: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:376: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:378: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:380: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:382: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:384: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:386: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:388: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:390: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:392: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:394: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:396: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:398: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:400: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:402: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:404: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:406: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:408: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:410: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:412: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:414: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:416: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:418: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:420: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:422: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:424: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:426: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:428: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:430: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:432: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:434: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:436: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:438: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:440: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:442: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:444: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:446: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:448: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:450: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:452: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:454: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:456: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:458: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:460: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:462: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:464: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:466: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:468: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:470: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:472: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:474: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:476: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:478: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:480: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:482: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:484: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:486: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:488: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:490: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:492: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:494: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:496: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:498: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:500: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:502: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:504: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:506: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:508: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:510: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:512: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:514: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:516: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:518: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:520: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:522: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:524: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:526: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:528: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:530: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:532: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:534: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:536: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:538: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:540: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:542: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:544: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:546: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:548: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:550: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:552: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:554: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:556: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:558: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:560: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:562: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:564: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:566: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:568: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:570: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:572: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:574: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:576: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:578: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:580: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:582: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:584: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:586: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:588: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:590: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:592: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:594: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:596: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:598: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:600: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:602: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:604: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:606: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:608: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:610: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:612: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:614: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:616: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:618: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:620: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:622: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:624: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:626: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:628: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:630: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:632: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:634: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:636: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:638: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:640: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:642: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:644: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:646: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:648: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:650: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:652: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:654: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:656: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:658: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:660: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:662: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:664: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:666: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:668: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:670: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:672: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:674: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:676: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:678: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:680: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:682: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:684: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:686: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:688: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:690: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:692: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:694: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:696: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:698: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:700: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:702: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:704: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:706: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:708: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:710: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:712: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:714: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:716: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:718: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:720: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:722: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:724: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:726: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:728: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:730: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:732: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:734: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:736: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:738: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:740: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:742: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:744: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:746: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:748: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:750: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:752: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:754: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:756: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:758: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:760: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:762: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:764: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:766: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:768: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:770: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:772: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:774: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:776: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:778: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:780: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:782: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:784: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:786: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:788: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:790: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:792: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:794: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:796: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:798: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:800: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:802: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:804: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:806: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:808: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:810: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:812: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:814: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:816: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:818: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:820: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:822: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:824: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:826: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:828: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:830: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:832: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:834: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:836: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:838: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:840: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:842: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:844: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:846: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:848: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:850: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:852: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:854: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:856: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:858: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:860: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:862: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:864: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:866: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:868: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:870: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:872: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:874: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:876: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:878: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:880: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:882: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:884: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:886: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:888: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:890: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:892: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:894: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:896: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:898: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:900: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:902: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:904: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:906: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:908: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:910: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:912: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:914: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:916: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:918: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:920: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:922: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:924: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:926: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:928: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:930: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:932: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:934: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:936: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:938: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:940: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:942: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:944: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:946: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:948: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:950: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:952: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:954: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:956: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:958: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:960: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:962: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:964: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:966: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:968: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:970: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:972: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:974: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:976: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:978: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:980: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:982: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:984: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:986: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:988: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:990: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:992: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:994: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:996: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:998: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1000: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1002: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1004: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1006: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1008: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1010: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1012: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1014: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1016: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1018: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1020: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1022: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1024: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1026: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1028: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1030: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1032: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1034: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1036: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1038: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1040: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1042: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1044: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1046: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1048: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1050: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1052: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1054: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1056: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1058: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1060: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1062: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1064: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1066: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1068: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1070: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1072: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1074: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1076: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1078: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1080: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1082: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1084: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1086: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1088: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1090: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1092: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1094: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1096: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1098: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1100: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1102: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1104: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1106: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1108: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1110: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1112: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1114: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1116: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1118: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1120: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1122: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1124: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1126: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1128: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1130: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1132: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1134: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1136: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1138: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1140: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1142: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1144: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1146: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1148: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1150: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1152: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1154: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1156: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1158: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1160: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1162: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1164: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1166: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1168: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1170: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1172: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1174: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1176: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1178: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1180: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1182: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1184: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1186: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1188: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1190: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1192: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1194: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1196: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1198: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1200: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1202: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1204: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1206: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1208: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1210: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1212: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1214: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1216: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1218: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1220: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1222: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1224: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1226: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1228: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1230: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1232: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1234: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1236: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1238: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1240: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1242: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1244: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1246: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1248: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1250: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1252: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1254: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1256: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1258: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1260: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1262: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1264: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1266: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1268: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1270: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1272: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1274: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1276: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1278: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1280: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1282: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1284: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1286: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1288: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1290: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1292: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1294: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1296: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1298: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1300: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1302: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1304: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1306: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1308: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:1310: trailing whitespace.
+++   719	
.oracle/checkins/batch-3-rev.md:1312: trailing whitespace.
+++   726	
.oracle/checkins/batch-3-rev.md:1314: trailing whitespace.
+++   728	
.oracle/checkins/batch-3-rev.md:1316: trailing whitespace.
+++   730	
.oracle/checkins/batch-3-rev.md:1318: trailing whitespace.
+++   731	
.oracle/checkins/batch-3-rev.md:1320: trailing whitespace.
+++   734	
.oracle/checkins/batch-3-rev.md:1322: trailing whitespace.
+++   740	
.oracle/checkins/batch-3-rev.md:1324: trailing whitespace.
+++   741	
.oracle/checkins/batch-3-rev.md:1326: trailing whitespace.
+++   769	
.oracle/checkins/batch-3-rev.md:1328: trailing whitespace.
+++   770	
.oracle/checkins/batch-3-rev.md:1330: trailing whitespace.
+++   786	
.oracle/checkins/batch-3-rev.md:1332: trailing whitespace.
+++   787	
.oracle/checkins/batch-3-rev.md:1334: trailing whitespace.
+++   794	
.oracle/checkins/batch-3-rev.md:1336: trailing whitespace.
+++   795	
.oracle/checkins/batch-3-rev.md:1338: trailing whitespace.
+++   829	
.oracle/checkins/batch-3-rev.md:1340: trailing whitespace.
+++   830	
.oracle/checkins/batch-3-rev.md:1342: trailing whitespace.
+++     2	
.oracle/checkins/batch-3-rev.md:1344: trailing whitespace.
+++     6	
.oracle/checkins/batch-3-rev.md:1346: trailing whitespace.
+++     7	
.oracle/checkins/batch-3-rev.md:1348: trailing whitespace.
+++    14	
.oracle/checkins/batch-3-rev.md:1350: trailing whitespace.
+++    15	
.oracle/checkins/batch-3-rev.md:1352: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:1354: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:1356: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:1358: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:1360: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:1362: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:1364: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:1366: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:1368: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:1370: trailing whitespace.
++++    45	
.oracle/checkins/batch-3-rev.md:1372: trailing whitespace.
++++    53	
.oracle/checkins/batch-3-rev.md:1374: trailing whitespace.
++++    58	
.oracle/checkins/batch-3-rev.md:1376: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:1378: trailing whitespace.
++++    65	
.oracle/checkins/batch-3-rev.md:1380: trailing whitespace.
++++    66	
.oracle/checkins/batch-3-rev.md:1382: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:1384: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:1386: trailing whitespace.
++++    83	
.oracle/checkins/batch-3-rev.md:1388: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:1390: trailing whitespace.
++++    88	
.oracle/checkins/batch-3-rev.md:1392: trailing whitespace.
++++    89	
.oracle/checkins/batch-3-rev.md:1394: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:1396: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:1398: trailing whitespace.
++++   110	
.oracle/checkins/batch-3-rev.md:1400: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:1402: trailing whitespace.
++++   116	
.oracle/checkins/batch-3-rev.md:1404: trailing whitespace.
++++   117	
.oracle/checkins/batch-3-rev.md:1406: trailing whitespace.
++++   135	
.oracle/checkins/batch-3-rev.md:1408: trailing whitespace.
++++   136	
.oracle/checkins/batch-3-rev.md:1410: trailing whitespace.
++++   149	
.oracle/checkins/batch-3-rev.md:1412: trailing whitespace.
++++   150	
.oracle/checkins/batch-3-rev.md:1414: trailing whitespace.
++++   163	
.oracle/checkins/batch-3-rev.md:1416: trailing whitespace.
++++   164	
.oracle/checkins/batch-3-rev.md:1418: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:1420: trailing whitespace.
++++   174	
.oracle/checkins/batch-3-rev.md:1422: trailing whitespace.
++++   180	
.oracle/checkins/batch-3-rev.md:1424: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:1426: trailing whitespace.
++++   191	
.oracle/checkins/batch-3-rev.md:1428: trailing whitespace.
++++   192	
.oracle/checkins/batch-3-rev.md:1430: trailing whitespace.
++++   198	
.oracle/checkins/batch-3-rev.md:1432: trailing whitespace.
++++   199	
.oracle/checkins/batch-3-rev.md:1434: trailing whitespace.
++++   206	
.oracle/checkins/batch-3-rev.md:1436: trailing whitespace.
++++   207	
.oracle/checkins/batch-3-rev.md:1438: trailing whitespace.
++++   223	
.oracle/checkins/batch-3-rev.md:1440: trailing whitespace.
++++   224	
.oracle/checkins/batch-3-rev.md:1442: trailing whitespace.
++++   228	
.oracle/checkins/batch-3-rev.md:1444: trailing whitespace.
++++   229	
.oracle/checkins/batch-3-rev.md:1446: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:1448: trailing whitespace.
++++   233	
.oracle/checkins/batch-3-rev.md:1450: trailing whitespace.
++++   237	
.oracle/checkins/batch-3-rev.md:1452: trailing whitespace.
++++   238	
.oracle/checkins/batch-3-rev.md:1454: trailing whitespace.
++++   242	
.oracle/checkins/batch-3-rev.md:1456: trailing whitespace.
++++   243	
.oracle/checkins/batch-3-rev.md:1458: trailing whitespace.
++++   250	
.oracle/checkins/batch-3-rev.md:1460: trailing whitespace.
++++   251	
.oracle/checkins/batch-3-rev.md:1462: trailing whitespace.
++++   254	
.oracle/checkins/batch-3-rev.md:1464: trailing whitespace.
++++   271	
.oracle/checkins/batch-3-rev.md:1466: trailing whitespace.
++++   275	
.oracle/checkins/batch-3-rev.md:1468: trailing whitespace.
++++   278	
.oracle/checkins/batch-3-rev.md:1470: trailing whitespace.
++++   288	
.oracle/checkins/batch-3-rev.md:1472: trailing whitespace.
++++   307	
.oracle/checkins/batch-3-rev.md:1474: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:1476: trailing whitespace.
++++   324	
.oracle/checkins/batch-3-rev.md:1478: trailing whitespace.
++++   336	
.oracle/checkins/batch-3-rev.md:1480: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:1482: trailing whitespace.
++++     8	
.oracle/checkins/batch-3-rev.md:1484: trailing whitespace.
++++    10	
.oracle/checkins/batch-3-rev.md:1486: trailing whitespace.
++++    21	
.oracle/checkins/batch-3-rev.md:1488: trailing whitespace.
++++    24	
.oracle/checkins/batch-3-rev.md:1490: trailing whitespace.
++++    25	
.oracle/checkins/batch-3-rev.md:1492: trailing whitespace.
++++    28	
.oracle/checkins/batch-3-rev.md:1494: trailing whitespace.
++++    29	
.oracle/checkins/batch-3-rev.md:1496: trailing whitespace.
++++    55	
.oracle/checkins/batch-3-rev.md:1498: trailing whitespace.
++++    56	
.oracle/checkins/batch-3-rev.md:1500: trailing whitespace.
++++    61	
.oracle/checkins/batch-3-rev.md:1502: trailing whitespace.
++++    62	
.oracle/checkins/batch-3-rev.md:1504: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:1506: trailing whitespace.
++++    72	
.oracle/checkins/batch-3-rev.md:1508: trailing whitespace.
++++    79	
.oracle/checkins/batch-3-rev.md:1510: trailing whitespace.
++++    80	
.oracle/checkins/batch-3-rev.md:1512: trailing whitespace.
++++    94	
.oracle/checkins/batch-3-rev.md:1514: trailing whitespace.
++++    95	
.oracle/checkins/batch-3-rev.md:1516: trailing whitespace.
++++   102	
.oracle/checkins/batch-3-rev.md:1518: trailing whitespace.
++++   104	
.oracle/checkins/batch-3-rev.md:1520: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:1522: trailing whitespace.
++++   113	
.oracle/checkins/batch-3-rev.md:1524: trailing whitespace.
++++   119	
.oracle/checkins/batch-3-rev.md:1526: trailing whitespace.
++++   128	
.oracle/checkins/batch-3-rev.md:1528: trailing whitespace.
++++   140	
.oracle/checkins/batch-3-rev.md:1530: trailing whitespace.
++++   162	
.oracle/checkins/batch-3-rev.md:1532: trailing whitespace.
++++   171	
.oracle/checkins/batch-3-rev.md:1534: trailing whitespace.
++++   201	
.oracle/checkins/batch-3-rev.md:1536: trailing whitespace.
++++   202	
.oracle/checkins/batch-3-rev.md:1538: trailing whitespace.
++++   214	
.oracle/checkins/batch-3-rev.md:1540: trailing whitespace.
++++   215	
.oracle/checkins/batch-3-rev.md:1542: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:1544: trailing whitespace.
++++   245	
.oracle/checkins/batch-3-rev.md:1546: trailing whitespace.
++++   248	
.oracle/checkins/batch-3-rev.md:1548: trailing whitespace.
++++   266	
.oracle/checkins/batch-3-rev.md:1550: trailing whitespace.
++++   313	
.oracle/checkins/batch-3-rev.md:1552: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:1554: trailing whitespace.
++++   335	
.oracle/checkins/batch-3-rev.md:1556: trailing whitespace.
++++   339	
.oracle/checkins/batch-3-rev.md:1558: trailing whitespace.
++++   360	
.oracle/checkins/batch-3-rev.md:1560: trailing whitespace.
++++   361	
.oracle/checkins/batch-3-rev.md:1562: trailing whitespace.
++++   385	
.oracle/checkins/batch-3-rev.md:1564: trailing whitespace.
++++   386	
.oracle/checkins/batch-3-rev.md:1566: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1568: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1570: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1572: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1574: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1576: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1578: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1580: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1582: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1584: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1586: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1588: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1590: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1592: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1594: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1596: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1598: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1600: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1602: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1604: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1606: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1608: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1610: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1612: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1614: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1616: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1618: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1620: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1622: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1624: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1626: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1628: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1630: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1632: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1634: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:1636: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:1638: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:1640: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:1642: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:1644: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:1646: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:1648: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:1650: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:1652: trailing whitespace.
++++    45	
.oracle/checkins/batch-3-rev.md:1654: trailing whitespace.
++++    53	
.oracle/checkins/batch-3-rev.md:1656: trailing whitespace.
++++    58	
.oracle/checkins/batch-3-rev.md:1658: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:1660: trailing whitespace.
++++    65	
.oracle/checkins/batch-3-rev.md:1662: trailing whitespace.
++++    66	
.oracle/checkins/batch-3-rev.md:1664: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:1666: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:1668: trailing whitespace.
++++    83	
.oracle/checkins/batch-3-rev.md:1670: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:1672: trailing whitespace.
++++    88	
.oracle/checkins/batch-3-rev.md:1674: trailing whitespace.
++++    89	
.oracle/checkins/batch-3-rev.md:1676: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:1678: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:1680: trailing whitespace.
++++   110	
.oracle/checkins/batch-3-rev.md:1682: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:1684: trailing whitespace.
++++   116	
.oracle/checkins/batch-3-rev.md:1686: trailing whitespace.
++++   117	
.oracle/checkins/batch-3-rev.md:1688: trailing whitespace.
++++   135	
.oracle/checkins/batch-3-rev.md:1690: trailing whitespace.
++++   136	
.oracle/checkins/batch-3-rev.md:1692: trailing whitespace.
++++   149	
.oracle/checkins/batch-3-rev.md:1694: trailing whitespace.
++++   150	
.oracle/checkins/batch-3-rev.md:1696: trailing whitespace.
++++   163	
.oracle/checkins/batch-3-rev.md:1698: trailing whitespace.
++++   164	
.oracle/checkins/batch-3-rev.md:1700: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:1702: trailing whitespace.
++++   174	
.oracle/checkins/batch-3-rev.md:1704: trailing whitespace.
++++   180	
.oracle/checkins/batch-3-rev.md:1706: trailing whitespace.
++++   180	
.oracle/checkins/batch-3-rev.md:1708: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:1710: trailing whitespace.
++++   191	
.oracle/checkins/batch-3-rev.md:1712: trailing whitespace.
++++   192	
.oracle/checkins/batch-3-rev.md:1714: trailing whitespace.
++++   198	
.oracle/checkins/batch-3-rev.md:1716: trailing whitespace.
++++   199	
.oracle/checkins/batch-3-rev.md:1718: trailing whitespace.
++++   206	
.oracle/checkins/batch-3-rev.md:1720: trailing whitespace.
++++   207	
.oracle/checkins/batch-3-rev.md:1722: trailing whitespace.
++++   223	
.oracle/checkins/batch-3-rev.md:1724: trailing whitespace.
++++   224	
.oracle/checkins/batch-3-rev.md:1726: trailing whitespace.
++++   228	
.oracle/checkins/batch-3-rev.md:1728: trailing whitespace.
++++   229	
.oracle/checkins/batch-3-rev.md:1730: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:1732: trailing whitespace.
++++   233	
.oracle/checkins/batch-3-rev.md:1734: trailing whitespace.
++++   237	
.oracle/checkins/batch-3-rev.md:1736: trailing whitespace.
++++   238	
.oracle/checkins/batch-3-rev.md:1738: trailing whitespace.
++++   242	
.oracle/checkins/batch-3-rev.md:1740: trailing whitespace.
++++   243	
.oracle/checkins/batch-3-rev.md:1742: trailing whitespace.
++++   250	
.oracle/checkins/batch-3-rev.md:1744: trailing whitespace.
++++   251	
.oracle/checkins/batch-3-rev.md:1746: trailing whitespace.
++++   254	
.oracle/checkins/batch-3-rev.md:1748: trailing whitespace.
++++   271	
.oracle/checkins/batch-3-rev.md:1750: trailing whitespace.
++++   275	
.oracle/checkins/batch-3-rev.md:1752: trailing whitespace.
++++   278	
.oracle/checkins/batch-3-rev.md:1754: trailing whitespace.
++++   288	
.oracle/checkins/batch-3-rev.md:1756: trailing whitespace.
++++   307	
.oracle/checkins/batch-3-rev.md:1758: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:1760: trailing whitespace.
++++   324	
.oracle/checkins/batch-3-rev.md:1762: trailing whitespace.
++++   336	
.oracle/checkins/batch-3-rev.md:1764: trailing whitespace.
++++   347	
.oracle/checkins/batch-3-rev.md:1766: trailing whitespace.
++++   352	
.oracle/checkins/batch-3-rev.md:1768: trailing whitespace.
++++   374	
.oracle/checkins/batch-3-rev.md:1770: trailing whitespace.
++++   388	
.oracle/checkins/batch-3-rev.md:1772: trailing whitespace.
++++   423	
.oracle/checkins/batch-3-rev.md:1774: trailing whitespace.
++++   436	
.oracle/checkins/batch-3-rev.md:1776: trailing whitespace.
++++   462	
.oracle/checkins/batch-3-rev.md:1778: trailing whitespace.
++++   477	
.oracle/checkins/batch-3-rev.md:1780: trailing whitespace.
++++   479	
.oracle/checkins/batch-3-rev.md:1782: trailing whitespace.
++++   480	
.oracle/checkins/batch-3-rev.md:1784: trailing whitespace.
++++   486	
.oracle/checkins/batch-3-rev.md:1786: trailing whitespace.
++++   487	
.oracle/checkins/batch-3-rev.md:1788: trailing whitespace.
++++   491	
.oracle/checkins/batch-3-rev.md:1790: trailing whitespace.
++++   492	
.oracle/checkins/batch-3-rev.md:1792: trailing whitespace.
++++   507	
.oracle/checkins/batch-3-rev.md:1794: trailing whitespace.
++++   508	
.oracle/checkins/batch-3-rev.md:1796: trailing whitespace.
++++   511	
.oracle/checkins/batch-3-rev.md:1798: trailing whitespace.
++++   531	
.oracle/checkins/batch-3-rev.md:1800: trailing whitespace.
++++   532	
.oracle/checkins/batch-3-rev.md:1802: trailing whitespace.
++++   539	
.oracle/checkins/batch-3-rev.md:1804: trailing whitespace.
++++   584	
.oracle/checkins/batch-3-rev.md:1806: trailing whitespace.
++++   601	
.oracle/checkins/batch-3-rev.md:1808: trailing whitespace.
++++   613	
.oracle/checkins/batch-3-rev.md:1810: trailing whitespace.
++++   614	
.oracle/checkins/batch-3-rev.md:1812: trailing whitespace.
++++   627	
.oracle/checkins/batch-3-rev.md:1814: trailing whitespace.
++++   628	
.oracle/checkins/batch-3-rev.md:1816: trailing whitespace.
++++   632	
.oracle/checkins/batch-3-rev.md:1818: trailing whitespace.
++++   633	
.oracle/checkins/batch-3-rev.md:1820: trailing whitespace.
++++   647	
.oracle/checkins/batch-3-rev.md:1822: trailing whitespace.
++++   654	
.oracle/checkins/batch-3-rev.md:1824: trailing whitespace.
++++   655	
.oracle/checkins/batch-3-rev.md:1826: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1828: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1830: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1832: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1834: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1836: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1838: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1840: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1842: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1844: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1846: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1848: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1850: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1852: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1854: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1856: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1858: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1860: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1862: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1864: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1866: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1868: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1870: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1872: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1874: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1876: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1878: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1880: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1882: trailing whitespace.
++++   174	
.oracle/checkins/batch-3-rev.md:1884: trailing whitespace.
++++   177	
.oracle/checkins/batch-3-rev.md:1886: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:1888: trailing whitespace.
++++   185	
.oracle/checkins/batch-3-rev.md:1890: trailing whitespace.
++++   193	
.oracle/checkins/batch-3-rev.md:1892: trailing whitespace.
++++   196	
.oracle/checkins/batch-3-rev.md:1894: trailing whitespace.
++++   140	
.oracle/checkins/batch-3-rev.md:1896: trailing whitespace.
++++   162	
.oracle/checkins/batch-3-rev.md:1898: trailing whitespace.
++++   171	
.oracle/checkins/batch-3-rev.md:1900: trailing whitespace.
++++   201	
.oracle/checkins/batch-3-rev.md:1902: trailing whitespace.
++++   202	
.oracle/checkins/batch-3-rev.md:1904: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:1906: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:1908: trailing whitespace.
++++    77	
.oracle/checkins/batch-3-rev.md:1910: trailing whitespace.
++++    78	
.oracle/checkins/batch-3-rev.md:1912: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:1914: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:1916: trailing whitespace.
++++   104	
.oracle/checkins/batch-3-rev.md:1918: trailing whitespace.
++++   105	
.oracle/checkins/batch-3-rev.md:1920: trailing whitespace.
++++   113	
.oracle/checkins/batch-3-rev.md:1922: trailing whitespace.
++++   114	
.oracle/checkins/batch-3-rev.md:1924: trailing whitespace.
++++   127	
.oracle/checkins/batch-3-rev.md:1926: trailing whitespace.
++++   128	
.oracle/checkins/batch-3-rev.md:1928: trailing whitespace.
++++   142	
.oracle/checkins/batch-3-rev.md:1930: trailing whitespace.
++++   143	
.oracle/checkins/batch-3-rev.md:1932: trailing whitespace.
++++   161	
.oracle/checkins/batch-3-rev.md:1934: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:1936: trailing whitespace.
++++   176	
.oracle/checkins/batch-3-rev.md:1938: trailing whitespace.
++++   177	
.oracle/checkins/batch-3-rev.md:1940: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:1942: trailing whitespace.
++++   182	
.oracle/checkins/batch-3-rev.md:1944: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1946: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1948: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1950: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1952: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1954: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1956: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1958: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1960: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:1962: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:1964: trailing whitespace.
++++     8	
.oracle/checkins/batch-3-rev.md:1966: trailing whitespace.
++++    10	
.oracle/checkins/batch-3-rev.md:1968: trailing whitespace.
++++    21	
.oracle/checkins/batch-3-rev.md:1970: trailing whitespace.
++++    24	
.oracle/checkins/batch-3-rev.md:1972: trailing whitespace.
++++    25	
.oracle/checkins/batch-3-rev.md:1974: trailing whitespace.
++++    28	
.oracle/checkins/batch-3-rev.md:1976: trailing whitespace.
++++    29	
.oracle/checkins/batch-3-rev.md:1978: trailing whitespace.
++++    55	
.oracle/checkins/batch-3-rev.md:1980: trailing whitespace.
++++    56	
.oracle/checkins/batch-3-rev.md:1982: trailing whitespace.
++++    61	
.oracle/checkins/batch-3-rev.md:1984: trailing whitespace.
++++    62	
.oracle/checkins/batch-3-rev.md:1986: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:1988: trailing whitespace.
++++    72	
.oracle/checkins/batch-3-rev.md:1990: trailing whitespace.
++++    79	
.oracle/checkins/batch-3-rev.md:1992: trailing whitespace.
++++    80	
.oracle/checkins/batch-3-rev.md:1994: trailing whitespace.
++++    94	
.oracle/checkins/batch-3-rev.md:1996: trailing whitespace.
++++    95	
.oracle/checkins/batch-3-rev.md:1998: trailing whitespace.
++++   102	
.oracle/checkins/batch-3-rev.md:2000: trailing whitespace.
++++   104	
.oracle/checkins/batch-3-rev.md:2002: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:2004: trailing whitespace.
++++   113	
.oracle/checkins/batch-3-rev.md:2006: trailing whitespace.
++++   119	
.oracle/checkins/batch-3-rev.md:2008: trailing whitespace.
++++   128	
.oracle/checkins/batch-3-rev.md:2010: trailing whitespace.
++++   140	
.oracle/checkins/batch-3-rev.md:2012: trailing whitespace.
++++   162	
.oracle/checkins/batch-3-rev.md:2014: trailing whitespace.
++++   171	
.oracle/checkins/batch-3-rev.md:2016: trailing whitespace.
++++   201	
.oracle/checkins/batch-3-rev.md:2018: trailing whitespace.
++++   202	
.oracle/checkins/batch-3-rev.md:2020: trailing whitespace.
++++   214	
.oracle/checkins/batch-3-rev.md:2022: trailing whitespace.
++++   215	
.oracle/checkins/batch-3-rev.md:2024: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:2026: trailing whitespace.
++++   245	
.oracle/checkins/batch-3-rev.md:2028: trailing whitespace.
++++   248	
.oracle/checkins/batch-3-rev.md:2030: trailing whitespace.
++++   266	
.oracle/checkins/batch-3-rev.md:2032: trailing whitespace.
++++   313	
.oracle/checkins/batch-3-rev.md:2034: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:2036: trailing whitespace.
++++   335	
.oracle/checkins/batch-3-rev.md:2038: trailing whitespace.
++++   339	
.oracle/checkins/batch-3-rev.md:2040: trailing whitespace.
++++   360	
.oracle/checkins/batch-3-rev.md:2042: trailing whitespace.
++++   361	
.oracle/checkins/batch-3-rev.md:2044: trailing whitespace.
++++   385	
.oracle/checkins/batch-3-rev.md:2046: trailing whitespace.
++++   386	
.oracle/checkins/batch-3-rev.md:2048: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:2050: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:2052: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:2054: trailing whitespace.
++++    14	
.oracle/checkins/batch-3-rev.md:2056: trailing whitespace.
++++    21	
.oracle/checkins/batch-3-rev.md:2058: trailing whitespace.
++++    23	
.oracle/checkins/batch-3-rev.md:2060: trailing whitespace.
++++    27	
.oracle/checkins/batch-3-rev.md:2062: trailing whitespace.
++++    28	
.oracle/checkins/batch-3-rev.md:2064: trailing whitespace.
++++    30	
.oracle/checkins/batch-3-rev.md:2066: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:2068: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:2070: trailing whitespace.
++++    36	
.oracle/checkins/batch-3-rev.md:2072: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:2074: trailing whitespace.
++++    41	
.oracle/checkins/batch-3-rev.md:2076: trailing whitespace.
++++    62	
.oracle/checkins/batch-3-rev.md:2078: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:2080: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:2082: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:2084: trailing whitespace.
++++    77	
.oracle/checkins/batch-3-rev.md:2086: trailing whitespace.
++++    78	
.oracle/checkins/batch-3-rev.md:2088: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:2090: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:2092: trailing whitespace.
++++   104	
.oracle/checkins/batch-3-rev.md:2094: trailing whitespace.
++++   105	
.oracle/checkins/batch-3-rev.md:2096: trailing whitespace.
++++   113	
.oracle/checkins/batch-3-rev.md:2098: trailing whitespace.
++++   114	
.oracle/checkins/batch-3-rev.md:2100: trailing whitespace.
++++   127	
.oracle/checkins/batch-3-rev.md:2102: trailing whitespace.
++++   128	
.oracle/checkins/batch-3-rev.md:2104: trailing whitespace.
++++   142	
.oracle/checkins/batch-3-rev.md:2106: trailing whitespace.
++++   143	
.oracle/checkins/batch-3-rev.md:2108: trailing whitespace.
++++   161	
.oracle/checkins/batch-3-rev.md:2110: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:2112: trailing whitespace.
++++   176	
.oracle/checkins/batch-3-rev.md:2114: trailing whitespace.
++++   177	
.oracle/checkins/batch-3-rev.md:2116: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:2118: trailing whitespace.
++++   182	
.oracle/checkins/batch-3-rev.md:2120: trailing whitespace.
++++   204	
.oracle/checkins/batch-3-rev.md:2122: trailing whitespace.
++++   205	
.oracle/checkins/batch-3-rev.md:2124: trailing whitespace.
++++   208	
.oracle/checkins/batch-3-rev.md:2126: trailing whitespace.
++++   319	
.oracle/checkins/batch-3-rev.md:2128: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:2130: trailing whitespace.
++++   326	
.oracle/checkins/batch-3-rev.md:2132: trailing whitespace.
++++   334	
.oracle/checkins/batch-3-rev.md:2134: trailing whitespace.
++++   338	
.oracle/checkins/batch-3-rev.md:2136: trailing whitespace.
++++   341	
.oracle/checkins/batch-3-rev.md:2138: trailing whitespace.
++++   344	
.oracle/checkins/batch-3-rev.md:2140: trailing whitespace.
++++   345	
.oracle/checkins/batch-3-rev.md:2142: trailing whitespace.
++++   348	
.oracle/checkins/batch-3-rev.md:2144: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:2146: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:2148: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:2150: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:2152: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:2154: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:2156: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:2158: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:2160: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:2162: trailing whitespace.
++++    45	
.oracle/checkins/batch-3-rev.md:2164: trailing whitespace.
++++    53	
.oracle/checkins/batch-3-rev.md:2166: trailing whitespace.
++++    58	
.oracle/checkins/batch-3-rev.md:2168: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:2170: trailing whitespace.
++++    65	
.oracle/checkins/batch-3-rev.md:2172: trailing whitespace.
++++    66	
.oracle/checkins/batch-3-rev.md:2174: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:2176: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:2178: trailing whitespace.
++++    83	
.oracle/checkins/batch-3-rev.md:2180: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:2182: trailing whitespace.
++++    88	
.oracle/checkins/batch-3-rev.md:2184: trailing whitespace.
++++    89	
.oracle/checkins/batch-3-rev.md:2186: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:2188: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:2190: trailing whitespace.
++++   110	
.oracle/checkins/batch-3-rev.md:2192: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:2194: trailing whitespace.
++++   116	
.oracle/checkins/batch-3-rev.md:2196: trailing whitespace.
++++   117	
.oracle/checkins/batch-3-rev.md:2198: trailing whitespace.
++++   135	
.oracle/checkins/batch-3-rev.md:2200: trailing whitespace.
++++   136	
.oracle/checkins/batch-3-rev.md:2202: trailing whitespace.
++++   149	
.oracle/checkins/batch-3-rev.md:2204: trailing whitespace.
++++   150	
.oracle/checkins/batch-3-rev.md:2206: trailing whitespace.
++++   163	
.oracle/checkins/batch-3-rev.md:2208: trailing whitespace.
++++   164	
.oracle/checkins/batch-3-rev.md:2210: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:2212: trailing whitespace.
++++   174	
.oracle/checkins/batch-3-rev.md:2214: trailing whitespace.
++++   180	
.oracle/checkins/batch-3-rev.md:2216: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:2218: trailing whitespace.
++++   191	
.oracle/checkins/batch-3-rev.md:2220: trailing whitespace.
++++   192	
.oracle/checkins/batch-3-rev.md:2222: trailing whitespace.
++++   198	
.oracle/checkins/batch-3-rev.md:2224: trailing whitespace.
++++   199	
.oracle/checkins/batch-3-rev.md:2226: trailing whitespace.
++++   206	
.oracle/checkins/batch-3-rev.md:2228: trailing whitespace.
++++   207	
.oracle/checkins/batch-3-rev.md:2230: trailing whitespace.
++++   223	
.oracle/checkins/batch-3-rev.md:2232: trailing whitespace.
++++   224	
.oracle/checkins/batch-3-rev.md:2234: trailing whitespace.
++++   228	
.oracle/checkins/batch-3-rev.md:2236: trailing whitespace.
++++   229	
.oracle/checkins/batch-3-rev.md:2238: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:2240: trailing whitespace.
++++   233	
.oracle/checkins/batch-3-rev.md:2242: trailing whitespace.
++++   237	
.oracle/checkins/batch-3-rev.md:2244: trailing whitespace.
++++   238	
.oracle/checkins/batch-3-rev.md:2246: trailing whitespace.
++++   242	
.oracle/checkins/batch-3-rev.md:2248: trailing whitespace.
++++   243	
.oracle/checkins/batch-3-rev.md:2250: trailing whitespace.
++++   250	
.oracle/checkins/batch-3-rev.md:2252: trailing whitespace.
++++   251	
.oracle/checkins/batch-3-rev.md:2254: trailing whitespace.
++++   254	
.oracle/checkins/batch-3-rev.md:2256: trailing whitespace.
++++   271	
.oracle/checkins/batch-3-rev.md:2258: trailing whitespace.
++++   275	
.oracle/checkins/batch-3-rev.md:2260: trailing whitespace.
++++   278	
.oracle/checkins/batch-3-rev.md:2262: trailing whitespace.
++++   288	
.oracle/checkins/batch-3-rev.md:2264: trailing whitespace.
++++   307	
.oracle/checkins/batch-3-rev.md:2266: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:2268: trailing whitespace.
++++   324	
.oracle/checkins/batch-3-rev.md:2270: trailing whitespace.
++++   336	
.oracle/checkins/batch-3-rev.md:2272: trailing whitespace.
++++   347	
.oracle/checkins/batch-3-rev.md:2274: trailing whitespace.
++++   352	
.oracle/checkins/batch-3-rev.md:2276: trailing whitespace.
++++   374	
.oracle/checkins/batch-3-rev.md:2278: trailing whitespace.
++++   388	
.oracle/checkins/batch-3-rev.md:2280: trailing whitespace.
++++   423	
.oracle/checkins/batch-3-rev.md:2282: trailing whitespace.
++++   436	
.oracle/checkins/batch-3-rev.md:2284: trailing whitespace.
++++   462	
.oracle/checkins/batch-3-rev.md:2286: trailing whitespace.
++++   477	
.oracle/checkins/batch-3-rev.md:2288: trailing whitespace.
++++   479	
.oracle/checkins/batch-3-rev.md:2290: trailing whitespace.
++++   480	
.oracle/checkins/batch-3-rev.md:2292: trailing whitespace.
++++   486	
.oracle/checkins/batch-3-rev.md:2294: trailing whitespace.
++++   487	
.oracle/checkins/batch-3-rev.md:2296: trailing whitespace.
++++   491	
.oracle/checkins/batch-3-rev.md:2298: trailing whitespace.
++++   492	
.oracle/checkins/batch-3-rev.md:2300: trailing whitespace.
++++   507	
.oracle/checkins/batch-3-rev.md:2302: trailing whitespace.
++++   508	
.oracle/checkins/batch-3-rev.md:2304: trailing whitespace.
++++   511	
.oracle/checkins/batch-3-rev.md:2306: trailing whitespace.
++++   531	
.oracle/checkins/batch-3-rev.md:2308: trailing whitespace.
++++   532	
.oracle/checkins/batch-3-rev.md:2310: trailing whitespace.
++++   539	
.oracle/checkins/batch-3-rev.md:2312: trailing whitespace.
++++   584	
.oracle/checkins/batch-3-rev.md:2314: trailing whitespace.
++++   601	
.oracle/checkins/batch-3-rev.md:2316: trailing whitespace.
++++   613	
.oracle/checkins/batch-3-rev.md:2318: trailing whitespace.
++++   614	
.oracle/checkins/batch-3-rev.md:2320: trailing whitespace.
++++   627	
.oracle/checkins/batch-3-rev.md:2322: trailing whitespace.
++++   628	
.oracle/checkins/batch-3-rev.md:2324: trailing whitespace.
++++   632	
.oracle/checkins/batch-3-rev.md:2326: trailing whitespace.
++++   633	
.oracle/checkins/batch-3-rev.md:2328: trailing whitespace.
++++   647	
.oracle/checkins/batch-3-rev.md:2330: trailing whitespace.
++++   654	
.oracle/checkins/batch-3-rev.md:2332: trailing whitespace.
++++   655	
.oracle/checkins/batch-3-rev.md:2334: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:2336: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:2338: trailing whitespace.
++++     9	
.oracle/checkins/batch-3-rev.md:2340: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:2342: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:2344: trailing whitespace.
++++    20	
.oracle/checkins/batch-3-rev.md:2346: trailing whitespace.
++++    21	
.oracle/checkins/batch-3-rev.md:2348: trailing whitespace.
++++    24	
.oracle/checkins/batch-3-rev.md:2350: trailing whitespace.
++++    25	
.oracle/checkins/batch-3-rev.md:2352: trailing whitespace.
++++    30	
.oracle/checkins/batch-3-rev.md:2354: trailing whitespace.
++++    38	
.oracle/checkins/batch-3-rev.md:2356: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:2358: trailing whitespace.
++++    44	
.oracle/checkins/batch-3-rev.md:2360: trailing whitespace.
++++    49	
.oracle/checkins/batch-3-rev.md:2362: trailing whitespace.
++++    50	
.oracle/checkins/batch-3-rev.md:2364: trailing whitespace.
++++    54	
.oracle/checkins/batch-3-rev.md:2366: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:2368: trailing whitespace.
++++    11	
.oracle/checkins/batch-3-rev.md:2370: trailing whitespace.
++++    16	
.oracle/checkins/batch-3-rev.md:2372: trailing whitespace.
++++    18	
.oracle/checkins/batch-3-rev.md:2374: trailing whitespace.
++++    22	
.oracle/checkins/batch-3-rev.md:2376: trailing whitespace.
++++    23	
.oracle/checkins/batch-3-rev.md:2378: trailing whitespace.
++++    36	
.oracle/checkins/batch-3-rev.md:2380: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:2382: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:2384: trailing whitespace.
++++    56	
.oracle/checkins/batch-3-rev.md:2386: trailing whitespace.
++++    57	
.oracle/checkins/batch-3-rev.md:2388: trailing whitespace.
++++    60	
.oracle/checkins/batch-3-rev.md:2390: trailing whitespace.
++++    61	
.oracle/checkins/batch-3-rev.md:2392: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:2394: trailing whitespace.
++++    64	
.oracle/checkins/batch-3-rev.md:2396: trailing whitespace.
++++    68	
.oracle/checkins/batch-3-rev.md:2398: trailing whitespace.
++++    69	
.oracle/checkins/batch-3-rev.md:2400: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:2402: trailing whitespace.
++++    72	
.oracle/checkins/batch-3-rev.md:2404: trailing whitespace.
++++    76	
.oracle/checkins/batch-3-rev.md:2406: trailing whitespace.
++++    77	
.oracle/checkins/batch-3-rev.md:2408: trailing whitespace.
++++    79	
.oracle/checkins/batch-3-rev.md:2410: trailing whitespace.
++++    80	
.oracle/checkins/batch-3-rev.md:2412: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:2414: trailing whitespace.
++++    85	
.oracle/checkins/batch-3-rev.md:2416: trailing whitespace.
++++   100	
.oracle/checkins/batch-3-rev.md:2418: trailing whitespace.
++++   106	
.oracle/checkins/batch-3-rev.md:2420: trailing whitespace.
++++   107	
.oracle/checkins/batch-3-rev.md:2422: trailing whitespace.
++++   153	
.oracle/checkins/batch-3-rev.md:2424: trailing whitespace.
++++   162	
.oracle/checkins/batch-3-rev.md:2426: trailing whitespace.
++++   213	
.oracle/checkins/batch-3-rev.md:2428: trailing whitespace.
++++   219	
.oracle/checkins/batch-3-rev.md:2430: trailing whitespace.
++++   220	
.oracle/checkins/batch-3-rev.md:2432: trailing whitespace.
++++   222	
.oracle/checkins/batch-3-rev.md:2434: trailing whitespace.
++++   223	
.oracle/checkins/batch-3-rev.md:2436: trailing whitespace.
++++   229	
.oracle/checkins/batch-3-rev.md:2438: trailing whitespace.
++++   230	
.oracle/checkins/batch-3-rev.md:2440: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:2442: trailing whitespace.
++++   233	
.oracle/checkins/batch-3-rev.md:2444: trailing whitespace.
++++   242	
.oracle/checkins/batch-3-rev.md:2446: trailing whitespace.
++++   243	
.oracle/checkins/batch-3-rev.md:2448: trailing whitespace.
++++   245	
.oracle/checkins/batch-3-rev.md:2450: trailing whitespace.
++++   246	
.oracle/checkins/batch-3-rev.md:2452: trailing whitespace.
++++   249	
.oracle/checkins/batch-3-rev.md:2454: trailing whitespace.
++++   256	
.oracle/checkins/batch-3-rev.md:2456: trailing whitespace.
++++   259	
.oracle/checkins/batch-3-rev.md:2458: trailing whitespace.
++++   264	
.oracle/checkins/batch-3-rev.md:2460: trailing whitespace.
++++   265	
.oracle/checkins/batch-3-rev.md:2462: trailing whitespace.
++++   269	
.oracle/checkins/batch-3-rev.md:2464: trailing whitespace.
++++   270	
.oracle/checkins/batch-3-rev.md:2466: trailing whitespace.
++++   274	
.oracle/checkins/batch-3-rev.md:2468: trailing whitespace.
++++   278	
.oracle/checkins/batch-3-rev.md:2470: trailing whitespace.
++++   279	
.oracle/checkins/batch-3-rev.md:2472: trailing whitespace.
++++   285	
.oracle/checkins/batch-3-rev.md:2474: trailing whitespace.
++++   292	
.oracle/checkins/batch-3-rev.md:2476: trailing whitespace.
++++   293	
.oracle/checkins/batch-3-rev.md:2478: trailing whitespace.
++++   297	
.oracle/checkins/batch-3-rev.md:2480: trailing whitespace.
++++   303	
.oracle/checkins/batch-3-rev.md:2482: trailing whitespace.
++++   309	
.oracle/checkins/batch-3-rev.md:2484: trailing whitespace.
++++   310	
.oracle/checkins/batch-3-rev.md:2486: trailing whitespace.
++++   316	
.oracle/checkins/batch-3-rev.md:2488: trailing whitespace.
++++   329	
.oracle/checkins/batch-3-rev.md:2490: trailing whitespace.
++++   330	
.oracle/checkins/batch-3-rev.md:2492: trailing whitespace.
++++   335	
.oracle/checkins/batch-3-rev.md:2494: trailing whitespace.
++++   341	
.oracle/checkins/batch-3-rev.md:2496: trailing whitespace.
++++   342	
.oracle/checkins/batch-3-rev.md:2498: trailing whitespace.
++++   344	
.oracle/checkins/batch-3-rev.md:2500: trailing whitespace.
++++   345	
.oracle/checkins/batch-3-rev.md:2502: trailing whitespace.
++++   352	
.oracle/checkins/batch-3-rev.md:2504: trailing whitespace.
++++   353	
.oracle/checkins/batch-3-rev.md:2506: trailing whitespace.
++++   356	
.oracle/checkins/batch-3-rev.md:2508: trailing whitespace.
++++   357	
.oracle/checkins/batch-3-rev.md:2510: trailing whitespace.
++++   380	
.oracle/checkins/batch-3-rev.md:2512: trailing whitespace.
++++   381	
.oracle/checkins/batch-3-rev.md:2514: trailing whitespace.
++++   391	
.oracle/checkins/batch-3-rev.md:2516: trailing whitespace.
++++   392	
.oracle/checkins/batch-3-rev.md:2518: trailing whitespace.
++++   400	
.oracle/checkins/batch-3-rev.md:2520: trailing whitespace.
++++   401	
.oracle/checkins/batch-3-rev.md:2522: trailing whitespace.
++++   407	
.oracle/checkins/batch-3-rev.md:2524: trailing whitespace.
++++   408	
.oracle/checkins/batch-3-rev.md:2526: trailing whitespace.
++++   417	
.oracle/checkins/batch-3-rev.md:2528: trailing whitespace.
++++   418	
.oracle/checkins/batch-3-rev.md:2530: trailing whitespace.
++++   421	
.oracle/checkins/batch-3-rev.md:2532: trailing whitespace.
++++   428	
.oracle/checkins/batch-3-rev.md:2534: trailing whitespace.
++++   432	
.oracle/checkins/batch-3-rev.md:2536: trailing whitespace.
++++   434	
.oracle/checkins/batch-3-rev.md:2538: trailing whitespace.
++++   440	
.oracle/checkins/batch-3-rev.md:2540: trailing whitespace.
++++   441	
.oracle/checkins/batch-3-rev.md:2542: trailing whitespace.
++++   445	
.oracle/checkins/batch-3-rev.md:2544: trailing whitespace.
++++   451	
.oracle/checkins/batch-3-rev.md:2546: trailing whitespace.
++++   452	
.oracle/checkins/batch-3-rev.md:2548: trailing whitespace.
++++   455	
.oracle/checkins/batch-3-rev.md:2550: trailing whitespace.
++++   463	
.oracle/checkins/batch-3-rev.md:2552: trailing whitespace.
++++   468	
.oracle/checkins/batch-3-rev.md:2554: trailing whitespace.
++++   471	
.oracle/checkins/batch-3-rev.md:2556: trailing whitespace.
++++   472	
.oracle/checkins/batch-3-rev.md:2558: trailing whitespace.
++++   475	
.oracle/checkins/batch-3-rev.md:2560: trailing whitespace.
++++   481	
.oracle/checkins/batch-3-rev.md:2562: trailing whitespace.
++++   488	
.oracle/checkins/batch-3-rev.md:2564: trailing whitespace.
++++   494	
.oracle/checkins/batch-3-rev.md:2566: trailing whitespace.
++++   495	
.oracle/checkins/batch-3-rev.md:2568: trailing whitespace.
++++   498	
.oracle/checkins/batch-3-rev.md:2570: trailing whitespace.
++++   506	
.oracle/checkins/batch-3-rev.md:2572: trailing whitespace.
++++   517	
.oracle/checkins/batch-3-rev.md:2574: trailing whitespace.
++++   532	
.oracle/checkins/batch-3-rev.md:2576: trailing whitespace.
++++   533	
.oracle/checkins/batch-3-rev.md:2578: trailing whitespace.
++++   536	
.oracle/checkins/batch-3-rev.md:2580: trailing whitespace.
++++   543	
.oracle/checkins/batch-3-rev.md:2582: trailing whitespace.
++++   547	
.oracle/checkins/batch-3-rev.md:2584: trailing whitespace.
++++   554	
.oracle/checkins/batch-3-rev.md:2586: trailing whitespace.
++++   557	
.oracle/checkins/batch-3-rev.md:2588: trailing whitespace.
++++   558	
.oracle/checkins/batch-3-rev.md:2590: trailing whitespace.
++++   562	
.oracle/checkins/batch-3-rev.md:2592: trailing whitespace.
++++   565	
.oracle/checkins/batch-3-rev.md:2594: trailing whitespace.
++++   576	
.oracle/checkins/batch-3-rev.md:2596: trailing whitespace.
++++   584	
.oracle/checkins/batch-3-rev.md:2598: trailing whitespace.
++++   587	
.oracle/checkins/batch-3-rev.md:2600: trailing whitespace.
++++   588	
.oracle/checkins/batch-3-rev.md:2602: trailing whitespace.
++++   592	
.oracle/checkins/batch-3-rev.md:2604: trailing whitespace.
++++   595	
.oracle/checkins/batch-3-rev.md:2606: trailing whitespace.
++++   606	
.oracle/checkins/batch-3-rev.md:2608: trailing whitespace.
++++   615	
.oracle/checkins/batch-3-rev.md:2610: trailing whitespace.
++++   619	
.oracle/checkins/batch-3-rev.md:2612: trailing whitespace.
++++   620	
.oracle/checkins/batch-3-rev.md:2614: trailing whitespace.
++++   624	
.oracle/checkins/batch-3-rev.md:2616: trailing whitespace.
++++   629	
.oracle/checkins/batch-3-rev.md:2618: trailing whitespace.
++++   630	
.oracle/checkins/batch-3-rev.md:2620: trailing whitespace.
++++   633	
.oracle/checkins/batch-3-rev.md:2622: trailing whitespace.
++++   634	
.oracle/checkins/batch-3-rev.md:2624: trailing whitespace.
++++   655	
.oracle/checkins/batch-3-rev.md:2626: trailing whitespace.
++++   656	
.oracle/checkins/batch-3-rev.md:2628: trailing whitespace.
++++   661	
.oracle/checkins/batch-3-rev.md:2630: trailing whitespace.
++++   663	
.oracle/checkins/batch-3-rev.md:2632: trailing whitespace.
++++   672	
.oracle/checkins/batch-3-rev.md:2634: trailing whitespace.
++++   676	
.oracle/checkins/batch-3-rev.md:2636: trailing whitespace.
++++   679	
.oracle/checkins/batch-3-rev.md:2638: trailing whitespace.
++++   682	
.oracle/checkins/batch-3-rev.md:2640: trailing whitespace.
++++   694	
.oracle/checkins/batch-3-rev.md:2642: trailing whitespace.
++++   706	
.oracle/checkins/batch-3-rev.md:2644: trailing whitespace.
++++   707	
.oracle/checkins/batch-3-rev.md:2646: trailing whitespace.
++++   711	
.oracle/checkins/batch-3-rev.md:2648: trailing whitespace.
++++   714	
.oracle/checkins/batch-3-rev.md:2650: trailing whitespace.
++++   720	
.oracle/checkins/batch-3-rev.md:2652: trailing whitespace.
++++   721	
.oracle/checkins/batch-3-rev.md:2654: trailing whitespace.
++++   724	
.oracle/checkins/batch-3-rev.md:2656: trailing whitespace.
++++   731	
.oracle/checkins/batch-3-rev.md:2658: trailing whitespace.
++++   733	
.oracle/checkins/batch-3-rev.md:2660: trailing whitespace.
++++   738	
.oracle/checkins/batch-3-rev.md:2662: trailing whitespace.
++++   744	
.oracle/checkins/batch-3-rev.md:2664: trailing whitespace.
++++   745	
.oracle/checkins/batch-3-rev.md:2666: trailing whitespace.
++++   749	
.oracle/checkins/batch-3-rev.md:2668: trailing whitespace.
++++   752	
.oracle/checkins/batch-3-rev.md:2670: trailing whitespace.
++++   758	
.oracle/checkins/batch-3-rev.md:2672: trailing whitespace.
++++   760	
.oracle/checkins/batch-3-rev.md:2674: trailing whitespace.
++++   762	
.oracle/checkins/batch-3-rev.md:2676: trailing whitespace.
++++   763	
.oracle/checkins/batch-3-rev.md:2678: trailing whitespace.
++++   767	
.oracle/checkins/batch-3-rev.md:2680: trailing whitespace.
++++   772	
.oracle/checkins/batch-3-rev.md:2682: trailing whitespace.
++++   777	
.oracle/checkins/batch-3-rev.md:2684: trailing whitespace.
++++   782	
.oracle/checkins/batch-3-rev.md:2686: trailing whitespace.
++++   787	
.oracle/checkins/batch-3-rev.md:2688: trailing whitespace.
++++   792	
.oracle/checkins/batch-3-rev.md:2690: trailing whitespace.
++++   793	
.oracle/checkins/batch-3-rev.md:2692: trailing whitespace.
++++   797	
.oracle/checkins/batch-3-rev.md:2694: trailing whitespace.
++++   804	
.oracle/checkins/batch-3-rev.md:2696: trailing whitespace.
++++   811	
.oracle/checkins/batch-3-rev.md:2698: trailing whitespace.
++++   818	
.oracle/checkins/batch-3-rev.md:2700: trailing whitespace.
++++   819	
.oracle/checkins/batch-3-rev.md:2702: trailing whitespace.
++++   823	
.oracle/checkins/batch-3-rev.md:2704: trailing whitespace.
++++   829	
.oracle/checkins/batch-3-rev.md:2706: trailing whitespace.
++++   834	
.oracle/checkins/batch-3-rev.md:2708: trailing whitespace.
++++   839	
.oracle/checkins/batch-3-rev.md:2710: trailing whitespace.
++++   840	
.oracle/checkins/batch-3-rev.md:2712: trailing whitespace.
++++   844	
.oracle/checkins/batch-3-rev.md:2714: trailing whitespace.
++++   845	
.oracle/checkins/batch-3-rev.md:2716: trailing whitespace.
++++   849	
.oracle/checkins/batch-3-rev.md:2718: trailing whitespace.
++++   861	
.oracle/checkins/batch-3-rev.md:2720: trailing whitespace.
++++   867	
.oracle/checkins/batch-3-rev.md:2722: trailing whitespace.
++++   881	
.oracle/checkins/batch-3-rev.md:2724: trailing whitespace.
++++   882	
.oracle/checkins/batch-3-rev.md:2726: trailing whitespace.
++++   886	
.oracle/checkins/batch-3-rev.md:2728: trailing whitespace.
++++   932	
.oracle/checkins/batch-3-rev.md:2730: trailing whitespace.
++++   948	
.oracle/checkins/batch-3-rev.md:2732: trailing whitespace.
++++   949	
.oracle/checkins/batch-3-rev.md:2734: trailing whitespace.
++++   953	
.oracle/checkins/batch-3-rev.md:2736: trailing whitespace.
++++   973	
.oracle/checkins/batch-3-rev.md:2738: trailing whitespace.
++++   985	
.oracle/checkins/batch-3-rev.md:2740: trailing whitespace.
++++   990	
.oracle/checkins/batch-3-rev.md:2742: trailing whitespace.
++++   995	
.oracle/checkins/batch-3-rev.md:2744: trailing whitespace.
++++  1000	
.oracle/checkins/batch-3-rev.md:2746: trailing whitespace.
++++  1004	
.oracle/checkins/batch-3-rev.md:2748: trailing whitespace.
++++  1005	
.oracle/checkins/batch-3-rev.md:2750: trailing whitespace.
++++  1009	
.oracle/checkins/batch-3-rev.md:2752: trailing whitespace.
++++  1010	
.oracle/checkins/batch-3-rev.md:2754: trailing whitespace.
++++  1015	
.oracle/checkins/batch-3-rev.md:2756: trailing whitespace.
++++  1028	
.oracle/checkins/batch-3-rev.md:2758: trailing whitespace.
++++  1029	
.oracle/checkins/batch-3-rev.md:2760: trailing whitespace.
++++  1042	
.oracle/checkins/batch-3-rev.md:2762: trailing whitespace.
++++  1043	
.oracle/checkins/batch-3-rev.md:2764: trailing whitespace.
++++  1051	
.oracle/checkins/batch-3-rev.md:2766: trailing whitespace.
++++  1052	
.oracle/checkins/batch-3-rev.md:2768: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:2770: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:2772: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:2774: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:2776: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:2778: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:2780: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:2782: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:2784: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:2786: trailing whitespace.
++++    45	
.oracle/checkins/batch-3-rev.md:2788: trailing whitespace.
++++    53	
.oracle/checkins/batch-3-rev.md:2790: trailing whitespace.
++++    58	
.oracle/checkins/batch-3-rev.md:2792: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:2794: trailing whitespace.
++++    65	
.oracle/checkins/batch-3-rev.md:2796: trailing whitespace.
++++    66	
.oracle/checkins/batch-3-rev.md:2798: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:2800: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:2802: trailing whitespace.
++++    83	
.oracle/checkins/batch-3-rev.md:2804: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:2806: trailing whitespace.
++++    88	
.oracle/checkins/batch-3-rev.md:2808: trailing whitespace.
++++    89	
.oracle/checkins/batch-3-rev.md:2810: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:2812: trailing whitespace.
++++    98	
.oracle/checkins/batch-3-rev.md:2814: trailing whitespace.
++++   110	
.oracle/checkins/batch-3-rev.md:2816: trailing whitespace.
++++   111	
.oracle/checkins/batch-3-rev.md:2818: trailing whitespace.
++++   116	
.oracle/checkins/batch-3-rev.md:2820: trailing whitespace.
++++   117	
.oracle/checkins/batch-3-rev.md:2822: trailing whitespace.
++++   135	
.oracle/checkins/batch-3-rev.md:2824: trailing whitespace.
++++   136	
.oracle/checkins/batch-3-rev.md:2826: trailing whitespace.
++++   149	
.oracle/checkins/batch-3-rev.md:2828: trailing whitespace.
++++   150	
.oracle/checkins/batch-3-rev.md:2830: trailing whitespace.
++++   163	
.oracle/checkins/batch-3-rev.md:2832: trailing whitespace.
++++   164	
.oracle/checkins/batch-3-rev.md:2834: trailing whitespace.
++++   173	
.oracle/checkins/batch-3-rev.md:2836: trailing whitespace.
++++   174	
.oracle/checkins/batch-3-rev.md:2838: trailing whitespace.
++++   180	
.oracle/checkins/batch-3-rev.md:2840: trailing whitespace.
++++   181	
.oracle/checkins/batch-3-rev.md:2842: trailing whitespace.
++++   191	
.oracle/checkins/batch-3-rev.md:2844: trailing whitespace.
++++   192	
.oracle/checkins/batch-3-rev.md:2846: trailing whitespace.
++++   198	
.oracle/checkins/batch-3-rev.md:2848: trailing whitespace.
++++   199	
.oracle/checkins/batch-3-rev.md:2850: trailing whitespace.
++++   206	
.oracle/checkins/batch-3-rev.md:2852: trailing whitespace.
++++   207	
.oracle/checkins/batch-3-rev.md:2854: trailing whitespace.
++++   223	
.oracle/checkins/batch-3-rev.md:2856: trailing whitespace.
++++   224	
.oracle/checkins/batch-3-rev.md:2858: trailing whitespace.
++++   228	
.oracle/checkins/batch-3-rev.md:2860: trailing whitespace.
++++   229	
.oracle/checkins/batch-3-rev.md:2862: trailing whitespace.
++++   232	
.oracle/checkins/batch-3-rev.md:2864: trailing whitespace.
++++   233	
.oracle/checkins/batch-3-rev.md:2866: trailing whitespace.
++++   237	
.oracle/checkins/batch-3-rev.md:2868: trailing whitespace.
++++   238	
.oracle/checkins/batch-3-rev.md:2870: trailing whitespace.
++++   531	
.oracle/checkins/batch-3-rev.md:2872: trailing whitespace.
++++   532	
.oracle/checkins/batch-3-rev.md:2874: trailing whitespace.
++++   539	
.oracle/checkins/batch-3-rev.md:2876: trailing whitespace.
++++   584	
.oracle/checkins/batch-3-rev.md:2878: trailing whitespace.
++++   601	
.oracle/checkins/batch-3-rev.md:2880: trailing whitespace.
++++   613	
.oracle/checkins/batch-3-rev.md:2882: trailing whitespace.
++++   614	
.oracle/checkins/batch-3-rev.md:2884: trailing whitespace.
++++   627	
.oracle/checkins/batch-3-rev.md:2886: trailing whitespace.
++++   628	
.oracle/checkins/batch-3-rev.md:2888: trailing whitespace.
++++   632	
.oracle/checkins/batch-3-rev.md:2890: trailing whitespace.
++++   633	
.oracle/checkins/batch-3-rev.md:2892: trailing whitespace.
++++   647	
.oracle/checkins/batch-3-rev.md:2894: trailing whitespace.
++++   654	
.oracle/checkins/batch-3-rev.md:2896: trailing whitespace.
++++   655	
.oracle/checkins/batch-3-rev.md:2898: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2900: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2902: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2904: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2906: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2908: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2910: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2912: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2914: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2916: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2918: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2920: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2922: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2924: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2926: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2928: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2930: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2932: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2934: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2936: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2938: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2940: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2942: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2944: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2946: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2948: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2950: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:2952: trailing whitespace.
++++   242	
.oracle/checkins/batch-3-rev.md:2954: trailing whitespace.
++++   243	
.oracle/checkins/batch-3-rev.md:2956: trailing whitespace.
++++   250	
.oracle/checkins/batch-3-rev.md:2958: trailing whitespace.
++++   251	
.oracle/checkins/batch-3-rev.md:2960: trailing whitespace.
++++   254	
.oracle/checkins/batch-3-rev.md:2962: trailing whitespace.
++++   271	
.oracle/checkins/batch-3-rev.md:2964: trailing whitespace.
++++   275	
.oracle/checkins/batch-3-rev.md:2966: trailing whitespace.
++++   278	
.oracle/checkins/batch-3-rev.md:2968: trailing whitespace.
++++   288	
.oracle/checkins/batch-3-rev.md:2970: trailing whitespace.
++++   307	
.oracle/checkins/batch-3-rev.md:2972: trailing whitespace.
++++   320	
.oracle/checkins/batch-3-rev.md:2974: trailing whitespace.
++++   324	
.oracle/checkins/batch-3-rev.md:2976: trailing whitespace.
++++   336	
.oracle/checkins/batch-3-rev.md:2978: trailing whitespace.
++++   347	
.oracle/checkins/batch-3-rev.md:2980: trailing whitespace.
++++   352	
.oracle/checkins/batch-3-rev.md:2982: trailing whitespace.
++++   374	
.oracle/checkins/batch-3-rev.md:2984: trailing whitespace.
++++   388	
.oracle/checkins/batch-3-rev.md:2986: trailing whitespace.
++++   423	
.oracle/checkins/batch-3-rev.md:2988: trailing whitespace.
++++   436	
.oracle/checkins/batch-3-rev.md:2990: trailing whitespace.
++++   462	
.oracle/checkins/batch-3-rev.md:2992: trailing whitespace.
++++   477	
.oracle/checkins/batch-3-rev.md:2994: trailing whitespace.
++++   479	
.oracle/checkins/batch-3-rev.md:2996: trailing whitespace.
++++   480	
.oracle/checkins/batch-3-rev.md:2998: trailing whitespace.
++++   486	
.oracle/checkins/batch-3-rev.md:3000: trailing whitespace.
++++   487	
.oracle/checkins/batch-3-rev.md:3002: trailing whitespace.
++++   491	
.oracle/checkins/batch-3-rev.md:3004: trailing whitespace.
++++   492	
.oracle/checkins/batch-3-rev.md:3006: trailing whitespace.
++++   507	
.oracle/checkins/batch-3-rev.md:3008: trailing whitespace.
++++   508	
.oracle/checkins/batch-3-rev.md:3010: trailing whitespace.
++++   511	
.oracle/checkins/batch-3-rev.md:3012: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:3014: trailing whitespace.
++++ 
.oracle/checkins/batch-3-rev.md:3016: trailing whitespace.
++++   280	
.oracle/checkins/batch-3-rev.md:3018: trailing whitespace.
++++   283	
.oracle/checkins/batch-3-rev.md:3020: trailing whitespace.
++++   300	
.oracle/checkins/batch-3-rev.md:3022: trailing whitespace.
++++   311	
.oracle/checkins/batch-3-rev.md:3024: trailing whitespace.
++++   317	
.oracle/checkins/batch-3-rev.md:3026: trailing whitespace.
++++   326	
.oracle/checkins/batch-3-rev.md:3028: trailing whitespace.
++++   365	
.oracle/checkins/batch-3-rev.md:3030: trailing whitespace.
++++   370	
.oracle/checkins/batch-3-rev.md:3032: trailing whitespace.
++++   392	
.oracle/checkins/batch-3-rev.md:3034: trailing whitespace.
++++   404	
.oracle/checkins/batch-3-rev.md:3036: trailing whitespace.
++++   423	
.oracle/checkins/batch-3-rev.md:3038: trailing whitespace.
++++   451	
.oracle/checkins/batch-3-rev.md:3040: trailing whitespace.
++++   465	
.oracle/checkins/batch-3-rev.md:3042: trailing whitespace.
++++   469	
.oracle/checkins/batch-3-rev.md:3044: trailing whitespace.
++++   472	
.oracle/checkins/batch-3-rev.md:3046: trailing whitespace.
++++   481	
.oracle/checkins/batch-3-rev.md:3048: trailing whitespace.
++++   492	
.oracle/checkins/batch-3-rev.md:3050: trailing whitespace.
++++   496	
.oracle/checkins/batch-3-rev.md:3052: trailing whitespace.
++++   241	
.oracle/checkins/batch-3-rev.md:3054: trailing whitespace.
++++   252	
.oracle/checkins/batch-3-rev.md:3056: trailing whitespace.
++++   255	
.oracle/checkins/batch-3-rev.md:3058: trailing whitespace.
++++   264	
.oracle/checkins/batch-3-rev.md:3060: trailing whitespace.
++++   268	
.oracle/checkins/batch-3-rev.md:3062: trailing whitespace.
++++   275	
.oracle/checkins/batch-3-rev.md:3064: trailing whitespace.
++++   277	
.oracle/checkins/batch-3-rev.md:3066: trailing whitespace.
++++   280	
.oracle/checkins/batch-3-rev.md:3068: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:3070: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:3072: trailing whitespace.
++++    79	
.oracle/checkins/batch-3-rev.md:3074: trailing whitespace.
++++    80	
.oracle/checkins/batch-3-rev.md:3076: trailing whitespace.
++++    92	
.oracle/checkins/batch-3-rev.md:3078: trailing whitespace.
++++    97	
.oracle/checkins/batch-3-rev.md:3080: trailing whitespace.
++++    99	
.oracle/checkins/batch-3-rev.md:3082: trailing whitespace.
++++   100	
.oracle/checkins/batch-3-rev.md:3084: trailing whitespace.
++++   107	
.oracle/checkins/batch-3-rev.md:3086: trailing whitespace.
++++   108	
.oracle/checkins/batch-3-rev.md:3088: trailing whitespace.
++++     2	
.oracle/checkins/batch-3-rev.md:3090: trailing whitespace.
++++     7	
.oracle/checkins/batch-3-rev.md:3092: trailing whitespace.
++++    12	
.oracle/checkins/batch-3-rev.md:3094: trailing whitespace.
++++    15	
.oracle/checkins/batch-3-rev.md:3096: trailing whitespace.
++++    31	
.oracle/checkins/batch-3-rev.md:3098: trailing whitespace.
++++    35	
.oracle/checkins/batch-3-rev.md:3100: trailing whitespace.
++++    37	
.oracle/checkins/batch-3-rev.md:3102: trailing whitespace.
++++    40	
.oracle/checkins/batch-3-rev.md:3104: trailing whitespace.
++++    43	
.oracle/checkins/batch-3-rev.md:3106: trailing whitespace.
++++    45	
.oracle/checkins/batch-3-rev.md:3108: trailing whitespace.
++++    53	
.oracle/checkins/batch-3-rev.md:3110: trailing whitespace.
++++    58	
.oracle/checkins/batch-3-rev.md:3112: trailing whitespace.
++++    63	
.oracle/checkins/batch-3-rev.md:3114: trailing whitespace.
++++    65	
.oracle/checkins/batch-3-rev.md:3116: trailing whitespace.
++++    66	
.oracle/checkins/batch-3-rev.md:3118: trailing whitespace.
++++    70	
.oracle/checkins/batch-3-rev.md:3120: trailing whitespace.
++++    71	
.oracle/checkins/batch-3-rev.md:3122: trailing whitespace.
++++    83	
.oracle/checkins/batch-3-rev.md:3124: trailing whitespace.
++++    84	
.oracle/checkins/batch-3-rev.md:3126: trailing whitespace.
+++    80	
.oracle/checkins/batch-3-rev.md:3128: trailing whitespace.
+++    92	
.oracle/checkins/batch-3-rev.md:3130: trailing whitespace.
+++    97	
.oracle/checkins/batch-3-rev.md:3132: trailing whitespace.
+++    99	
.oracle/checkins/batch-3-rev.md:3134: trailing whitespace.
+++   100	
.oracle/checkins/batch-3-rev.md:3136: trailing whitespace.
+++   107	
.oracle/checkins/batch-3-rev.md:3138: trailing whitespace.
+++   108	
.oracle/checkins/batch-3-rev.md:3140: trailing whitespace.
+++   121	
.oracle/checkins/batch-3-rev.md:3142: trailing whitespace.
+++   125	
.oracle/checkins/batch-3-rev.md:3144: trailing whitespace.
+++   129	
.oracle/checkins/batch-3-rev.md:3146: trailing whitespace.
+++   130	
.oracle/checkins/batch-3-rev.md:3148: trailing whitespace.
+++   140	
.oracle/checkins/batch-3-rev.md:3150: trailing whitespace.
+++   141	
.oracle/checkins/batch-3-rev.md:3152: trailing whitespace.
+++   148	
.oracle/checkins/batch-3-rev.md:3154: trailing whitespace.
+++   149	
.oracle/checkins/batch-3-rev.md:3156: trailing whitespace.
+++   154	
.oracle/checkins/batch-3-rev.md:3158: trailing whitespace.
+++   155	
.oracle/checkins/batch-3-rev.md:3160: trailing whitespace.
+++   158	
.oracle/checkins/batch-3-rev.md:3162: trailing whitespace.
+++   170	
.oracle/checkins/batch-3-rev.md:3164: trailing whitespace.
+++   171	
.oracle/checkins/batch-3-rev.md:3166: trailing whitespace.
+++   275	
.oracle/checkins/batch-3-rev.md:3168: trailing whitespace.
+++   277	
.oracle/checkins/batch-3-rev.md:3170: trailing whitespace.
+++   280	
.oracle/checkins/batch-3-rev.md:3172: trailing whitespace.
+++   283	
.oracle/checkins/batch-3-rev.md:3174: trailing whitespace.
+++   300	
.oracle/checkins/batch-3-rev.md:3176: trailing whitespace.
+++   311	
.oracle/checkins/batch-3-rev.md:3178: trailing whitespace.
+++   317	
.oracle/checkins/batch-3-rev.md:3180: trailing whitespace.
+++   326	
.oracle/checkins/batch-3-rev.md:3182: trailing whitespace.
+++   365	
.oracle/checkins/batch-3-rev.md:3184: trailing whitespace.
+++   370	
.oracle/checkins/batch-3-rev.md:3186: trailing whitespace.
+++   392	
.oracle/checkins/batch-3-rev.md:3188: trailing whitespace.
+++   404	
.oracle/checkins/batch-3-rev.md:3190: trailing whitespace.
+++   423	
.oracle/checkins/batch-3-rev.md:3192: trailing whitespace.
+++   451	
.oracle/checkins/batch-3-rev.md:3194: trailing whitespace.
+++   465	
.oracle/checkins/batch-3-rev.md:3196: trailing whitespace.
+++   469	
.oracle/checkins/batch-3-rev.md:3198: trailing whitespace.
+++   472	
.oracle/checkins/batch-3-rev.md:3200: trailing whitespace.
+++   481	
.oracle/checkins/batch-3-rev.md:3202: trailing whitespace.
+++   492	
.oracle/checkins/batch-3-rev.md:3204: trailing whitespace.
+++   496	
.oracle/checkins/batch-3-rev.md:3206: trailing whitespace.
+++   513	
.oracle/checkins/batch-3-rev.md:3208: trailing whitespace.
+++   515	
.oracle/checkins/batch-3-rev.md:3210: trailing whitespace.
+++   538	
.oracle/checkins/batch-3-rev.md:3212: trailing whitespace.
+++   550	
.oracle/checkins/batch-3-rev.md:3214: trailing whitespace.
+++   556	
.oracle/checkins/batch-3-rev.md:3216: trailing whitespace.
+++   568	
.oracle/checkins/batch-3-rev.md:3218: trailing whitespace.
+++   584	
.oracle/checkins/batch-3-rev.md:3220: trailing whitespace.
+++   596	
.oracle/checkins/batch-3-rev.md:3222: trailing whitespace.
+++   604	
.oracle/checkins/batch-3-rev.md:3224: trailing whitespace.
+++   620	
.oracle/checkins/batch-3-rev.md:3226: trailing whitespace.
+++   631	
.oracle/checkins/batch-3-rev.md:3228: trailing whitespace.
+++   634	
.oracle/checkins/batch-3-rev.md:3230: trailing whitespace.
+++   733	
.oracle/checkins/batch-3-rev.md:3232: trailing whitespace.
+++   759	
.oracle/checkins/batch-3-rev.md:3234: trailing whitespace.
+++   764	
.oracle/checkins/batch-3-rev.md:3236: trailing whitespace.
+++   768	
.oracle/checkins/batch-3-rev.md:3238: trailing whitespace.
+++   784	
.oracle/checkins/batch-3-rev.md:3240: trailing whitespace.
+++   787	
.oracle/checkins/batch-3-rev.md:3242: trailing whitespace.
+++   794	
.oracle/checkins/batch-3-rev.md:3244: trailing whitespace.
+++   796	
.oracle/checkins/batch-3-rev.md:3246: trailing whitespace.
+++   803	
.oracle/checkins/batch-3-rev.md:3248: trailing whitespace.
+++   813	
.oracle/checkins/batch-3-rev.md:3250: trailing whitespace.
+++   820	
.oracle/checkins/batch-3-rev.md:3252: trailing whitespace.
+++   823	
.oracle/checkins/batch-3-rev.md:3254: trailing whitespace.
+++   826	
.oracle/checkins/batch-3-rev.md:3256: trailing whitespace.
+++   840	
.oracle/checkins/batch-3-rev.md:3258: trailing whitespace.
+++   847	
.oracle/checkins/batch-3-rev.md:3260: trailing whitespace.
+++   857	
.oracle/checkins/batch-3-rev.md:3262: trailing whitespace.
+++   995	
.oracle/checkins/batch-3-rev.md:3264: trailing whitespace.
+++   996	
.oracle/checkins/batch-3-rev.md:3266: trailing whitespace.
+++  1007	
.oracle/checkins/batch-3-rev.md:3268: trailing whitespace.
+++  1008	
.oracle/checkins/batch-3-rev.md:3270: trailing whitespace.
+++  1019	
.oracle/checkins/batch-3-rev.md:3272: trailing whitespace.
+++  1020	
.oracle/checkins/batch-3-rev.md:3274: trailing whitespace.
+++  1027	
.oracle/checkins/batch-3-rev.md:3276: trailing whitespace.
+++  1031	
.oracle/checkins/batch-3-rev.md:3278: trailing whitespace.
+++  1032	
.oracle/checkins/batch-3-rev.md:3280: trailing whitespace.
+++  1043	
.oracle/checkins/batch-3-rev.md:3282: trailing whitespace.
+++  1044	
.oracle/checkins/batch-3-rev.md:3284: trailing whitespace.
+++  1049	
.oracle/checkins/batch-3-rev.md:3286: trailing whitespace.
+++  1050	
.oracle/checkins/batch-3-rev.md:3288: trailing whitespace.
+++  1054	
.oracle/checkins/batch-3-rev.md:3290: trailing whitespace.
+++  1055	
.oracle/checkins/batch-3-rev.md:3292: trailing whitespace.
+++  1066	
.oracle/checkins/batch-3-rev.md:3294: trailing whitespace.
+++  1067	
.oracle/checkins/batch-3-rev.md:3296: trailing whitespace.
+++  1070	
.oracle/checkins/batch-3-rev.md:3298: trailing whitespace.
+++  1071	
.oracle/checkins/batch-3-rev.md:3300: trailing whitespace.
+++  1078	
.oracle/checkins/batch-3-rev.md:3302: trailing whitespace.
+++  1079	
.oracle/checkins/batch-3-rev.md:3304: trailing whitespace.
+++  1083	
.oracle/checkins/batch-3-rev.md:3306: trailing whitespace.
+++  1087	
.oracle/checkins/batch-3-rev.md:3308: trailing whitespace.
+++  1088	
.oracle/checkins/batch-3-rev.md:3310: trailing whitespace.
+++  1107	
.oracle/checkins/batch-3-rev.md:3312: trailing whitespace.
+++  1108	
.oracle/checkins/batch-3-rev.md:3314: trailing whitespace.
+++  1150	
.oracle/checkins/batch-3-rev.md:3316: trailing whitespace.
+++  1151	
.oracle/checkins/batch-3-rev.md:3318: trailing whitespace.
+++  1154	
.oracle/checkins/batch-3-rev.md:3320: trailing whitespace.
+++  1155	
.oracle/checkins/batch-3-rev.md:3322: trailing whitespace.
+++  1158	
.oracle/checkins/batch-3-rev.md:3324: trailing whitespace.
+++  1172	
.oracle/checkins/batch-3-rev.md:3326: trailing whitespace.
+++  1173	
.oracle/checkins/batch-3-rev.md:3328: trailing whitespace.
+++  1178	
.oracle/checkins/batch-3-rev.md:3330: trailing whitespace.
+++  1191	
.oracle/checkins/batch-3-rev.md:3332: trailing whitespace.
+++  1192	
.oracle/checkins/batch-3-rev.md:3334: trailing whitespace.
+++  1199	
.oracle/checkins/batch-3-rev.md:3336: trailing whitespace.
+++  1206	
.oracle/checkins/batch-3-rev.md:3338: trailing whitespace.
+++  1211	
.oracle/checkins/batch-3-rev.md:3340: trailing whitespace.
+++  1215	
.oracle/checkins/batch-3-rev.md:3342: trailing whitespace.
+++  1232	
.oracle/checkins/batch-3-rev.md:3344: trailing whitespace.
+++  1250	
.oracle/checkins/batch-3-rev.md:3346: trailing whitespace.
+++  1251	
.oracle/checkins/batch-3-rev.md:3348: trailing whitespace.
+++  1261	
.oracle/checkins/batch-3-rev.md:3350: trailing whitespace.
+++  1262	
.oracle/checkins/batch-3-rev.md:3352: trailing whitespace.
+++  1753	
.oracle/checkins/batch-3-rev.md:3354: trailing whitespace.
+++  1754	
.oracle/checkins/batch-3-rev.md:3356: trailing whitespace.
+++  1773	
.oracle/checkins/batch-3-rev.md:3358: trailing whitespace.
+++  1774	
.oracle/checkins/batch-3-rev.md:3360: trailing whitespace.
+++  1782	
.oracle/checkins/batch-3-rev.md:3362: trailing whitespace.
+++  1789	
.oracle/checkins/batch-3-rev.md:3364: trailing whitespace.
+++  1797	
.oracle/checkins/batch-3-rev.md:3366: trailing whitespace.
+++  1798	
.oracle/checkins/batch-3-rev.md:3368: trailing whitespace.
+++  1801	
.oracle/checkins/batch-3-rev.md:3370: trailing whitespace.
+++  1807	
.oracle/checkins/batch-3-rev.md:3372: trailing whitespace.
+++  1808	
.oracle/checkins/batch-3-rev.md:3374: trailing whitespace.
+++  1812	
.oracle/checkins/batch-3-rev.md:3376: trailing whitespace.
+++  1815	
.oracle/checkins/batch-3-rev.md:3378: trailing whitespace.
+++  1816	
.oracle/checkins/batch-3-rev.md:3380: trailing whitespace.
+++   733	
.oracle/checkins/batch-3-rev.md:3382: trailing whitespace.
+++   759	
.oracle/checkins/batch-3-rev.md:3384: trailing whitespace.
+++   764	
.oracle/checkins/batch-3-rev.md:3386: trailing whitespace.
+++   768	
.oracle/checkins/batch-3-rev.md:3388: trailing whitespace.
+++   784	
.oracle/checkins/batch-3-rev.md:3390: trailing whitespace.
+++   787	
.oracle/checkins/batch-3-rev.md:3392: trailing whitespace.
+++   794	
.oracle/checkins/batch-3-rev.md:3394: trailing whitespace.
+++   796	
.oracle/checkins/batch-3-rev.md:3396: trailing whitespace.
+++   803	
.oracle/checkins/batch-3-rev.md:3398: trailing whitespace.
+++   813	
.oracle/checkins/batch-3-rev.md:3400: trailing whitespace.
+++   820	
.oracle/checkins/batch-3-rev.md:3402: trailing whitespace.
+++   823	
.oracle/checkins/batch-3-rev.md:3404: trailing whitespace.
+++   826	
.oracle/checkins/batch-3-rev.md:3406: trailing whitespace.
+++   840	
.oracle/checkins/batch-3-rev.md:3408: trailing whitespace.
+++   847	
.oracle/checkins/batch-3-rev.md:3410: trailing whitespace.
+++   995	
.oracle/checkins/batch-3-rev.md:3412: trailing whitespace.
+++   996	
.oracle/checkins/batch-3-rev.md:3414: trailing whitespace.
+++  1007	
.oracle/checkins/batch-3-rev.md:3416: trailing whitespace.
+++  1008	
.oracle/checkins/batch-3-rev.md:3418: trailing whitespace.
+++  1019	
.oracle/checkins/batch-3-rev.md:3420: trailing whitespace.
+++  1020	
.oracle/checkins/batch-3-rev.md:3422: trailing whitespace.
+++  1027	
.oracle/checkins/batch-3-rev.md:3424: trailing whitespace.
+++  1031	
.oracle/checkins/batch-3-rev.md:3426: trailing whitespace.
+++  1032	
.oracle/checkins/batch-3-rev.md:3428: trailing whitespace.
+++  1043	
.oracle/checkins/batch-3-rev.md:3430: trailing whitespace.
+++  1044	
.oracle/checkins/batch-3-rev.md:3432: trailing whitespace.
+++  1049	
.oracle/checkins/batch-3-rev.md:3434: trailing whitespace.
+++  1050	
.oracle/checkins/batch-3-rev.md:3436: trailing whitespace.
+++  1054	
.oracle/checkins/batch-3-rev.md:3438: trailing whitespace.
+++  1055	
.oracle/checkins/batch-3-rev.md:3440: trailing whitespace.
+++  1270	
.oracle/checkins/batch-3-rev.md:3442: trailing whitespace.
+++  1325	
.oracle/checkins/batch-3-rev.md:3444: trailing whitespace.
+++  1326	
.oracle/checkins/batch-3-rev.md:3446: trailing whitespace.
+++  1338	
.oracle/checkins/batch-3-rev.md:3448: trailing whitespace.
+++  1339	
.oracle/checkins/batch-3-rev.md:3450: trailing whitespace.
+++   187	
.oracle/checkins/batch-3-rev.md:3452: trailing whitespace.
+++   190	
.oracle/checkins/batch-3-rev.md:3454: trailing whitespace.
+++   206	
.oracle/checkins/batch-3-rev.md:3456: trailing whitespace.
+++   209	
.oracle/checkins/batch-3-rev.md:3458: trailing whitespace.
+++   214	
.oracle/checkins/batch-3-rev.md:3460: trailing whitespace.
+++   217	
.oracle/checkins/batch-3-rev.md:3462: trailing whitespace.
+++   222	
.oracle/checkins/batch-3-rev.md:3464: trailing whitespace.
+++   226	
.oracle/checkins/batch-3-rev.md:3466: trailing whitespace.
+++   229	
.oracle/checkins/batch-3-rev.md:3468: trailing whitespace.
+++   232	
.oracle/checkins/batch-3-rev.md:3470: trailing whitespace.
+++   235	
.oracle/checkins/batch-3-rev.md:3472: trailing whitespace.
+++   238	
.oracle/checkins/batch-3-rev.md:3474: trailing whitespace.
+++   241	
.oracle/checkins/batch-3-rev.md:3476: trailing whitespace.
+++   252	
.oracle/checkins/batch-3-rev.md:3478: trailing whitespace.
+++   255	
.oracle/checkins/batch-3-rev.md:3480: trailing whitespace.
+++   264	
.oracle/checkins/batch-3-rev.md:3482: trailing whitespace.
+++   268	
.oracle/checkins/batch-3-rev.md:3484: trailing whitespace.
+++   430	
.oracle/checkins/batch-3-rev.md:3486: trailing whitespace.
+++   431	
.oracle/checkins/batch-3-rev.md:3488: trailing whitespace.
+++   434	
.oracle/checkins/batch-3-rev.md:3490: trailing whitespace.
+++   441	
.oracle/checkins/batch-3-rev.md:3492: trailing whitespace.
+++   449	
.oracle/checkins/batch-3-rev.md:3494: trailing whitespace.
+++   458	
.oracle/checkins/batch-3-rev.md:3496: trailing whitespace.
+++   478	
.oracle/checkins/batch-3-rev.md:3498: trailing whitespace.
+++   482	
.oracle/checkins/batch-3-rev.md:3500: trailing whitespace.
+++   503	
.oracle/checkins/batch-3-rev.md:3502: trailing whitespace.
+++   507	
.oracle/checkins/batch-3-rev.md:3504: trailing whitespace.
+++   511	
.oracle/checkins/batch-3-rev.md:3506: trailing whitespace.
+++   513	
.oracle/checkins/batch-3-rev.md:3508: trailing whitespace.
+++   522	
.oracle/checkins/batch-3-rev.md:3510: trailing whitespace.
+++   607	
.oracle/checkins/batch-3-rev.md:3512: trailing whitespace.
+++   634	
.oracle/checkins/batch-3-rev.md:3514: trailing whitespace.
+++   685	
.oracle/checkins/batch-3-rev.md:3516: trailing whitespace.
+++    37	
.oracle/checkins/batch-3-rev.md:3518: trailing whitespace.
+++    47	
.oracle/checkins/batch-3-rev.md:3520: trailing whitespace.
+++    58	
.oracle/checkins/batch-3-rev.md:3522: trailing whitespace.
+++    60	
.oracle/checkins/batch-3-rev.md:3524: trailing whitespace.
+++    65	
.oracle/checkins/batch-3-rev.md:3526: trailing whitespace.
+++    69	
.oracle/checkins/batch-3-rev.md:3528: trailing whitespace.
+++    70	
.oracle/checkins/batch-3-rev.md:3530: trailing whitespace.
+++   345	
.oracle/checkins/batch-3-rev.md:3532: trailing whitespace.
+++   347	
.oracle/checkins/batch-3-rev.md:3534: trailing whitespace.
+++   354	
.oracle/checkins/batch-3-rev.md:3536: trailing whitespace.
+++   940	
.oracle/checkins/batch-3-rev.md:3538: trailing whitespace.
+++   948	
.oracle/checkins/batch-3-rev.md:3540: trailing whitespace.
+++   949	
.oracle/checkins/batch-3-rev.md:3542: trailing whitespace.
+++   964	
.oracle/checkins/batch-3-rev.md:3544: trailing whitespace.
+++   965	
.oracle/checkins/batch-3-rev.md:3546: trailing whitespace.
+++   719	
.oracle/checkins/batch-3-rev.md:3548: trailing whitespace.
+++   726	
.oracle/checkins/batch-3-rev.md:3550: trailing whitespace.
+++   728	
.oracle/checkins/batch-3-rev.md:3552: trailing whitespace.
+++   730	
.oracle/checkins/batch-3-rev.md:3554: trailing whitespace.
+++   731	
.oracle/checkins/batch-3-rev.md:3556: trailing whitespace.
+++   734	
.oracle/checkins/batch-3-rev.md:3558: trailing whitespace.
+++   740	
.oracle/checkins/batch-3-rev.md:3560: trailing whitespace.
+++   741	
.oracle/checkins/batch-3-rev.md:3562: trailing whitespace.
+++   769	
.oracle/checkins/batch-3-rev.md:3564: trailing whitespace.
+++   770	
.oracle/checkins/batch-3-rev.md:3566: trailing whitespace.
+++   786	
.oracle/checkins/batch-3-rev.md:3568: trailing whitespace.
+++   787	
.oracle/checkins/batch-3-rev.md:3570: trailing whitespace.
+++   794	
.oracle/checkins/batch-3-rev.md:3572: trailing whitespace.
+++   795	
.oracle/checkins/batch-3-rev.md:3574: trailing whitespace.
+++   829	
.oracle/checkins/batch-3-rev.md:3576: trailing whitespace.
+++   830	
.oracle/checkins/batch-3-rev.md:3578: trailing whitespace.
+++   830	
.oracle/checkins/batch-3-rev.md:3580: trailing whitespace.
+++   951	
.oracle/checkins/batch-3-rev.md:3582: trailing whitespace.
+++   967	
.oracle/checkins/batch-3-rev.md:3584: trailing whitespace.
+++   969	
.oracle/checkins/batch-3-rev.md:3586: trailing whitespace.
+++   974	
.oracle/checkins/batch-3-rev.md:3588: trailing whitespace.
+++   981	
.oracle/checkins/batch-3-rev.md:3590: trailing whitespace.
+++   982	
.oracle/checkins/batch-3-rev.md:3592: trailing whitespace.
+++   985	
.oracle/checkins/batch-3-rev.md:3594: trailing whitespace.
+++   986	
.oracle/checkins/batch-3-rev.md:3596: trailing whitespace.
+++   989	
.oracle/checkins/batch-3-rev.md:3598: trailing whitespace.
+++   998	
.oracle/checkins/batch-3-rev.md:3600: trailing whitespace.
+++   999	
.oracle/checkins/batch-3-rev.md:3602: trailing whitespace.
+++  1018	
.oracle/checkins/batch-3-rev.md:3604: trailing whitespace.
+++  1019	
.oracle/checkins/batch-3-rev.md:3606: trailing whitespace.
+++  1043	
.oracle/checkins/batch-3-rev.md:3608: trailing whitespace.
+++  1044	
.oracle/checkins/batch-3-rev.md:3610: trailing whitespace.
+++     2	
.oracle/checkins/batch-3-rev.md:3612: trailing whitespace.
+++     4	
.oracle/checkins/batch-3-rev.md:3614: trailing whitespace.
+++     5	
.oracle/checkins/batch-3-rev.md:3616: trailing whitespace.
+++     7	
.oracle/checkins/batch-3-rev.md:3618: trailing whitespace.
+++     8	
.oracle/checkins/batch-3-rev.md:3620: trailing whitespace.
+++    19	
.oracle/checkins/batch-3-rev.md:3622: trailing whitespace.
+++    25	
.oracle/checkins/batch-3-rev.md:3624: trailing whitespace.
+++    29	
.oracle/checkins/batch-3-rev.md:3626: trailing whitespace.
+++    38	
.oracle/checkins/batch-3-rev.md:3628: trailing whitespace.
+++    39	
.oracle/checkins/batch-3-rev.md:3630: trailing whitespace.
+++    42	
.oracle/checkins/batch-3-rev.md:3632: trailing whitespace.
+++    48	
.oracle/checkins/batch-3-rev.md:3634: trailing whitespace.
+++    49	
.oracle/checkins/batch-3-rev.md:3636: trailing whitespace.
+++    53	
.oracle/checkins/batch-3-rev.md:3638: trailing whitespace.
+++    54	
.oracle/checkins/batch-3-rev.md:3640: trailing whitespace.
+++    50	
.oracle/checkins/batch-3-rev.md:3642: trailing whitespace.
+++    51	
.oracle/checkins/batch-3-rev.md:3644: trailing whitespace.
+++    54	
.oracle/checkins/batch-3-rev.md:3646: trailing whitespace.
+++    81	
.oracle/checkins/batch-3-rev.md:3648: trailing whitespace.
+++     2	
.oracle/checkins/batch-3-rev.md:3650: trailing whitespace.
+++     4	
.oracle/checkins/batch-3-rev.md:3652: trailing whitespace.
+++     7	
.oracle/checkins/batch-3-rev.md:3654: trailing whitespace.
+++    12	
.oracle/checkins/batch-3-rev.md:3656: trailing whitespace.
+++    13	
.oracle/checkins/batch-3-rev.md:3658: trailing whitespace.
+++    16	
.oracle/checkins/batch-3-rev.md:3660: trailing whitespace.
+++    23	
.oracle/checkins/batch-3-rev.md:3662: trailing whitespace.
+++    26	
.oracle/checkins/batch-3-rev.md:3664: trailing whitespace.
+++    31	
.oracle/checkins/batch-3-rev.md:3666: trailing whitespace.
+++    44	
.oracle/checkins/batch-3-rev.md:3668: trailing whitespace.
+++    79	
.oracle/checkins/batch-3-rev.md:3670: trailing whitespace.
+++    97	
.oracle/checkins/batch-3-rev.md:3672: trailing whitespace.
+++   104	
.oracle/checkins/batch-3-rev.md:3674: trailing whitespace.
+++   107	
.oracle/checkins/batch-3-rev.md:3676: trailing whitespace.
+++   117	
.oracle/checkins/batch-3-rev.md:3678: trailing whitespace.
+++   124	
.oracle/checkins/batch-3-rev.md:3680: trailing whitespace.
+++   383	
.oracle/checkins/batch-3-rev.md:3682: trailing whitespace.
+++   384	
.oracle/checkins/batch-3-rev.md:3684: trailing whitespace.
+++   393	
.oracle/checkins/batch-3-rev.md:3686: trailing whitespace.
+++   394	
.oracle/checkins/batch-3-rev.md:3688: trailing whitespace.
+++   402	
.oracle/checkins/batch-3-rev.md:3690: trailing whitespace.
+++   403	
.oracle/checkins/batch-3-rev.md:3692: trailing whitespace.
+++   406	
.oracle/checkins/batch-3-rev.md:3694: trailing whitespace.
+++   416	
.oracle/checkins/batch-3-rev.md:3696: trailing whitespace.
+++   417	
.oracle/checkins/batch-3-rev.md:3698: trailing whitespace.
+++   430	
.oracle/checkins/batch-3-rev.md:3700: trailing whitespace.
+++  1670	
.oracle/checkins/batch-3-rev.md:3702: trailing whitespace.
+++  1671	
.oracle/checkins/batch-3-rev.md:3704: trailing whitespace.
+++  1680	
.oracle/checkins/batch-3-rev.md:3706: trailing whitespace.
+++  1681	
.oracle/checkins/batch-3-rev.md:3708: trailing whitespace.
+++  1690	
.oracle/checkins/batch-3-rev.md:3710: trailing whitespace.
+++  1691	
.oracle/checkins/batch-3-rev.md:3712: trailing whitespace.
+++  1699	
.oracle/checkins/batch-3-rev.md:3714: trailing whitespace.
+++  1700	
.oracle/checkins/batch-3-rev.md:3716: trailing whitespace.
+++  1710	
.oracle/checkins/batch-3-rev.md:3718: trailing whitespace.
+++  1711	
.oracle/checkins/batch-3-rev.md:3720: trailing whitespace.
+++  1724	
.oracle/checkins/batch-3-rev.md:3722: trailing whitespace.
+++  1725	
.oracle/checkins/batch-3-rev.md:3724: trailing whitespace.
+++  1753	
.oracle/checkins/batch-3-rev.md:3726: trailing whitespace.
+++  1754	
.oracle/checkins/batch-3-rev.md:3728: trailing whitespace.
+++  1773	
.oracle/checkins/batch-3-rev.md:3730: trailing whitespace.
+++  1774	
.oracle/checkins/batch-3-rev.md:3732: trailing whitespace.
+++  1782	
.oracle/checkins/batch-3-rev.md:3734: trailing whitespace.
+++  1789	
.oracle/checkins/batch-3-rev.md:3736: trailing whitespace.
+++  1797	
.oracle/checkins/batch-3-rev.md:3738: trailing whitespace.
+++  1798	
.oracle/checkins/batch-3-rev.md:3740: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3742: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3744: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3746: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3748: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3750: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3752: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3754: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3756: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3758: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3760: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3762: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3764: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3766: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3768: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3770: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3772: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3774: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3776: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3778: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3780: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3782: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3784: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3786: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3788: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3790: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3792: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3794: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3796: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3798: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3800: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3802: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3804: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3806: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3808: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3810: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3812: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3814: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3816: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3818: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3820: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3822: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3824: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3826: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3828: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3830: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3832: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3834: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3836: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3838: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3840: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3842: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3844: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3846: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3848: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3850: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3852: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3854: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3856: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3858: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3860: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3862: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3864: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3866: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3868: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3870: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3872: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3874: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3876: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3878: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3880: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3882: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3884: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3886: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3888: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3890: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3892: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3894: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3896: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3898: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3900: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3902: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3904: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3906: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3908: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3910: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3912: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3914: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3916: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3918: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3920: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3922: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3924: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3926: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3928: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3930: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3932: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3934: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3936: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3938: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3940: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3942: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3944: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3946: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3948: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3950: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:3952: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3954: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3956: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3958: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3960: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3962: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3964: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3966: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3968: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3970: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3972: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3974: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3976: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3978: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3980: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3982: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3984: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3986: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3988: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3990: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3992: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3994: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3996: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:3998: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4000: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4002: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4004: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4006: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4008: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4010: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4012: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4014: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4016: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4018: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4020: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4022: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4024: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4026: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4028: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4030: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4032: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4034: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4036: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4038: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4040: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4042: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4044: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4046: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4048: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4050: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4052: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4054: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4056: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4058: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4060: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4062: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4064: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4066: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4068: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4070: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4072: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4074: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4076: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4078: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4080: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4082: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4084: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4086: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4088: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4090: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4092: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4094: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4096: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4098: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4100: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4102: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4104: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4106: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4108: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4110: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4112: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4114: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4116: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4118: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4120: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4122: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4124: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4126: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4128: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4130: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4132: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4134: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4136: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4138: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4140: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4142: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4144: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4146: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4148: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4150: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4152: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4154: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4156: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4158: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4160: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4162: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4164: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4166: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4168: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4170: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4172: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4174: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4176: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4178: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4180: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4182: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4184: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4186: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4188: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4190: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4192: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4194: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4196: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4198: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4200: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4202: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4204: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4206: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4208: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4210: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4212: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4214: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4216: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4218: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4220: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4222: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4224: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4226: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4228: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4230: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4232: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4234: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4236: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4238: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4240: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4242: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4244: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4246: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4248: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4250: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4252: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4254: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4256: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4258: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4260: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4262: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4264: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4266: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4268: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4270: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4272: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4274: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4276: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4278: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4280: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4282: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4284: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4286: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4288: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4290: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4292: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4294: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4296: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4298: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4300: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4302: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4304: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4306: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4308: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4310: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4312: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4314: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4316: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4318: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4320: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4322: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4324: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4326: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4328: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4330: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4332: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4334: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4336: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4338: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4340: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4342: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4344: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4346: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4348: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4350: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4352: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4354: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4356: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4358: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4360: trailing whitespace.
++     2	
.oracle/checkins/batch-3-rev.md:4362: trailing whitespace.
++     8	
.oracle/checkins/batch-3-rev.md:4364: trailing whitespace.
++    15	
.oracle/checkins/batch-3-rev.md:4366: trailing whitespace.
++    18	
.oracle/checkins/batch-3-rev.md:4368: trailing whitespace.
++    19	
.oracle/checkins/batch-3-rev.md:4370: trailing whitespace.
++    27	
.oracle/checkins/batch-3-rev.md:4372: trailing whitespace.
++    32	
.oracle/checkins/batch-3-rev.md:4374: trailing whitespace.
++    33	
.oracle/checkins/batch-3-rev.md:4376: trailing whitespace.
++    38	
.oracle/checkins/batch-3-rev.md:4378: trailing whitespace.
++    39	
.oracle/checkins/batch-3-rev.md:4380: trailing whitespace.
++    54	
.oracle/checkins/batch-3-rev.md:4382: trailing whitespace.
++    55	
.oracle/checkins/batch-3-rev.md:4384: trailing whitespace.
++    62	
.oracle/checkins/batch-3-rev.md:4386: trailing whitespace.
++    63	
.oracle/checkins/batch-3-rev.md:4388: trailing whitespace.
++    71	
.oracle/checkins/batch-3-rev.md:4390: trailing whitespace.
++    72	
.oracle/checkins/batch-3-rev.md:4392: trailing whitespace.
++    80	
.oracle/checkins/batch-3-rev.md:4394: trailing whitespace.
++    81	
.oracle/checkins/batch-3-rev.md:4396: trailing whitespace.
++    93	
.oracle/checkins/batch-3-rev.md:4398: trailing whitespace.
++    98	
.oracle/checkins/batch-3-rev.md:4400: trailing whitespace.
++   100	
.oracle/checkins/batch-3-rev.md:4402: trailing whitespace.
++   101	
.oracle/checkins/batch-3-rev.md:4404: trailing whitespace.
++   108	
.oracle/checkins/batch-3-rev.md:4406: trailing whitespace.
++   109	
.oracle/checkins/batch-3-rev.md:4408: trailing whitespace.
++   122	
.oracle/checkins/batch-3-rev.md:4410: trailing whitespace.
++   126	
.oracle/checkins/batch-3-rev.md:4412: trailing whitespace.
++   130	
.oracle/checkins/batch-3-rev.md:4414: trailing whitespace.
++   131	
.oracle/checkins/batch-3-rev.md:4416: trailing whitespace.
++   141	
.oracle/checkins/batch-3-rev.md:4418: trailing whitespace.
++   142	
.oracle/checkins/batch-3-rev.md:4420: trailing whitespace.
++   149	
.oracle/checkins/batch-3-rev.md:4422: trailing whitespace.
++   150	
.oracle/checkins/batch-3-rev.md:4424: trailing whitespace.
++   155	
.oracle/checkins/batch-3-rev.md:4426: trailing whitespace.
++   156	
.oracle/checkins/batch-3-rev.md:4428: trailing whitespace.
++   159	
.oracle/checkins/batch-3-rev.md:4430: trailing whitespace.
++   171	
.oracle/checkins/batch-3-rev.md:4432: trailing whitespace.
++   172	
.oracle/checkins/batch-3-rev.md:4434: trailing whitespace.
++   188	
.oracle/checkins/batch-3-rev.md:4436: trailing whitespace.
++   191	
.oracle/checkins/batch-3-rev.md:4438: trailing whitespace.
++   207	
.oracle/checkins/batch-3-rev.md:4440: trailing whitespace.
++   210	
.oracle/checkins/batch-3-rev.md:4442: trailing whitespace.
++   215	
.oracle/checkins/batch-3-rev.md:4444: trailing whitespace.
++   218	
.oracle/checkins/batch-3-rev.md:4446: trailing whitespace.
++   223	
.oracle/checkins/batch-3-rev.md:4448: trailing whitespace.
++   227	
.oracle/checkins/batch-3-rev.md:4450: trailing whitespace.
++   230	
.oracle/checkins/batch-3-rev.md:4452: trailing whitespace.
++   233	
.oracle/checkins/batch-3-rev.md:4454: trailing whitespace.
++   236	
.oracle/checkins/batch-3-rev.md:4456: trailing whitespace.
++   239	
.oracle/checkins/batch-3-rev.md:4458: trailing whitespace.
++   242	
.oracle/checkins/batch-3-rev.md:4460: trailing whitespace.
++   253	
.oracle/checkins/batch-3-rev.md:4462: trailing whitespace.
++   256	
.oracle/checkins/batch-3-rev.md:4464: trailing whitespace.
++   266	
.oracle/checkins/batch-3-rev.md:4466: trailing whitespace.
++   270	
.oracle/checkins/batch-3-rev.md:4468: trailing whitespace.
++   277	
.oracle/checkins/batch-3-rev.md:4470: trailing whitespace.
++   279	
.oracle/checkins/batch-3-rev.md:4472: trailing whitespace.
++   282	
.oracle/checkins/batch-3-rev.md:4474: trailing whitespace.
++   285	
.oracle/checkins/batch-3-rev.md:4476: trailing whitespace.
++   302	
.oracle/checkins/batch-3-rev.md:4478: trailing whitespace.
++   313	
.oracle/checkins/batch-3-rev.md:4480: trailing whitespace.
++   319	
.oracle/checkins/batch-3-rev.md:4482: trailing whitespace.
++   328	
.oracle/checkins/batch-3-rev.md:4484: trailing whitespace.
++   367	
.oracle/checkins/batch-3-rev.md:4486: trailing whitespace.
++   372	
.oracle/checkins/batch-3-rev.md:4488: trailing whitespace.
++   394	
.oracle/checkins/batch-3-rev.md:4490: trailing whitespace.
++   406	
.oracle/checkins/batch-3-rev.md:4492: trailing whitespace.
++   425	
.oracle/checkins/batch-3-rev.md:4494: trailing whitespace.
++   782	
.oracle/checkins/batch-3-rev.md:4496: trailing whitespace.
++   798	
.oracle/checkins/batch-3-rev.md:4498: trailing whitespace.
++   801	
.oracle/checkins/batch-3-rev.md:4500: trailing whitespace.
++   808	
.oracle/checkins/batch-3-rev.md:4502: trailing whitespace.
++   810	
.oracle/checkins/batch-3-rev.md:4504: trailing whitespace.
++   817	
.oracle/checkins/batch-3-rev.md:4506: trailing whitespace.
++   827	
.oracle/checkins/batch-3-rev.md:4508: trailing whitespace.
++   834	
.oracle/checkins/batch-3-rev.md:4510: trailing whitespace.
++   837	
.oracle/checkins/batch-3-rev.md:4512: trailing whitespace.
++   840	
.oracle/checkins/batch-3-rev.md:4514: trailing whitespace.
++   854	
.oracle/checkins/batch-3-rev.md:4516: trailing whitespace.
++   861	
.oracle/checkins/batch-3-rev.md:4518: trailing whitespace.
++   871	
.oracle/checkins/batch-3-rev.md:4520: trailing whitespace.
++   886	
.oracle/checkins/batch-3-rev.md:4522: trailing whitespace.
++   898	
.oracle/checkins/batch-3-rev.md:4524: trailing whitespace.
++   904	
.oracle/checkins/batch-3-rev.md:4526: trailing whitespace.
++   907	
.oracle/checkins/batch-3-rev.md:4528: trailing whitespace.
++   917	
.oracle/checkins/batch-3-rev.md:4530: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4532: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4534: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4536: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4538: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4540: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4542: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4544: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4546: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4548: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4550: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4552: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4554: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4556: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4558: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4560: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4562: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4564: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4566: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4568: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4570: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4572: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4574: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4576: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4578: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4580: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4582: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4584: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4586: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4588: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4590: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4592: trailing whitespace.
++   418	
.oracle/checkins/batch-3-rev.md:4594: trailing whitespace.
++   419	
.oracle/checkins/batch-3-rev.md:4596: trailing whitespace.
++   432	
.oracle/checkins/batch-3-rev.md:4598: trailing whitespace.
++   433	
.oracle/checkins/batch-3-rev.md:4600: trailing whitespace.
++   436	
.oracle/checkins/batch-3-rev.md:4602: trailing whitespace.
++   443	
.oracle/checkins/batch-3-rev.md:4604: trailing whitespace.
++   451	
.oracle/checkins/batch-3-rev.md:4606: trailing whitespace.
++   460	
.oracle/checkins/batch-3-rev.md:4608: trailing whitespace.
++   480	
.oracle/checkins/batch-3-rev.md:4610: trailing whitespace.
++   484	
.oracle/checkins/batch-3-rev.md:4612: trailing whitespace.
++   505	
.oracle/checkins/batch-3-rev.md:4614: trailing whitespace.
++   509	
.oracle/checkins/batch-3-rev.md:4616: trailing whitespace.
++   513	
.oracle/checkins/batch-3-rev.md:4618: trailing whitespace.
++   515	
.oracle/checkins/batch-3-rev.md:4620: trailing whitespace.
++   524	
.oracle/checkins/batch-3-rev.md:4622: trailing whitespace.
++   609	
.oracle/checkins/batch-3-rev.md:4624: trailing whitespace.
++   636	
.oracle/checkins/batch-3-rev.md:4626: trailing whitespace.
++   646	
.oracle/checkins/batch-3-rev.md:4628: trailing whitespace.
++   840	
.oracle/checkins/batch-3-rev.md:4630: trailing whitespace.
++   841	
.oracle/checkins/batch-3-rev.md:4632: trailing whitespace.
++   956	
.oracle/checkins/batch-3-rev.md:4634: trailing whitespace.
++   966	
.oracle/checkins/batch-3-rev.md:4636: trailing whitespace.
++   968	
.oracle/checkins/batch-3-rev.md:4638: trailing whitespace.
++   973	
.oracle/checkins/batch-3-rev.md:4640: trailing whitespace.
++   980	
.oracle/checkins/batch-3-rev.md:4642: trailing whitespace.
++   981	
.oracle/checkins/batch-3-rev.md:4644: trailing whitespace.
++   984	
.oracle/checkins/batch-3-rev.md:4646: trailing whitespace.
++   985	
.oracle/checkins/batch-3-rev.md:4648: trailing whitespace.
++   988	
.oracle/checkins/batch-3-rev.md:4650: trailing whitespace.
++19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 345) 
.oracle/checkins/batch-3-rev.md:4652: trailing whitespace.
++19d559a6b vibecomfy/porting/emit_subgraph.py (POM 2026-06-10 08:24:16 +0200 347) 
.oracle/checkins/batch-3-rev.md:4654: trailing whitespace.
++    90	
.oracle/checkins/batch-3-rev.md:4656: trailing whitespace.
++    97	
.oracle/checkins/batch-3-rev.md:4658: trailing whitespace.
++    98	
.oracle/checkins/batch-3-rev.md:4660: trailing whitespace.
++   125	
.oracle/checkins/batch-3-rev.md:4662: trailing whitespace.
++   126	
.oracle/checkins/batch-3-rev.md:4664: trailing whitespace.
++   140	
.oracle/checkins/batch-3-rev.md:4666: trailing whitespace.
++   141	
.oracle/checkins/batch-3-rev.md:4668: trailing whitespace.
++   149	
.oracle/checkins/batch-3-rev.md:4670: trailing whitespace.
++   150	
.oracle/checkins/batch-3-rev.md:4672: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4674: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4676: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4678: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4680: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4682: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4684: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4686: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4688: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4690: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4692: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4694: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4696: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4698: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4700: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4702: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4704: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4706: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4708: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4710: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4712: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4714: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4716: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4718: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4720: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4722: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4724: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4726: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4728: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4730: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4732: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4734: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4736: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4738: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4740: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4742: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4744: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4746: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4748: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4750: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4752: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4754: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4756: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4758: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4760: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4762: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4764: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4766: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4768: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4770: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4772: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4774: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4776: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4778: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4780: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4782: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4784: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4786: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4788: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4790: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4792: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4794: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4796: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4798: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4800: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4802: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4804: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4806: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4808: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4810: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4812: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4814: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4816: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4818: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4820: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4822: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4824: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4826: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4828: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4830: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4832: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4834: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4836: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4838: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4840: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4842: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4844: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4846: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4848: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4850: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4852: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4854: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4856: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4858: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4860: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4862: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4864: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4866: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4868: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4870: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4872: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4874: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4876: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4878: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4880: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4882: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4884: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4886: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4888: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4890: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4892: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4894: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4896: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4898: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4900: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4902: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4904: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4906: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4908: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4910: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4912: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4914: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4916: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4918: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4920: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4922: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4924: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4926: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4928: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4930: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4932: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4934: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4936: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4938: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4940: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4942: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4944: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4946: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4948: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4950: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4952: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4954: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4956: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4958: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4960: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4962: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4964: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4966: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4968: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4970: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4972: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4974: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4976: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4978: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4980: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4982: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4984: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4986: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4988: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4990: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4992: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4994: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4996: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:4998: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5000: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5002: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5004: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5006: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5008: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5010: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5012: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5014: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5016: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5018: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5020: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5022: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5024: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5026: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5028: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5030: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5032: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5034: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5036: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5038: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5040: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5042: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5044: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5046: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5048: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5050: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5052: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5054: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5056: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5058: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5060: trailing whitespace.
++   387	
.oracle/checkins/batch-3-rev.md:5062: trailing whitespace.
++   388	
.oracle/checkins/batch-3-rev.md:5064: trailing whitespace.
++   397	
.oracle/checkins/batch-3-rev.md:5066: trailing whitespace.
++   414	
.oracle/checkins/batch-3-rev.md:5068: trailing whitespace.
++   415	
.oracle/checkins/batch-3-rev.md:5070: trailing whitespace.
++   418	
.oracle/checkins/batch-3-rev.md:5072: trailing whitespace.
++   421	
.oracle/checkins/batch-3-rev.md:5074: trailing whitespace.
++   423	
.oracle/checkins/batch-3-rev.md:5076: trailing whitespace.
++   424	
.oracle/checkins/batch-3-rev.md:5078: trailing whitespace.
++   427	
.oracle/checkins/batch-3-rev.md:5080: trailing whitespace.
++   451	
.oracle/checkins/batch-3-rev.md:5082: trailing whitespace.
++   452	
.oracle/checkins/batch-3-rev.md:5084: trailing whitespace.
++   459	
.oracle/checkins/batch-3-rev.md:5086: trailing whitespace.
++   467	
.oracle/checkins/batch-3-rev.md:5088: trailing whitespace.
++   478	
.oracle/checkins/batch-3-rev.md:5090: trailing whitespace.
++   488	
.oracle/checkins/batch-3-rev.md:5092: trailing whitespace.
++   513	
.oracle/checkins/batch-3-rev.md:5094: trailing whitespace.
++   514	
.oracle/checkins/batch-3-rev.md:5096: trailing whitespace.
++   519	
.oracle/checkins/batch-3-rev.md:5098: trailing whitespace.
++   520	
.oracle/checkins/batch-3-rev.md:5100: trailing whitespace.
++  1343	
.oracle/checkins/batch-3-rev.md:5102: trailing whitespace.
++  1348	
.oracle/checkins/batch-3-rev.md:5104: trailing whitespace.
++  1382	
.oracle/checkins/batch-3-rev.md:5106: trailing whitespace.
++  1383	
.oracle/checkins/batch-3-rev.md:5108: trailing whitespace.
++  1391	
.oracle/checkins/batch-3-rev.md:5110: trailing whitespace.
++  1392	
.oracle/checkins/batch-3-rev.md:5112: trailing whitespace.
++  1401	
.oracle/checkins/batch-3-rev.md:5114: trailing whitespace.
++  1402	
.oracle/checkins/batch-3-rev.md:5116: trailing whitespace.
++  1421	
.oracle/checkins/batch-3-rev.md:5118: trailing whitespace.
++  1426	
.oracle/checkins/batch-3-rev.md:5120: trailing whitespace.
++  1428	
.oracle/checkins/batch-3-rev.md:5122: trailing whitespace.
++  1429	
.oracle/checkins/batch-3-rev.md:5124: trailing whitespace.
++  1434	
.oracle/checkins/batch-3-rev.md:5126: trailing whitespace.
++  1445	
.oracle/checkins/batch-3-rev.md:5128: trailing whitespace.
++  2014	
.oracle/checkins/batch-3-rev.md:5130: trailing whitespace.
++  2019	
.oracle/checkins/batch-3-rev.md:5132: trailing whitespace.
++  2041	
.oracle/checkins/batch-3-rev.md:5134: trailing whitespace.
++  2042	
.oracle/checkins/batch-3-rev.md:5136: trailing whitespace.
++  2065	
.oracle/checkins/batch-3-rev.md:5138: trailing whitespace.
++  2394	
.oracle/checkins/batch-3-rev.md:5140: trailing whitespace.
++  2411	
.oracle/checkins/batch-3-rev.md:5142: trailing whitespace.
++  2417	
.oracle/checkins/batch-3-rev.md:5144: trailing whitespace.
++  2425	
.oracle/checkins/batch-3-rev.md:5146: trailing whitespace.
++  2432	
.oracle/checkins/batch-3-rev.md:5148: trailing whitespace.
++  2436	
.oracle/checkins/batch-3-rev.md:5150: trailing whitespace.
++  1480	
.oracle/checkins/batch-3-rev.md:5152: trailing whitespace.
++  1497	
.oracle/checkins/batch-3-rev.md:5154: trailing whitespace.
++  1525	
.oracle/checkins/batch-3-rev.md:5156: trailing whitespace.
++  1526	
.oracle/checkins/batch-3-rev.md:5158: trailing whitespace.
++  1533	
.oracle/checkins/batch-3-rev.md:5160: trailing whitespace.
++  1534	
.oracle/checkins/batch-3-rev.md:5162: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5164: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5166: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5168: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5170: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5172: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5174: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5176: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5178: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5180: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5182: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5184: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5186: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5188: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5190: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5192: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5194: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5196: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5198: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5200: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5202: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5204: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5206: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5208: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5210: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5212: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5214: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5216: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5218: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5220: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5222: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5224: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5226: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5228: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5230: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5232: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5234: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5236: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5238: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5240: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5242: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5244: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5246: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5248: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5250: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5252: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5254: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5256: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5258: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5260: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5262: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5264: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5266: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5268: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5270: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5272: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5274: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5276: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5278: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5280: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5282: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5284: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5286: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5288: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5290: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5292: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5294: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5296: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5298: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5300: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5302: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5304: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5306: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5308: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5310: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5312: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5314: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5316: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5318: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5320: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5322: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5324: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5326: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5328: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5330: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5332: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5334: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5336: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5338: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5340: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5342: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5344: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5346: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5348: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5350: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5352: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5354: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5356: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5358: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5360: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5362: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5364: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5366: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5368: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5370: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5372: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5374: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5376: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5378: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5380: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5382: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5384: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5386: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5388: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5390: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5392: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5394: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5396: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5398: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5400: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5402: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5404: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5406: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5408: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5410: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5412: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5414: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5416: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5418: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5420: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5422: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5424: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5426: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5428: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5430: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5432: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5434: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5436: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5438: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5440: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5442: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5444: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5446: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5448: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5450: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5452: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5454: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5456: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5458: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5460: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5462: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5464: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5466: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5468: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5470: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5472: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5474: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5476: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5478: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5480: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5482: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5484: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5486: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5488: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5490: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5492: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5494: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5496: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5498: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5500: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5502: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5504: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5506: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5508: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5510: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5512: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5514: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5516: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5518: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5520: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5522: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5524: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5526: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5528: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5530: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5532: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5534: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5536: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5538: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5540: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5542: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5544: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5546: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5548: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5550: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5552: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5554: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5556: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5558: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5560: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5562: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5564: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5566: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5568: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5570: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5572: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5574: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5576: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5578: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5580: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5582: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5584: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5586: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5588: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5590: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5592: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5594: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5596: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5598: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5600: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5602: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5604: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5606: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5608: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5610: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5612: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5614: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5616: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5618: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5620: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5622: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5624: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5626: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5628: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5630: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5632: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5634: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5636: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5638: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5640: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5642: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5644: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5646: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5648: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5650: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5652: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5654: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5656: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5658: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5660: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5662: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5664: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5666: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5668: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5670: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5672: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5674: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5676: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5678: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5680: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5682: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5684: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5686: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5688: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5690: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5692: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5694: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5696: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5698: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5700: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5702: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5704: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5706: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5708: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5710: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5712: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5714: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5716: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5718: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5720: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5722: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5724: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5726: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5728: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5730: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5732: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5734: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5736: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5738: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5740: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5742: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5744: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5746: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5748: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5750: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5752: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5754: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5756: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5758: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5760: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5762: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5764: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5766: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5768: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5770: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5772: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5774: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5776: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5778: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5780: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5782: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5784: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5786: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5788: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5790: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5792: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5794: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5796: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5798: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5800: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5802: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5804: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5806: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5808: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5810: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5812: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5814: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5816: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5818: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5820: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5822: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5824: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5826: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5828: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5830: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5832: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5834: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5836: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5838: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5840: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5842: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5844: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5846: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5848: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5850: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5852: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5854: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5856: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5858: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5860: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5862: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5864: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5866: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5868: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5870: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5872: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5874: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5876: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5878: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5880: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5882: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5884: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5886: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5888: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5890: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5892: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5894: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5896: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5898: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5900: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5902: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5904: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5906: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5908: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5910: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5912: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5914: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5916: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5918: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5920: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5922: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5924: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5926: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5928: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5930: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5932: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5934: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5936: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5938: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5940: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5942: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5944: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5946: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5948: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5950: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5952: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5954: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5956: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5958: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5960: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5962: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5964: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5966: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5968: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5970: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5972: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5974: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5976: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5978: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5980: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5982: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5984: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5986: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5988: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5990: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5992: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5994: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5996: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:5998: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6000: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6002: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6004: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6006: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6008: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6010: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6012: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6014: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6016: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6018: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6020: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6022: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6024: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6026: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6028: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6030: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6032: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6034: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6036: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6038: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6040: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6042: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6044: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6046: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6048: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6050: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6052: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6054: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6056: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6058: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6060: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6062: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6064: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6066: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6068: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6070: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6072: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6074: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6076: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6078: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6080: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6082: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6084: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6086: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6088: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6090: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6092: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6094: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6096: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6098: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6100: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6102: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6104: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6106: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6108: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6110: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6112: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6114: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6116: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6118: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6120: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6122: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6124: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6126: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6128: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6130: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6132: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6134: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6136: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6138: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6140: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6142: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6144: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6146: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6148: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6150: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6152: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6154: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6156: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6158: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6160: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6162: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6164: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6166: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6168: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6170: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6172: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6174: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6176: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6178: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6180: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6182: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6184: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6186: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6188: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6190: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6192: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6194: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6196: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6198: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6200: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6202: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6204: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6206: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6208: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6210: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6212: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6214: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6216: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6218: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6220: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6222: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6224: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6226: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6228: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6230: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6232: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6234: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6236: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6238: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6240: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6242: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6244: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6246: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6248: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6250: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6252: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6254: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6256: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6258: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6260: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6262: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6264: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6266: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6268: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6270: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6272: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6274: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6276: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6278: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6280: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6282: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6284: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6286: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6288: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6290: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6292: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6294: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6296: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6298: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6300: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6302: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6304: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6306: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6308: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6310: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6312: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6314: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6316: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6318: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6320: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6322: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6324: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6326: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6328: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6330: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6332: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6334: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6336: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6338: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6340: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6342: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6344: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6346: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6348: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6350: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6352: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6354: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6356: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6358: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6360: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6362: trailing whitespace.
++    50	
.oracle/checkins/batch-3-rev.md:6364: trailing whitespace.
++    52	
.oracle/checkins/batch-3-rev.md:6366: trailing whitespace.
++    71	
.oracle/checkins/batch-3-rev.md:6368: trailing whitespace.
++    72	
.oracle/checkins/batch-3-rev.md:6370: trailing whitespace.
++    88	
.oracle/checkins/batch-3-rev.md:6372: trailing whitespace.
++   103	
.oracle/checkins/batch-3-rev.md:6374: trailing whitespace.
++   112	
.oracle/checkins/batch-3-rev.md:6376: trailing whitespace.
++   113	
.oracle/checkins/batch-3-rev.md:6378: trailing whitespace.
++   120	
.oracle/checkins/batch-3-rev.md:6380: trailing whitespace.
++   122	
.oracle/checkins/batch-3-rev.md:6382: trailing whitespace.
++   126	
.oracle/checkins/batch-3-rev.md:6384: trailing whitespace.
++   127	
.oracle/checkins/batch-3-rev.md:6386: trailing whitespace.
++   134	
.oracle/checkins/batch-3-rev.md:6388: trailing whitespace.
++   139	
.oracle/checkins/batch-3-rev.md:6390: trailing whitespace.
++   145	
.oracle/checkins/batch-3-rev.md:6392: trailing whitespace.
++   146	
.oracle/checkins/batch-3-rev.md:6394: trailing whitespace.
++   163	
.oracle/checkins/batch-3-rev.md:6396: trailing whitespace.
++   166	
.oracle/checkins/batch-3-rev.md:6398: trailing whitespace.
++   170	
.oracle/checkins/batch-3-rev.md:6400: trailing whitespace.
++   171	
.oracle/checkins/batch-3-rev.md:6402: trailing whitespace.
++   179	
.oracle/checkins/batch-3-rev.md:6404: trailing whitespace.
++   182	
.oracle/checkins/batch-3-rev.md:6406: trailing whitespace.
++   183	
.oracle/checkins/batch-3-rev.md:6408: trailing whitespace.
++   186	
.oracle/checkins/batch-3-rev.md:6410: trailing whitespace.
++   188	
.oracle/checkins/batch-3-rev.md:6412: trailing whitespace.
++   190	
.oracle/checkins/batch-3-rev.md:6414: trailing whitespace.
++   191	
.oracle/checkins/batch-3-rev.md:6416: trailing whitespace.
++   194	
.oracle/checkins/batch-3-rev.md:6418: trailing whitespace.
++   195	
.oracle/checkins/batch-3-rev.md:6420: trailing whitespace.
++   198	
.oracle/checkins/batch-3-rev.md:6422: trailing whitespace.
++  2193	
.oracle/checkins/batch-3-rev.md:6424: trailing whitespace.
++  2206	
.oracle/checkins/batch-3-rev.md:6426: trailing whitespace.
++  2212	
.oracle/checkins/batch-3-rev.md:6428: trailing whitespace.
++  2213	
.oracle/checkins/batch-3-rev.md:6430: trailing whitespace.
++  2238	
.oracle/checkins/batch-3-rev.md:6432: trailing whitespace.
++  2240	
.oracle/checkins/batch-3-rev.md:6434: trailing whitespace.
++  2243	
.oracle/checkins/batch-3-rev.md:6436: trailing whitespace.
++  2244	
.oracle/checkins/batch-3-rev.md:6438: trailing whitespace.
++  2266	
.oracle/checkins/batch-3-rev.md:6440: trailing whitespace.
++  2268	
.oracle/checkins/batch-3-rev.md:6442: trailing whitespace.
++  2277	
.oracle/checkins/batch-3-rev.md:6444: trailing whitespace.
++  2278	
.oracle/checkins/batch-3-rev.md:6446: trailing whitespace.
++  2282	
.oracle/checkins/batch-3-rev.md:6448: trailing whitespace.
++  2283	
.oracle/checkins/batch-3-rev.md:6450: trailing whitespace.
++  2286	
.oracle/checkins/batch-3-rev.md:6452: trailing whitespace.
++  2303	
.oracle/checkins/batch-3-rev.md:6454: trailing whitespace.
++  2309	
.oracle/checkins/batch-3-rev.md:6456: trailing whitespace.
++  2314	
.oracle/checkins/batch-3-rev.md:6458: trailing whitespace.
++  2315	
.oracle/checkins/batch-3-rev.md:6460: trailing whitespace.
++  2318	
.oracle/checkins/batch-3-rev.md:6462: trailing whitespace.
++  2327	
.oracle/checkins/batch-3-rev.md:6464: trailing whitespace.
++  2337	
.oracle/checkins/batch-3-rev.md:6466: trailing whitespace.
++  2343	
.oracle/checkins/batch-3-rev.md:6468: trailing whitespace.
++  2346	
.oracle/checkins/batch-3-rev.md:6470: trailing whitespace.
++  2347	
.oracle/checkins/batch-3-rev.md:6472: trailing whitespace.
++  2350	
.oracle/checkins/batch-3-rev.md:6474: trailing whitespace.
++  2366	
.oracle/checkins/batch-3-rev.md:6476: trailing whitespace.
++  2375	
.oracle/checkins/batch-3-rev.md:6478: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6480: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6482: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6484: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6486: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6488: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6490: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6492: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6494: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6496: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6498: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6500: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6502: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6504: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6506: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6508: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6510: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6512: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6514: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6516: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6518: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6520: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6522: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6524: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6526: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6528: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6530: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6532: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6534: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6536: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6538: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6540: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6542: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6544: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6546: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6548: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6550: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6552: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6554: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6556: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6558: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6560: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6562: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6564: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6566: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6568: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6570: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6572: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6574: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6576: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6578: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6580: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6582: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6584: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6586: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6588: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6590: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6592: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6594: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6596: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6598: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6600: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6602: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6604: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6606: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6608: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6610: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6612: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6614: trailing whitespace.
++ 
.oracle/checkins/batch-3-rev.md:6616: trailing whitespace.
++  1010	
.oracle/checkins/batch-3-rev.md:6618: trailing whitespace.
++  1022	
.oracle/checkins/batch-3-rev.md:6620: trailing whitespace.
++  1025	
.oracle/checkins/batch-3-rev.md:6622: trailing whitespace.
++  1031	
.oracle/checkins/batch-3-rev.md:6624: trailing whitespace.
++  1040	
.oracle/checkins/batch-3-rev.md:6626: trailing whitespace.
++  1045	
.oracle/checkins/batch-3-rev.md:6628: trailing whitespace.
++  1049	
.oracle/checkins/batch-3-rev.md:6630: trailing whitespace.
++  1083	
.oracle/checkins/batch-3-rev.md:6632: trailing whitespace.
++  1086	
.oracle/checkins/batch-3-rev.md:6634: trailing whitespace.
++  1087	
.oracle/checkins/batch-3-rev.md:6636: trailing whitespace.
++  1091	
.oracle/checkins/batch-3-rev.md:6638: trailing whitespace.
++  1092	
.oracle/checkins/batch-3-rev.md:6640: trailing whitespace.
++  1095	
.oracle/checkins/batch-3-rev.md:6642: trailing whitespace.
++  1102	
.oracle/checkins/batch-3-rev.md:6644: trailing whitespace.
++  1105	
.oracle/checkins/batch-3-rev.md:6646: trailing whitespace.
++     4	
.oracle/checkins/batch-3-rev.md:6648: trailing whitespace.
++   356	
.oracle/checkins/batch-3-rev.md:6650: trailing whitespace.
++   357	
.oracle/checkins/batch-3-rev.md:6652: trailing whitespace.
++   360	
.oracle/checkins/batch-3-rev.md:6654: trailing whitespace.
++   363	
.oracle/checkins/batch-3-rev.md:6656: trailing whitespace.
++   374	
.oracle/checkins/batch-3-rev.md:6658: trailing whitespace.
++   405	
.oracle/checkins/batch-3-rev.md:6660: trailing whitespace.
++   411	
.oracle/checkins/batch-3-rev.md:6662: trailing whitespace.
++   418	
.oracle/checkins/batch-3-rev.md:6664: trailing whitespace.
++   427	
.oracle/checkins/batch-3-rev.md:6666: trailing whitespace.
++   488	
.oracle/checkins/batch-3-rev.md:6668: trailing whitespace.
++   489	
.oracle/checkins/batch-3-rev.md:6670: trailing whitespace.
++   498	
.oracle/checkins/batch-3-rev.md:6672: trailing whitespace.
++   499	
.oracle/checkins/batch-3-rev.md:6674: trailing whitespace.
++   504	
.oracle/checkins/batch-3-rev.md:6676: trailing whitespace.
++   507	
.oracle/checkins/batch-3-rev.md:6678: trailing whitespace.
++   524	
.oracle/checkins/batch-3-rev.md:6680: trailing whitespace.
++   525	
.oracle/checkins/batch-3-rev.md:6682: trailing whitespace.
++   873	
.oracle/checkins/batch-3-rev.md:6684: trailing whitespace.
++   882	
.oracle/checkins/batch-3-rev.md:6686: trailing whitespace.
++   883	
.oracle/checkins/batch-3-rev.md:6688: trailing whitespace.
++   886	
.oracle/checkins/batch-3-rev.md:6690: trailing whitespace.
++   888	
.oracle/checkins/batch-3-rev.md:6692: trailing whitespace.
++   889	
.oracle/checkins/batch-3-rev.md:6694: trailing whitespace.
++   896	
.oracle/checkins/batch-3-rev.md:6696: trailing whitespace.
++   902	
.oracle/checkins/batch-3-rev.md:6698: trailing whitespace.
++   903	
.oracle/checkins/batch-3-rev.md:6700: trailing whitespace.
++   909	
.oracle/checkins/batch-3-rev.md:6702: trailing whitespace.
++   912	
.oracle/checkins/batch-3-rev.md:6704: trailing whitespace.
++   917	
.oracle/checkins/batch-3-rev.md:6706: trailing whitespace.
++   919	
.oracle/checkins/batch-3-rev.md:6708: trailing whitespace.
++   924	
.oracle/checkins/batch-3-rev.md:6710: trailing whitespace.
++   710	
.oracle/checkins/batch-3-rev.md:6712: trailing whitespace.
++  1142	
.oracle/checkins/batch-3-rev.md:6714: trailing whitespace.
++  1146	
.oracle/checkins/batch-3-rev.md:6716: trailing whitespace.
++  1157	
.oracle/checkins/batch-3-rev.md:6718: trailing whitespace.
++  1164	
.oracle/checkins/batch-3-rev.md:6720: trailing whitespace.
++  1169	
.oracle/checkins/batch-3-rev.md:6722: trailing whitespace.
++  1178	
.oracle/checkins/batch-3-rev.md:6724: trailing whitespace.
++  1206	
.oracle/checkins/batch-3-rev.md:6726: trailing whitespace.
++   968	
.oracle/checkins/batch-3-rev.md:6728: trailing whitespace.
++  1087	
.oracle/checkins/batch-3-rev.md:6730: trailing whitespace.
++  1109	
.oracle/checkins/batch-3-rev.md:6732: trailing whitespace.
++  2170	
.oracle/checkins/batch-3-rev.md:6734: trailing whitespace.
++  2185	
.oracle/checkins/batch-3-rev.md:6736: trailing whitespace.
++  2191	
.oracle/checkins/batch-3-rev.md:6738: trailing whitespace.
++  2199	
.oracle/checkins/batch-3-rev.md:6740: trailing whitespace.
++  2203	
.oracle/checkins/batch-3-rev.md:6742: trailing whitespace.
++  2217	
.oracle/checkins/batch-3-rev.md:6744: trailing whitespace.
++  2220	
.oracle/checkins/batch-3-rev.md:6746: trailing whitespace.
++  2228	
.oracle/checkins/batch-3-rev.md:6748: trailing whitespace.
++compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: 
.oracle/checkins/batch-3-rev.md:6815: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6821: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6823: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6838: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6839: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6843: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6844: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6847: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6848: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6851: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6854: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6857: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6858: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6868: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6869: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6872: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6878: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6889: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6890: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6893: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6900: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6903: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6915: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6924: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6927: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6932: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6936: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6937: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6941: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6942: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6948: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6951: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6956: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:6957: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7094: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7095: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7102: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7112: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7117: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7118: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7121: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7158: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7161: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7169: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7170: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7195: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7196: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7201: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7221: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7240: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7246: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7276: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7314: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7316: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7323: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7344: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7345: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7368: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7369: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7389: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7400: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7402: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7411: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7420: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7425: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7434: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7438: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7444: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7446: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7458: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7477: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7480: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7483: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7486: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7491: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7495: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7501: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7506: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7510: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7511: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7541: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7552: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7553: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7568: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7569: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7592: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7629: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7656: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7699: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:7714: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8013: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8015: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8016: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8018: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8019: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8031: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8036: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8040: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8054: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8055: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8066: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8067: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8070: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8076: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8077: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8092: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8093: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8122: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8126: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8137: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8144: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8158: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:8205: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9052: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9053: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9061: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9062: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9070: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9071: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9075: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9076: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9088: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9090: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9114: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9115: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9118: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9119: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9134: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9135: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9141: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9152: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9156: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9157: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9160: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9172: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9174: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9178: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9179: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9183: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9185: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9192: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9193: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9196: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9203: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9204: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9208: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9209: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9212: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9216: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9233: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9236: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9239: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9250: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9252: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9263: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9264: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9272: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9273: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9277: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9278: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9284: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9285: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9289: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9290: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9302: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9304: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9308: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9309: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9317: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9318: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9325: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9326: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9346: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9347: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9353: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9365: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9366: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9383: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9387: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9389: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9393: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9394: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9396: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9397: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9404: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9416: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9417: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9428: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9429: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9451: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9453: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9460: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9461: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9477: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9479: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9486: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9487: trailing whitespace.
+ 
.oracle/checkins/batch-3-rev.md:9702: trailing whitespace.
+   135	
.oracle/checkins/batch-3-rev.md:9705: trailing whitespace.
+   138	
.oracle/checkins/batch-3-rev.md:9710: trailing whitespace.
+   143	
.oracle/checkins/batch-3-rev.md:9711: trailing whitespace.
+   144	
.oracle/checkins/batch-3-rev.md:9716: trailing whitespace.
+   149	
.oracle/checkins/batch-3-rev.md:9719: trailing whitespace.
+   152	
.oracle/checkins/batch-3-rev.md:9722: trailing whitespace.
+   155	
.oracle/checkins/batch-3-rev.md:9723: trailing whitespace.
+   156	
.oracle/checkins/batch-3-rev.md:9727: trailing whitespace.
+   160	
.oracle/checkins/batch-3-rev.md:9730: trailing whitespace.
+   163	
.oracle/checkins/batch-3-rev.md:9733: trailing whitespace.
+   166	
.oracle/checkins/batch-3-rev.md:9734: trailing whitespace.
+   167	
.oracle/checkins/batch-3-rev.md:9750: trailing whitespace.
+   183	
.oracle/checkins/batch-3-rev.md:9753: trailing whitespace.
+   186	
.oracle/checkins/batch-3-rev.md:9756: trailing whitespace.
+   189	
.oracle/checkins/batch-3-rev.md:9757: trailing whitespace.
+   190	
.oracle/checkins/batch-3-rev.md:9763: trailing whitespace.
+   196	
.oracle/checkins/batch-3-rev.md:9765: trailing whitespace.
+   198	
.oracle/checkins/batch-3-rev.md:9769: trailing whitespace.
+   202	
.oracle/checkins/batch-3-rev.md:9770: trailing whitespace.
+   203	
.oracle/checkins/batch-3-rev.md:9820: trailing whitespace.
+   253	
.oracle/checkins/batch-3-rev.md:9849: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:9851: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:9853: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:9855: trailing whitespace.
+++ 
.oracle/checkins/batch-3-rev.md:9857: trailing whitespace.
+++ 

 succeeded in 127ms:
 .oracle/checkins/batch-3-rev.md             | 9895 +++++++++++++++++++++++++++
 .oracle/checkins/batch-3.md                 |    1 +
 scripts/migrate_external_workflow_corpus.py |    8 +
 tests/intent/test_static_lowering.py        |   34 +-
 tests/test_layout_store.py                  |   39 +-
 tests/test_porting_normalize_ingest.py      |   65 +
 tests/test_porting_synthetic_fixtures.py    |    4 +-
 tests/test_porting_ui_emitter.py            |   31 +-
 tests/test_position_fidelity.py             |    9 +-
 tests/test_reconcile.py                     |   16 +-
 tests/test_workflow_core.py                 |   90 +
 vibecomfy/ingest/normalize.py               |   47 +
 vibecomfy/porting/convert.py                |    5 +-
 vibecomfy/porting/emit/ui.py                |   14 +-
 vibecomfy/porting/layout/reconcile.py       |    5 +-
 vibecomfy/porting/layout_store.py           |   13 +-
 vibecomfy/porting/lowering.py               |   22 +-
 vibecomfy/workflow.py                       |   53 +
 18 files changed, 10281 insertions(+), 70 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
A	.oracle/checkins/batch-3-rev.md
M	.oracle/checkins/batch-3.md
M	scripts/migrate_external_workflow_corpus.py
M	tests/intent/test_static_lowering.py
M	tests/test_layout_store.py
M	tests/test_porting_normalize_ingest.py
M	tests/test_porting_synthetic_fixtures.py
M	tests/test_porting_ui_emitter.py
M	tests/test_position_fidelity.py
M	tests/test_reconcile.py
M	tests/test_workflow_core.py
M	vibecomfy/ingest/normalize.py
M	vibecomfy/porting/convert.py
M	vibecomfy/porting/emit/ui.py
M	vibecomfy/porting/layout/reconcile.py
M	vibecomfy/porting/layout_store.py
M	vibecomfy/porting/lowering.py
M	vibecomfy/workflow.py

 succeeded in 173ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
## elegance-run2
?? .oracle/checkins/batch-4.md
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
6e97450a7b75551d30d8e0a48a4e529e4cf15963
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2ddd1f06af6ce30b4588f7390429637a660ea0a3
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2ddd1f06 megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved

codex
The initial range audit surfaced a discrepancy with the supplied evidence: the literal `6e97450a..2ddd1f06` range contains 18 files, including `.oracle` artifacts and a corpus-migration script, and unfiltered `git diff --check` reports whitespace errors in the added oracle transcript. I’m separating checkpoint bookkeeping from product/test changes now, then I’ll determine whether either discrepancy affects the frozen Batch C gate.
exec
/bin/zsh -lc 'git log --graph --decorate --oneline --date-order 6e97450a..2ddd1f06' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git show --stat --oneline --decorate --summary 2ddd1f06 && git show --name-status --format='' 2ddd1f06" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc 'git diff 6e97450a..2ddd1f06 -- scripts/migrate_external_workflow_corpus.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/scripts/migrate_external_workflow_corpus.py b/scripts/migrate_external_workflow_corpus.py
index 567ba36e..893fc736 100644
--- a/scripts/migrate_external_workflow_corpus.py
+++ b/scripts/migrate_external_workflow_corpus.py
@@ -111,6 +111,14 @@ def _migrate_envelope(raw: dict[str, Any], *, filename: str) -> tuple[dict[str,
 
     migrated = workflow.to_envelope()
 
+    # Batch A's migration contract permits only groups/mode additions and
+    # compiled_api removal. Newer optional IR fields must not make the already
+    # migrated corpus non-idempotent or force another corpus rewrite.
+    for node_id, raw_entry in raw_nodes.items():
+        for field_name in ("pos", "size"):
+            if field_name not in raw_entry:
+                migrated["nodes"][node_id].pop(field_name, None)
+
     if migrated.get("metadata") != raw.get("metadata"):
         raise ValueError(f"{filename}: top-level metadata changed during serialization")
     for node_id, entry in raw_nodes.items():

exec
/bin/zsh -lc "git diff --numstat 6e97450a..2ddd1f06 -- . ':(exclude).oracle/**' && git diff --check 6e97450a..2ddd1f06 -- . ':(exclude).oracle/**'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 62ms:
* 2ddd1f06 (HEAD -> elegance-run2) megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved
* 5795812e megado run2: record Batch D+E checkpoint PASS

 succeeded in 85ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2ddd1f06 (HEAD -> elegance-run2) megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved
 scripts/migrate_external_workflow_corpus.py |  8 +++
 tests/intent/test_static_lowering.py        | 34 +++++------
 tests/test_layout_store.py                  | 39 +++++++++++--
 tests/test_porting_normalize_ingest.py      | 65 +++++++++++++++++++++
 tests/test_porting_synthetic_fixtures.py    |  4 +-
 tests/test_porting_ui_emitter.py            | 31 ++++++++--
 tests/test_position_fidelity.py             |  9 ++-
 tests/test_reconcile.py                     | 16 ++++-
 tests/test_workflow_core.py                 | 90 +++++++++++++++++++++++++++++
 vibecomfy/ingest/normalize.py               | 47 +++++++++++++++
 vibecomfy/porting/convert.py                |  5 +-
 vibecomfy/porting/emit/ui.py                | 14 ++---
 vibecomfy/porting/layout/reconcile.py       |  5 +-
 vibecomfy/porting/layout_store.py           | 13 ++---
 vibecomfy/porting/lowering.py               | 22 ++-----
 vibecomfy/workflow.py                       | 53 +++++++++++++++++
 16 files changed, 385 insertions(+), 70 deletions(-)
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
M	scripts/migrate_external_workflow_corpus.py
M	tests/intent/test_static_lowering.py
M	tests/test_layout_store.py
M	tests/test_porting_normalize_ingest.py
M	tests/test_porting_synthetic_fixtures.py
M	tests/test_porting_ui_emitter.py
M	tests/test_position_fidelity.py
M	tests/test_reconcile.py
M	tests/test_workflow_core.py
M	vibecomfy/ingest/normalize.py
M	vibecomfy/porting/convert.py
M	vibecomfy/porting/emit/ui.py
M	vibecomfy/porting/layout/reconcile.py
M	vibecomfy/porting/layout_store.py
M	vibecomfy/porting/lowering.py
M	vibecomfy/workflow.py

 succeeded in 80ms:
8	0	scripts/migrate_external_workflow_corpus.py
17	17	tests/intent/test_static_lowering.py
35	4	tests/test_layout_store.py
65	0	tests/test_porting_normalize_ingest.py
2	2	tests/test_porting_synthetic_fixtures.py
26	5	tests/test_porting_ui_emitter.py
7	2	tests/test_position_fidelity.py
14	2	tests/test_reconcile.py
90	0	tests/test_workflow_core.py
47	0	vibecomfy/ingest/normalize.py
2	3	vibecomfy/porting/convert.py
5	9	vibecomfy/porting/emit/ui.py
2	3	vibecomfy/porting/layout/reconcile.py
6	7	vibecomfy/porting/layout_store.py
6	16	vibecomfy/porting/lowering.py
53	0	vibecomfy/workflow.py
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc 'git diff 6e97450a..2ddd1f06 -- vibecomfy/workflow.py vibecomfy/ingest/normalize.py vibecomfy/porting/layout_store.py vibecomfy/porting/lowering.py vibecomfy/porting/layout/reconcile.py vibecomfy/porting/convert.py vibecomfy/porting/emit/ui.py scripts/migrate_external_workflow_corpus.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 28ms:
diff --git a/scripts/migrate_external_workflow_corpus.py b/scripts/migrate_external_workflow_corpus.py
index 567ba36e..893fc736 100644
--- a/scripts/migrate_external_workflow_corpus.py
+++ b/scripts/migrate_external_workflow_corpus.py
@@ -111,6 +111,14 @@ def _migrate_envelope(raw: dict[str, Any], *, filename: str) -> tuple[dict[str,
 
     migrated = workflow.to_envelope()
 
+    # Batch A's migration contract permits only groups/mode additions and
+    # compiled_api removal. Newer optional IR fields must not make the already
+    # migrated corpus non-idempotent or force another corpus rewrite.
+    for node_id, raw_entry in raw_nodes.items():
+        for field_name in ("pos", "size"):
+            if field_name not in raw_entry:
+                migrated["nodes"][node_id].pop(field_name, None)
+
     if migrated.get("metadata") != raw.get("metadata"):
         raise ValueError(f"{filename}: top-level metadata changed during serialization")
     for node_id, entry in raw_nodes.items():
diff --git a/vibecomfy/ingest/normalize.py b/vibecomfy/ingest/normalize.py
index 1dddec49..9d4bed19 100644
--- a/vibecomfy/ingest/normalize.py
+++ b/vibecomfy/ingest/normalize.py
@@ -1,6 +1,7 @@
 from __future__ import annotations
 
 from copy import deepcopy
+import math
 from pathlib import Path
 from typing import Any
 
@@ -431,6 +432,46 @@ def _node_mode_from_metadata(metadata: dict[str, Any]) -> int:
     return 0
 
 
+def _geometry_pair(value: Any) -> list[float] | None:
+    """Return a detached finite numeric pair, or ``None`` when invalid/absent."""
+    if value is None or not isinstance(value, (list, tuple)) or len(value) != 2:
+        return None
+    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
+        return None
+    try:
+        pair = [float(value[0]), float(value[1])]
+    except (OverflowError, TypeError, ValueError):
+        return None
+    return pair if all(math.isfinite(coord) for coord in pair) else None
+
+
+def _decode_envelope_geometry(
+    entry: dict[str, Any], metadata: dict[str, Any], field_name: str, node_id: str
+) -> list[float] | None:
+    """Decode strict first-class geometry with an independent legacy ``_ui`` fallback."""
+    if field_name in entry:
+        node_value = entry[field_name]
+        if node_value is None:
+            return None
+        pair = _geometry_pair(node_value)
+        if pair is None:
+            raise ValueError(
+                f"node {node_id!r}: {field_name} must contain exactly two finite numeric coordinates or null"
+            )
+        return pair
+
+    ui = metadata.get("_ui")
+    legacy_value = ui.get(field_name) if isinstance(ui, dict) else None
+    if legacy_value is None:
+        return None
+    pair = _geometry_pair(legacy_value)
+    if pair is None:
+        raise ValueError(
+            f"node {node_id!r}: legacy _ui.{field_name} must contain exactly two finite numeric coordinates or null"
+        )
+    return pair
+
+
 def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
     """Implementation of :meth:`VibeWorkflow.from_envelope`.
 
@@ -595,6 +636,8 @@ def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
         node_mode = (
             entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
         )
+        node_pos = _decode_envelope_geometry(entry, node_metadata, "pos", node_id)
+        node_size = _decode_envelope_geometry(entry, node_metadata, "size", node_id)
         workflow.nodes[node_id] = VibeNode(
             id=node_id,
             class_type=class_type,
@@ -605,6 +648,8 @@ def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
             uid=uid,
             raw_widgets=raw_widget_payload,
             mode=node_mode,
+            pos=node_pos,
+            size=node_size,
         )
 
     # ── edges ──────────────────────────────────────────────────────────────
@@ -948,6 +993,8 @@ def _from_api_impl(
             uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
             raw_widgets=raw_widgets,
             mode=_node_mode_from_metadata(metadata),
+            pos=_geometry_pair(_ui_node.get("pos")) if isinstance(_ui_raw, dict) else None,
+            size=_geometry_pair(_ui_node.get("size")) if isinstance(_ui_raw, dict) else None,
         )
         _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
         if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
diff --git a/vibecomfy/porting/convert.py b/vibecomfy/porting/convert.py
index 92009a61..094d6f51 100644
--- a/vibecomfy/porting/convert.py
+++ b/vibecomfy/porting/convert.py
@@ -179,9 +179,8 @@ def _capture_virtual_wires(workflow: VibeWorkflow) -> dict[str, dict[str, Any]]:
         if node.class_type not in _VIRTUAL_WIRE_CLASS_TYPES:
             continue
         uid = node.uid or str(node_id)
-        ui = node.metadata.get("_ui") if isinstance(node.metadata, dict) else None
-        pos = ui.get("pos") if isinstance(ui, dict) else None
-        size = ui.get("size") if isinstance(ui, dict) else None
+        pos = copy.deepcopy(node.pos)
+        size = copy.deepcopy(node.size)
         channel = (
             broadcast_name(node)
             if node.class_type in BROADCAST_HELPER_CLASS_TYPES
diff --git a/vibecomfy/porting/emit/ui.py b/vibecomfy/porting/emit/ui.py
index bcaea9d0..e4bd11ac 100644
--- a/vibecomfy/porting/emit/ui.py
+++ b/vibecomfy/porting/emit/ui.py
@@ -307,17 +307,14 @@ def _resolve_furniture(
 
 
 def _captured_geometry(node: Any) -> dict[str, list[float]] | None:
-    """Return {pos, size} from ``node.metadata['_ui']``, or None when absent.
+    """Return first-class ``{pos, size}``, or ``None`` when either is absent.
 
     The ``None`` fallthrough is intentional: callers should chain through to
     ``_stub_layout`` when no captured geometry exists (e.g. programmatic nodes
     or workflows loaded from a .py file without a sidecar).
     """
-    _ui = getattr(node, "metadata", {}).get("_ui")
-    if not isinstance(_ui, dict):
-        return None
-    pos = _ui.get("pos")
-    size = _ui.get("size")
+    pos = getattr(node, "pos", None)
+    size = getattr(node, "size", None)
     if not isinstance(pos, (list, tuple)) or len(pos) < 2:
         return None
     if not isinstance(size, (list, tuple)) or len(size) < 2:
@@ -2479,9 +2476,8 @@ def emit_ui_json(
             furniture = _resolve_furniture(node, matched_entry)
         else:
             # Unmatched (new / unmatched_legacy / removed-then-readded).
-            # The captured _ui inline on the node (direct-ingest fallback) is the
-            # source of truth when present; the engine owns geometry only when
-            # no captured _ui exists (programmatic / scratchpad path).
+            # First-class node geometry is the direct-ingest source of truth; the
+            # engine owns geometry only when no complete captured pair exists.
             geometry = (
                 _captured_geometry(node)
                 or engine_positions.get(node.uid)
diff --git a/vibecomfy/porting/layout/reconcile.py b/vibecomfy/porting/layout/reconcile.py
index 0dc99e28..f734b13b 100644
--- a/vibecomfy/porting/layout/reconcile.py
+++ b/vibecomfy/porting/layout/reconcile.py
@@ -279,9 +279,8 @@ def _compute_hash(
 
 
 def _pos_from_node(node: Any) -> tuple[float, float]:
-    """Extract (x, y) from node.metadata['_ui']['pos'], fallback to (0, 0)."""
-    ui = node.metadata.get("_ui", {}) if hasattr(node, "metadata") else {}
-    pos = ui.get("pos", [0.0, 0.0])
+    """Extract first-class ``(x, y)`` from a node, falling back to ``(0, 0)``."""
+    pos = getattr(node, "pos", None)
     try:
         return (float(pos[0]), float(pos[1]))
     except (TypeError, IndexError, ValueError):
diff --git a/vibecomfy/porting/layout_store.py b/vibecomfy/porting/layout_store.py
index ff96b2fd..3af1de3e 100644
--- a/vibecomfy/porting/layout_store.py
+++ b/vibecomfy/porting/layout_store.py
@@ -172,8 +172,8 @@ def _assemble_definition_entries(
 def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
     """Serialize the full M2 layout envelope for ``wf`` to the sidecar file.
 
-    Per-uid node geometry is captured from each node's ``metadata['_ui']``.
-    Nodes with an empty uid or no captured ``pos`` are skipped (M1.5 behavior).
+    Per-uid node geometry is captured from first-class ``pos``/``size`` fields.
+    Nodes with an empty uid or no first-class ``pos`` are skipped (M1.5 behavior).
     Groups are serialized from the first-class ``wf.groups`` field.  Other
     graph-level sections are read from ``wf.metadata`` when present and
     otherwise serialized as empty/absent. Returns the sidecar path written.
@@ -183,12 +183,11 @@ def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
         uid = node.uid
         if not uid:
             continue
-        ui = node.metadata.get("_ui")
-        if not isinstance(ui, dict):
-            continue
-        if ui.get("pos") is None:
+        if node.pos is None:
             continue
-        entries[uid] = _build_entry(ui)
+        ui = node.metadata.get("_ui")
+        furniture = ui if isinstance(ui, dict) else {}
+        entries[uid] = _build_entry({**furniture, "pos": node.pos, "size": node.size})
 
     meta = getattr(wf, "metadata", {}) or {}
     layout_meta = meta.get("_layout") if isinstance(meta.get("_layout"), dict) else {}
diff --git a/vibecomfy/porting/lowering.py b/vibecomfy/porting/lowering.py
index 1cead444..42937214 100644
--- a/vibecomfy/porting/lowering.py
+++ b/vibecomfy/porting/lowering.py
@@ -350,14 +350,9 @@ def _clone_node(
     }
 
     # --- Deterministic clone layout positioning ---
-    # Read source node position from _ui metadata; default to (0, 0).
-    source_ui = source_node.metadata.get("_ui")
-    if isinstance(source_ui, dict):
-        source_pos = source_ui.get("pos", [0, 0])
-        source_size = source_ui.get("size")
-    else:
-        source_pos = [0, 0]
-        source_size = None
+    # Read first-class source geometry; a geometry-less source uses the existing
+    # deterministic clone-layout origin.
+    source_pos = source_node.pos if source_node.pos is not None else [0, 0]
     try:
         source_x = float(source_pos[0])
         source_y = float(source_pos[1])
@@ -366,14 +361,6 @@ def _clone_node(
     # Compute clone position: horizontal stride per iteration, same y.
     clone_pos = [source_x + HORIZONTAL_STRIDE * iteration_index, source_y]
     snapped_pos = snap_pos(clone_pos)
-    # Ensure _ui sub-dict exists and store the snapped position.
-    clone_ui: dict[str, Any] = cloned_metadata.setdefault("_ui", {})
-    clone_ui["pos"] = snapped_pos
-    if source_size is not None:
-        try:
-            clone_ui["size"] = source_size
-        except (TypeError, IndexError):
-            pass
     # --- End layout positioning ---
 
     cloned = source_node.__class__(
@@ -385,6 +372,9 @@ def _clone_node(
         metadata=cloned_metadata,
         uid=clone_uid,
         raw_widgets=copy.deepcopy(source_node.raw_widgets),
+        mode=source_node.mode,
+        pos=snapped_pos,
+        size=copy.deepcopy(source_node.size),
     )
     workflow.nodes[new_id] = cloned
     return cloned
diff --git a/vibecomfy/workflow.py b/vibecomfy/workflow.py
index 6731c6e2..5075fc4a 100644
--- a/vibecomfy/workflow.py
+++ b/vibecomfy/workflow.py
@@ -3,6 +3,7 @@ from __future__ import annotations
 import copy
 import dataclasses
 from dataclasses import dataclass, field, replace
+import math
 import warnings
 from typing import TYPE_CHECKING, Any
 
@@ -53,6 +54,41 @@ def _to_plain(obj: Any) -> Any:
     return obj
 
 
+def _geometry_error(value: Any) -> str | None:
+    """Return why a first-class geometry value is invalid, if it is invalid."""
+    if value is None:
+        return None
+    if not isinstance(value, list) or len(value) != 2:
+        return "must be a list containing exactly two coordinates"
+    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
+        return "coordinates must be numeric (not booleans)"
+    try:
+        finite = all(math.isfinite(float(coord)) for coord in value)
+    except (OverflowError, TypeError, ValueError):
+        finite = False
+    if not finite:
+        return "coordinates must be finite"
+    return None
+
+
+def _invalid_geometry_details(workflow: "VibeWorkflow") -> list[dict[str, Any]]:
+    details: list[dict[str, Any]] = []
+    for node_id, node in workflow.nodes.items():
+        for field_name in ("pos", "size"):
+            value = getattr(node, field_name)
+            error = _geometry_error(value)
+            if error is not None:
+                details.append(
+                    {
+                        "node_id": str(node_id),
+                        "field": field_name,
+                        "value": value,
+                        "reason": error,
+                    }
+                )
+    return details
+
+
 @dataclass(slots=True)
 class WorkflowSource:
     id: str
@@ -90,6 +126,8 @@ class VibeNode:
     uid: str = ""
     raw_widgets: RawWidgetPayload | None = None
     mode: int = 0
+    pos: list[float] | None = None
+    size: list[float] | None = None
 
     @property
     def provenance(self) -> str:
@@ -260,6 +298,12 @@ class VibeWorkflow:
         this, not here.
         """
         _raise_embedded_api_links(self, surface="envelope serialization")
+        invalid_geometry = _invalid_geometry_details(self)
+        if invalid_geometry:
+            detail = invalid_geometry[0]
+            raise ValueError(
+                f"node {detail['node_id']!r}: {detail['field']} {detail['reason']}"
+            )
         plain = _to_plain(self)
         plain["vibecomfy_format_version"] = FORMAT_VERSION
         return plain
@@ -696,6 +740,15 @@ class VibeWorkflow:
                 issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
             if edge.to_node not in self.nodes:
                 issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
+        for detail in _invalid_geometry_details(self):
+            issues.append(
+                ValidationIssue(
+                    "invalid_geometry",
+                    f"Node {detail['node_id']} {detail['field']} {detail['reason']}.",
+                    severity="error",
+                    detail=detail,
+                )
+            )
         embedded_links = _embedded_api_link_details(self)
         for detail in embedded_links:
             issues.append(

exec
/bin/zsh -lc "nl -ba vibecomfy/workflow.py | sed -n '1,155p'; nl -ba vibecomfy/workflow.py | sed -n '270,325p'; nl -ba vibecomfy/workflow.py | sed -n '690,770p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 4ms:
   690	    def remove_node(self, node_id: str) -> "VibeWorkflow":
   691	        """Remove a node and all edges attached to it."""
   692	        node_id = str(node_id)
   693	        self.nodes.pop(node_id, None)
   694	        self.edges = [
   695	            edge
   696	            for edge in self.edges
   697	            if str(edge.from_node) != node_id and str(edge.to_node) != node_id
   698	        ]
   699	        self.inputs = {
   700	            name: target
   701	            for name, target in self.inputs.items()
   702	            if str(target.node_id) != node_id
   703	        }
   704	        self.outputs = [
   705	            output
   706	            for output in self.outputs
   707	            if str(output.node_id) != node_id
   708	        ]
   709	        return self
   710	
   711	    def replace_edge(self, to_ref: str, new_from_ref: str | Handle) -> "VibeWorkflow":
   712	        """Redirect the edge feeding ``to_ref`` so it now originates from ``new_from_ref``.
   713	
   714	        Disconnects the existing edge (if any) and connects the new source. Returns
   715	        ``self`` for chaining.
   716	        """
   717	        self._parse_target_ref(to_ref, operation="replace_edge")
   718	        self._parse_source_ref(new_from_ref, operation="replace_edge")
   719	        self.disconnect(to_ref)
   720	        return self.connect(new_from_ref, to_ref)
   721	
   722	    def validate(self, schema_provider: SchemaProvider | None = None) -> ValidationReport:
   723	        issues: list[ValidationIssue] = []
   724	        if not self.nodes:
   725	            issues.append(ValidationIssue("empty_workflow", "Workflow contains no nodes."))
   726	        for spec in comfyui_node_issue_specs(
   727	            (node_id, node.class_type, node.inputs, node.metadata)
   728	            for node_id, node in self.nodes.items()
   729	        ):
   730	            issues.append(
   731	                ValidationIssue(
   732	                    spec.code,
   733	                    spec.message,
   734	                    severity=spec.severity,
   735	                    detail=spec.detail,
   736	                )
   737	            )
   738	        for edge in self.edges:
   739	            if edge.from_node not in self.nodes:
   740	                issues.append(ValidationIssue("missing_edge_source", f"Missing source node {edge.from_node}."))
   741	            if edge.to_node not in self.nodes:
   742	                issues.append(ValidationIssue("missing_edge_target", f"Missing target node {edge.to_node}."))
   743	        for detail in _invalid_geometry_details(self):
   744	            issues.append(
   745	                ValidationIssue(
   746	                    "invalid_geometry",
   747	                    f"Node {detail['node_id']} {detail['field']} {detail['reason']}.",
   748	                    severity="error",
   749	                    detail=detail,
   750	                )
   751	            )
   752	        embedded_links = _embedded_api_link_details(self)
   753	        for detail in embedded_links:
   754	            issues.append(
   755	                ValidationIssue(
   756	                    "embedded_api_link",
   757	                    _embedded_api_link_message(detail, surface="validation"),
   758	                    severity="error",
   759	                    detail=detail,
   760	                )
   761	            )
   762	        api: dict[str, Any] | None = None
   763	        if not embedded_links:
   764	            try:
   765	                api = self.compile(backend="api")
   766	            except Exception as exc:
   767	                detail: dict[str, Any] = {}
   768	                if isinstance(exc, WorkflowCompileError):
   769	                    detail = {"compile_code": exc.code, **exc.detail}
   770	                issues.append(ValidationIssue("api_compile_failed", str(exc), severity="error", detail=detail))

exec
/bin/zsh -lc "nl -ba vibecomfy/ingest/normalize.py | sed -n '400,680p'; nl -ba vibecomfy/ingest/normalize.py | sed -n '820,1025p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
   400	    if value is None:
   401	        return []
   402	    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
   403	        raise ValueError(f"serialized vibe envelope {label} must be a list of strings")
   404	    return list(value)
   405	
   406	
   407	def _vibe_groups(value: Any) -> list[dict[str, Any]]:
   408	    """Decode the serialized graph-level ``groups`` field: ``None`` → ``[]``.
   409	
   410	    Fail-closed like the rest of the envelope decoder: when present, ``groups``
   411	    must be a list of group objects (LiteGraph ``{title, bounding, ...}``
   412	    dicts).  Old envelopes without the key decode to an empty list.
   413	    """
   414	    if value is None:
   415	        return []
   416	    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
   417	        raise ValueError("serialized vibe envelope 'groups' must be a list of group objects")
   418	    return deepcopy(value)
   419	
   420	
   421	def _node_mode_from_metadata(metadata: dict[str, Any]) -> int:
   422	    """First-class mode value for a node: ``_ui.mode`` then legacy
   423	    ``metadata["mode"]``, else 0.  Only ints are accepted."""
   424	    ui = metadata.get("_ui")
   425	    if isinstance(ui, dict):
   426	        ui_mode = ui.get("mode", 0)
   427	        if isinstance(ui_mode, int):
   428	            return ui_mode
   429	    meta_mode = metadata.get("mode")
   430	    if isinstance(meta_mode, int):
   431	        return meta_mode
   432	    return 0
   433	
   434	
   435	def _geometry_pair(value: Any) -> list[float] | None:
   436	    """Return a detached finite numeric pair, or ``None`` when invalid/absent."""
   437	    if value is None or not isinstance(value, (list, tuple)) or len(value) != 2:
   438	        return None
   439	    if any(isinstance(coord, bool) or not isinstance(coord, (int, float)) for coord in value):
   440	        return None
   441	    try:
   442	        pair = [float(value[0]), float(value[1])]
   443	    except (OverflowError, TypeError, ValueError):
   444	        return None
   445	    return pair if all(math.isfinite(coord) for coord in pair) else None
   446	
   447	
   448	def _decode_envelope_geometry(
   449	    entry: dict[str, Any], metadata: dict[str, Any], field_name: str, node_id: str
   450	) -> list[float] | None:
   451	    """Decode strict first-class geometry with an independent legacy ``_ui`` fallback."""
   452	    if field_name in entry:
   453	        node_value = entry[field_name]
   454	        if node_value is None:
   455	            return None
   456	        pair = _geometry_pair(node_value)
   457	        if pair is None:
   458	            raise ValueError(
   459	                f"node {node_id!r}: {field_name} must contain exactly two finite numeric coordinates or null"
   460	            )
   461	        return pair
   462	
   463	    ui = metadata.get("_ui")
   464	    legacy_value = ui.get(field_name) if isinstance(ui, dict) else None
   465	    if legacy_value is None:
   466	        return None
   467	    pair = _geometry_pair(legacy_value)
   468	    if pair is None:
   469	        raise ValueError(
   470	            f"node {node_id!r}: legacy _ui.{field_name} must contain exactly two finite numeric coordinates or null"
   471	        )
   472	    return pair
   473	
   474	
   475	def _decode_serialized_vibe(raw: dict[str, Any]) -> VibeWorkflow:
   476	    """Implementation of :meth:`VibeWorkflow.from_envelope`.
   477	
   478	    Do not call this from new code — use ``VibeWorkflow.from_envelope`` (or
   479	    the module-level ``from_envelope``).  The decoder is fail-closed and
   480	    unrelaxed: the rich top-level ``nodes`` mapping and ``edges`` list are
   481	    the ONLY structural authority; ``compiled_api`` is never consulted for
   482	    which nodes exist.  Any malformed or mixed entry raises ``ValueError``
   483	    and no partial graph is ever returned.
   484	
   485	    Every field is deep-copied.  Node ``metadata`` is preserved verbatim
   486	    (including ``metadata._ui``) except that ``metadata[PROVENANCE_KEY]`` is
   487	    unconditionally enforced to ``"untrusted_source"`` at this external JSON
   488	    boundary, and stable node ``uid`` values are preserved exactly.
   489	    """
   490	    if not isinstance(raw, dict):
   491	        raise ValueError("serialized vibe envelope must be a JSON object")
   492	
   493	    nodes_raw = raw.get("nodes")
   494	    if not isinstance(nodes_raw, dict):
   495	        raise ValueError("serialized vibe envelope 'nodes' must be a mapping of node objects")
   496	    for key, entry in nodes_raw.items():
   497	        if not isinstance(entry, dict):
   498	            raise ValueError(
   499	                f"node {key!r}: node entries must be mappings, got {type(entry).__name__}"
   500	            )
   501	
   502	    # ── top-level envelope fields ──────────────────────────────────────────
   503	    source_raw = raw.get("source")
   504	    if not isinstance(source_raw, dict):
   505	        raise ValueError("serialized vibe envelope 'source' must be a mapping")
   506	    source_id = source_raw.get("id")
   507	    if not isinstance(source_id, str) or not source_id.strip():
   508	        raise ValueError("source.id must be a nonblank string")
   509	    source_path = source_raw.get("path")
   510	    if source_path is not None and not isinstance(source_path, str):
   511	        raise ValueError("source.path must be a string or null")
   512	    source_provenance = source_raw.get("provenance")
   513	    if source_provenance is not None and not isinstance(source_provenance, dict):
   514	        raise ValueError("source.provenance must be a mapping or null")
   515	    source = WorkflowSource(
   516	        id=source_id,
   517	        path=source_path,
   518	        source_type=str(source_raw.get("source_type", "unknown")),
   519	        provenance=deepcopy(source_provenance) if isinstance(source_provenance, dict) else {},
   520	    )
   521	
   522	    workflow_id = raw.get("id")
   523	    if not isinstance(workflow_id, str) or not workflow_id.strip():
   524	        workflow_id = source_id
   525	
   526	    requirements_raw = raw.get("requirements")
   527	    if not isinstance(requirements_raw, dict):
   528	        raise ValueError("serialized vibe envelope 'requirements' must be a mapping")
   529	    requirements = WorkflowRequirements(
   530	        models=_vibe_string_list(
   531	            requirements_raw.get("models"), "requirements.models"
   532	        ),
   533	        custom_nodes=_vibe_string_list(
   534	            requirements_raw.get("custom_nodes"), "requirements.custom_nodes"
   535	        ),
   536	        missing_models=_vibe_string_list(
   537	            requirements_raw.get("missing_models"), "requirements.missing_models"
   538	        ),
   539	        missing_nodes=_vibe_string_list(
   540	            requirements_raw.get("missing_nodes"), "requirements.missing_nodes"
   541	        ),
   542	        unsupported=_vibe_string_list(
   543	            requirements_raw.get("unsupported"), "requirements.unsupported"
   544	        ),
   545	    )
   546	
   547	    metadata_raw = raw.get("metadata")
   548	    if metadata_raw is not None and not isinstance(metadata_raw, dict):
   549	        raise ValueError("serialized vibe envelope 'metadata' must be a mapping or null")
   550	
   551	    strict_types = raw.get("strict_types", False)
   552	    if not isinstance(strict_types, bool):
   553	        raise ValueError("strict_types must be a boolean")
   554	
   555	    groups = _vibe_groups(raw.get("groups"))
   556	
   557	    workflow = VibeWorkflow(
   558	        id=workflow_id,
   559	        source=source,
   560	        requirements=requirements,
   561	        metadata=deepcopy(metadata_raw) if isinstance(metadata_raw, dict) else {},
   562	        strict_types=strict_types,
   563	        groups=groups,
   564	    )
   565	
   566	    # ── nodes ──────────────────────────────────────────────────────────────
   567	    for key, entry in nodes_raw.items():
   568	        node_id = entry.get("id")
   569	        if not isinstance(node_id, str) or not node_id.strip():
   570	            raise ValueError(f"node {key!r}: id must be a nonblank string")
   571	        if str(key) != node_id:
   572	            raise ValueError(f"node mapping key {key!r} must equal node.id {node_id!r}")
   573	        class_type = entry.get("class_type")
   574	        if not isinstance(class_type, str) or not class_type.strip():
   575	            raise ValueError(f"node {node_id!r}: class_type must be a nonblank string")
   576	        uid = entry.get("uid")
   577	        if not isinstance(uid, str) or not uid.strip():
   578	            raise ValueError(f"node {node_id!r}: uid must be a nonblank string")
   579	        pack = entry.get("pack")
   580	        if pack is not None and not isinstance(pack, str):
   581	            raise ValueError(f"node {node_id!r}: pack must be a string or null")
   582	        for field_name in ("inputs", "widgets", "metadata"):
   583	            value = entry.get(field_name)
   584	            if not isinstance(value, dict):
   585	                raise ValueError(f"node {node_id!r}: {field_name} must be a mapping")
   586	        raw_widgets = entry.get("raw_widgets")
   587	        raw_widget_payload: RawWidgetPayload | None = None
   588	        if raw_widgets is not None:
   589	            if not isinstance(raw_widgets, dict) or not {
   590	                "values",
   591	                "shape",
   592	                "source",
   593	                "has_dict_rows",
   594	                "length",
   595	            } <= set(raw_widgets):
   596	                raise ValueError(
   597	                    f"node {node_id!r}: raw_widgets must be a RawWidgetPayload mapping or null"
   598	                )
   599	            length = raw_widgets["length"]
   600	            if not isinstance(length, int) or isinstance(length, bool) or length < 0:
   601	                raise ValueError(
   602	                    f"node {node_id!r}: raw_widgets.length must be a nonnegative integer"
   603	                )
   604	            shape = raw_widgets["shape"]
   605	            source_name = raw_widgets["source"]
   606	            has_dict_rows = raw_widgets["has_dict_rows"]
   607	            if not isinstance(shape, str) or not shape.strip():
   608	                raise ValueError(
   609	                    f"node {node_id!r}: raw_widgets.shape must be a nonblank string"
   610	                )
   611	            if not isinstance(source_name, str) or not source_name.strip():
   612	                raise ValueError(
   613	                    f"node {node_id!r}: raw_widgets.source must be a nonblank string"
   614	                )
   615	            if not isinstance(has_dict_rows, bool):
   616	                raise ValueError(
   617	                    f"node {node_id!r}: raw_widgets.has_dict_rows must be a boolean"
   618	                )
   619	            raw_widget_payload = RawWidgetPayload(
   620	                values=deepcopy(raw_widgets["values"]),
   621	                shape=shape,
   622	                source=source_name,
   623	                has_dict_rows=has_dict_rows,
   624	                length=length,
   625	            )
   626	        node_metadata = deepcopy(entry["metadata"])
   627	        # S4 capability fence: ingest is the external-JSON boundary, so every
   628	        # decoded node is tagged untrusted_source. Unconditional set — never
   629	        # `setdefault` — so hostile JSON cannot pre-declare itself trusted.
   630	        node_metadata[PROVENANCE_KEY] = "untrusted_source"
   631	        # Mode is first-class: prefer the serialized node-level ``mode`` field
   632	        # (written by to_envelope's dataclass walk), falling back to the legacy
   633	        # ``_ui.mode`` / ``metadata["mode"]`` locations for old envelopes.
   634	        # ``_ui`` stays verbatim so the emitter's furniture keeps re-emitting it.
   635	        entry_mode = entry.get("mode")
   636	        node_mode = (
   637	            entry_mode if isinstance(entry_mode, int) else _node_mode_from_metadata(node_metadata)
   638	        )
   639	        node_pos = _decode_envelope_geometry(entry, node_metadata, "pos", node_id)
   640	        node_size = _decode_envelope_geometry(entry, node_metadata, "size", node_id)
   641	        workflow.nodes[node_id] = VibeNode(
   642	            id=node_id,
   643	            class_type=class_type,
   644	            pack=pack,
   645	            inputs=deepcopy(entry["inputs"]),
   646	            widgets=deepcopy(entry["widgets"]),
   647	            metadata=node_metadata,
   648	            uid=uid,
   649	            raw_widgets=raw_widget_payload,
   650	            mode=node_mode,
   651	            pos=node_pos,
   652	            size=node_size,
   653	        )
   654	
   655	    # ── edges ──────────────────────────────────────────────────────────────
   656	    edges_raw = raw.get("edges")
   657	    if not isinstance(edges_raw, list):
   658	        raise ValueError("serialized vibe envelope 'edges' must be a list")
   659	    for index, edge in enumerate(edges_raw):
   660	        if not isinstance(edge, dict):
   661	            raise ValueError(
   662	                f"edge {index}: edge entries must be mappings, got {type(edge).__name__}"
   663	            )
   664	        for field_name in ("from_node", "from_output", "to_node", "to_input"):
   665	            value = edge.get(field_name)
   666	            if not isinstance(value, str) or not value.strip():
   667	                raise ValueError(f"edge {index}: {field_name} must be a nonblank string")
   668	        if edge["from_node"] not in workflow.nodes or edge["to_node"] not in workflow.nodes:
   669	            raise ValueError(
   670	                f"edge {index}: endpoint node ids {edge['from_node']!r}/{edge['to_node']!r} "
   671	                "must exist in nodes"
   672	            )
   673	        workflow.edges.append(
   674	            VibeEdge(
   675	                from_node=edge["from_node"],
   676	                from_output=edge["from_output"],
   677	                to_node=edge["to_node"],
   678	                to_input=edge["to_input"],
   679	            )
   680	        )
   820	    # Graph-level LiteGraph groups are first-class on the IR.  The API dict
   821	    # produced by the converter drops them, so carry them across from the raw
   822	    # graph here (fail-closed: a non-list groups is rejected).
   823	    workflow.groups = _vibe_groups(raw.get("groups"))
   824	    return workflow
   825	
   826	
   827	def from_api(
   828	    api_workflow: dict[str, Any],
   829	    *,
   830	    source_path: str | None = None,
   831	    workflow_id: str | None = None,
   832	    schema_provider: SchemaProvider | None = None,
   833	) -> VibeWorkflow:
   834	    """Ingest a Comfy prompt dict into a :class:`VibeWorkflow`."""
   835	    with untrusted_scope():
   836	        return _from_api_impl(
   837	            api_workflow,
   838	            source_path=source_path,
   839	            workflow_id=workflow_id,
   840	            schema_provider=schema_provider,
   841	        )
   842	
   843	
   844	def _is_vibe_envelope(raw: dict[str, Any]) -> bool:
   845	    """True when *raw* is a versioned (or compiled_api-bearing) rich envelope."""
   846	    return isinstance(raw.get("nodes"), dict) and (
   847	        "vibecomfy_format_version" in raw
   848	        or isinstance(raw.get("compiled_api"), dict)
   849	    )
   850	
   851	
   852	def _named_import(
   853	    raw: dict[str, Any],
   854	    *,
   855	    source_path: str | None = None,
   856	    workflow_id: str | None = None,
   857	    schema_provider: SchemaProvider | None = None,
   858	    use_comfy_converter: bool = True,
   859	    comfy_converter_strict: bool = True,
   860	) -> VibeWorkflow:
   861	    """Happy-path import: envelope, then UI, then API. Never ``compile()`` to reach IR."""
   862	    if _is_vibe_envelope(raw):
   863	        return from_envelope(raw)
   864	    if isinstance(raw.get("nodes"), list):
   865	        return from_ui(
   866	            raw,
   867	            source_path=source_path,
   868	            workflow_id=workflow_id,
   869	            schema_provider=schema_provider,
   870	            use_comfy_converter=use_comfy_converter,
   871	            comfy_converter_strict=comfy_converter_strict,
   872	        )
   873	    api = normalize_to_api(
   874	        raw,
   875	        schema_provider=schema_provider,
   876	        use_comfy_converter=use_comfy_converter,
   877	        comfy_converter_strict=comfy_converter_strict,
   878	    )
   879	    return from_api(
   880	        api,
   881	        source_path=source_path,
   882	        workflow_id=workflow_id,
   883	        schema_provider=schema_provider,
   884	    )
   885	
   886	
   887	def _from_api_impl(
   888	    api_workflow: dict[str, Any],
   889	    *,
   890	    source_path: str | None = None,
   891	    workflow_id: str | None = None,
   892	    schema_provider: SchemaProvider | None = None,
   893	) -> VibeWorkflow:
   894	    """Ingest a Comfy prompt dict. Caller holds :func:`untrusted_scope`."""
   895	    _enforce_exec_source_limits(api_workflow, surface="api.ingest")
   896	    source = WorkflowSource(
   897	        id=workflow_id or (Path(source_path).stem if source_path else "workflow"),
   898	        path=source_path,
   899	        source_type="api",
   900	    )
   901	    workflow = VibeWorkflow(id=source.id, source=source)
   902	    for node_id, node in api_workflow.items():
   903	        if not isinstance(node, dict):
   904	            continue
   905	        raw_inputs = dict(node.get("inputs", {}))
   906	        input_provenance = node.get("_input_provenance")
   907	        if not isinstance(input_provenance, dict):
   908	            input_provenance = {}
   909	        inputs: dict[str, Any] = {}
   910	        widgets: dict[str, Any] = {}
   911	        class_type = str(node.get("class_type", "Unknown"))
   912	        for key, value in raw_inputs.items():
   913	            if input_provenance.get(key) != "widget" and is_canonical_api_link(value):
   914	                continue
   915	            if key.startswith("widget_") or _is_exec_widget_key(class_type, key):
   916	                widgets[key] = value
   917	            else:
   918	                inputs[key] = value
   919	        raw_widgets = _coerce_raw_widget_payload(
   920	            node.get("_raw_widgets", node.get("raw_widgets"))
   921	        )
   922	        if raw_widgets is None:
   923	            raw_ui = node.get("_ui")
   924	            if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
   925	                raw_widgets = _coerce_raw_widget_payload(
   926	                    _raw_widget_payload_dict(raw_ui["widgets_values"], source="ui.widgets_values")
   927	                )
   928	        metadata = {
   929	            key: value
   930	            for key, value in node.items()
   931	            if key
   932	            not in {
   933	                "class_type",
   934	                "inputs",
   935	                "_raw_widgets",
   936	                "raw_widgets",
   937	                "_input_provenance",
   938	            }
   939	        }
   940	        # ── retain control_after_generate (UI-only) into metadata ──
   941	        # Captured here, before the compile-time `_is_ui_only_prompt_input` filter
   942	        # (workflow.py:471) drops it from the compiled API dict, so the emitter can
   943	        # re-render it. Metadata-only: it never re-enters `inputs`/`widgets`, so
   944	        # `compile("api")` stays byte-for-byte identical. Never guessed — when no
   945	        # recognized control token is present, metadata stays unset and the emitter
   946	        # emits the documented `fixed` default itself.
   947	        control_value = _capture_control_after_generate(node, class_type)
   948	        if control_value is not None:
   949	            metadata.setdefault("control_after_generate", control_value)
   950	        # ── retain flags/color/bgcolor from _ui into top-level metadata ──
   951	        # Both paths: pure-Python path stores the full raw node in _ui (line 99);
   952	        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
   953	        # Captured as metadata DATA only — never enters inputs/widgets (K3 invariant).
   954	        # mode is first-class on VibeNode (the compile mute/bypass signal): the
   955	        # field is populated below from `_ui.mode` (fallback metadata["mode"]) and
   956	        # `_ui.mode` is LEFT IN PLACE so emit_ui_json's furniture keeps re-emitting
   957	        # it.  No duplicate metadata["mode"] is written on new ingests.
   958	        _ui_raw = metadata.get("_ui")
   959	        if isinstance(_ui_raw, dict):
   960	            # The _ui dict may alias the input API node's _ui (pure-Python path);
   961	            # deepcopy so the caller's node dict is never corrupted.
   962	            # Only assign when a real _ui was present — do not invent {}.
   963	            _ui_node = deepcopy(_ui_raw)
   964	            metadata["_ui"] = _ui_node
   965	            for _vis_field in ("flags", "color", "bgcolor"):
   966	                if _vis_field in _ui_node:
   967	                    metadata.setdefault(_vis_field, _ui_node[_vis_field])
   968	        # ── enrich node metadata from schema ──
   969	        output_names = _schema_output_names(schema_provider, class_type)
   970	        if output_names:
   971	            metadata.setdefault("output_names", output_names)
   972	        output_types = _schema_output_types(schema_provider, class_type)
   973	        if output_types:
   974	            metadata.setdefault("output_types", output_types)
   975	        input_aliases = _schema_input_aliases(schema_provider, class_type)
   976	        if input_aliases:
   977	            metadata.setdefault("input_aliases", input_aliases)
   978	        schema_source = _schema_source_provenance(schema_provider, class_type)
   979	        if schema_source is not None:
   980	            metadata.setdefault("schema_source", schema_source)
   981	        if class_type == EXEC_CLASS_TYPE:
   982	            _rebuild_exec_reload_metadata(metadata, widgets.get("io"))
   983	        # S4 capability fence: ingest is the external-JSON boundary, so every
   984	        # ingested node is tagged untrusted_source. Unconditional set — never
   985	        # `setdefault` — so a hostile JSON cannot pre-declare itself trusted.
   986	        metadata[PROVENANCE_KEY] = "untrusted_source"
   987	        workflow.nodes[str(node_id)] = VibeNode(
   988	            id=str(node_id),
   989	            class_type=class_type,
   990	            inputs=inputs,
   991	            widgets=widgets,
   992	            metadata=metadata,
   993	            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
   994	            raw_widgets=raw_widgets,
   995	            mode=_node_mode_from_metadata(metadata),
   996	            pos=_geometry_pair(_ui_node.get("pos")) if isinstance(_ui_raw, dict) else None,
   997	            size=_geometry_pair(_ui_node.get("size")) if isinstance(_ui_raw, dict) else None,
   998	        )
   999	        _register_common_inputs(workflow, str(node_id), workflow.nodes[str(node_id)])
  1000	        if workflow.nodes[str(node_id)].class_type in OUTPUT_NODE_NAMES:
  1001	            workflow.outputs.append(VibeOutput(node_id=str(node_id), output_type=workflow.nodes[str(node_id)].class_type))
  1002	    workflow.outputs.sort(key=lambda o: (int(o.node_id) if o.node_id.isdigit() else (1 << 30), o.node_id))
  1003	
  1004	    for node_id, node in api_workflow.items():
  1005	        if not isinstance(node, dict):
  1006	            continue
  1007	        input_provenance = node.get("_input_provenance")
  1008	        if not isinstance(input_provenance, dict):
  1009	            input_provenance = {}
  1010	        for name, value in dict(node.get("inputs", {})).items():
  1011	            if input_provenance.get(name) != "widget" and is_canonical_api_link(value):
  1012	                workflow.edges.append(VibeEdge(str(value[0]), str(value[1]), str(node_id), name))
  1013	
  1014	    workflow.requirements = _infer_requirements(workflow)
  1015	
  1016	    # Stash an ingest-time snapshot immediately after uid minting and edge setup.
  1017	    # Captured once here so downstream delta computation can detect edits.
  1018	    from vibecomfy.ingest.snapshot import capture_ingest_snapshot  # local to avoid circular at module level
  1019	    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(api_workflow, workflow)
  1020	
  1021	    # ``workflow.metadata`` is ``dict[str, Any]`` and transparently accepts
  1022	    # any extra keys.  In particular, ``summary`` (a ``WorkflowSummary`` dict)
  1023	    # may be present when re-ingesting a corpus JSON that was enriched with
  1024	    # LLM-generated summaries.  It is left untouched here — no validation,
  1025	    # no stripping — so it survives round-trips through this pipeline intact.

exec
/bin/zsh -lc "rg -n -U \"metadata(?:\\.get|\\[).*?_ui.*?(?:pos|size)|\\['_ui'\\].*?\\[(?:'|\\\")?(?:pos|size)|\\[\\\"_ui\\\"\\].*?\\[(?:'|\\\")?(?:pos|size)|_ui(?:\\.get|\\[).*?(?:pos|size)\" vibecomfy scripts tests -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "git diff --check 5795812e..2ddd1f06; git show --check --oneline --no-renames 2ddd1f06 --format='%h %s' | sed -n '1,80p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 71ms:
tests/test_porting_normalize_ingest.py:323:        assert _ui["pos"] == expected["pos"], (
tests/test_porting_normalize_ingest.py:324:            f"node {nid} pos mismatch: {_ui['pos']} != {expected['pos']}"
tests/test_porting_normalize_ingest.py:326:        assert _ui["size"] == expected["size"], (
tests/test_porting_normalize_ingest.py:327:            f"node {nid} size mismatch: {_ui['size']} != {expected['size']}"
tests/test_porting_ui_emitter.py:2575:    n.metadata["_ui"] = {"pos": [0.0, 0.0], "size": [200.0, 100.0], "flags": {}, "mode": 0}
tests/test_porting_ui_emitter.py:2657:    wf.nodes["10"].metadata["_ui"] = {"pos": list(set_pos), "size": [30, 30]}
tests/test_porting_ui_emitter.py:2660:    wf.nodes["11"].metadata["_ui"] = {"pos": list(get_pos), "size": [30, 30]}
tests/test_porting_ui_emitter.py:2664:    wf.nodes["12"].metadata["_ui"] = {"pos": list(orphan_pos), "size": [30, 30]}
tests/test_porting_ui_emitter.py:2668:    wf.nodes["20"].metadata["_ui"] = {"pos": list(reroute_pos), "size": [20, 20]}
tests/test_position_fidelity.py:776:    rn1.metadata["_ui"] = {"id": int(rn1.id), "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}
tests/test_position_fidelity.py:782:    rn2.metadata["_ui"] = {"id": int(rn2.id), "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}
tests/test_reconcile.py:1137:        node_x = node.metadata["_ui"]["pos"][0]
tests/test_reconcile.py:1203:        node_x = node.metadata["_ui"]["pos"][0]
tests/intent/test_static_lowering.py:1115:        md["_ui"]["size"] = list(size)

 succeeded in 108ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
2ddd1f06 megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved


exec
/bin/zsh -lc "rg -n \"_ui.*(pos|size)|(pos|size).*_ui\" vibecomfy -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
exec
/bin/zsh -lc "rg -n \"metadata\\s*\\[\\s*['\\\"]_ui['\\\"]\\s*\\]|metadata\\.get\\(\\s*['\\\"]_ui['\\\"]|\\.get\\(\\s*['\\\"]pos['\\\"]|\\.get\\(\\s*['\\\"]size['\\\"]\" vibecomfy -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/porting/widgets/compact_resolver.py:123:    ui_names = _ui_widget_names(metadata.get("_ui"))
vibecomfy/porting/widgets/compact_resolver.py:321:        ui = metadata.get("_ui")
vibecomfy/porting/widgets/compact_resolver.py:381:    ui = metadata.get("_ui")
vibecomfy/porting/layout_store.py:102:    size = ui.get("size")
vibecomfy/porting/layout_store.py:161:            if node.get("pos") is None:
vibecomfy/porting/layout_store.py:188:        ui = node.metadata.get("_ui")
vibecomfy/porting/layout_store.py:280:            pos = node.get("pos")
vibecomfy/porting/layout_store.py:281:            size = node.get("size")
vibecomfy/demo_factory/creative.py:82:            "pos": node.get("pos"),
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:195:        result_nodes.append({"uid": node_identity_v1(node), "pos": list(node["pos"][:2]) if isinstance(node.get("pos"), list) else None, "size": list(node["size"][:2]) if isinstance(node.get("size"), list) else None})
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:416:            "pos": _legacy_layout_vector(node.get("pos"), 2),
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:417:            "size": _legacy_layout_vector(node.get("size"), 2),
vibecomfy/porting/layout/reconcile.py:470:        raw = entry.get("pos", [0.0, 0.0])
vibecomfy/porting/layout/reconcile.py:504:    ui = node.metadata.get("_ui", {}) if hasattr(node, "metadata") else {}
vibecomfy/porting/layout/reconcile.py:691:            fresh_uid = mint_local_uid(node.metadata.get("_ui"), node_id)
vibecomfy/porting/layout/reconcile.py:749:                    fresh_uid = mint_local_uid(node.metadata.get("_ui"), node_id)
vibecomfy/porting/layout/engine.py:281:            pos = entry.get("pos", [0.0, 0.0])
vibecomfy/porting/layout/engine.py:282:            sz = entry.get("size", [float(_DEFAULT_NODE_WIDTH), 30.0])
vibecomfy/porting/layout/groups.py:185:            pos = pos_entry.get("pos")
vibecomfy/workflow.py:1292:    ``metadata["_ui"]["mode"]``; it is consulted only when the field is unset
vibecomfy/workflow.py:1299:    ui = node.metadata.get("_ui")
vibecomfy/porting/layout/felt.py:152:        raw_pos = entry.get("pos") or [0.0, 0.0]
vibecomfy/porting/layout/felt.py:153:        raw_size = entry.get("size") or [0.0, 0.0]
vibecomfy/porting/layout/layout_vector.py:58:        raw_pos = node.get("pos", [0, 0])
vibecomfy/porting/layout/layout_vector.py:59:        raw_size = node.get("size", [0, 0])
vibecomfy/porting/emit/ui.py:237:    pos = layout_entry.get("pos")
vibecomfy/porting/emit/ui.py:238:    size = layout_entry.get("size")
vibecomfy/porting/emit/ui.py:259:    2. ``node.metadata['_ui']`` for those same fields when no sidecar exists.
vibecomfy/porting/emit/ui.py:277:        # Source 2: node.metadata['_ui'] (direct-ingest fallback)
vibecomfy/porting/emit/ui.py:1103:    raw_ui = metadata.get("_ui")
vibecomfy/ingest/normalize.py:269:        raw_ui = metadata.get("_ui") if isinstance(metadata, dict) else rich_node.get("_ui")
vibecomfy/ingest/normalize.py:346:                    "pos": matched.get("pos"),
vibecomfy/ingest/normalize.py:347:                    "size": matched.get("size"),
vibecomfy/ingest/normalize.py:370:                    "pos": raw_node.get("pos"),
vibecomfy/ingest/normalize.py:371:                    "size": raw_node.get("size"),
vibecomfy/ingest/normalize.py:424:    ui = metadata.get("_ui")
vibecomfy/ingest/normalize.py:463:    ui = metadata.get("_ui")
vibecomfy/ingest/normalize.py:958:        _ui_raw = metadata.get("_ui")
vibecomfy/ingest/normalize.py:964:            metadata["_ui"] = _ui_node
vibecomfy/ingest/normalize.py:993:            uid=make_uid("", mint_local_uid(metadata.get("_ui"), str(node_id))),
vibecomfy/ingest/normalize.py:996:            pos=_geometry_pair(_ui_node.get("pos")) if isinstance(_ui_raw, dict) else None,
vibecomfy/ingest/normalize.py:997:            size=_geometry_pair(_ui_node.get("size")) if isinstance(_ui_raw, dict) else None,
vibecomfy/ingest/normalize.py:1047:    ui = metadata.get("_ui")
vibecomfy/ingest/normalize.py:1050:        metadata["_ui"] = ui
vibecomfy/porting/emit/emit_subgraph.py:301:        output_names = _ui_output_names(metadata.get("_ui"))
vibecomfy/porting/emit/emit_subgraph.py:310:            uid=make_uid(subgraph_id, mint_local_uid(metadata.get("_ui"), str(node_id))),
vibecomfy/porting/reorganise/graph_facts.py:485:                pos=node.get("pos"),
vibecomfy/porting/reorganise/graph_facts.py:486:                size=node.get("size"),
vibecomfy/porting/reorganise/graph_facts.py:700:                if isinstance(node, Mapping) and node.get("pos") is not None
vibecomfy/contracts/intent_nodes.py:367:    ui = metadata.get("_ui")
vibecomfy/porting/reorganise/compile.py:5807:        _sequence_delta(current.get("pos"), compiled.get("pos")),
vibecomfy/porting/reorganise/compile.py:5808:        _sequence_delta(current.get("size"), compiled.get("size")),
vibecomfy/porting/edit/apply_field_aliases.py:459:    pos = node.get("pos")
vibecomfy/porting/reorganise/visualize.py:127:    pos = node.get("pos")
vibecomfy/porting/reorganise/visualize.py:128:    size = node.get("size")
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:156:    if "pos" in raw and raw.get("pos") is not None:
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:157:        result["pos"] = _geo_vector(raw.get("pos"), 2, "pos")
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:158:    if "size" in raw and raw.get("size") is not None:
vibecomfy/comfy_nodes/agent/mutation_materialization_v1.py:159:        result["size"] = _geo_vector(raw.get("size"), 2, "size")
vibecomfy/executor/graph_inspection.py:308:        raw_ui = metadata.get("_ui")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:149:        pos = _geometry_vector(raw.get("pos"), 2, "pos")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:151:        if "size" in raw and raw.get("size") is not None:
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:152:            normalized["size"] = _geometry_vector(raw.get("size"), 2, "size")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:399:        pos = node.get("pos")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:400:        size = node.get("size")
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:405:        prev_pos = prev.get("pos") if prev is not None else None
vibecomfy/comfy_nodes/agent/layout_operation_v1.py:406:        prev_size = prev.get("size") if prev is not None else None
vibecomfy/porting/edit/apply_place.py:295:    pos = node.get("pos")
vibecomfy/porting/edit/apply_place.py:296:    size = node.get("size")
vibecomfy/porting/edit/_describe.py:65:        pos_raw = node.get("pos")
vibecomfy/porting/edit/_describe.py:73:        size_raw = node.get("size")
vibecomfy/porting/edit/apply_mutate.py:307:                "pos": list(node.get("pos") or []),

 succeeded in 0ms:
vibecomfy/intent/metric.py:83:        text_v: JudgeVerdict = judge_text_fn(fx.pre_ui, fx.post_ui, fx.nl_intent)
vibecomfy/intent/_fixture.py:21:    post_ui: Any
vibecomfy/intent/_fixture.py:33:    workflow to produce ``post_ui``.
vibecomfy/intent/_fixture.py:40:    post_ui = copy.deepcopy(pre_ui)
vibecomfy/intent/_fixture.py:45:        _apply_op(post_ui, op)
vibecomfy/intent/_fixture.py:56:        post_ui=post_ui,
vibecomfy/commands/port/_export.py:551:            # correct positions in properties['vibecomfy_uid']).  Do NOT call
vibecomfy/porting/layout/engine.py:94:        ``{new_uid: anchor_uid, ...}`` — new nodes whose positions are resolved
vibecomfy/porting/layout/engine.py:298:            sz = sizes.get(new_uid, (_DEFAULT_NODE_WIDTH, 30))
vibecomfy/porting/layout/engine.py:307:            positions[new_uid] = {
vibecomfy/ingest/normalize.py:303:    """Merge slim _ui {id, pos, size, properties} from raw litegraph nodes onto converted API nodes.
vibecomfy/ingest/normalize.py:305:    Called after convert_ui_to_api so pos/properties survive on the comfy-converter path.
vibecomfy/ingest/normalize.py:996:            pos=_geometry_pair(_ui_node.get("pos")) if isinstance(_ui_raw, dict) else None,
vibecomfy/ingest/normalize.py:997:            size=_geometry_pair(_ui_node.get("size")) if isinstance(_ui_raw, dict) else None,
vibecomfy/comfy_nodes/agent/projection_registry_v1.py:55:    "node.vibecomfy_uid": "derived_native", "node.id": "derived_native", "node.type": "execution_semantic", "node.mode": "native_defaulted", "node.fields": "execution_semantic", "node.widgets_values": "execution_semantic", "node.inputs": "derived_native", "node.outputs": "derived_native", "node.properties": "derived_native", "node.flags": "derived_native", "node.order": "derived_native", "node.showAdvanced": "derived_native", "node.pos": "layout_semantic", "node.size": "layout_semantic", "node.title": "layout_semantic", "node.color": "layout_semantic", "node.bgcolor": "layout_semantic", "node.boxcolor": "layout_semantic", "node.shape": "layout_semantic", "node.extensions": "opaque_extension",
vibecomfy/porting/emit/emit_subgraph.py:85:    "_positional_ui_widget_names",
vibecomfy/porting/emit/emit_subgraph.py:839:def _positional_ui_widget_names(ui_node: Mapping[str, Any], value_count: int) -> list[str | None]:
vibecomfy/porting/emit/emit_subgraph.py:930:    for index, name in enumerate(_positional_ui_widget_names(ui_node, len(raw_values))):
vibecomfy/porting/emit/ui.py:36:ComfyUI's ``convert_ui_to_api`` reads ``widgets_values`` *positionally* against the

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/layout/reconcile.py | sed -n '260,310p'; nl -ba vibecomfy/porting/layout/reconcile.py | sed -n '485,520p'; nl -ba vibecomfy/porting/layout_store.py | sed -n '150,210p'; nl -ba vibecomfy/porting/lowering.py | sed -n '325,395p'; nl -ba vibecomfy/porting/convert.py | sed -n '160,205p'; nl -ba vibecomfy/porting/emit/ui.py | sed -n '295,345p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
   260	        (name, inp.field)
   261	        for name, inp in wf.inputs.items()
   262	        if inp.node_id == node_id
   263	    )
   264	
   265	    canonical = repr((
   266	        node.class_type,
   267	        tuple(incoming),
   268	        tuple(scalar_values),
   269	        tuple(public_bindings),
   270	    ))
   271	    h = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
   272	    cache[node_id] = h
   273	    return h
   274	
   275	
   276	# ---------------------------------------------------------------------------
   277	# Stage 3 helpers: bipartite assignment for multi-candidate hash groups
   278	# ---------------------------------------------------------------------------
   279	
   280	
   281	def _pos_from_node(node: Any) -> tuple[float, float]:
   282	    """Extract first-class ``(x, y)`` from a node, falling back to ``(0, 0)``."""
   283	    pos = getattr(node, "pos", None)
   284	    try:
   285	        return (float(pos[0]), float(pos[1]))
   286	    except (TypeError, IndexError, ValueError):
   287	        return (0.0, 0.0)
   288	
   289	
   290	def _euclidean(p1: tuple[float, float], p2: tuple[float, float]) -> float:
   291	    dx = p1[0] - p2[0]
   292	    dy = p1[1] - p2[1]
   293	    return (dx * dx + dy * dy) ** 0.5
   294	
   295	
   296	# Maximum safe size for exact exhaustive assignment and the corresponding
   297	# permutation budget (8! = 40320).  Above these thresholds a deterministic
   298	# greedy nearest-neighbour fallback is used to keep reconcile fast and
   299	# predictable on large hash-collision groups.
   300	_SAFE_K = 8
   301	_SAFE_PERM_BUDGET = 40320  # math.perm(8, 8)
   302	
   303	
   304	def _permutation_count(n: int, m: int) -> int:
   305	    """Return the number of permutations for the n×m assignment problem.
   306	
   307	    When *n* ≤ *m* this is P(m, n); otherwise P(n, m).  Returns 1 when the
   308	    smaller dimension is 0 (no assignment to make).
   309	    """
   310	    k = min(n, m)
   485	
   486	
   487	# ---------------------------------------------------------------------------
   488	# Stage 4 helpers: subgraph inner-node preserve (content-hash keying)
   489	# ---------------------------------------------------------------------------
   490	
   491	
   492	def _is_subgraph_type(class_type: str) -> bool:
   493	    """Return True if *class_type* is a UUID subgraph container node."""
   494	    return bool(_UUID_RE.match(class_type))
   495	
   496	
   497	def _subgraph_content_hash(node: Any) -> str:
   498	    """Return a short content hash for a subgraph container node.
   499	
   500	    Derived from the node's visible definition: class_type, sorted input
   501	    names/types (from ``_ui.inputs``), and the ``ver`` property.  Position
   502	    and size are excluded so the hash is layout-invariant.
   503	    """
   504	    ui = node.metadata.get("_ui", {}) if hasattr(node, "metadata") else {}
   505	    ui = ui if isinstance(ui, dict) else {}
   506	    props = ui.get("properties", {}) or {}
   507	    ver = props.get("ver", "") if isinstance(props, dict) else ""
   508	    raw_inputs = ui.get("inputs") or []
   509	    inputs_schema: list[tuple[str, str]] = sorted(
   510	        (str(inp.get("name", "")), str(inp.get("type", "")))
   511	        for inp in raw_inputs
   512	        if isinstance(inp, dict)
   513	    )
   514	    canonical = repr((node.class_type, tuple(inputs_schema), ver))
   515	    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
   516	
   517	
   518	def nearest_wired_neighbor_uid(
   519	    new_node_id: str,
   520	    wf: "VibeWorkflow",
   150	    the scope_path is the full chain of sg_keys (SD1). A raw litegraph inner node
   151	    already exposes the same pos/size/flags/color/bgcolor/properties keys that
   152	    ``_build_entry`` reads.
   153	    """
   154	    entries: dict[str, dict] = {}
   155	    for sg_def in _iter_subgraph_defs(definitions):
   156	        chain = (*scope_chain, sg_key(sg_def))
   157	        scope_path = compose_scope_path(chain)
   158	        for node in sg_def.get("nodes") or []:
   159	            if not isinstance(node, dict):
   160	                continue
   161	            if node.get("pos") is None:
   162	                continue
   163	            local_uid = mint_local_uid(node, str(node.get("id")))
   164	            uid = make_uid(scope_path, local_uid)
   165	            entries[uid] = _build_entry(node)
   166	        nested = sg_def.get("definitions")
   167	        if nested:
   168	            entries.update(_assemble_definition_entries(nested, chain))
   169	    return entries
   170	
   171	
   172	def write_layout(py_path: Path, wf: VibeWorkflow) -> Path:
   173	    """Serialize the full M2 layout envelope for ``wf`` to the sidecar file.
   174	
   175	    Per-uid node geometry is captured from first-class ``pos``/``size`` fields.
   176	    Nodes with an empty uid or no first-class ``pos`` are skipped (M1.5 behavior).
   177	    Groups are serialized from the first-class ``wf.groups`` field.  Other
   178	    graph-level sections are read from ``wf.metadata`` when present and
   179	    otherwise serialized as empty/absent. Returns the sidecar path written.
   180	    """
   181	    entries: dict[str, dict] = {}
   182	    for node in wf.nodes.values():
   183	        uid = node.uid
   184	        if not uid:
   185	            continue
   186	        if node.pos is None:
   187	            continue
   188	        ui = node.metadata.get("_ui")
   189	        furniture = ui if isinstance(ui, dict) else {}
   190	        entries[uid] = _build_entry({**furniture, "pos": node.pos, "size": node.size})
   191	
   192	    meta = getattr(wf, "metadata", {}) or {}
   193	    layout_meta = meta.get("_layout") if isinstance(meta.get("_layout"), dict) else {}
   194	
   195	    # Subgraph-inner nodes: mint scoped uids over the captured definitions
   196	    # skeleton (T10 furniture) and add their geometry entries keyed by uid (SD1).
   197	    definitions = meta.get("definitions")
   198	    if definitions:
   199	        entries.update(_assemble_definition_entries(definitions, ()))
   200	
   201	    def _section(key: str, default: Any) -> Any:
   202	        # Prefer an explicit _layout section, then a top-level metadata key.
   203	        if key in layout_meta:
   204	            return layout_meta[key]
   205	        if key in meta:
   206	            return meta[key]
   207	        return default
   208	
   209	    extra = _section("extra", None)
   210	    if not isinstance(extra, dict):
   325	    workflow: "VibeWorkflow",
   326	    source_node: "VibeNode",
   327	    *,
   328	    loop_node_id: str,
   329	    loop_uid: str | None,
   330	    iteration_index: int,
   331	    clone_role: str,
   332	    variable: str,
   333	    iteration_value: Any,
   334	    original_intent_hash: str,
   335	) -> "VibeNode":
   336	    new_id = workflow._next_node_id()
   337	    source_uid = source_node.uid or source_node.id
   338	    clone_uid = _clone_uid(loop_uid, source_uid, iteration_index)
   339	    cloned_metadata = copy.deepcopy(source_node.metadata)
   340	    cloned_metadata["vibecomfy.lowering"] = {
   341	        "loop_node_id": loop_node_id,
   342	        "loop_uid": loop_uid or loop_node_id,
   343	        "source_node_id": source_node.id,
   344	        "source_uid": source_uid,
   345	        "iteration_index": iteration_index,
   346	        "clone_role": clone_role,
   347	        "variable": variable,
   348	        "iteration_value": iteration_value,
   349	        "original_intent_hash": original_intent_hash,
   350	    }
   351	
   352	    # --- Deterministic clone layout positioning ---
   353	    # Read first-class source geometry; a geometry-less source uses the existing
   354	    # deterministic clone-layout origin.
   355	    source_pos = source_node.pos if source_node.pos is not None else [0, 0]
   356	    try:
   357	        source_x = float(source_pos[0])
   358	        source_y = float(source_pos[1])
   359	    except (TypeError, IndexError, ValueError):
   360	        source_x, source_y = 0.0, 0.0
   361	    # Compute clone position: horizontal stride per iteration, same y.
   362	    clone_pos = [source_x + HORIZONTAL_STRIDE * iteration_index, source_y]
   363	    snapped_pos = snap_pos(clone_pos)
   364	    # --- End layout positioning ---
   365	
   366	    cloned = source_node.__class__(
   367	        id=new_id,
   368	        class_type=source_node.class_type,
   369	        pack=source_node.pack,
   370	        inputs=copy.deepcopy(source_node.inputs),
   371	        widgets=copy.deepcopy(source_node.widgets),
   372	        metadata=cloned_metadata,
   373	        uid=clone_uid,
   374	        raw_widgets=copy.deepcopy(source_node.raw_widgets),
   375	        mode=source_node.mode,
   376	        pos=snapped_pos,
   377	        size=copy.deepcopy(source_node.size),
   378	    )
   379	    workflow.nodes[new_id] = cloned
   380	    return cloned
   381	
   382	
   383	def _matches_variable_target(variable: str, field: str) -> bool:
   384	    if variable == "seed":
   385	        return field in SEED_FIELDS
   386	    return field in TEXT_FIELDS
   387	
   388	
   389	def _collect_loop_target_fields(
   390	    workflow: "VibeWorkflow",
   391	    plan: LoopLoweringPlan,
   392	) -> tuple[tuple[LoopTargetField, ...] | None, list[LoweringDiagnostic]]:
   393	    diagnostics: list[LoweringDiagnostic] = []
   394	    target_fields: list[LoopTargetField] = []
   395	    for edge in sorted(
   160	# helper, not a wire, so it is intentionally excluded here.
   161	_VIRTUAL_WIRE_CLASS_TYPES: frozenset[str] = frozenset({"SetNode", "GetNode", "Reroute"})
   162	
   163	
   164	def _capture_virtual_wires(workflow: VibeWorkflow) -> dict[str, dict[str, Any]]:
   165	    """Snapshot Get/Set/Reroute virtual-wire nodes BEFORE helper resolution.
   166	
   167	    Captures uid, type, channel name, pos/size, and the routed endpoints for each
   168	    virtual-wire node, keyed by uid. This must run before both
   169	    ``resolve_subgraph_helpers`` and ``resolve_helpers`` (which delete these nodes
   170	    in place). Returns ``{}`` when the graph has no virtual-wire nodes.
   171	    """
   172	    from vibecomfy._compile._helpers import (
   173	        BROADCAST_HELPER_CLASS_TYPES,
   174	        broadcast_name,
   175	    )
   176	
   177	    captured: dict[str, dict[str, Any]] = {}
   178	    for node_id, node in workflow.nodes.items():
   179	        if node.class_type not in _VIRTUAL_WIRE_CLASS_TYPES:
   180	            continue
   181	        uid = node.uid or str(node_id)
   182	        pos = copy.deepcopy(node.pos)
   183	        size = copy.deepcopy(node.size)
   184	        channel = (
   185	            broadcast_name(node)
   186	            if node.class_type in BROADCAST_HELPER_CLASS_TYPES
   187	            else None
   188	        )
   189	        endpoints = [
   190	            [edge.from_node, edge.from_output, edge.to_node, edge.to_input]
   191	            for edge in workflow.edges
   192	            if str(edge.from_node) == str(node_id) or str(edge.to_node) == str(node_id)
   193	        ]
   194	        captured[uid] = {
   195	            "type": node.class_type,
   196	            "channel": channel,
   197	            "pos": pos,
   198	            "size": size,
   199	            "endpoints": endpoints,
   200	        }
   201	    return captured
   202	
   203	
   204	def _node_object_info_identities(raw_workflow: dict[str, Any]) -> dict[str, ObjectInfoIdentity]:
   205	    """Derive a node_id -> ObjectInfoIdentity map from raw workflow provenance."""
   295	    if not isinstance(properties, dict):
   296	        properties = {}
   297	    # title stays None for absent/default — the caller decides whether to emit it
   298	
   299	    return {
   300	        "flags": flags,
   301	        "color": color,
   302	        "bgcolor": bgcolor,
   303	        "mode": _get_node_mode(node),
   304	        "properties": properties,
   305	        "title": title,
   306	    }
   307	
   308	
   309	def _captured_geometry(node: Any) -> dict[str, list[float]] | None:
   310	    """Return first-class ``{pos, size}``, or ``None`` when either is absent.
   311	
   312	    The ``None`` fallthrough is intentional: callers should chain through to
   313	    ``_stub_layout`` when no captured geometry exists (e.g. programmatic nodes
   314	    or workflows loaded from a .py file without a sidecar).
   315	    """
   316	    pos = getattr(node, "pos", None)
   317	    size = getattr(node, "size", None)
   318	    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
   319	        return None
   320	    if not isinstance(size, (list, tuple)) or len(size) < 2:
   321	        return None
   322	    return {
   323	        "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
   324	        "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
   325	    }
   326	
   327	
   328	def _envelope_id(wf: Any) -> str:
   329	    """Deterministic envelope id derived from the workflow id."""
   330	    return str(uuid.uuid5(_ENVELOPE_ID_NAMESPACE, str(getattr(wf, "id", "workflow"))))
   331	
   332	
   333	def _source_template_name(wf: Any) -> str | None:
   334	    """Best-effort source-template name for the breadcrumb / output path.
   335	
   336	    Prefers an explicit source id, then the source file stem.  The ingest default
   337	    id ``"workflow"`` (and an empty value) is treated as *unnamed* so the IR-hash
   338	    fallback path takes over.  Returns ``None`` when no real name is available.
   339	    """
   340	    source = getattr(wf, "source", None)
   341	    candidate = getattr(source, "id", None) if source is not None else None
   342	    if isinstance(candidate, str) and candidate and candidate != "workflow":
   343	        return candidate
   344	    path = getattr(source, "path", None) if source is not None else None
   345	    if isinstance(path, str) and path:

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/emit/ui.py | sed -n '215,292p'; nl -ba vibecomfy/porting/emit/ui.py | sed -n '1080,1125p'; nl -ba vibecomfy/workflow.py | sed -n '1270,1320p'; nl -ba vibecomfy/ingest/normalize.py | sed -n '240,390p'; nl -ba vibecomfy/ingest/normalize.py | sed -n '1028,1060p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
   215	    """
   216	    col = order % _STUB_COLUMNS
   217	    row = order // _STUB_COLUMNS
   218	    return {
   219	        "pos": [
   220	            _canonicalize_coord(float(col * _STUB_COLUMN_WIDTH)),
   221	            _canonicalize_coord(float(row * _STUB_ROW_HEIGHT)),
   222	        ],
   223	        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
   224	    }
   225	
   226	
   227	def _extract_geometry(layout_entry: dict | None) -> dict[str, list[float]] | None:
   228	    """Extract {pos, size} from a layout-store entry, or None.
   229	
   230	    This isolates the pos/size geometry chain from the furniture resolver so the
   231	    two paths never accidentally couple.  A layout entry that is ``None`` or
   232	    lacks a valid ``pos`` returns ``None``, letting the caller fall through to
   233	    ``_captured_geometry`` or ``_stub_layout``.
   234	    """
   235	    if not isinstance(layout_entry, dict):
   236	        return None
   237	    pos = layout_entry.get("pos")
   238	    size = layout_entry.get("size")
   239	    if not isinstance(pos, (list, tuple)) or len(pos) < 2:
   240	        return None
   241	    if not isinstance(size, (list, tuple)) or len(size) < 2:
   242	        return None
   243	    return {
   244	        "pos": [_canonicalize_coord(float(pos[0])), _canonicalize_coord(float(pos[1]))],
   245	        "size": [_canonicalize_coord(float(size[0])), _canonicalize_coord(float(size[1]))],
   246	    }
   247	
   248	
   249	def _resolve_furniture(
   250	    node: Any,
   251	    layout_entry: dict | None,
   252	) -> dict[str, Any]:
   253	    """Resolve display furniture while taking mode only from the IR node.
   254	
   255	    This is a SEPARATE path from the pos/size geometry chain
   256	    (:func:`_captured_geometry`).  Precedence:
   257	
   258	    1. Sidecar entry (``layout_entry``) for flags, colors, properties, and title.
   259	    2. ``node.metadata['_ui']`` for those same fields when no sidecar exists.
   260	    3. :func:`vibecomfy.workflow._get_node_mode` for mode.  This is the exact
   261	       authority used by compilation, including its single legacy ``_ui.mode``
   262	       fallback.
   263	    4. Fixed defaults (``flags={}``, ``color=None``, ``bgcolor=None``,
   264	       ``properties={}``, ``title=None``).
   265	
   266	    Returns a dict with keys ``flags``, ``color``, ``bgcolor``, ``mode``,
   267	    ``properties``, ``title``.
   268	    """
   269	    # Source 1: sidecar entry (authoritative)
   270	    if layout_entry:
   271	        flags = layout_entry.get("flags")
   272	        color = layout_entry.get("color")
   273	        bgcolor = layout_entry.get("bgcolor")
   274	        properties = layout_entry.get("properties")
   275	        title = layout_entry.get("title")
   276	    else:
   277	        # Source 2: node.metadata['_ui'] (direct-ingest fallback)
   278	        _ui = getattr(node, "metadata", {}).get("_ui")
   279	        if isinstance(_ui, dict):
   280	            flags = _ui.get("flags")
   281	            color = _ui.get("color")
   282	            bgcolor = _ui.get("bgcolor")
   283	            properties = _ui.get("properties")
   284	            title = _ui.get("title")
   285	        else:
   286	            flags = None
   287	            color = None
   288	            bgcolor = None
   289	            properties = None
   290	            title = None
   291	
   292	    # Source 3: fixed defaults
  1080	            values.append(_CONTROL_AFTER_GENERATE_DEFAULT)
  1081	        else:
  1082	            values.append(None)
  1083	
  1084	    while values and values[-1] is None:
  1085	        values.pop()
  1086	    return values
  1087	
  1088	
  1089	def _preserve_observed_widget_carriers(
  1090	    node: Any,
  1091	    *,
  1092	    raw_widgets: list[Any],
  1093	) -> bool:
  1094	    if raw_widgets:
  1095	        return True
  1096	    raw_widget_payload = getattr(node, "raw_widgets", None)
  1097	    raw_widget_values = getattr(raw_widget_payload, "values", None)
  1098	    if isinstance(raw_widget_values, list) and raw_widget_values:
  1099	        return True
  1100	    metadata = getattr(node, "metadata", {})
  1101	    if not isinstance(metadata, Mapping):
  1102	        return False
  1103	    raw_ui = metadata.get("_ui")
  1104	    if isinstance(raw_ui, Mapping) and isinstance(raw_ui.get("widgets_values"), list):
  1105	        return True
  1106	    return bool(metadata.get("provenance"))
  1107	
  1108	
  1109	def _schema_outputs_for_unwired_node(schema: Any | None) -> list[dict[str, Any]]:
  1110	    schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []
  1111	    return [
  1112	        {
  1113	            "name": out_spec.name or f"output_{slot_idx}",
  1114	            "type": out_spec.type or "",
  1115	            "links": None,
  1116	            "slot_index": slot_idx,
  1117	        }
  1118	        for slot_idx, out_spec in enumerate(schema_outputs)
  1119	    ]
  1120	
  1121	
  1122	def _exec_node_field(node: Any, key: str) -> Any:
  1123	    """Return a vibecomfy.exec field from widgets first, then inputs."""
  1124	    node_widgets = getattr(node, "widgets", None)
  1125	    if isinstance(node_widgets, Mapping) and key in node_widgets:
  1270	        **runtime_result.normalized.as_dict(),
  1271	        "vibecomfy_uid": node.uid or intent_result.vibecomfy_uid,
  1272	        "kind": payload.get("kind"),
  1273	        "io": payload.get("io"),
  1274	    }
  1275	    source = intent.get("source")
  1276	    spec = intent.get("spec")
  1277	    if isinstance(source, str):
  1278	        compiled["source"] = source
  1279	    if isinstance(spec, str):
  1280	        compiled["spec"] = spec
  1281	    return compiled
  1282	
  1283	
  1284	_MODE_MUTED: int = 2   # ComfyUI node.mode == 2 → muted (never executes)
  1285	_MODE_BYPASS: int = 4  # ComfyUI node.mode == 4 → bypassed (dropped; edges rewired)
  1286	
  1287	
  1288	def _get_node_mode(node: VibeNode) -> int:
  1289	    """Read the litegraph mode (0/2/4); ``node.mode`` is the authority.
  1290	
  1291	    Legacy fallback: hand-built nodes that predate the field signal mode via
  1292	    ``metadata["_ui"]["mode"]``; it is consulted only when the field is unset
  1293	    (0).  Ingest and envelope decode always populate the field, so production
  1294	    graphs read the field.
  1295	    """
  1296	    mode = node.mode
  1297	    if isinstance(mode, int) and mode:
  1298	        return mode
  1299	    ui = node.metadata.get("_ui")
  1300	    if not isinstance(ui, dict):
  1301	        return 0
  1302	    legacy = ui.get("mode", 0)
  1303	    return legacy if isinstance(legacy, int) else 0
  1304	
  1305	
  1306	def _compute_dropped_bypassed_ids(
  1307	    nodes: dict[str, VibeNode],
  1308	) -> tuple[frozenset[str], frozenset[str]]:
  1309	    """Return (dropped_ids, bypassed_ids) for compile(api) mode filtering.
  1310	
  1311	    dropped_ids: node ids with mode 2 (muted) or mode 4 (bypassed) — excluded from output.
  1312	    bypassed_ids: subset of dropped_ids with mode 4 — edges are rewired around them.
  1313	    """
  1314	    dropped: set[str] = set()
  1315	    bypassed: set[str] = set()
  1316	    for node_id, node in nodes.items():
  1317	        mode = _get_node_mode(node)
  1318	        if mode in (_MODE_MUTED, _MODE_BYPASS):
  1319	            dropped.add(str(node_id))
  1320	        if mode == _MODE_BYPASS:
   240	        "values": deepcopy(values),
   241	        "shape": shape,
   242	        "source": source,
   243	        "has_dict_rows": has_dict_rows,
   244	        "length": length,
   245	    }
   246	
   247	
   248	def _merge_vibe_node_widget_evidence(raw: dict[str, Any], api: dict[str, Any]) -> None:
   249	    """Carry rich Vibe node widget evidence into the compiled API graph.
   250	
   251	    The rich ``nodes`` map is the sole structural authority of a serialized
   252	    Vibe workflow; the executable API view is derived by compiling the IR
   253	    (``compile("api")``), never read from stored data.  Widget-shape recovery
   254	    needs the observed LiteGraph widget vector from the rich ``nodes`` map.
   255	    """
   256	    nodes = raw.get("nodes")
   257	    if not isinstance(nodes, dict):
   258	        return
   259	    for node_id, rich_node in nodes.items():
   260	        if not isinstance(rich_node, dict):
   261	            continue
   262	        api_node = api.get(str(node_id))
   263	        if not isinstance(api_node, dict):
   264	            continue
   265	        raw_widgets = rich_node.get("raw_widgets") or rich_node.get("_raw_widgets")
   266	        if isinstance(raw_widgets, dict):
   267	            api_node.setdefault("_raw_widgets", deepcopy(raw_widgets))
   268	        metadata = rich_node.get("metadata")
   269	        raw_ui = metadata.get("_ui") if isinstance(metadata, dict) else rich_node.get("_ui")
   270	        if (
   271	            isinstance(raw_widgets, dict)
   272	            and bool(raw_widgets.get("has_dict_rows"))
   273	            and isinstance(raw_ui, dict)
   274	            and "widgets_values" in raw_ui
   275	        ):
   276	            api_node.setdefault("_ui", deepcopy(raw_ui))
   277	        if "_raw_widgets" in api_node:
   278	            continue
   279	        if isinstance(raw_ui, dict) and "widgets_values" in raw_ui:
   280	            api_node["_raw_widgets"] = _raw_widget_payload_dict(
   281	                raw_ui["widgets_values"],
   282	                source="ui.widgets_values",
   283	            )
   284	
   285	
   286	def _coerce_raw_widget_payload(raw: Any) -> RawWidgetPayload | None:
   287	    if isinstance(raw, RawWidgetPayload):
   288	        return raw
   289	    if not isinstance(raw, dict):
   290	        return None
   291	    if not {"values", "shape", "source", "has_dict_rows", "length"} <= set(raw):
   292	        return None
   293	    return RawWidgetPayload(
   294	        values=deepcopy(raw["values"]),
   295	        shape=str(raw["shape"]),
   296	        source=str(raw["source"]),
   297	        has_dict_rows=bool(raw["has_dict_rows"]),
   298	        length=int(raw["length"]),
   299	    )
   300	
   301	
   302	def _merge_slim_ui(raw: dict[str, Any], converted: dict[str, Any]) -> None:
   303	    """Merge slim _ui {id, pos, size, properties} from raw litegraph nodes onto converted API nodes.
   304	
   305	    Called after convert_ui_to_api so pos/properties survive on the comfy-converter path.
   306	    Verifies id preservation: if converted keys diverge from raw node ids, falls back to
   307	    class_type+position matching and emits a warning (correctness-2 gate).
   308	    """
   309	    raw_nodes_by_id: dict[str, dict] = {
   310	        str(node["id"]): node
   311	        for node in raw.get("nodes", [])
   312	        if isinstance(node, dict) and "id" in node
   313	    }
   314	    raw_ids = set(raw_nodes_by_id.keys())
   315	    converted_ids = set(converted.keys())
   316	    ids_diverge = bool(converted_ids - raw_ids)
   317	
   318	    if ids_diverge:
   319	        warnings.warn(
   320	            "convert_ui_to_api produced node ids not present in raw litegraph nodes; "
   321	            "falling back to class_type+order matching for _ui merge (correctness-2).",
   322	            stacklevel=4,
   323	        )
   324	        # Build a lookup by (class_type, order_index) as a best-effort fallback
   325	        raw_by_class_order: dict[tuple[str, int], dict] = {}
   326	        for node in raw.get("nodes", []):
   327	            if not isinstance(node, dict):
   328	                continue
   329	            class_type = str(node.get("type", ""))
   330	            order = int(node.get("order", -1))
   331	            raw_by_class_order[(class_type, order)] = node
   332	
   333	        for node_id, node_data in converted.items():
   334	            if not isinstance(node_data, dict) or "_ui" in node_data:
   335	                continue
   336	            class_type = str(node_data.get("class_type", ""))
   337	            # Try to find a match; use first class_type match as a last resort
   338	            matched = None
   339	            for (ct, _order), raw_node in raw_by_class_order.items():
   340	                if ct == class_type:
   341	                    matched = raw_node
   342	                    break
   343	            if matched is not None:
   344	                slim: dict = {
   345	                    "id": matched.get("id"),
   346	                    "pos": matched.get("pos"),
   347	                    "size": matched.get("size"),
   348	                    "properties": matched.get("properties", {}),
   349	                }
   350	                if "widgets_values" in matched:
   351	                    slim["widgets_values"] = deepcopy(matched["widgets_values"])
   352	                    node_data.setdefault(
   353	                        "_raw_widgets",
   354	                        _raw_widget_payload_dict(matched["widgets_values"], source="ui.widgets_values"),
   355	                    )
   356	                for _f in ("mode", "flags", "color", "bgcolor"):
   357	                    if _f in matched:
   358	                        slim[_f] = matched[_f]
   359	                node_data["_ui"] = slim
   360	            else:
   361	                node_data["_ui"] = {}
   362	    else:
   363	        for node_id, node_data in converted.items():
   364	            if not isinstance(node_data, dict) or "_ui" in node_data:
   365	                continue
   366	            raw_node = raw_nodes_by_id.get(node_id)
   367	            if raw_node is not None:
   368	                slim = {
   369	                    "id": raw_node.get("id"),
   370	                    "pos": raw_node.get("pos"),
   371	                    "size": raw_node.get("size"),
   372	                    "properties": raw_node.get("properties", {}),
   373	                }
   374	                if "widgets_values" in raw_node:
   375	                    slim["widgets_values"] = deepcopy(raw_node["widgets_values"])
   376	                    node_data.setdefault(
   377	                        "_raw_widgets",
   378	                        _raw_widget_payload_dict(raw_node["widgets_values"], source="ui.widgets_values"),
   379	                    )
   380	                for _f in ("mode", "flags", "color", "bgcolor"):
   381	                    if _f in raw_node:
   382	                        slim[_f] = raw_node[_f]
   383	                node_data["_ui"] = slim
   384	            else:
   385	                node_data["_ui"] = {}
   386	
   387	
   388	def _has_unknown_widget_inputs(api: dict[str, Any]) -> bool:
   389	    for node in api.values():
   390	        if not isinstance(node, dict):
  1028	
  1029	def _is_exec_widget_key(class_type: str, key: str) -> bool:
  1030	    return class_type == EXEC_CLASS_TYPE and key in {"source", "io"}
  1031	
  1032	
  1033	def _normalize_exec_io_metadata(io_value: Any) -> dict[str, list[list[str | None]]] | None:
  1034	    from vibecomfy.comfy_nodes.exec_node import ExecNodeContractError, parse_io
  1035	
  1036	    try:
  1037	        io_spec = parse_io(io_value)
  1038	    except ExecNodeContractError:
  1039	        return None
  1040	    normalized: dict[str, list[list[str | None]]] = {"inputs": [], "outputs": []}
  1041	    for field in ("inputs", "outputs"):
  1042	        normalized[field] = [[name, type_name] for name, type_name in io_spec.get(field, ())]
  1043	    return normalized
  1044	
  1045	
  1046	def _rebuild_exec_reload_metadata(metadata: dict[str, Any], io_value: Any) -> None:
  1047	    ui = metadata.get("_ui")
  1048	    if not isinstance(ui, dict):
  1049	        ui = {}
  1050	        metadata["_ui"] = ui
  1051	    properties = ui.get("properties")
  1052	    if not isinstance(properties, dict):
  1053	        properties = {}
  1054	        ui["properties"] = properties
  1055	    vibecomfy = properties.get("vibecomfy")
  1056	    if not isinstance(vibecomfy, dict):
  1057	        vibecomfy = {}
  1058	        properties["vibecomfy"] = vibecomfy
  1059	    normalized_io = _normalize_exec_io_metadata(io_value)
  1060	    if normalized_io is None:

exec
/bin/zsh -lc 'git diff 5795812e..2ddd1f06 -- tests/test_workflow_core.py tests/test_porting_normalize_ingest.py tests/test_layout_store.py tests/intent/test_static_lowering.py tests/test_porting_ui_emitter.py tests/test_position_fidelity.py tests/test_reconcile.py tests/test_porting_synthetic_fixtures.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
diff --git a/tests/intent/test_static_lowering.py b/tests/intent/test_static_lowering.py
index bb17b518..dd7e0530 100644
--- a/tests/intent/test_static_lowering.py
+++ b/tests/intent/test_static_lowering.py
@@ -1109,11 +1109,17 @@ def test_lower_workflow_over_takes_precedence() -> None:
 
 
 def _node_with_ui(node_id: str, class_type: str, *, pos: tuple[float, float], size: tuple[float, float] | None = None, inputs: dict | None = None) -> VibeNode:
-    """Create a node with explicit _ui pos/size metadata."""
+    """Create a node with first-class and retained raw UI geometry."""
     md: dict[str, Any] = {"_ui": {"pos": list(pos)}}
     if size is not None:
         md["_ui"]["size"] = list(size)
-    node = VibeNode(id=node_id, class_type=class_type, metadata=md)
+    node = VibeNode(
+        id=node_id,
+        class_type=class_type,
+        metadata=md,
+        pos=list(pos),
+        size=list(size) if size is not None else None,
+    )
     if inputs is not None:
         node.inputs = dict(inputs)
     return node
@@ -1138,8 +1144,7 @@ def test_clone_nodes_have_horizontal_stride_positions() -> None:
     # Iter 1: x = 100 + 300*1 = 400
     # Iter 2: x = 100 + 300*2 = 700
     for node_id, node in result.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         lowering = node.metadata.get("vibecomfy.lowering", {})
         source_id = lowering.get("source_node_id")
         iter_idx = lowering.get("iteration_index")
@@ -1169,8 +1174,7 @@ def test_clone_positions_are_snapped_to_whole_integers() -> None:
     assert result.workflow is not None
 
     for node_id, node in result.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         if pos is None:
             continue
         assert isinstance(pos[0], int), f"Node {node_id}: pos[0] should be int, got {pos[0]} ({type(pos[0]).__name__})"
@@ -1201,14 +1205,12 @@ def test_clone_positions_deterministic_across_repeated_lowerings() -> None:
     second_positions: dict[str, list[int]] = {}
 
     for node_id, node in first.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         if pos is not None:
             first_positions[node.uid] = list(pos)
 
     for node_id, node in second.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         if pos is not None:
             second_positions[node.uid] = list(pos)
 
@@ -1237,11 +1239,11 @@ def test_clone_layout_policy_descriptor_in_evidence() -> None:
     assert f"offset={HORIZONTAL_STRIDE}" in result.evidence[0].layout_policy
 
 
-def test_clone_positions_default_to_zero_when_no_source_ui() -> None:
-    """Clones of nodes without _ui metadata default to (0, 0) base position."""
+def test_clone_positions_default_to_zero_when_no_source_geometry() -> None:
+    """Clones of nodes without first-class geometry default to a (0, 0) base."""
     wf = _make_workflow()
     wf.nodes["10"] = _make_loop_node("10", uid="loop-10", var="seed", count=2)
-    # Nodes without _ui metadata
+    # Nodes without first-class geometry.
     wf.nodes["20"] = VibeNode("20", "KSampler", inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0})
     wf.nodes["30"] = _make_save_image_node("30")
 
@@ -1253,8 +1255,7 @@ def test_clone_positions_default_to_zero_when_no_source_ui() -> None:
     assert result.workflow is not None
 
     for node_id, node in result.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         if pos is None:
             continue
         lowering = node.metadata.get("vibecomfy.lowering", {})
@@ -1280,8 +1281,7 @@ def test_clone_positions_honor_source_y_offset() -> None:
     assert result.workflow is not None
 
     for node_id, node in result.workflow.nodes.items():
-        ui = node.metadata.get("_ui", {})
-        pos = ui.get("pos")
+        pos = node.pos
         if pos is None:
             continue
         lowering = node.metadata.get("vibecomfy.lowering", {})
diff --git a/tests/test_layout_store.py b/tests/test_layout_store.py
index e98e63b9..a3dcd36d 100644
--- a/tests/test_layout_store.py
+++ b/tests/test_layout_store.py
@@ -38,7 +38,7 @@ def _node(node_id: str, uid: str = "", pos=None, size=None) -> VibeNode:
     if size is not None:
         ui["size"] = size
     metadata = {"_ui": ui} if ui else {}
-    n = VibeNode(node_id, "SaveImage", metadata=metadata)
+    n = VibeNode(node_id, "SaveImage", metadata=metadata, pos=pos, size=size)
     n.uid = uid
     return n
 
@@ -116,6 +116,8 @@ def test_envelope_full_round_trip(tmp_path: Path):
                 "properties": {"vibecomfy_uid": "abc", "extra": 1},
             }
         },
+        pos=[10, 20],
+        size=[300, 100],
     )
     n.uid = "1"
     wf.nodes["1"] = n
@@ -190,11 +192,15 @@ def test_skip_empty_uid(tmp_path: Path):
 
 
 def test_skip_no_pos(tmp_path: Path):
-    """Nodes with uid but no pos in _ui are skipped."""
+    """Nodes with uid but no first-class pos are skipped, despite legacy _ui."""
     py_path = tmp_path / "flat.py"
     wf = _wf()
-    # Node has uid but _ui has no pos
-    n = VibeNode("1", "SaveImage", metadata={"_ui": {"size": [100, 100]}})
+    n = VibeNode(
+        "1",
+        "SaveImage",
+        metadata={"_ui": {"pos": [9, 9], "size": [100, 100]}},
+        size=[100, 100],
+    )
     n.uid = "1"
     wf.nodes["1"] = n
     write_layout(py_path, wf)
@@ -203,6 +209,31 @@ def test_skip_no_pos(tmp_path: Path):
     assert layout == {}
 
 
+def test_first_class_geometry_wins_and_size_is_optional(tmp_path: Path):
+    py_path = tmp_path / "first_class.py"
+    wf = _wf()
+    wf.nodes["1"] = VibeNode(
+        "1",
+        "SaveImage",
+        uid="uid-1",
+        pos=[10, 20],
+        size=None,
+        metadata={"_ui": {"pos": [900, 900], "size": [300, 400]}},
+    )
+
+    write_layout(py_path, wf)
+
+    assert read_layout(py_path)["uid-1"] == {
+        "pos": [10, 20],
+        "size": None,
+        "flags": None,
+        "color": None,
+        "bgcolor": None,
+        "mode": 0,
+        "properties": {},
+    }
+
+
 def test_skip_no_ui_metadata(tmp_path: Path):
     """Nodes with uid but no _ui metadata entry are skipped."""
     py_path = tmp_path / "flat.py"
diff --git a/tests/test_porting_normalize_ingest.py b/tests/test_porting_normalize_ingest.py
index 007aa6eb..b17a8d73 100644
--- a/tests/test_porting_normalize_ingest.py
+++ b/tests/test_porting_normalize_ingest.py
@@ -326,6 +326,8 @@ def test_flat_pos_size_reachable_via_metadata_ui() -> None:
         assert _ui["size"] == expected["size"], (
             f"node {nid} size mismatch: {_ui['size']} != {expected['size']}"
         )
+        assert node.pos == [float(coord) for coord in expected["pos"]]
+        assert node.size == [float(coord) for coord in expected["size"]]
 
 
 def test_flat_determinism_same_source_identical_uids() -> None:
@@ -450,6 +452,69 @@ _MINIMAL_UI_RAW: dict = {
 }
 
 
+def test_live_and_offline_ui_ingest_copy_identical_first_class_geometry() -> None:
+    from unittest.mock import MagicMock, patch
+
+    from vibecomfy.comfy_backend import ComfyCompatibility
+
+    raw = {
+        "nodes": [
+            {
+                "id": 1,
+                "type": "SaveImage",
+                "inputs": [],
+                "pos": [10, 20.5],
+                "size": [300.25, 180],
+            }
+        ],
+        "links": [],
+    }
+    converted = {"1": {"class_type": "SaveImage", "inputs": {}}}
+    fake_module = MagicMock()
+    fake_module.convert_ui_to_api = MagicMock(return_value=deepcopy(converted))
+    compatible = ComfyCompatibility(
+        ok=True,
+        reason_code="ok",
+        expected={"commit": "expected", "version": "pinned"},
+        actual={"commit": "expected", "version": None},
+        safe_families=[],
+    )
+
+    offline = from_ui(raw, use_comfy_converter=False)
+    with patch.dict(
+        "sys.modules",
+        {
+            "comfy": MagicMock(),
+            "comfy.component_model": MagicMock(),
+            "comfy.component_model.workflow_convert": fake_module,
+        },
+    ), patch(
+        "vibecomfy.ingest.normalize.check_comfy_compatibility",
+        return_value=compatible,
+    ):
+        live = from_ui(raw)
+
+    assert live.nodes["1"].pos == offline.nodes["1"].pos == [10.0, 20.5]
+    assert live.nodes["1"].size == offline.nodes["1"].size == [300.25, 180.0]
+    raw["nodes"][0]["pos"][0] = 999
+    raw["nodes"][0]["size"][0] = 999
+    assert live.nodes["1"].pos == offline.nodes["1"].pos == [10.0, 20.5]
+    assert live.nodes["1"].size == offline.nodes["1"].size == [300.25, 180.0]
+
+
+def test_api_ingest_tolerates_malformed_geometry_and_retains_raw_ui() -> None:
+    raw_ui = {"pos": [1], "size": [float("inf"), 2], "custom": {"keep": True}}
+    workflow = from_api(
+        {"1": {"class_type": "SaveImage", "inputs": {}, "_ui": raw_ui}}
+    )
+    node = workflow.nodes["1"]
+
+    assert node.pos is None
+    assert node.size is None
+    assert node.metadata["_ui"] == raw_ui
+    assert node.metadata["_ui"] is not raw_ui
+
+
 def test_comfy_converter_strict_absent_comfy_falls_through_to_offline() -> None:
     """comfy_converter_strict=True with comfy absent: import guard skips cleanly.
 
diff --git a/tests/test_porting_synthetic_fixtures.py b/tests/test_porting_synthetic_fixtures.py
index aa5fd020..9cc5b77d 100644
--- a/tests/test_porting_synthetic_fixtures.py
+++ b/tests/test_porting_synthetic_fixtures.py
@@ -58,7 +58,7 @@ def _node_with_ui(
         metadata["_ui"] = ui
     if mode is not None:
         metadata["mode"] = mode
-    n = VibeNode(node_id, class_type, metadata=metadata)
+    n = VibeNode(node_id, class_type, metadata=metadata, pos=pos, size=size)
     n.uid = uid or node_id
     return n
 
@@ -79,7 +79,7 @@ def _virtual_node(
         ui["pos"] = pos
     if size is not None:
         ui["size"] = size
-    n = VibeNode(node_id, class_type, metadata={"_ui": ui})
+    n = VibeNode(node_id, class_type, metadata={"_ui": ui}, pos=pos, size=size)
     n.uid = node_id
     return n
 
diff --git a/tests/test_porting_ui_emitter.py b/tests/test_porting_ui_emitter.py
index 2c85e2fa..98357554 100644
--- a/tests/test_porting_ui_emitter.py
+++ b/tests/test_porting_ui_emitter.py
@@ -1901,6 +1901,25 @@ def test_captured_geometry_used_when_layout_empty_and_ui_present() -> None:
         )
 
 
+def test_captured_geometry_requires_both_first_class_pairs() -> None:
+    from vibecomfy.porting.emit.ui import _captured_geometry
+
+    node = VibeNode(
+        "1",
+        "SaveImage",
+        metadata={"_ui": {"pos": [900, 900], "size": [300, 400]}},
+        pos=[10.0, 20.0],
+        size=None,
+    )
+    assert _captured_geometry(node) is None
+
+    node.size = [300.0, 180.0]
+    assert _captured_geometry(node) == {
+        "pos": [10.0, 20.0],
+        "size": [300.0, 180.0],
+    }
+
+
 def test_captured_properties_blob_re_emitted_verbatim_with_ir_keys_merged() -> None:
     """A node with captured cnr_id / ver in its sidecar properties re-emits them
     verbatim, with vibecomfy_uid / vibecomfy_id / 'Node name for S&R' overlaid."""
@@ -2634,18 +2653,18 @@ def test_virtual_wires_display_and_flat_modes() -> None:
     orphan_pos = [300.0, 250.0]
     reroute_pos = [500.0, 100.0]
 
-    wf.nodes["10"] = VibeNode("10", "SetNode", widgets={"widget_0": "MY_BUS"})
+    wf.nodes["10"] = VibeNode("10", "SetNode", widgets={"widget_0": "MY_BUS"}, pos=list(set_pos), size=[30, 30])
     wf.nodes["10"].metadata["_ui"] = {"pos": list(set_pos), "size": [30, 30]}
 
-    wf.nodes["11"] = VibeNode("11", "GetNode", widgets={"widget_0": "MY_BUS"})
+    wf.nodes["11"] = VibeNode("11", "GetNode", widgets={"widget_0": "MY_BUS"}, pos=list(get_pos), size=[30, 30])
     wf.nodes["11"].metadata["_ui"] = {"pos": list(get_pos), "size": [30, 30]}
 
     # Orphaned GetNode: broadcast name has no matching SetNode
-    wf.nodes["12"] = VibeNode("12", "GetNode", widgets={"widget_0": "NO_SUCH_BUS"})
+    wf.nodes["12"] = VibeNode("12", "GetNode", widgets={"widget_0": "NO_SUCH_BUS"}, pos=list(orphan_pos), size=[30, 30])
     wf.nodes["12"].metadata["_ui"] = {"pos": list(orphan_pos), "size": [30, 30]}
 
     # Reroute passthrough
-    wf.nodes["20"] = VibeNode("20", "Reroute")
+    wf.nodes["20"] = VibeNode("20", "Reroute", pos=list(reroute_pos), size=[20, 20])
     wf.nodes["20"].metadata["_ui"] = {"pos": list(reroute_pos), "size": [20, 20]}
 
     # Edges
@@ -2729,6 +2748,8 @@ def test_coordinates_canonicalized_to_m2_precision() -> None:
     wf.nodes["98"] = VibeNode(
         "98", "LoadImage",
         metadata={"_ui": {"pos": [123.456789, 987.654321], "size": [319.999999, 180.000001]}},
+        pos=[123.456789, 987.654321],
+        size=[319.999999, 180.000001],
     )
     wf.nodes["99"] = VibeNode("99", "SaveImage")
     wf.connect("98.0", "99.images")
@@ -2738,7 +2759,7 @@ def test_coordinates_canonicalized_to_m2_precision() -> None:
     })
     result = emit_ui_json(wf, schema_provider=provider)
 
-    # Node 98 uses _captured_geometry (from _ui metadata)
+    # Node 98 uses first-class _captured_geometry.
     n98 = next(n for n in result["nodes"] if n["id"] == 98)
     assert n98["pos"] == [123.46, 987.65], f"pos not M2-canonicalized: {n98['pos']}"
     assert n98["size"] == [320.0, 180.0], f"size not M2-canonicalized: {n98['size']}"
diff --git a/tests/test_position_fidelity.py b/tests/test_position_fidelity.py
index bd97e5df..2eb04012 100644
--- a/tests/test_position_fidelity.py
+++ b/tests/test_position_fidelity.py
@@ -768,16 +768,20 @@ def test_duplicate_safety_twin_randomnoise():
     with open(corpus_path) as fh:
         raw = _json.load(fh)
 
-    wf = from_ui(raw)
+    wf = from_ui(raw, use_comfy_converter=False)
 
     # ── Add two twin RandomNoise nodes ──
     rn1 = wf.add_node("RandomNoise")
     rn1.inputs["noise_seed"] = 42
     rn1.metadata["_ui"] = {"id": int(rn1.id), "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}
+    rn1.pos = [0.0, 0.0]
+    rn1.size = [200.0, 100.0]
 
     rn2 = wf.add_node("RandomNoise")
     rn2.inputs["noise_seed"] = 42
     rn2.metadata["_ui"] = {"id": int(rn2.id), "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}
+    rn2.pos = [1000.0, 0.0]
+    rn2.size = [200.0, 100.0]
 
     # Verify they are structural twins.
     h1 = legacy_hash(rn1.id, wf)
@@ -816,7 +820,8 @@ def test_duplicate_safety_twin_randomnoise():
             f"twin node {node_id} (uid={uid}) must be in matched"
         )
         assigned_pos = result.matched[uid]["pos"]
-        node_pos = rn_node.metadata["_ui"]["pos"]
+        node_pos = rn_node.pos
+        assert node_pos is not None
         d_assigned = abs(node_pos[0] - assigned_pos[0])
         d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
         assert d_assigned <= d_other, (
diff --git a/tests/test_reconcile.py b/tests/test_reconcile.py
index aa2a179c..c5baf4cf 100644
--- a/tests/test_reconcile.py
+++ b/tests/test_reconcile.py
@@ -450,6 +450,8 @@ def _twin_rn_workflow() -> VibeWorkflow:
         inputs={"noise_seed": 42},
         uid="",
         metadata={"_ui": {"id": 1, "pos": [0.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
+        pos=[0.0, 0.0],
+        size=[200.0, 100.0],
     )
     n2 = VibeNode(
         id="2",
@@ -457,6 +459,8 @@ def _twin_rn_workflow() -> VibeWorkflow:
         inputs={"noise_seed": 42},
         uid="",
         metadata={"_ui": {"id": 2, "pos": [1000.0, 0.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
+        pos=[1000.0, 0.0],
+        size=[200.0, 100.0],
     )
     wf.nodes["1"] = n1
     wf.nodes["2"] = n2
@@ -508,7 +512,8 @@ def test_twin_randomnoise_no_swap():
     for uid, node_id in uid_for_node.items():
         node = wf.nodes[node_id]
         assigned_pos = result.matched[uid]["pos"]
-        node_pos = node.metadata["_ui"]["pos"]
+        node_pos = node.pos
+        assert node_pos is not None
         # Distance to assigned prior pos must be ≤ distance to the other prior pos.
         d_assigned = abs(node_pos[0] - assigned_pos[0])
         d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
@@ -532,6 +537,8 @@ def _twin_sampler_workflow() -> VibeWorkflow:
         inputs={"width": 512, "height": 512, "batch_size": 1},
         uid="latent-shared",
         metadata={"_ui": {"id": 0, "pos": [0.0, 300.0], "size": [200.0, 100.0], "mode": 0, "properties": {}}},
+        pos=[0.0, 300.0],
+        size=[200.0, 100.0],
     )
     s1 = VibeNode(
         id="1",
@@ -539,6 +546,8 @@ def _twin_sampler_workflow() -> VibeWorkflow:
         inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
         uid="",
         metadata={"_ui": {"id": 1, "pos": [0.0, 0.0], "size": [300.0, 200.0], "mode": 0, "properties": {}}},
+        pos=[0.0, 0.0],
+        size=[300.0, 200.0],
     )
     s2 = VibeNode(
         id="2",
@@ -546,6 +555,8 @@ def _twin_sampler_workflow() -> VibeWorkflow:
         inputs={"seed": 42, "steps": 20, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0},
         uid="",
         metadata={"_ui": {"id": 2, "pos": [1000.0, 0.0], "size": [300.0, 200.0], "mode": 0, "properties": {}}},
+        pos=[1000.0, 0.0],
+        size=[300.0, 200.0],
     )
     wf.nodes["0"] = latent
     wf.nodes["1"] = s1
@@ -598,7 +609,8 @@ def test_cloned_samplers_8b36a85a_no_swap():
     for uid, node_id in uid_for_node.items():
         node = wf.nodes[node_id]
         assigned_pos = result.matched[uid]["pos"]
-        node_pos = node.metadata["_ui"]["pos"]
+        node_pos = node.pos
+        assert node_pos is not None
         d_assigned = abs(node_pos[0] - assigned_pos[0])
         d_other = abs(node_pos[0] - (1000.0 if assigned_pos[0] == 0.0 else 0.0))
         assert d_assigned <= d_other, (
diff --git a/tests/test_workflow_core.py b/tests/test_workflow_core.py
index 4b4402a1..d6ca062b 100644
--- a/tests/test_workflow_core.py
+++ b/tests/test_workflow_core.py
@@ -1,6 +1,7 @@
 from __future__ import annotations
 
 import builtins
+from copy import deepcopy
 import importlib.util
 import json
 import sys
@@ -572,6 +573,95 @@ def test_copy_is_derived_and_preserves_mode_and_groups_deeply() -> None:
     ]
 
 
+def test_geometry_copy_and_compile_are_deep_and_execution_invariant() -> None:
+    workflow = VibeWorkflow("geometry", WorkflowSource("geometry"))
+    workflow.nodes["1"] = VibeNode(
+        "1",
+        "SaveImage",
+        uid="uid-1",
+        pos=[10.0, 20.0],
+        size=[300.0, 180.0],
+    )
+    compiled = workflow.compile("api")
+
+    cloned = workflow.copy()
+    cloned.nodes["1"].pos[0] = 999.0  # type: ignore[index]
+    cloned.nodes["1"].size[1] = 999.0  # type: ignore[index]
+
+    assert workflow.nodes["1"].pos == [10.0, 20.0]
+    assert workflow.nodes["1"].size == [300.0, 180.0]
+    assert cloned.compile("api") == compiled == workflow.compile("api")
+
+
+def test_geometry_envelope_new_fields_win_and_legacy_fallback_is_independent() -> None:
+    workflow = VibeWorkflow("geometry-envelope", WorkflowSource("geometry-envelope"))
+    workflow.nodes["1"] = VibeNode(
+        "1",
+        "SaveImage",
+        uid="uid-1",
+        metadata={"_ui": {"pos": [1, 2], "size": [3, 4]}},
+        pos=[10.0, 20.0],
+        size=[300.0, 180.0],
+    )
+    envelope = workflow.to_envelope()
+    assert envelope["nodes"]["1"]["pos"] == [10.0, 20.0]
+    assert envelope["nodes"]["1"]["size"] == [300.0, 180.0]
+
+    restored = from_envelope(envelope)
+    assert restored.nodes["1"].pos == [10.0, 20.0]
+    assert restored.nodes["1"].size == [300.0, 180.0]
+
+    old_mixed = deepcopy(envelope)
+    del old_mixed["nodes"]["1"]["pos"]
+    old_mixed["nodes"]["1"]["size"] = [30, 40]
+    old_mixed["nodes"]["1"]["metadata"]["_ui"] = {
+        "pos": [5, 6],
+        "size": [500, 600],
+    }
+    restored_old = from_envelope(old_mixed)
+    assert restored_old.nodes["1"].pos == [5.0, 6.0]
+    assert restored_old.nodes["1"].size == [30.0, 40.0]
+
+    explicit_absence = deepcopy(old_mixed)
+    explicit_absence["nodes"]["1"]["pos"] = None
+    assert from_envelope(explicit_absence).nodes["1"].pos is None
+
+
+@pytest.mark.parametrize(
+    "field_name,value",
+    [
+        ("pos", [1]),
+        ("pos", [1, 2, 3]),
+        ("pos", [True, 2]),
+        ("size", ["1", 2]),
+        ("size", [float("inf"), 2]),
+        ("size", [float("nan"), 2]),
+    ],
+)
+def test_versioned_envelope_rejects_malformed_present_geometry(
+    field_name: str, value: object
+) -> None:
+    workflow = VibeWorkflow("bad-geometry", WorkflowSource("bad-geometry"))
+    workflow.nodes["1"] = VibeNode("1", "SaveImage", uid="uid-1")
+    envelope = workflow.to_envelope()
+    envelope["nodes"]["1"][field_name] = value
+
+    with pytest.raises(ValueError, match=field_name):
+        from_envelope(envelope)
+
+
+def test_validation_and_envelope_writer_reject_invalid_programmatic_geometry() -> None:
+    workflow = VibeWorkflow("bad-geometry", WorkflowSource("bad-geometry"))
+    workflow.nodes["1"] = VibeNode(
+        "1", "SaveImage", uid="uid-1", pos=[1.0], size=[2.0, 3.0]
+    )
+
+    report = workflow.validate()
+    assert any(issue.code == "invalid_geometry" for issue in report.issues)
+    with pytest.raises(ValueError, match="pos"):
+        workflow.to_envelope()
+
+
 def test_node_mode_and_groups_survive_envelope_round_trip() -> None:
     """P10: node.mode and workflow.groups are serialized by to_envelope and
     restored by from_envelope (dataclass walk — no hand-listed fields)."""

codex
The substantive Batch C commit is exactly the reported 16 files; the extra two range files belong to the intervening checkpoint-record commit `5795812e`. The code audit confirms the six requested production descents now source `node.pos`/`node.size`, while reconcile’s non-geometry `_ui` hash read remains intact. I’m running the focused suite next and probing edge cases around malformed ingest, independent envelope fallback, stub layout, and compilation invariance.
exec
/bin/zsh -lc 'PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider -q tests/test_workflow_core.py tests/test_porting_normalize_ingest.py tests/test_layout_store.py tests/intent/test_static_lowering.py tests/test_porting_ui_emitter.py tests/test_position_fidelity.py tests/test_reconcile.py tests/test_porting_synthetic_fixtures.py' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 1582ms:
Traceback (most recent call last):
  File "/Users/peteromalley/.pyenv/versions/3.11.11/bin/pytest", line 6, in <module>
    sys.exit(console_main())
             ^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 223, in console_main
    code = main()
           ^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 193, in main
    config = _prepareconfig(new_args, plugins)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 361, in _prepareconfig
    config: Config = pluginmanager.hook.pytest_cmdline_parse(
                     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/helpconfig.py", line 124, in pytest_cmdline_parse
    config = yield
             ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 121, in _multicall
    res = hook_impl.function(*args)
          ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1186, in pytest_cmdline_parse
    self.parse(args)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/config/__init__.py", line 1556, in parse
    self.hook.pytest_load_initial_conftests(
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_hooks.py", line 512, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_manager.py", line 120, in _hookexec
    return self._inner_hookexec(hook_name, methods, kwargs, firstresult)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 167, in _multicall
    raise exception
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 139, in _multicall
    teardown.throw(exception)
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/warnings.py", line 128, in pytest_load_initial_conftests
    return (yield)
            ^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/pluggy/_callers.py", line 116, in _multicall
    next(function_gen)  # first yield
    ^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 170, in pytest_load_initial_conftests
    capman.start_global_capturing()
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 773, in start_global_capturing
    self._global_capturing = _get_multicapture(self._method)
                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 714, in _get_multicapture
    return MultiCapture(in_=FDCapture(0), out=FDCapture(1), err=FDCapture(2))
                                              ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/site-packages/_pytest/capture.py", line 493, in __init__
    TemporaryFile(buffering=0),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 628, in TemporaryFile
    prefix, suffix, dir, output_type = _sanitize_params(prefix, suffix, dir)
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 127, in _sanitize_params
    dir = gettempdir()
          ^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 316, in gettempdir
    return _os.fsdecode(_gettempdir())
                        ^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 309, in _gettempdir
    tempdir = _get_default_tempdir()
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/peteromalley/.pyenv/versions/3.11.11/lib/python3.11/tempfile.py", line 224, in _get_default_tempdir
    raise FileNotFoundError(_errno.ENOENT,
FileNotFoundError: [Errno 2] No usable temporary directory found in ['/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/', '/tmp', '/var/tmp', '/usr/tmp', '/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2']

codex
The local pytest rerun cannot start because this oracle sandbox has no writable temporary directory; it failed before collection, so this is environmental rather than a test failure. I’ll compensate with read-only, in-memory smoke assertions and continue the static call-path audit; the supplied host run remains the executable gate evidence.
exec
/bin/zsh -lc 'rg -n "''^def from_ui|''^def _from_ui|_merge_slim_ui|_ui.*deepcopy|deepcopy.*_ui" vibecomfy/ingest/normalize.py; nl -ba vibecomfy/ingest/normalize.py | sed -n '"'680,825p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
151:                    _merge_slim_ui(raw, converted)
276:            api_node.setdefault("_ui", deepcopy(raw_ui))
302:def _merge_slim_ui(raw: dict[str, Any], converted: dict[str, Any]) -> None:
798:def from_ui(
952:        # comfy-converter path stores a slim _ui enriched by _merge_slim_ui.
963:            _ui_node = deepcopy(_ui_raw)
   680	        )
   681	
   682	    # ── top-level inputs / outputs ─────────────────────────────────────────
   683	    embedded_links = _embedded_api_link_details(workflow)
   684	    if embedded_links:
   685	        raise ValueError(
   686	            "embedded_api_link: "
   687	            + _embedded_api_link_message(
   688	                embedded_links[0], surface="serialized vibe envelope decode"
   689	            )
   690	        )
   691	
   692	    inputs_raw = raw.get("inputs")
   693	    if not isinstance(inputs_raw, dict):
   694	        raise ValueError("serialized vibe envelope 'inputs' must be a mapping")
   695	    for name, entry in inputs_raw.items():
   696	        if not isinstance(entry, dict):
   697	            raise ValueError(
   698	                f"input {name!r}: input entries must be mappings, got {type(entry).__name__}"
   699	            )
   700	        input_name = entry.get("name")
   701	        node_id = entry.get("node_id")
   702	        field = entry.get("field")
   703	        if not isinstance(input_name, str) or not input_name.strip():
   704	            raise ValueError(f"input {name!r}: name must be a nonblank string")
   705	        if str(name) != input_name:
   706	            raise ValueError(
   707	                f"input mapping key {name!r} must equal input.name {input_name!r}"
   708	            )
   709	        if not isinstance(node_id, str) or not node_id.strip():
   710	            raise ValueError(f"input {name!r}: node_id must be a nonblank string")
   711	        if node_id not in workflow.nodes:
   712	            raise ValueError(f"input {name!r}: node_id {node_id!r} must exist in nodes")
   713	        if not isinstance(field, str) or not field.strip():
   714	            raise ValueError(f"input {name!r}: field must be a nonblank string")
   715	        required = entry.get("required", False)
   716	        if not isinstance(required, bool):
   717	            raise ValueError(f"input {name!r}: required must be a boolean")
   718	        aliases = entry.get("aliases", ())
   719	        if not isinstance(aliases, (list, tuple)) or not all(
   720	            isinstance(alias, str) for alias in aliases
   721	        ):
   722	            raise ValueError(f"input {name!r}: aliases must be a list of strings")
   723	        media_semantics = entry.get("media_semantics")
   724	        if media_semantics is not None and not isinstance(media_semantics, str):
   725	            raise ValueError(f"input {name!r}: media_semantics must be a string or null")
   726	        input_type = entry.get("type")
   727	        if input_type is not None and not isinstance(input_type, str):
   728	            raise ValueError(f"input {name!r}: type must be a string or null")
   729	        workflow.inputs[str(input_name)] = VibeInput(
   730	            name=str(input_name),
   731	            node_id=str(node_id),
   732	            field=str(field),
   733	            value=deepcopy(entry.get("value")),
   734	            type=input_type,
   735	            default=deepcopy(entry.get("default")),
   736	            required=required,
   737	            range=deepcopy(entry.get("range")),
   738	            aliases=tuple(aliases),
   739	            media_semantics=media_semantics,
   740	        )
   741	
   742	    outputs_raw = raw.get("outputs")
   743	    if not isinstance(outputs_raw, list):
   744	        raise ValueError("serialized vibe envelope 'outputs' must be a list")
   745	    for index, entry in enumerate(outputs_raw):
   746	        if not isinstance(entry, dict):
   747	            raise ValueError(
   748	                f"output {index}: output entries must be mappings, got {type(entry).__name__}"
   749	            )
   750	        node_id = entry.get("node_id")
   751	        output_type = entry.get("output_type")
   752	        if not isinstance(node_id, str) or not node_id.strip():
   753	            raise ValueError(f"output {index}: node_id must be a nonblank string")
   754	        if node_id not in workflow.nodes:
   755	            raise ValueError(
   756	                f"output {index}: node_id {node_id!r} must exist in nodes"
   757	            )
   758	        if not isinstance(output_type, str) or not output_type.strip():
   759	            raise ValueError(f"output {index}: output_type must be a nonblank string")
   760	        for field_name in ("name", "artifact_kind", "mime_type", "filename_prefix"):
   761	            value = entry.get(field_name)
   762	            if value is not None and not isinstance(value, str):
   763	                raise ValueError(f"output {index}: {field_name} must be a string or null")
   764	        workflow.outputs.append(
   765	            VibeOutput(
   766	                node_id=node_id,
   767	                output_type=output_type,
   768	                name=entry.get("name"),
   769	                artifact_kind=entry.get("artifact_kind"),
   770	                mime_type=entry.get("mime_type"),
   771	                filename_prefix=entry.get("filename_prefix"),
   772	                expected_cardinality=deepcopy(entry.get("expected_cardinality")),
   773	            )
   774	        )
   775	
   776	    # The serialized snapshot is JSON-shaped (tuples became lists) and may have
   777	    # been produced from an older derived execution view. Rehydrate this
   778	    # derived evidence from the just-decoded rich graph so an untouched rich
   779	    # envelope has no synthetic widget/link delta at its first canonical emit.
   780	    # All non-derived workflow metadata remains preserved verbatim.
   781	    from vibecomfy.ingest.snapshot import capture_ingest_snapshot
   782	
   783	    workflow.metadata["_ingest_snapshot"] = capture_ingest_snapshot(raw, workflow)
   784	
   785	    return workflow
   786	
   787	
   788	def from_envelope(raw: dict[str, Any]) -> VibeWorkflow:
   789	    """Fail-closed lossless decode of a serialized Vibe envelope.
   790	
   791	    The rich ``nodes`` mapping and ``edges`` list are the only structural
   792	    authority. ``compiled_api`` is ignored. Same decoder as
   793	    :meth:`VibeWorkflow.from_envelope`.
   794	    """
   795	    return VibeWorkflow.from_envelope(raw)
   796	
   797	
   798	def from_ui(
   799	    raw: dict[str, Any],
   800	    *,
   801	    source_path: str | None = None,
   802	    workflow_id: str | None = None,
   803	    schema_provider: SchemaProvider | None = None,
   804	    use_comfy_converter: bool = True,
   805	    comfy_converter_strict: bool = True,
   806	) -> VibeWorkflow:
   807	    """Ingest a LiteGraph list-nodes graph into a :class:`VibeWorkflow`."""
   808	    api = _ui_graph_to_api(
   809	        raw,
   810	        schema_provider=schema_provider,
   811	        use_comfy_converter=use_comfy_converter,
   812	        comfy_converter_strict=comfy_converter_strict,
   813	    )
   814	    workflow = from_api(
   815	        api,
   816	        source_path=source_path,
   817	        workflow_id=workflow_id,
   818	        schema_provider=schema_provider,
   819	    )
   820	    # Graph-level LiteGraph groups are first-class on the IR.  The API dict
   821	    # produced by the converter drops them, so carry them across from the raw
   822	    # graph here (fail-closed: a non-list groups is rejected).
   823	    workflow.groups = _vibe_groups(raw.get("groups"))
   824	    return workflow
   825	

exec
/bin/zsh -lc "rg -n \"VibeNode\\(\" vibecomfy -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
vibecomfy/workflow.py:588:        node = VibeNode(id=node_id, class_type=class_type, inputs=dict(inputs))
vibecomfy/runtime/eval/core.py:248:    preview_node = VibeNode(
vibecomfy/runtime/eval/core.py:300:    decode_node = VibeNode(
vibecomfy/runtime/eval/core.py:315:    preview_node = VibeNode(
vibecomfy/porting/readability_inventory.py:265:    # Also look for VibeNode('<uuid>', ...) patterns
vibecomfy/ingest/normalize.py:641:        workflow.nodes[node_id] = VibeNode(
vibecomfy/ingest/normalize.py:987:        workflow.nodes[str(node_id)] = VibeNode(
vibecomfy/porting/reorganise/graph_facts.py:905:        wf.nodes[node_id] = VibeNode(
vibecomfy/porting/emit/ui.py:1346:    node = VibeNode(
vibecomfy/porting/edit/_resolve.py:1281:        return estimate_node_size(VibeNode(id="__batch__", class_type=class_type, uid="__batch__"), schema)[0]

exec
/bin/zsh -lc 'git diff --name-only 6e97450a..2ddd1f06 -- ready_templates external_workflows workflows corpus tests/fixtures || true; git diff --name-only 5795812e..2ddd1f06 | rg -n "(''^|/)(ready_templates|external_workflows|corpus|workflows)/|'"\\.json"'$" || true' in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "git show -s --format='commit=%H%nparent=%P%nsubject=%s' 2ddd1f06; git show -s --format='commit=%H%nparent=%P%nsubject=%s' 5795812e; git diff --check 2ddd1f06"'^..2ddd1f06 -- . '"':(exclude).oracle/**'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit=2ddd1f06af6ce30b4588f7390429637a660ea0a3
parent=5795812e7adff2b11758cde2c971df357bb99a5a
subject=megado run2 Batch C: first-class VibeNode.pos/.size — mint at ingest, decode precedence, 6 descents replaced, stub-layout preserved
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead
commit=5795812e7adff2b11758cde2c971df357bb99a5a
parent=6e97450a7b75551d30d8e0a48a4e529e4cf15963
subject=megado run2: record Batch D+E checkpoint PASS
git: warning: confstr() failed with code 5: couldn't get path of DARWIN_USER_TEMP_DIR; using /tmp instead

exec
/bin/zsh -lc "nl -ba vibecomfy/ingest/normalize.py | sed -n '60,185p'; nl -ba vibecomfy/porting/emit/ui.py | sed -n '1320,1375p'; nl -ba vibecomfy/porting/reorganise/graph_facts.py | sed -n '880,925p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
    60	    ):
    61	        return "vibe"
    62	    if isinstance(raw.get("nodes"), list):
    63	        return "ui"
    64	    if raw == {}:
    65	        return "api"
    66	    if raw and all(isinstance(value, dict) and "class_type" in value for value in raw.values()):
    67	        return "api"
    68	    return "unknown"
    69	
    70	
    71	def normalize_to_api(
    72	    raw: dict[str, Any],
    73	    *,
    74	    schema_provider: SchemaProvider | None = None,
    75	    use_comfy_converter: bool = True,
    76	    comfy_converter_strict: bool = True,
    77	) -> dict[str, Any]:
    78	    """Convert a raw workflow dict (UI or API shape) to ComfyUI API format.
    79	
    80	    By default this prefers the live ComfyUI converter and raises if
    81	    ``convert_ui_to_api`` fails. Pass ``comfy_converter_strict=False`` to keep the
    82	    legacy lenient fallback path when the converter is importable but errors. Pass
    83	    ``use_comfy_converter=False`` for explicit offline normalization that never
    84	    imports or calls the ComfyUI converter; in that mode
    85	    ``comfy_converter_strict`` is ignored.
    86	    """
    87	    shape = detect_workflow_shape(raw)
    88	    if shape == "api":
    89	        api = raw.get("prompt", raw)
    90	        _enforce_exec_source_limits(api, surface="api")
    91	        return api
    92	    if shape == "vibe":
    93	        # The rich envelope (nodes mapping + edges list) is the only structural
    94	        # authority. ``compiled_api`` is stale execution evidence and must never
    95	        # decide which rich nodes exist — the API view is derived by decoding
    96	        # the envelope into a VibeWorkflow and compiling it fresh.
    97	        workflow = VibeWorkflow.from_envelope(raw)
    98	        api = workflow.compile("api")
    99	        _merge_vibe_node_widget_evidence(raw, api)
   100	        _enforce_exec_source_limits(api, surface="vibe.compiled_api")
   101	        return api
   102	    if shape != "ui":
   103	        raise ValueError(f"Unsupported workflow shape: {shape}")
   104	    return _ui_graph_to_api(
   105	        raw,
   106	        schema_provider=schema_provider,
   107	        use_comfy_converter=use_comfy_converter,
   108	        comfy_converter_strict=comfy_converter_strict,
   109	    )
   110	
   111	
   112	def _ui_graph_to_api(
   113	    raw: dict[str, Any],
   114	    *,
   115	    schema_provider: SchemaProvider | None = None,
   116	    use_comfy_converter: bool = True,
   117	    comfy_converter_strict: bool = True,
   118	) -> dict[str, Any]:
   119	    """LiteGraph list-nodes → Comfy prompt dict. Does not sniff shape."""
   120	    if use_comfy_converter:
   121	        try:
   122	            from comfy.component_model.workflow_convert import convert_ui_to_api
   123	        except ImportError:
   124	            pass
   125	        else:
   126	            compatibility = check_comfy_compatibility()
   127	            if not compatibility.ok:
   128	                if comfy_converter_strict:
   129	                    require_comfy_compatibility(compatibility)
   130	                warnings.warn(
   131	                    "normalize_to_api(): live ComfyUI compatibility check failed "
   132	                    f"({compatibility.reason_code}); falling back to the offline "
   133	                    "normalizer because comfy_converter_strict=False.",
   134	                    stacklevel=3,
   135	                )
   136	                return _normalize_ui_to_api(raw, schema_provider=schema_provider)
   137	            try:
   138	                converted = convert_ui_to_api(raw)
   139	            except Exception:
   140	                if comfy_converter_strict:
   141	                    raise
   142	                warnings.warn(
   143	                    "normalize_to_api(): ComfyUI convert_ui_to_api raised; "
   144	                    "falling back to the offline normalizer because "
   145	                    "comfy_converter_strict=False.",
   146	                    stacklevel=3,
   147	                )
   148	            else:
   149	                _enforce_exec_source_limits(converted, surface="ui.converter")
   150	                if not _has_unknown_widget_inputs(converted):
   151	                    _merge_slim_ui(raw, converted)
   152	                    return converted
   153	                return _normalize_ui_to_api(raw, schema_provider=schema_provider)
   154	
   155	    return _normalize_ui_to_api(raw, schema_provider=schema_provider)
   156	
   157	
   158	def _normalize_ui_to_api(raw: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> dict[str, Any]:
   159	    nodes = {str(node["id"]): node for node in raw.get("nodes", []) if isinstance(node, dict) and "id" in node}
   160	    links = raw.get("links", [])
   161	    link_map: dict[int, tuple[str, int]] = {}
   162	    for link in links:
   163	        if isinstance(link, list) and len(link) >= 4:
   164	            link_map[int(link[0])] = (str(link[1]), int(link[2]))
   165	        elif isinstance(link, dict) and {"id", "origin_id", "origin_slot"} <= set(link):
   166	            link_map[int(link["id"])] = (str(link["origin_id"]), int(link["origin_slot"]))
   167	
   168	    api: dict[str, Any] = {}
   169	    for node_id, node in nodes.items():
   170	        inputs: dict[str, Any] = {}
   171	        input_provenance: dict[str, str] = {}
   172	        class_type = str(node.get("type", "Unknown"))
   173	        ui_widget_names: list[str] = []
   174	        for input_item in node.get("inputs", []) or []:
   175	            if not isinstance(input_item, dict):
   176	                continue
   177	            name = input_item.get("name")
   178	            link_id = input_item.get("link")
   179	            widget = input_item.get("widget")
   180	            if link_id is None and isinstance(name, str) and isinstance(widget, dict):
   181	                ui_widget_names.append(str(widget.get("name") or name))
   182	            if link_id is not None and link_id in link_map:
   183	                if not name:
   184	                    # Reroute / passthrough nodes may have empty-string input
   185	                    # names — use a stable generated key to preserve the edge.
  1320	    fields: Mapping[str, Any],
  1321	    schema: Any | None,
  1322	    node_id: int,
  1323	    uid: str,
  1324	    pos: list[float] | tuple[float, float],
  1325	) -> dict[str, Any]:
  1326	    """Materialize one unlinked LiteGraph node using emitter-equivalent defaults.
  1327	
  1328	    This is the creation-path substrate helper for agent-edit v2. It deliberately
  1329	    reuses the same widget ordering, property stamping, size defaults, and output
  1330	    slot construction that :func:`emit_ui_json` uses for a single node.
  1331	    """
  1332	    merged_fields: dict[str, Any] = {}
  1333	    schema_inputs = getattr(schema, "inputs", None)
  1334	    if isinstance(schema_inputs, dict):
  1335	        for name, spec in schema_inputs.items():
  1336	            default = getattr(spec, "default", None)
  1337	            if default is not None:
  1338	                merged_fields[name] = deepcopy(default)
  1339	    merged_fields.update(dict(fields))
  1340	
  1341	    metadata: dict[str, Any] = {}
  1342	    retained_control = merged_fields.pop("control_after_generate", None)
  1343	    if isinstance(retained_control, str):
  1344	        metadata["control_after_generate"] = retained_control
  1345	
  1346	    node = VibeNode(
  1347	        id=str(node_id),
  1348	        class_type=class_type,
  1349	        inputs=merged_fields,
  1350	        metadata=metadata,
  1351	        uid=uid,
  1352	    )
  1353	    geometry = {
  1354	        "pos": [
  1355	            _canonicalize_coord(float(pos[0])),
  1356	            _canonicalize_coord(float(pos[1])),
  1357	        ],
  1358	        "size": [_canonicalize_coord(s) for s in _STUB_NODE_SIZE],
  1359	    }
  1360	    furniture = _resolve_furniture(node, None)
  1361	    inputs: list[dict[str, Any]] = []
  1362	    outputs: list[dict[str, Any]] = _schema_outputs_for_unwired_node(schema)
  1363	    if class_type == "vibecomfy.exec":
  1364	        exec_io = _exec_io_for_node(node)
  1365	        if exec_io is not None:
  1366	            inputs = _exec_dynamic_inputs(exec_io, {})
  1367	            outputs = _exec_dynamic_outputs(exec_io, {})
  1368	    return _emit_litegraph_node_dict(
  1369	        node,
  1370	        litegraph_node_id=int(node_id),
  1371	        order=0,
  1372	        geometry=geometry,
  1373	        furniture=furniture,
  1374	        inputs=inputs,
  1375	        outputs=outputs,
   880	) -> dict[str, tuple[CanonicalRefFact, ...]]:
   881	    rows: dict[str, list[CanonicalRefFact]] = {}
   882	    for fact in canonical_refs:
   883	        rows.setdefault(fact.ref.scope_path, []).append(fact)
   884	    return {scope: tuple(facts) for scope, facts in rows.items()}
   885	
   886	
   887	def _topology_adapter(
   888	    scope_path: str,
   889	    scope: ScopeState,
   890	    node_facts: Sequence[CanonicalRefFact],
   891	) -> _ScopeTopologyAdapter:
   892	    id_to_ref: dict[str, CanonicalNodeRef] = {}
   893	    id_to_node: dict[str, Mapping[str, Any]] = {}
   894	    wf = VibeWorkflow(id=f"reorganise:{scope_path or 'root'}", source=WorkflowSource(id="reorganise"))
   895	    for fact in node_facts:
   896	        if fact.litegraph_id is None:
   897	            continue
   898	        node_id = str(fact.litegraph_id)
   899	        node = scope.graph.get("nodes")
   900	        raw_node = _node_by_id(node, fact.litegraph_id)
   901	        if raw_node is None:
   902	            continue
   903	        id_to_ref[node_id] = fact.ref
   904	        id_to_node[node_id] = raw_node
   905	        wf.nodes[node_id] = VibeNode(
   906	            id=node_id,
   907	            class_type=fact.class_type,
   908	            inputs=_workflow_inputs(raw_node),
   909	            widgets=_workflow_widgets(raw_node),
   910	            uid=fact.ref.uid,
   911	        )
   912	
   913	    raw_edges = tuple(
   914	        edge
   915	        for edge in _raw_edges(scope.graph)
   916	        if edge.from_node in id_to_ref and edge.to_node in id_to_ref
   917	    )
   918	    wf.edges = [
   919	        VibeEdge(edge.from_node, edge.from_output, edge.to_node, edge.to_input)
   920	        for edge in raw_edges
   921	    ]
   922	    return _ScopeTopologyAdapter(
   923	        scope_path=scope_path,
   924	        workflow=wf,
   925	        id_to_ref=id_to_ref,

exec
/bin/zsh -lc "nl -ba vibecomfy/ingest/normalize.py | sed -n '158,240p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
   158	def _normalize_ui_to_api(raw: dict[str, Any], *, schema_provider: SchemaProvider | None = None) -> dict[str, Any]:
   159	    nodes = {str(node["id"]): node for node in raw.get("nodes", []) if isinstance(node, dict) and "id" in node}
   160	    links = raw.get("links", [])
   161	    link_map: dict[int, tuple[str, int]] = {}
   162	    for link in links:
   163	        if isinstance(link, list) and len(link) >= 4:
   164	            link_map[int(link[0])] = (str(link[1]), int(link[2]))
   165	        elif isinstance(link, dict) and {"id", "origin_id", "origin_slot"} <= set(link):
   166	            link_map[int(link["id"])] = (str(link["origin_id"]), int(link["origin_slot"]))
   167	
   168	    api: dict[str, Any] = {}
   169	    for node_id, node in nodes.items():
   170	        inputs: dict[str, Any] = {}
   171	        input_provenance: dict[str, str] = {}
   172	        class_type = str(node.get("type", "Unknown"))
   173	        ui_widget_names: list[str] = []
   174	        for input_item in node.get("inputs", []) or []:
   175	            if not isinstance(input_item, dict):
   176	                continue
   177	            name = input_item.get("name")
   178	            link_id = input_item.get("link")
   179	            widget = input_item.get("widget")
   180	            if link_id is None and isinstance(name, str) and isinstance(widget, dict):
   181	                ui_widget_names.append(str(widget.get("name") or name))
   182	            if link_id is not None and link_id in link_map:
   183	                if not name:
   184	                    # Reroute / passthrough nodes may have empty-string input
   185	                    # names — use a stable generated key to preserve the edge.
   186	                    name = f"_un{link_id}"
   187	                inputs[name] = [link_map[link_id][0], link_map[link_id][1]]
   188	                input_provenance[str(name)] = "edge"
   189	        widgets_present = "widgets_values" in node
   190	        widgets = node.get("widgets_values", [])
   191	        if isinstance(widgets, dict):
   192	            for name, value in widgets.items():
   193	                if name in inputs:
   194	                    continue
   195	                inputs[str(name)] = value
   196	                input_provenance[str(name)] = "widget"
   197	        elif isinstance(widgets, list):
   198	            widget_names = _schema_input_names(schema_provider, class_type)
   199	            for idx, value in enumerate(widgets):
   200	                if idx < len(widget_names):
   201	                    name = _normalize_widget_input_name(widget_names, idx, value)
   202	                elif idx < len(ui_widget_names):
   203	                    name = ui_widget_names[idx]
   204	                else:
   205	                    name = f"widget_{idx}"
   206	                if name in inputs:
   207	                    continue
   208	                inputs[name] = value
   209	                input_provenance[str(name)] = "widget"
   210	        api_node = {
   211	            "class_type": class_type,
   212	            "inputs": inputs,
   213	            "_ui": node,
   214	            "_input_provenance": input_provenance,
   215	        }
   216	        if widgets_present:
   217	            api_node["_raw_widgets"] = _raw_widget_payload_dict(widgets, source="ui.widgets_values")
   218	        api[node_id] = api_node
   219	    _enforce_exec_source_limits(api, surface="ui.offline")
   220	    return api
   221	
   222	
   223	def _raw_widget_payload_dict(values: Any, *, source: str) -> dict[str, Any]:
   224	    if values is None:
   225	        shape = "none"
   226	        length = 0
   227	    elif isinstance(values, dict):
   228	        shape = "dict"
   229	        length = len(values)
   230	    elif isinstance(values, list):
   231	        shape = "list"
   232	        length = len(values)
   233	    else:
   234	        shape = "scalar"
   235	        length = 1
   236	    has_dict_rows = isinstance(values, dict) or (
   237	        isinstance(values, list) and any(isinstance(item, dict) for item in values)
   238	    )
   239	    return {
   240	        "values": deepcopy(values),

exec
/bin/zsh -lc "rg -n \"_merge_slim_ui|live_and_offline|comfy_converter\" tests -g '*.py'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
tests/test_reconcile.py:902:    api = normalize_to_api(data, use_comfy_converter=False)
tests/test_reconcile.py:967:    api = normalize_to_api(data, use_comfy_converter=False)
tests/test_position_fidelity.py:771:    wf = from_ui(raw, use_comfy_converter=False)
tests/test_position_fidelity.py:1031:    # Force the offline-normalize path (use_comfy_converter=False) so the test is
tests/test_position_fidelity.py:1038:        api_format = normalize_to_api(edited, use_comfy_converter=False)
tests/test_porting_edit_session.py:61:    Uses `use_comfy_converter=False` so the test stays offline and deterministic.
tests/test_porting_edit_session.py:63:    api = normalize_to_api(deepcopy(raw), use_comfy_converter=False)
tests/test_porting_ui_emitter.py:1290:    2. Also canonical-equal vs normalize_to_api(raw, comfy_converter_strict=True),
tests/test_porting_ui_emitter.py:1421:                    raw, comfy_converter_strict=True, use_comfy_converter=True
tests/test_porting_ui_emitter.py:1607:        normalize_to_api(raw, comfy_converter_strict=True)
tests/test_porting_ui_emitter.py:1610:    result = normalize_to_api(raw, comfy_converter_strict=False)
tests/test_porting_normalize_ingest.py:375:    api = normalize_to_api(raw_ui, use_comfy_converter=False)
tests/test_porting_normalize_ingest.py:384:def test_mode_captured_from_comfy_converter_path() -> None:
tests/test_porting_normalize_ingest.py:385:    """Comfy-converter path: mode:4 in _merge_slim_ui lands on VibeNode.mode."""
tests/test_porting_normalize_ingest.py:386:    # Simulate the result of convert_ui_to_api + _merge_slim_ui by providing
tests/test_porting_normalize_ingest.py:445:# T19 — comfy_converter_strict parameter semantics (offline, no comfy needed)
tests/test_porting_normalize_ingest.py:455:def test_live_and_offline_ui_ingest_copy_identical_first_class_geometry() -> None:
tests/test_porting_normalize_ingest.py:483:    offline = from_ui(raw, use_comfy_converter=False)
tests/test_porting_normalize_ingest.py:518:def test_comfy_converter_strict_absent_comfy_falls_through_to_offline() -> None:
tests/test_porting_normalize_ingest.py:519:    """comfy_converter_strict=True with comfy absent: import guard skips cleanly.
tests/test_porting_normalize_ingest.py:521:    When ``use_comfy_converter=True`` (default) but the comfy package cannot be
tests/test_porting_normalize_ingest.py:532:        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)
tests/test_porting_normalize_ingest.py:538:def test_comfy_converter_strict_no_op_when_use_comfy_converter_false() -> None:
tests/test_porting_normalize_ingest.py:539:    """comfy_converter_strict is a no-op when use_comfy_converter=False.
tests/test_porting_normalize_ingest.py:541:    When the comfy converter is disabled entirely (``use_comfy_converter=False``),
tests/test_porting_normalize_ingest.py:548:        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=False
tests/test_porting_normalize_ingest.py:551:        _MINIMAL_UI_RAW, use_comfy_converter=False, comfy_converter_strict=True
tests/test_porting_normalize_ingest.py:556:        "comfy_converter_strict must be a no-op when use_comfy_converter=False — "
tests/test_porting_normalize_ingest.py:561:def test_comfy_converter_default_raises_when_converter_errors() -> None:
tests/test_porting_normalize_ingest.py:599:def test_comfy_converter_strict_false_tolerant_when_converter_errors() -> None:
tests/test_porting_normalize_ingest.py:600:    """comfy_converter_strict=False keeps the explicit tolerant fallback path.
tests/test_porting_normalize_ingest.py:603:    ``comfy_converter_strict=False`` opt-out must still fall through to the
tests/test_porting_normalize_ingest.py:618:        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)
tests/test_porting_normalize_ingest.py:624:def test_comfy_converter_strict_surfaces_version_skew_before_converter_exec() -> None:
tests/test_porting_normalize_ingest.py:648:            normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=True)
tests/test_porting_normalize_ingest.py:654:def test_comfy_converter_lenient_skew_falls_back_offline_without_converter_exec() -> None:
tests/test_porting_normalize_ingest.py:679:        result = normalize_to_api(_MINIMAL_UI_RAW, comfy_converter_strict=False)
tests/test_porting_normalize_ingest.py:820:    api2 = normalize_to_api(ui1, use_comfy_converter=False)
tests/test_porting_normalize_ingest.py:1123:    api = normalize_to_api(raw, use_comfy_converter=False)
tests/test_porting_workbench.py:585:        use_comfy_converter=False,
tests/test_demo_factory_structural_baseline.py:414:    normalized = normalize_to_api(graph, use_comfy_converter=False)
tests/test_porting_emitter.py:50:    api = normalize_to_api(raw, use_comfy_converter=False)
tests/test_porting_emitter.py:1313:    src = load_port_source(str(fixture), use_comfy_converter=False)
tests/test_porting_emitter.py:1908:    api = normalize_to_api(raw, use_comfy_converter=False)
tests/acceptance/node_resolution/test_acceptance.py:210:    src = load_port_source(str(IDEOGRAM), use_comfy_converter=False)
tests/acceptance/node_resolution/test_acceptance.py:592:    src = load_port_source(str(IDEOGRAM), use_comfy_converter=False)
tests/acceptance/node_resolution/test_acceptance.py:1027:    src = load_port_source(str(src_path), use_comfy_converter=False)
tests/test_schema.py:10:    _merge_slim_ui,
tests/test_schema.py:525:    # use_comfy_converter=False forces the offline schema-provider-driven
tests/test_schema.py:528:    api = normalize_to_api(raw, schema_provider=provider, use_comfy_converter=False)
tests/test_schema.py:748:def test_merge_slim_ui_retains_widgets_values_and_raw_payload() -> None:
tests/test_schema.py:763:    _merge_slim_ui(raw, converted)
tests/test_exec_normalize.py:53:    api = normalize_to_api(_ui_exec_node("return {'image': image}"), use_comfy_converter=False)
tests/test_workflow_core.py:2017:    api = normalize_to_api(ui_raw, use_comfy_converter=False)
tests/test_subgraph_emission_contract.py:115:    api = normalize_to_api(raw, use_comfy_converter=False)

exec
/bin/zsh -lc "rg -n \"def convert_ui_to_api|convert_ui_to_api\\(\" . -g '*.py' -g '*.pyi'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
./scripts/roundtrip_fidelity_spike.py:42:        r = convert_ui_to_api(copy.deepcopy(ui))
./vibecomfy/intent/_refusal_spine_probe.py:59:            result = convert_ui_to_api(copy.deepcopy(wf))
./vibecomfy/ingest/normalize.py:138:                converted = convert_ui_to_api(raw)
./vibecomfy/porting/refuse.py:29:def _offline_convert_ui_to_api(raw: dict[str, Any]) -> dict[str, Any]:
./vibecomfy/porting/refuse.py:36:def _load_convert_ui_to_api() -> _ConvertUiToApi:
./vibecomfy/porting/refuse.py:72:        between ``convert_ui_to_api(original)`` and ``convert_ui_to_api(candidate)``.
./vibecomfy/porting/refuse.py:238:    Compares ``convert_ui_to_api(candidate_ui)`` against
./vibecomfy/porting/refuse.py:239:    ``convert_ui_to_api(original_ui)`` over the *scope set* — nodes that are
./vibecomfy/porting/refuse.py:279:    convert_ui_to_api = _load_convert_ui_to_api()
./vibecomfy/porting/refuse.py:280:    orig_api = convert_ui_to_api(dict(original_ui))
./vibecomfy/porting/refuse.py:281:    cand_api = convert_ui_to_api(dict(candidate_ui))
./tests/test_compile_invariance.py:144:def test_bypass_equivalence_against_convert_ui_to_api(
./tests/test_porting_ui_emitter.py:1153:def test_comfy_release_smoke_convert_ui_to_api() -> None:
./tests/test_porting_ui_emitter.py:1466:            # Check: canonical_equal(convert_ui_to_api(original),
./tests/test_porting_ui_emitter.py:1467:            #                        convert_ui_to_api(emit(ingest(original),

exec
/bin/zsh -lc "python -B -c 'import importlib.util; s=importlib.util.find_spec(\"comfy.component_model.workflow_convert\"); print(s.origin if s else \"ABSENT\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 32ms:
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "<frozen importlib.util>", line 95, in find_spec
ModuleNotFoundError: No module named 'comfy'

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -B -c 'from copy import deepcopy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode
from vibecomfy.ingest.normalize import from_api, from_ui, from_envelope
from vibecomfy.porting.emit.ui import emit_ui_json

raw_ui = {\"pos\": [1, 2.5], \"size\": [300, 180], \"custom\": {\"k\": [1]}}
raw_api = {\"1\": {\"class_type\": \"SaveImage\", \"inputs\": {}, \"_ui\": raw_ui}}
wf = from_api(raw_api)
assert wf.nodes[\"1\"].pos == [1.0, 2.5] and wf.nodes[\"1\"].size == [300.0, 180.0]
raw_ui[\"pos\"][0] = 99
assert wf.nodes[\"1\"].pos == [1.0, 2.5]
mal = {\"pos\": [1], \"size\": [float(\"inf\"), 2], \"keep\": {\"x\": 1}}
wm = from_api({\"1\": {\"class_type\": \"SaveImage\", \"inputs\": {}, \"_ui\": mal}})
assert wm.nodes[\"1\"].pos is None and wm.nodes[\"1\"].size is None
assert wm.nodes[\"1\"].metadata[\"_ui\"] == mal and wm.nodes[\"1\"].metadata[\"_ui\"] is not mal
ui = {\"nodes\": [{\"id\": 1, \"type\": \"SaveImage\", \"inputs\": [], \"pos\": [3, 4], \"size\": [5, 6]}], \"links\": []}
wu = from_ui(ui, use_comfy_converter=False)
assert wu.nodes[\"1\"].pos == [3.0, 4.0] and wu.nodes[\"1\"].size == [5.0, 6.0]

base = VibeWorkflow(\"e\", WorkflowSource(\"e\"))
base.nodes[\"1\"] = VibeNode(\"1\", \"SaveImage\", uid=\"u\", metadata={\"_ui\": {\"pos\": [1,2], \"size\": [3,4]}}, pos=[10.0,20.0], size=[30.0,40.0])
env = base.to_envelope()
r = from_envelope(env)
assert r.nodes[\"1\"].pos == [10.0,20.0] and r.nodes[\"1\"].size == [30.0,40.0]
old = deepcopy(env)
del old[\"nodes\"][\"1\"][\"pos\"]
old[\"nodes\"][\"1\"][\"size\"] = [50,60]
r = from_envelope(old)
assert r.nodes[\"1\"].pos == [1.0,2.0] and r.nodes[\"1\"].size == [50.0,60.0]
old[\"nodes\"][\"1\"][\"pos\"] = None
assert from_envelope(old).nodes[\"1\"].pos is None
bad = deepcopy(env)
bad[\"nodes\"][\"1\"][\"pos\"] = [1]
rejected = False
try:
    from_envelope(bad)
except ValueError:
    rejected = True
assert rejected

compiled = base.compile(\"api\")
clone = base.copy()
clone.nodes[\"1\"].pos[0] = 999
clone.nodes[\"1\"].size[0] = 999
assert base.nodes[\"1\"].pos == [10.0,20.0] and base.nodes[\"1\"].size == [30.0,40.0]
assert clone.compile(\"api\") == compiled == base.compile(\"api\")

stub = VibeWorkflow(\"s\", WorkflowSource(\"s\"))
stub.nodes[\"1\"] = VibeNode(\"1\", \"SaveImage\", uid=\"u\", metadata={\"_ui\": {\"pos\": [900,900], \"size\": [999,999]}}, pos=[10.0,20.0], size=None)
out = emit_ui_json(stub)
node = next(n for n in out[\"nodes\"] if n[\"id\"] == 1)
assert node[\"pos\"] == [0.0,0.0] and node[\"size\"] == [320.0,180.0], node
print(\"in-memory geometry smoke: PASS\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 exited 1 in 254ms:
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: u
<string>:50: UserWarning: emit_ui_json: schema-less node 1(SaveImage); emitting best-effort slots. Pass strict=True to hard-fail.
Traceback (most recent call last):
  File "<string>", line 52, in <module>
AssertionError: {'id': 1, 'type': 'SaveImage', 'pos': [0.0, 0.0], 'size': [320.0, 30.0], 'flags': {}, 'order': 0, 'mode': 0, 'inputs': [], 'outputs': [], 'properties': {'vibecomfy_id': 'SaveImage_0', 'Node name for S&R': 'SaveImage', 'vibecomfy_uid': 'u'}, 'widgets_values': []}

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -B -c 'from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode
from vibecomfy.porting.emit.ui import emit_ui_json
stub = VibeWorkflow(\"s\", WorkflowSource(\"s\"))
stub.nodes[\"1\"] = VibeNode(\"1\", \"SaveImage\", uid=\"u\", metadata={\"_ui\": {\"pos\": [900,900], \"size\": [999,999]}}, pos=[10.0,20.0], size=None)
out = emit_ui_json(stub)
node = next(n for n in out[\"nodes\"] if n[\"id\"] == 1)
assert node[\"pos\"] == [0.0,0.0] and node[\"size\"] == [320.0,30.0], node
print(\"stub-layout fallback smoke: PASS\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 84ms:
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: u
<string>:5: UserWarning: emit_ui_json: schema-less node 1(SaveImage); emitting best-effort slots. Pass strict=True to hard-fail.
stub-layout fallback smoke: PASS

exec
/bin/zsh -lc "PYTHONDONTWRITEBYTECODE=1 python -B -c 'from copy import deepcopy
from vibecomfy.workflow import VibeWorkflow, WorkflowSource, VibeNode
from vibecomfy.ingest.normalize import from_api, from_ui, from_envelope
from vibecomfy.porting.emit.ui import emit_ui_json
raw_ui = {\"pos\": [1, 2.5], \"size\": [300, 180], \"custom\": {\"k\": [1]}}
wf = from_api({\"1\": {\"class_type\": \"SaveImage\", \"inputs\": {}, \"_ui\": raw_ui}})
assert wf.nodes[\"1\"].pos == [1.0, 2.5] and wf.nodes[\"1\"].size == [300.0, 180.0]
raw_ui[\"pos\"][0] = 99
assert wf.nodes[\"1\"].pos == [1.0, 2.5]
mal = {\"pos\": [1], \"size\": [float(\"inf\"), 2], \"keep\": {\"x\": 1}}
wm = from_api({\"1\": {\"class_type\": \"SaveImage\", \"inputs\": {}, \"_ui\": mal}})
assert wm.nodes[\"1\"].pos is None and wm.nodes[\"1\"].size is None
assert wm.nodes[\"1\"].metadata[\"_ui\"] == mal and wm.nodes[\"1\"].metadata[\"_ui\"] is not mal
ui = {\"nodes\": [{\"id\": 1, \"type\": \"SaveImage\", \"inputs\": [], \"pos\": [3, 4], \"size\": [5, 6]}], \"links\": []}
wu = from_ui(ui, use_comfy_converter=False)
assert wu.nodes[\"1\"].pos == [3.0, 4.0] and wu.nodes[\"1\"].size == [5.0, 6.0]
base = VibeWorkflow(\"e\", WorkflowSource(\"e\"))
base.nodes[\"1\"] = VibeNode(\"1\", \"SaveImage\", uid=\"u\", metadata={\"_ui\": {\"pos\": [1,2], \"size\": [3,4]}}, pos=[10.0,20.0], size=[30.0,40.0])
env = base.to_envelope()
r = from_envelope(env)
assert r.nodes[\"1\"].pos == [10.0,20.0] and r.nodes[\"1\"].size == [30.0,40.0]
old = deepcopy(env)
del old[\"nodes\"][\"1\"][\"pos\"]
old[\"nodes\"][\"1\"][\"size\"] = [50,60]
r = from_envelope(old)
assert r.nodes[\"1\"].pos == [1.0,2.0] and r.nodes[\"1\"].size == [50.0,60.0]
old[\"nodes\"][\"1\"][\"pos\"] = None
assert from_envelope(old).nodes[\"1\"].pos is None
bad = deepcopy(env)
bad[\"nodes\"][\"1\"][\"pos\"] = [1]
try:
    from_envelope(bad)
except ValueError:
    pass
else:
    raise AssertionError(\"malformed envelope geometry accepted\")
compiled = base.compile(\"api\")
clone = base.copy()
clone.nodes[\"1\"].pos[0] = 999
clone.nodes[\"1\"].size[0] = 999
assert base.nodes[\"1\"].pos == [10.0,20.0] and base.nodes[\"1\"].size == [30.0,40.0]
assert clone.compile(\"api\") == compiled == base.compile(\"api\")
stub = VibeWorkflow(\"s\", WorkflowSource(\"s\"))
stub.nodes[\"1\"] = VibeNode(\"1\", \"SaveImage\", uid=\"u\", metadata={\"_ui\": {\"pos\": [900,900], \"size\": [999,999]}}, pos=[10.0,20.0], size=None)
node = next(n for n in emit_ui_json(stub)[\"nodes\"] if n[\"id\"] == 1)
assert node[\"pos\"] == [0.0,0.0] and node[\"size\"] == [320.0,30.0], node
print(\"in-memory geometry checks: PASS\")'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 228ms:
compute_layers: 1 uid(s) not reached by SCC/longest-path walk; assigned layer 0: u
<string>:45: UserWarning: emit_ui_json: schema-less node 1(SaveImage); emitting best-effort slots. Pass strict=True to hard-fail.
in-memory geometry checks: PASS

exec
/bin/zsh -lc "nl -ba vibecomfy/porting/layout_store.py | sed -n '80,120p'; nl -ba vibecomfy/porting/layout_store.py | sed -n '260,295p'; nl -ba vibecomfy/porting/emit/ui.py | sed -n '2440,2505p'; nl -ba vibecomfy/porting/convert.py | sed -n '410,485p'" in /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle2
 succeeded in 0ms:
    80	    return py_path.with_suffix(".layout.json")
    81	
    82	
    83	def _vibecomfy_version() -> str:
    84	    try:
    85	        from importlib.metadata import PackageNotFoundError, version
    86	
    87	        try:
    88	            return version("vibecomfy")
    89	        except PackageNotFoundError:
    90	            return "0"
    91	    except Exception:
    92	        return "0"
    93	
    94	
    95	def _build_entry(ui: dict) -> dict[str, Any]:
    96	    """Build a per-uid entry from a node's captured ``_ui`` blob.
    97	
    98	    ``pos`` is canonicalized (T3) so repeated round-trips are idempotent and
    99	    bit-stable. ``size`` is canonicalized when present.
   100	    """
   101	    entry: dict[str, Any] = {"pos": snap_pos(ui["pos"])}
   102	    size = ui.get("size")
   103	    entry["size"] = snap_size(size) if size is not None else None
   104	    entry["flags"] = ui.get("flags")
   105	    entry["color"] = ui.get("color")
   106	    entry["bgcolor"] = ui.get("bgcolor")
   107	    mode = ui.get("mode")
   108	    entry["mode"] = mode if isinstance(mode, int) else 0
   109	    properties = ui.get("properties")
   110	    entry["properties"] = properties if isinstance(properties, dict) else {}
   111	    return entry
   112	
   113	
   114	def _iter_subgraph_defs(definitions: Any) -> Iterable[dict]:
   115	    """Yield individual subgraph definition dicts from a ``definitions`` blob.
   116	
   117	    Tolerant of the shapes ComfyUI emits: ``{"subgraphs": [...]}``, a plain
   118	    ``{uuid: def}`` mapping, a single def dict (has its own ``nodes``), or a
   119	    bare list of defs.
   120	    """
   260	    The frozen M1.5 sidecar was a flat
   261	    ``{"layout_version": 1, "nodes": {uid: {pos, size, ...}}}``. This lifts each
   262	    v1 node into a per-uid envelope ``entry`` (preserving pos/size, canonicalized
   263	    via T3 snapping, plus any flags/color/bgcolor/properties present). Data that
   264	    is already a v2 envelope — or an unrecognized shape — is returned unchanged
   265	    (no-op), so the function is safe to invoke unconditionally on load.
   266	    """
   267	    if not isinstance(data, dict):
   268	        return data
   269	    if data.get("store_version") == STORE_VERSION:
   270	        return data
   271	    if data.get("layout_version") != 1:
   272	        return data
   273	
   274	    nodes = data.get("nodes")
   275	    entries: dict[str, dict] = {}
   276	    if isinstance(nodes, dict):
   277	        for uid, node in nodes.items():
   278	            if not isinstance(node, dict):
   279	                continue
   280	            pos = node.get("pos")
   281	            size = node.get("size")
   282	            properties = node.get("properties")
   283	            mode = node.get("mode")
   284	            entries[str(uid)] = {
   285	                "pos": snap_pos(pos) if pos is not None else None,
   286	                "size": snap_size(size) if size is not None else None,
   287	                "flags": node.get("flags"),
   288	                "color": node.get("color"),
   289	                "bgcolor": node.get("bgcolor"),
   290	                "mode": mode if isinstance(mode, int) else 0,
   291	                "properties": properties if isinstance(properties, dict) else {},
   292	            }
   293	
   294	    return {
   295	        "store_version": STORE_VERSION,
  2440	        if verdict.pin_opaque and _exec_io_for_node(node) is None:
  2441	            incoming_link_ids_by_input: dict[str, list[int]] = defaultdict(list)
  2442	            for edge in edges_to[node_id]:
  2443	                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
  2444	                incoming_link_ids_by_input[edge.to_input].append(lid)
  2445	            outgoing_link_ids_by_slot: dict[int, list[int]] = defaultdict(list)
  2446	            for edge in edges_from[node_id]:
  2447	                slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
  2448	                lid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
  2449	                outgoing_link_ids_by_slot[slot].append(lid)
  2450	            pinned = _raw_ui_payload_for_pin(
  2451	                verdict.raw_ui_node or {},
  2452	                node_id=node_id,
  2453	                class_type=node.class_type,
  2454	                canonical_uid=node.uid,
  2455	                litegraph_node_id=id_remap[node_id],
  2456	                order=order,
  2457	                incoming_link_ids_by_input=incoming_link_ids_by_input,
  2458	                outgoing_link_ids_by_slot=outgoing_link_ids_by_slot,
  2459	            )
  2460	            # The pinned raw copy comes from raw UI evidence and may lack mode;
  2461	            # stamp the same IR-authoritative mode used by compilation.
  2462	            pinned["mode"] = _resolve_furniture(node, matched_entries.get(key))["mode"]
  2463	            nodes.append(pinned)
  2464	            continue
  2465	        matched_entry = matched_entries.get(key)
  2466	        # T9b: reconcile-driven merge.
  2467	        #   matched → verbatim pos/size/flags/color/properties/group/title from the entry;
  2468	        #             mode remains IR-authoritative.
  2469	        #   else    → engine_positions (already incorporates anchors / pinning), else _stub.
  2470	        if matched_entry is not None:
  2471	            geometry = (
  2472	                _extract_geometry(matched_entry)
  2473	                or engine_positions.get(node.uid)
  2474	                or _stub_layout(order)
  2475	            )
  2476	            furniture = _resolve_furniture(node, matched_entry)
  2477	        else:
  2478	            # Unmatched (new / unmatched_legacy / removed-then-readded).
  2479	            # First-class node geometry is the direct-ingest source of truth; the
  2480	            # engine owns geometry only when no complete captured pair exists.
  2481	            geometry = (
  2482	                _captured_geometry(node)
  2483	                or engine_positions.get(node.uid)
  2484	                or _stub_layout(order)
  2485	            )
  2486	            furniture = _resolve_furniture(node, None)
  2487	        schema = schema_cache.get(node.class_type)
  2488	        schema_outputs = list(getattr(schema, "outputs", None) or []) if schema else []
  2489	        exec_io = _exec_io_for_node(node)
  2490	
  2491	        # --- outputs list ---
  2492	        outputs: list[dict[str, Any]] = []
  2493	        # Build a set of (from_output_val) → links for this node from edges
  2494	        output_links_by_slot: dict[int, list[int]] = defaultdict(list)
  2495	        for edge in edges_from[node_id]:
  2496	            slot, _ = _resolve_output_slot_and_type(edge.from_output, node.class_type, schema_cache)
  2497	            eid = link_id_map[(edge.from_node, edge.from_output, edge.to_node, edge.to_input)]
  2498	            output_links_by_slot[slot].append(eid)
  2499	
  2500	        if exec_io is not None:
  2501	            outputs = _exec_dynamic_outputs(exec_io, output_links_by_slot)
  2502	        elif schema_outputs:
  2503	            for slot_idx, out_spec in enumerate(schema_outputs):
  2504	                link_list = sorted(output_links_by_slot.get(slot_idx, []))
  2505	                outputs.append({
   410	            except Exception:
   411	                # Alias collection is best-effort conversion evidence, not a
   412	                # parity failure. Keep this out of the loud parity-error path
   413	                # unless focused schema-provider tests prove it masks a bug.
   414	                pass
   415	
   416	    result = PortConvertResult(mode=mode, text=text, ready_id=ready_id)
   417	    if validate:
   418	        result.validation = validate_emitted_module(text, schema_provider=schema_provider)
   419	        result.validation.emission_diagnostics = emission_diagnostics
   420	        if ready_id is not None and result.validation is not None:
   421	            _run_strict_ready_candidate_validation(
   422	                result.validation,
   423	                text,
   424	                ready_id=ready_id,
   425	                source_path=source_path,
   426	                schema_provider=schema_provider,
   427	            )
   428	
   429	        # Run parity: compile the emitted module and compare against source.
   430	        if source_api is not None and result.validation is not None and result.validation.compile_ok:
   431	            try:
   432	                with tempfile.TemporaryDirectory(prefix="vibecomfy-port-parity-") as tmp:
   433	                    parity_path = Path(tmp) / "emitted_parity.py"
   434	                    parity_path.write_text(text, encoding="utf-8")
   435	                    spec = importlib.util.spec_from_file_location(
   436	                        f"vibecomfy_port_parity_{parity_path.stem}", parity_path
   437	                    )
   438	                    if spec is not None and spec.loader is not None:
   439	                        module = importlib.util.module_from_spec(spec)
   440	                        spec.loader.exec_module(module)
   441	                        build_fn = getattr(module, "build", None)
   442	                        if callable(build_fn):
   443	                            emitted_wf = build_fn()
   444	                            if isinstance(emitted_wf, VibeWorkflow):
   445	                                emitted_api = emitted_wf.compile("api")
   446	                                parity_ok, parity_diffs = compile_equivalent(
   447	                                    source_api, emitted_api,
   448	                                    class_widget_aliases=class_widget_aliases,
   449	                                )
   450	
   451	                                result.validation.parity_ok = parity_ok
   452	                                result.validation.parity_diffs = parity_diffs
   453	
   454	                                # Output counts
   455	                                result.validation.source_output_count = len(source_api)
   456	                                result.validation.emitted_output_count = len(emitted_api)
   457	
   458	                                # Class type snapshots
   459	                                src_ct = class_type_counter(source_api)
   460	                                emit_ct = class_type_counter(emitted_api)
   461	                                result.validation.source_class_type_counts = dict(src_ct)
   462	                                result.validation.emitted_class_type_counts = dict(emit_ct)
   463	
   464	                                # Widget value snapshots (distinct count)
   465	                                src_wv = widget_value_counter(source_api)
   466	                                emit_wv = widget_value_counter(emitted_api)
   467	                                result.validation.source_widget_value_snapshot = len(src_wv)
   468	                                result.validation.emitted_widget_value_snapshot = len(emit_wv)
   469	
   470	                                # Topology snapshots (distinct count)
   471	                                src_topo = topology_counter(source_api)
   472	                                emit_topo = topology_counter(emitted_api)
   473	                                result.validation.source_topology_snapshot = len(src_topo)
   474	                                result.validation.emitted_topology_snapshot = len(emit_topo)
   475	
   476	                                # -- model-like value comparison (T8) --------
   477	                                _run_model_value_comparison(
   478	                                    result.validation,
   479	                                    source_api,
   480	                                    emitted_api,
   481	                                    workflow,
   482	                                    ready_id=ready_id,
   483	                                )
   484	            except Exception as exc:
   485	                parity_error = f"{type(exc).__name__}: {exc}"

codex
PASS — no substantive Batch C issues.

Confirmed:

- UI/API ingest mints detached, finite `node.pos`/`node.size`; malformed or absent geometry becomes `None` while raw `_ui` is retained.
- Envelope decoding independently falls back to legacy `_ui`; present first-class values—including explicit `None`—win.
- All six targeted geometry descents use first-class fields. Reconcile’s non-geometry `_ui` hash access remains unchanged.
- Lowering copies `mode`, `pos`, and `size`.
- Missing size still reaches stub layout.
- Deep-copy and compile geometry-invariance checks pass.
- Virtual wires, sidecar handling, reconciliation, and coordinate canonicalization remain consistent.
- No corpus files were regenerated.

The Batch C commit itself has 16 changed files and passes `diff --check`. The literal requested range additionally contains checkpoint commit `5795812e` with `.oracle` bookkeeping; its transcript has trailing whitespace, but this is not part of Batch C’s product/test diff.

Full pytest could not start in the read-only oracle sandbox because no writable temporary directory exists. In-memory geometry checks passed; the host-verified focused suite remains valid.
tokens used
101,586
PASS — no substantive Batch C issues.

Confirmed:

- UI/API ingest mints detached, finite `node.pos`/`node.size`; malformed or absent geometry becomes `None` while raw `_ui` is retained.
- Envelope decoding independently falls back to legacy `_ui`; present first-class values—including explicit `None`—win.
- All six targeted geometry descents use first-class fields. Reconcile’s non-geometry `_ui` hash access remains unchanged.
- Lowering copies `mode`, `pos`, and `size`.
- Missing size still reaches stub layout.
- Deep-copy and compile geometry-invariance checks pass.
- Virtual wires, sidecar handling, reconciliation, and coordinate canonicalization remain consistent.
- No corpus files were regenerated.

The Batch C commit itself has 16 changed files and passes `diff --check`. The literal requested range additionally contains checkpoint commit `5795812e` with `.oracle` bookkeeping; its transcript has trailing whitespace, but this is not part of Batch C’s product/test diff.

Full pytest could not start in the read-only oracle sandbox because no writable temporary directory exists. In-memory geometry checks passed; the host-verified focused suite remains valid.
2ddd1f06 PASS — Batch C (first-class geometry)
