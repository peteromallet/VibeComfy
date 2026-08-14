# Is there a distilled/faster way to run?

The user wants to know if there is a distilled or faster way to run
AnimateDiff-based video generation workflows in ComfyUI.

Run the canonical VibeComfy executor entrypoint,
`vibecomfy.executor.core.run_executor`, for the query
"is there a distilled/faster way to run?". Build an `ExecutorRequest` and
freeze the returned `ExecutorResult` as `evidence/executor_result.json`.

Also freeze `evidence/executor_report.json` and the deterministic research
evidence as `evidence/research.json` (scoped query + forwarded source tier
tuple). Record `actions.jsonl` entries showing the executor ran and that
research ran through the deterministic research phase (never the agent-edit
batch gate).

The goal is to prove the research route scopes deterministic research from the
classifier's triage fields, and that the focused query in `research.json` uses
domain anchors rather than generic words from the raw sentence.
