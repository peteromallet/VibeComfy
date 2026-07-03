# Agent Skills

This directory is the single authored source for the VibeComfy package agent
skills.

- Edit the umbrella `SKILL.md` here. Keep it short: routing, core rules, and first moves.
- Put dense API notes, command catalogs, RunPod env, and durable-template reference material in `REFERENCE.md`.
- Edit auxiliary package skills under `skills/<name>/SKILL.md`.
- Do not add root `AGENTS.md`, `CLAUDE.md`, or tracked `.claude/` copies.

After editing skills, copy/paste this from the repo root:

```bash
python scripts/sync_agent_skill.py --apply
python scripts/sync_agent_skill.py --install-user
pytest -q tests/test_agent_skill_sync.py
```

`--install-user` symlinks this directory and its auxiliary skills into local
Claude, Codex, and Hermes skill directories. Sync is package maintenance, not a
separate agent skill.

Use the `vibecomfy ...` console entrypoint in skill examples. If an editable
checkout has not installed console scripts, use the equivalent fallback:
`python -m vibecomfy.cli ...`.

## Package Skills

| Skill | Underlying runnable surface | Status |
|---|---|---|
| `vibecomfy-setup` | `vibecomfy config init/show/set-library`, `vibecomfy runtime doctor`, `vibecomfy nodes ensure`, `vibecomfy models stage`, `vibecomfy fetch` | Available. Ask whether to use installed/importable ComfyUI, the user's own ComfyUI path, or an existing server URL; ask about custom nodes/models only when local staging or embedded execution needs them. |
| `search-comfy-workflows` | `vibecomfy search ...`; Hivemind raw HTTP | Local search and raw Hivemind HTTP are available. Astrid executor use may require a bound Astrid project. |
| `explain-comfy-workflow` | `vibecomfy inspect`, `vibecomfy analyze info`, `vibecomfy port check`, `vibecomfy nodes spec` | Available. Answers workflow questions from evidence without editing or running unless the user asks. |
| `reorganise-comfy-workflow` | `vibecomfy reorganise ...`; `/reorganise_comfy_workflow`; `route="reorganise"` | Available for explicit layout-only cleanup. Preview is deterministic and offline by default; apply is preview-first and refuses stale source graphs before writing the exact previewed candidate. |
| `edit-comfy-workflow` | `vibecomfy port check`, `vibecomfy port convert`, Python `VibeWorkflow`, `vibecomfy validate`, `vibecomfy doctor` | Available. |
| `run-comfy-workflow` | `vibecomfy run ...` | CLI exists. Embedded local runs require a discoverable ComfyUI root and `comfy` module; server and RunPod paths are separate runtime options. |
| `debug-comfy-workflow` | `vibecomfy doctor`, `vibecomfy port doctor-all`, `vibecomfy inspect`, `vibecomfy analyze`, logs/runtime doctor | Available. |
| `add-comfy-workflow-template` | source JSON + manifest + `vibecomfy port check` + `vibecomfy port convert --ready-id` + tests | Available as a procedural template-addition workflow. |
