# VibeComfy Agentic Embedding

This directory contains the Sisypy agentic-test harness for VibeComfy.
It was established in M1 (embedding foundation) and is consumed by M2–M6.

## Quick start

```bash
# Run the chaining family in structural (no-GPU) mode with the fake actor:
python -m agentic.runner --mode structural --actor fake --tag run
```

## Layout

```
agentic/
  __init__.py        Package init
  adapter.py         VibeComfyProjectAdapter (extends FakeProjectAdapter)
  runner.py          Scenario runner: load YAML, dispatch actors, freeze evidence
  scenarios/         Scenario YAML files (one per user ask)
  briefs/            User-shaped markdown briefs (referenced by scenario YAML)
  README.md          This file
```

Evidence packs land in `out/agentic/reports/<tag>/`.

## How to add a scenario

1. Write a user-shaped brief in `agentic/briefs/<name>.md`.
2. Create a scenario YAML in `agentic/scenarios/<name>.yaml` referencing the brief.
3. Define `assessment.enforced`, `assessment.graded`, and `assessment.observed` rubric
   items anchored to frozen evidence (compiled API JSON, metadata.json, file existence,
   or action logs) — **never** to `report.md` narrative.
4. Run the scenario: `python -m agentic.runner --name <name>`.
5. Verify the evidence pack in `out/agentic/reports/<tag>/`.

## Metadata contract

### `entrypoint` / `layer` stamping

At the ops/blocks/patches boundary, VibeComfy stamps `workflow.metadata` with:

- `entrypoint`: `"op"`, `"block"`, or `"patch"` (identifies how the workflow graph was produced)
- `layer`: e.g. `"ops/image.py:t2i"`, `"ops/video.py:i2v"` (identifies the specific authoring layer)

These use first-writer-wins (set-if-absent) semantics. The runtime metadata writer
(``vibecomfy/runtime/session.py::_run_metadata``) reads these fields from workflow metadata
and copies them into `out/runs/<id>/metadata.json`.

### `chain_id` / `parent_run_id`

Multi-stage chains (like image→video) thread linkage through the runtime:

- `chain_id`: shared across all stages in the chain
- `parent_run_id`: the `run_id` of the immediately preceding stage

These flow through `Artifact.run(..., chain_id=..., parent_run_id=...)` →
`run_sync` / `run_embedded_sync` → `_run_metadata` → `RunResult`.

### `patch_applications`

When a workflow goes through the canonical `Patch.apply()` boundary, runtime metadata
copies `workflow.metadata["patch_applications"]` into `metadata.json` as additive
telemetry for structural grading.

- `called=true` means the patch boundary was invoked, even if the graph stayed unchanged.
- `layer="patch"` identifies the metadata entry as coming from the patch layer.
- `topology_changed=true` means the patch rewired or extended the graph.
- `introduced_edges` lists newly-added connections.
- `rewritten_edges` lists replaced connections, including the previous source and new source.
- No-op patch calls still emit an entry with `called=true` and `topology_changed=false`.

This lets scenarios distinguish "the actor called the canonical patch" from
"the patch materially changed the workflow."

## Evidence pack shape

Each evidence pack under `out/agentic/reports/<tag>/<scenario>/` contains:

| File | Content |
|---|---|
| `report.md` | Actor narrative (never used for proof) |
| `stdout.txt` | Captured stdout |
| `stderr.txt` | Captured stderr |
| `command_log.json` | Commands executed |
| `actions.jsonl` | Structured action log |
| `evidence/` | Frozen evidence files (compiled API JSON, metadata, output paths) |
| `tree_before.txt` / `tree_after.txt` | Directory snapshots |
| `git_diff.txt` | Git diff |

## Faking actor guard

`--actor faking` produces plausible narrative but intentionally omits frozen evidence
anchors. The enforced checks MUST fail the faking actor even if `report.md` claims success.
This guard proves the harness discriminates narrative from evidence.

## Evidence-vs-narrative falsification results

The harness classifies success from **frozen evidence only** (compiled API JSON,
metadata JSON, actions.jsonl, and output files). `report.md` is never used for
pass/fail decisions. The adversarial test suite proves the following invariants:

| Test | Action | Expected result | Verified? |
|---|---|---|---|
| `report.md` removal | Delete `report.md` while keeping all required evidence | Pass (COMPILED or VALIDATED) | ✅ |
| `report.md` lies | Write "FAILED" in `report.md` while evidence is complete | Pass (COMPILED or VALIDATED) | ✅ |
| Missing compiled API | Remove `stage1/compiled_api.json` but keep a glowing `report.md` | Fail (AUTHORED) | ✅ |
| Missing metadata | Remove `stage2/metadata.json` with `report.md` present | Fail (AUTHORED) | ✅ |
| Faking actor | Run `--actor faking` with only `report.md` + stdout/stderr | Fail (AUTHORED) | ✅ |

**Key design rule:** Rubric items in `assessment.enforced`, `assessment.graded`,
and `assessment.observed` must be anchored to frozen evidence files — **never**
to narrative text in `report.md`. If a check can be satisfied by editing
`report.md` alone, it is not an evidence-based check and must be rewritten.

## Handoff for M2–M6

- **M2 (discovery & limits):** Add negative scenarios proving the actor recognizes unwired
  ops and missing templates. The adapter dispatches structural scenarios through the
  `_M2_BUILDERS` dict (a mapping of scenario slug → builder function in `adapter.py`).
  Each scenario YAML declares `extras.required_frozen_evidence` — the exact set of frozen
  evidence files the harness must find for a COMPILED or VALIDATED classification. The
  faking actor guard (`_capture_structural_evidence` → `build_faking_structural_chain`)
  deliberately produces only `report.md`, `stdout.txt`, `stderr.txt` — omitting all frozen
  evidence anchors — so the faking actor always achieves at most AUTHORED, proving the
  harness discriminates narrative from evidence. The `project_universal_checks` hook
  reports missing required evidence as a hard error, and `classify_success` returns
  AUTHORED when any required frozen evidence is absent.
- **M3 (compose correctly):** Add block-based composition scenarios. The `entrypoint=block`
  marker will already be stamped. Scenario `#8` (`add-depth-controlnet-image`) proves
  positive image composition by requiring both the ControlNet topology rewrite and the
  controlnet patch marker in metadata. Scenario `#9` (`controlnet-video-noop`) is the
  companion no-op case: the action log must explicitly acknowledge `patch.apply` as
  `status=no_effect`, and metadata may still show a `patch_applications` entry with
  `called=true` plus `topology_changed=false`. Scenario `#12`
  (`add-save-node-finalize`) covers the finalize trap: the builder must add the save
  node and call `wf.finalize_metadata()` so `metadata.json.requirements.models` is
  non-empty before grading.
- **M4 (diagnose & recover):** Extend the recovery pattern established in scenario #4.
- **M5 (remote GPU):** Add `mode=live` scenarios with runpod lifecycle capture.
  The `prime()` and `capture()` adapter hooks are the integration points.
- **M6 (robustness backbone):** Add adversarial scenarios and expand `project_universal_checks`.
