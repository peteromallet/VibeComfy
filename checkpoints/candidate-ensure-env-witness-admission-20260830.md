# Ensure-env witness admission — 2026-08-30

- Candidate: `/tmp/vc-final-latest5-20260830`
- Candidate commit: `04a05813506e17386550dcbd4dff9d9299e2bcba`
- Exact parent/base: `cb51f4e0ccaa26c6eac5ff39e46796354a75894b`
- Independent witness source tip: `891f6b4f6faa1375abea4689fca18c0436764859`
- Witness campaign report: `reviews/luna-ensure-env-witness-891f6b4f-independent.md`

The cumulative base..tip tree was admitted as one single-parent squash. Only
these four source/test files were changed, and each candidate blob matches the
source tip exactly:

- `tests/test_runtime_ensure_env.py`
- `vibecomfy/node_packs/__init__.py`
- `vibecomfy/node_packs/_install.py`
- `vibecomfy/runtime/ensure_env.py`

The rejected witness commits `fbc16d2cfc12b50d0427fb5f440317b1ed6addb2` and
`891f6b4f6faa1375abea4689fca18c0436764859` are not ancestors of the candidate.
The candidate worktree is clean; no receipt, review, or rejected-history
artifacts were admitted.

Verification:

- `tests/test_runtime_ensure_env.py`: **27 passed**.
- Neighbor gate (node-pack Git + resolver + six object-info authority tests): **81 passed**.
- Bounded interaction selections: registry **20 passed**, object-info **17 passed**, runtime **19 passed**, HTTP authorization/mutation **25 passed**.
- Compileall for the four changed files: passed.
- Ruff F-only and Ruff with pre-existing E401/E701/E702 exclusions: passed.
- Full Ruff reports 30 pre-existing E401/E701/E702 findings in `vibecomfy/node_packs/_install.py`; this admission does not alter them.
- The selected HTTP route-inventory check has an unrelated existing failure for duplicate `POST /vibecomfy/roundtrip`; the authorization/mutation subset passes.
