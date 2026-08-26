I'll read the full run contract and the settled-plan findings, then re-verify against the attempt-3 persist-index fix.I'll read the three settled-plan findings and spot-check the persist/index claims at HEAD.I'll spot-check serialize merge, preflight, extract, and ensure so the persist-index and r3-deferred claims hold.**1. Mixed-pack persist still duplicates runtime class R inside the on-demand pack file (checks 2, 4).**

Attempt-3 only post-processes `index.json` (`plan.md:64`). `build_cache(..., full_pack_refresh=False)` still merge-copies every same-pack class into the new file (`serialize.py:327–333`, then dump at `:223–225`). C extracts the whole pack (`only_classes` omitted, `extract.py:742`; C 3.3). After drop-higher-tier + merge, `Pack@on_demand_*` contains runtime R with the **same** `pack_slug`/`git_commit`/`evidence_identity` as the `@runpod-snapshot` file.

`get_class` is index-safe after the restore. Identity lookup is not: `_all_pack_filenames` globs every `*.json` (`consume.py:193–200`), so `get_class_by_identity(R)` raises `ObjectInfoIdentityAmbiguityError` (`consume.py:377–382`). That is a reproducible runtime-capture break, not a silent index remap.

Checkpoint A’s “on_demand file does not silently shadow R” is not oracle-checkable (no assertion that on-demand keys == `{G}`, or that identity lookup for R stays unique). Index-only hygiene does not close the mixed-pack hole.

**Required before freeze:** after `build_cache`, strip non-new classes from the new pack file; Checkpoint A must assert on-demand keys == `{G}` and `get_class_by_identity(R)` uniquely returns the runtime entry.
