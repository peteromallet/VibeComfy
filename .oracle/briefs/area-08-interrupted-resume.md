Explore area: Interrupted-run recovery for the live harness runner.

Context: the runner (tests/live_agentic_harness/runner.py) writes partial summaries but reportedly has no safe resume mechanism. A configuration-hash-guarded resume should be explored ONLY if operational evidence shows rerunning a long interrupted lane would be costly; do not build speculatively.

Task: inspect the runner's summary persistence (run_summary.json writing, per-scenario attempt dirs, --tag, concurrency, infra retry), whether partial state survives a killed run, whether a resume would be safe/valuable, and the cost of a full rerun (100 scenarios × typical per-scenario runtime). Report verified facts with file:line, whether resume is warranted, unknowns, risks, and a minimal design if warranted (config hash, which state to skip/reuse). Ranked findings, <300 words.
