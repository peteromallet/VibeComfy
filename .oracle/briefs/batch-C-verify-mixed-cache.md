# VERIFY — mixed-pack + committed-cache mutation (read-only)

You are ox-alpha probing Batch C at HEAD `5f3e635f` in
`/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle`.
Do NOT edit source. Do not commit. You MAY run pytest and inspect git.

Executor claimed: running `tests/test_schemas_ensure.py` rewrites committed
`vibecomfy/porting/cache/object_info/index.json` (strips trailing newline).
Tests MUST use tmp dirs. If they mutate the committed cache, that is a finding.

## 1. Cache mutation probe (do this first)

```
cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle
git status --porcelain vibecomfy/porting/cache
git diff --stat HEAD -- vibecomfy/porting/cache
python3 -c "from pathlib import Path; p=Path('vibecomfy/porting/cache/object_info/index.json'); b=p.read_bytes(); print('exists',p.exists(),'size',len(b),'endswith_nl',b.endswith(b'\\n'),'sha',__import__('hashlib').sha256(b).hexdigest())"
```

Then run ONLY:
```
python3 -m pytest tests/test_schemas_ensure.py -q --tb=line
```

Immediately after:
```
git status --porcelain vibecomfy/porting/cache
git diff --stat HEAD -- vibecomfy/porting/cache
python3 -c "from pathlib import Path; p=Path('vibecomfy/porting/cache/object_info/index.json'); b=p.read_bytes(); print('exists',p.exists(),'size',len(b),'endswith_nl',b.endswith(b'\\n'),'sha',__import__('hashlib').sha256(b).hexdigest())"
git diff HEAD -- vibecomfy/porting/cache/object_info/index.json | head -40
```

If the cache is dirty: restore with `git checkout -- vibecomfy/porting/cache` after capturing evidence (do not leave dirt).

Inspect `tests/test_schemas_ensure.py` (new TestSchemasEnsureCommand and helpers) and `vibecomfy/commands/schemas.py` `_cmd_schemas_ensure` / persist path:
- Do tests monkeypatch cache dir / VIBECOMFY_* / `object_info` cache root to tmp?
- Does `_cmd_schemas_ensure` or `persist_on_demand_pack` default to the committed cache when the patch is incomplete?
- Does `reset_cache()` or `build_cache` rewrite `index.json` as a side effect even when targeting tmp?

Cite file:line.

## 2. Mixed-pack through the CLI ensure path

Batch A mixed-pack contract (still required of C glue):
cache has runtime capture for class R of pack P; ensure extracts P (R + gap G).
Assert: on_demand file keys == {G}; index[R] stays runtime file; index[G] maps to on_demand; get_class_by_identity(R) unique.

Does Batch C `_capture_missing_classes` / `_cmd_schemas_ensure` call `persist_on_demand_pack` (Batch A) so mixed-pack hygiene still applies? Or does it write a whole-pack file / use `full_pack_refresh=True` / `clone_and_extract_packs`?

If there is no C-level mixed-pack test, say so. Then either:
- run existing `tests/test_ensure_capture.py` mixed-pack test and quote it, AND
- read the C glue and state whether a mixed-pack ensure would still be safe.

Optional: construct a tmp-cache probe if cheap (no network): seed runtime file+index for R, stub/missing G, call persist or ensure with mocked extract of {R,G}.

## Return (max 400 words)

- Cache mutation: YES/NO. Before/after sha, git porcelain, whether you restored.
- Root cause file:line if YES.
- Mixed-pack: SAFE / UNSAFE / UNTESTED-BUT-DELEGATES with evidence.
- Findings list (empty if none).
