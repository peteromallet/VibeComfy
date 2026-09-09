# Scripts

Repository-local operational scripts. These are normally run from the repository
root as direct paths:

```bash
uv run python scripts/<name>.py --help
```

Use `scripts/` for direct-run helpers, RunPod harnesses, local debugging, smoke
checks, shell loops, and one-off maintenance. Use `tools/` instead for importable
developer tools that are meant to run as `python -m tools.<name>`.

## RunPod

| Script | Purpose |
|---|---|
| `runpod_runner.py` | Shared RunPod pod, shipping, and artifact helpers. |
| `runpod_acceptance.py` | Retired fail-closed placeholder; exits before provisioning or executing a payload. |
| `runpod_validate.py` | Live remote smoke launcher; requires RunPod credentials, network, and a GPU. |
| `runpod_corpus_matrix.py` | Live remote corpus/ready-template matrix launcher; requires network, dependencies, and GPU capacity. |
| `runpod_e2e_matrix.py` | End-to-end RunPod matrix wrapper used by CI. |
| `runpod_matrix_plan.py` | Matrix planning and manifest helpers. |
| `runpod_matrix_remote.py` | Remote workflow preparation and compatibility patches. |
| `runpod_model_matrix.py` | Model-focused RunPod matrix runner. |
| `runpod_artifacts.py` | Artifact download and summary helpers used by RunPod scripts. |

## Agent / Editor

| Script | Purpose |
|---|---|
| `agentic_success_rate.py` | Agentic-evaluation success-rate harness. |
| `run_local_agent_comfy.sh` | Starts a local agent-edit ComfyUI session. |
| `sync_agent_skill.py` | Checks the canonical skill in `docs/agent-skill/` and installs it into local agent harnesses. |
| `vibecomfy_debug.py` | Debug helper for agent-edit sessions. |
| `_agent_edit_prompt_dump.py` | Private prompt-dump helper. |

## Maintenance / Smoke

| Script | Purpose |
|---|---|
| `warm_session_smoke.py` | Runtime warm-session smoke helper. |
| `demo_wrapper_codegen.py` | Wrapper codegen demonstration script. |
| `roundtrip_fidelity_spike.py` | Round-trip fidelity spike. |

## Megaplan / Local Ops

| Script | Purpose |
|---|---|
| `megaplan_cloud_operator_loop.sh` | Megaplan cloud operator loop. |
| `megaplan_cloud_recovery_loop.sh` | Megaplan cloud recovery loop. |
| `patch_shannon_unattended_root.sh` | Local operator patch helper used by the cloud loops. |
