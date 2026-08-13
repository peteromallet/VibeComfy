Explore area: Artifact portability for the final report.

Context: the final B09 report must be reproducible from persisted evidence. The latest live evidence and the external workflow corpus live outside this worktree (external_workflows/ is gitignored). The report needs source hashes and stable references.

Task: check what's available for pinning: scenario corpus files (tests/live_agentic_harness/scenarios/), external_workflows corpus location + availability (is it on disk? at what path? how many files?), existing run summaries (out/agentic/*/run_summary.json), any manifest/hash infrastructure (scripts/, D13 manifest references), and how the B02 preservation checker (scripts/check_b02_rich_preservation.py) pins corpus hashes. Report verified facts, what a reproducible pin would need, unknowns, risks, suggested approach for the B09 preflight + report references. Ranked findings, <300 words.
