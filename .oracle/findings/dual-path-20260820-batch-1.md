# Dual-path live failures — 2026-08-20

Run evidence:

- Four-mode comparator: `/private/tmp/vibecomfy-dualpath-four-run-20260820-r3/comparison.json`
- Preserved audio pair: `/private/tmp/vibecomfy-dualpath-five-run-20260820-r2/`
- Locked inputs matched for every staged/threaded pair.

## Findings

1. **CLASS: judge_fail — shared authority replay mismatch.** All five generated edit candidates were rejected before final projection. Qwen accepted `widget_0` although its frozen witness exposes `prompt`; direct replay rejects positional fields. Audio similarly accepted positional `widget_5`/`widget_6`/`widget_7` because the touched IndexTTS schema was absent. Threaded multi-video targeted named `prompt`, but the touched LayerMask schema was absent. Authority correctly failed closed with `authority_replay_mismatch`; artifact synthesis correctly kept `final.ui.json` equal to original.
2. **CLASS: judge_fail — threaded research short-circuit.** The classifier-free threaded planner maps every non-`answer_only` request to `adapt/edit`. The no-graph speed-research request exits before any agent call with `No graph attached; implementation skipped.` The health-control assessment has no research-evidence requirement, so zero calls/evidence passed.
3. **CLASS: judge_fail — staged inspect contradiction.** The request and current `inspect_graph()` contain three nodes/three edges, but staged prose claims an empty graph. The exact reply prompt is not persisted and there is no semantic postcondition rejecting an empty-graph claim against a non-empty census.
4. **CLASS: incomplete — staged research/protocol amplification.** Research allows unlimited turns/calls inside a 450-second wall deadline. Multi-video made 37 research calls with repeated Hivemind timeouts, then handed a very large context to implementation. After one protocol correction, the model emitted multiple `batch` fences; the atomic turn correctly aborted.

## Required repair properties

- Canonical accepted deltas must use render-visible named fields before authority replay.
- Touched custom-node schemas must be present in the frozen witness or the candidate must be rejected before narration.
- Threaded and staged must share request, edit, authority, evidence, and assessment contracts; only deliberation policy may differ.
- A research pass must require actual research evidence; an inspect pass must contradict neither the graph census nor topology.
- Research/tool and malformed-protocol retries must be bounded deterministically.

