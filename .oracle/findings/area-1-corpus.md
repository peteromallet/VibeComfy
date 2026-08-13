# Area 1 — Corpus ownership
- Worktree has NO external_workflows/ (not symlinked). Corpus lives only in main checkout: 1.0G total, corpus/ 466M (2799 *.json + 2 *.layout.json sidecars), manifest.json 9.9MB/2798 rows. Fully gitignored (line 26) in both checkouts; git ls-files shows only 4 tracked files (2 scripts + 2 tests).
- Scripts resolve REPO_ROOT=Path(__file__).resolve().parents[1]: ingest/upload write in place under REPO_ROOT/external_workflows (worktree run creates a FRESH empty corpus there, does NOT touch main's); check_b02 default 'external_workflows/corpus' is CWD-relative and READ-ONLY.
- check_b02 VACUOUSLY PASSES on empty/missing dir (ok=True, workflows=0). test_b02_rich_preservation.py calls check_corpus() with default path, no env skip — would silently pass in the worktree.
- Regeneration must run against the main checkout's corpus (explicit --corpus-dir / run in main), and CI assertion needs a pinned hydration artifact (or explicit corpus-dir arg); never allow the assertion to skip when absent.
- Ingest is idempotent by canonical hash; filenames canonical_hash[:16].json.
