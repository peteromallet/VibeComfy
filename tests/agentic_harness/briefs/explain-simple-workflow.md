# Explain: what does this workflow do?

The user has loaded a simple text-to-image ComfyUI workflow and asks:
"What does this workflow do?"

Run the canonical VibeComfy executor entrypoint,
`vibecomfy.executor.core.run_executor`, with an `ExecutorRequest` that includes
the fixture graph at `tests/fixtures/agent_edit/flat.json`.

Freeze the returned `ExecutorResult` as `evidence/executor_result.json`, freeze
`evidence/executor_report.json`, and freeze the graph inspection artifact as
`evidence/graph_report.txt` for readability. Record `actions.jsonl`
entries showing the executor ran and reached the canonical `inspect` route
(implement=False, route=inspect) — graph explanations must not invoke the edit
implementation path.

The executor reply/report should be thorough enough that a reader can identify
the key nodes (CheckpointLoaderSimple, CLIPTextEncode, EmptyLatentImage,
KSampler, VAEDecode, SaveImage) and the overall data flow. Structural/fake runs
must be deterministic and avoid live model calls.
