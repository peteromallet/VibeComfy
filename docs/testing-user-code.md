# Testing your VibeComfy recipes

A 10-minute walkthrough for testing recipes, scratchpads, and custom ready-templates built on top of VibeComfy.

## Why this exists

VibeComfy is a library you build *on top of*. The Python you write — recipes, scratchpads, custom ready-templates — needs the same test discipline as any other production code:

- "Does my recipe build the right graph?"
- "Did renaming this template break its snapshot?"
- "Does my dual-pass actually wire the second stage correctly?"

The `vibecomfy.testing` module + `vibecomfy test` CLI + `pytest-vibecomfy` plugin answer those, without spinning up GPUs.

## Install

VibeComfy ships the testing surface inside the main wheel; nothing extra to install. The pytest plugin auto-loads via the `pytest11` entry point.

## Write your first recipe test

Suppose you have `recipes/my_dual_pass.py`:

```python
from vibecomfy import load_workflow_any

def build():
    wf = load_workflow_any("image/z_image")
    # ... your customizations
    return wf
```

Drop a sibling test:

```python
# recipes/test_my_dual_pass.py
from vibecomfy.testing import (
    assert_compiles_cleanly,
    assert_node_present,
    assert_input_value,
    dry_run,
)
from recipes.my_dual_pass import build


def test_my_recipe_compiles():
    wf = build()
    assert_compiles_cleanly(wf)
    assert_node_present(wf, "VAELoader", count=1)
    assert_node_present(wf, "SaveImage", count=1)


def test_dry_run_records_nodes():
    wf = build()
    result = dry_run(wf)
    assert "VAELoader" in {r.class_type for r in result.would_invoke}
```

Run it:

```bash
pytest recipes/
```

## Snapshot the recipe

```bash
vibecomfy test snapshot recipes/my_dual_pass.py    # one-time
vibecomfy test verify recipes/                     # in CI
vibecomfy test diff recipes/my_dual_pass.py        # when iterating
```

`snapshot` writes `recipes/my_dual_pass.py.snapshot.json` next to the recipe. `verify` walks any directory and exits non-zero on drift. `diff` shows a unified diff between committed and rebuilt output.

## The seven assertions

| Assertion | What it checks |
|---|---|
| `assert_node_present(wf, class_type, *, count=None)` | At least one (or exactly `count`) node of that class type |
| `assert_edge(wf, from_node_id, to_node_id, *, to_input=None)` | Given edge exists; optionally pinned to an input name |
| `assert_input_value(wf, node_id, input_name, expected)` | Widget or input value matches |
| `assert_output_kind(wf, expected_kind)` | A `Save*` of the right shape is present in outputs |
| `assert_input_bound(wf, input_name, *, node_id=None, field=None, default=...)` | Registered input metadata matches |
| `assert_compiles_cleanly(wf, *, schema_provider=None)` | `wf.compile("api")` succeeds and `validate()` is clean |
| `assert_no_dangling_handles(wf)` | Every handle is wired into an edge |

Failure messages include `wf.id`, the offending node id, and the field — so a regression points you at the exact place.

## Dry-run runtime

`dry_run(wf)` returns a `DryRunResult` with the compiled API dict plus one `WouldInvoke` record per node. No ComfyUI, no GPU, no checkpoints. Good for asserting wiring on workflows whose models you don't have locally.

```python
from vibecomfy.testing import dry_run

result = dry_run(build())
print({r.class_type for r in result.would_invoke})
```

## Pytest plugin: `test_workflow_*.py`

Any file matching `test_workflow_*.py` is collected by the `pytest-vibecomfy` plugin. Functions whose return value is a `VibeWorkflow` are auto-wrapped with `assert_compiles_cleanly`:

```python
# test_workflow_my_recipe.py
from recipes.my_dual_pass import build

def test_compiles():
    return build()   # auto-wrapped with assert_compiles_cleanly
```

Plain `test_*` functions in the same file collect normally. The `--vibecomfy-snapshot-update` flag rewrites stale sibling `.snapshot.json` files.

## Where snapshots live

- `tests/snapshots/<stem>.{api,class_types,widget_values}.json` — the curated registry for `STEM_TO_READY_ID` (the 9 canonical ready-templates).
- Sibling `<recipe>.snapshot.json` — your recipes' frozen compile output.

Both routes use the same canonicalizer (`vibecomfy.testing.snapshot.canonicalize_api`), so a `vibecomfy test verify` pass exercises both shapes uniformly. See [`docs/testing.md`](testing.md) for the internal contract; this page is for users building on top.

## Cross-links

- [Internal testing contract](testing.md) — coverage gate, CI, RunPod budget cap.
- [Three worked examples](testing-user-code-examples/) — a single-template recipe, a dual-pass with an `ignore-field` directive, a pytest-plugin demo.
- [`recipes/example_tested_recipe.py`](../recipes/example_tested_recipe.py) and its committed `.snapshot.json` baseline — `vibecomfy test verify recipes/` exits 0 against it.
