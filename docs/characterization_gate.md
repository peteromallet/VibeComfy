# Characterization Gate

> **Phase**: M0 — Behavior oracle + first cleanup pass
>
> **Purpose**: Detect behavioral drift in the vibecomfy public API surface, emitter
> output, and agent-edit roundtrip semantics by comparing every run against
> committed golden artifacts. Any change that alters one of these artifacts is a
> *regression* unless the golden is intentionally updated at the same commit.
>
> **TL;DR**: `PYTHONHASHSEED=0 pytest -m characterization` must always pass on
> `main`. If it doesn't, either (a) you changed something that shifted output
> (regression), or (b) you changed output intentionally and must regenerate the
> relevant golden files at the same commit.

---

## 1. Three-layer coverage

The characterization suite guards three distinct output surfaces. Each layer is
a separate parametrised test file, and each is gated by the `characterization`
pytest marker.

### Layer 1 — API surface immutability

**File:** `tests/characterization/_api_surface_snapshot.txt`

A byte-identical capture of `sorted(vibecomfy.__all__)`. This snapshot is
compared at the Python level (not a test — it is the canonical reference) and
ensures that no cleanup or refactor accidentally adds, removes, or renames a
public symbol in `vibecomfy/__init__.py`.

**35 symbols currently exported:**

```
Artifact, Audio, Handle, Image, Latent, Mask, RawWidgetPayload,
ValidationIssue, ValidationReport, VibeEdge, VibeInput, VibeNode, VibeOutput,
VibeWorkflow, Video, WorkflowRequirements, WorkflowSource,
blocks, ensure_plugins_loaded, find_repo_root, image, load_template,
load_workflow_any, load_workflow_json, patches, ready_template_ids, router,
run, run_embedded, run_embedded_sync, run_sync, video, workflow_from_file,
workflow_from_id, workflow_from_ready
```

Any change to this file in a commit signals a public-API surface change that
must be reviewed.

### Layer 2 — Compile-API snapshots

**File:** `tests/characterization/test_compile_api_snapshots.py`

Parametrised over all 11 stems in `STEM_TO_READY_ID`. For each stem:

1. Load the ready template via `load_workflow_any(ready_id)`.
2. Call `workflow.compile("api")`.
3. Deserialize the committed `tests/snapshots/{stem}.class_types.json` and
   `tests/snapshots/{stem}.widget_values.json`.
4. Regenerate those same two JSON documents from the compiled API and compare
   them structurally (JSON equality).

Regeneration: `python scripts/regenerate_snapshots.py --write`

### Layer 3 — Emitter golden snapshots

**File:** `tests/characterization/test_emitter_snapshots.py`

Parametrised over all 11 stems × 2 kinds (scratchpad, ready). For each triple
`(stem, kind)`:

1. Load the ready template.
2. Drive `emit_scratchpad_python` or `emit_ready_template_python`.
3. Neutralize absolute repo-root paths via `_canon.neutralize_paths`.
4. Assert no residual absolute paths remain (regex check).
5. Assert output is under 200 KB.
6. Compare against the committed golden at
   `tests/characterization/goldens/emitter/{stem}.{kind}.py.golden`.

Golden files are full Python source — the comparison is byte-for-byte string
equality (after path neutralization).

### Layer 4 — Agent-edit roundtrip fixtures

**File:** `tests/characterization/test_agent_edit_roundtrips.py`

Parametrised over 5 case directories under
`tests/characterization/fixtures/agent_edit/case_{01..05}_*/`. Each case has a
triplet:

- **`input_ui.json`** — initial raw UI dict (ComfyUI-style JSON).
- **`batch.py.txt`** — DSL code string passed to `EditSession.apply_batch(code=...)`.
- **`expected.json`** — committed expected state with 5 fields:
  - `working_ui_structural_hash` — SHA-256 of `strip_volatile_ui(session.working_ui)`.
  - `sorted_diagnostic_codes` — sorted diagnostic codes from the batch result.
  - `ok` — whether the batch succeeded.
  - `landed_op_kinds` — resolved operation class names.
  - `done_summary_prefix_120` — first 120 characters of `session.done().summary`.

The 5 cases cover: widget-set, add-node, connect, disconnect, and multi-op.

### Stem list

The canonical stem list lives in
`vibecomfy/testing/snapshot_registry.py` and currently contains **11 stems**:

| Stem | Ready ID | Kind |
|---|---|---|
| `z_image` | `image/z_image` | image |
| `flux2_klein_4b_t2i` | `image/flux2_klein_4b_t2i` | image |
| `flux2_klein_9b_gguf_t2i` | `image/flux2_klein_9b_gguf_t2i` | image |
| `flux2_klein_4b_image_edit_distilled` | `edit/flux2_klein_4b_image_edit_distilled` | edit |
| `qwen_image_edit` | `edit/qwen_image_edit` | edit |
| `wan_t2v` | `video/wan_t2v` | video |
| `wan_i2v` | `video/wan_i2v` | video |
| `ltx2_3_t2v` | `video/ltx2_3_t2v` | video |
| `ltx2_3_i2v` | `video/ltx2_3_i2v` | video |
| `empty_image_red` | `smoke/empty_image_red` | smoke |
| `empty_image_red_smoke_required` | `smoke/empty_image_red` | smoke |

Note: `empty_image_red` and `empty_image_red_smoke_required` both map to the
same ready ID (`smoke/empty_image_red`) but exercise different compilation
modes (the `_smoke_required` variant verifies the mode that includes the smoke
template's `__init__` requirements).

---

## 2. How to regenerate goldens (`--write` flags)

There are **three independent golden domains**, each with its own regeneration
mechanism:

### Emitter goldens (Layer 3) and Agent-edit expected.json (Layer 4)

Set the **`VIBECOMFY_CHARACTERIZATION_WRITE=1`** environment variable:

```bash
PYTHONHASHSEED=0 VIBECOMFY_CHARACTERIZATION_WRITE=1 \
  python -m pytest -m characterization \
    tests/characterization/test_emitter_snapshots.py \
    tests/characterization/test_agent_edit_roundtrips.py \
    -v
```

- For emitters: overwrites all 22 `.py.golden` files (11 stems × 2 kinds).
- For agent-edit: overwrites all 5 `expected.json` files.

The test files check for this env var at the top of each parametrised test — if
set, the test writes the golden and returns early (no assertion). **Do not
commit regenerated goldens without reviewing the diff.** A golden change is an
intentional contract change.

### Compile-API snapshots (Layer 2)

Use the **`--write`** flag on the dedicated script:

```bash
python scripts/regenerate_snapshots.py --write
```

This updates the `.api.json`, `.class_types.json`, and `.widget_values.json`
files in `tests/snapshots/`. The script's `--write` flag is the only supported
mechanism — setting `VIBECOMFY_CHARACTERIZATION_WRITE=1` has no effect on Layer
2.

---

## 3. Diff semantics — regression vs intended change

### When the gate fails

When a characterization test fails, it means the current code produces different
output than the committed golden. The test output shows a unified diff (for
emitter goldens) or a field-by-field mismatch (for agent-edit roundtrips).

**Determine whether the diff is:**

1. **A regression** — your change accidentally altered output that should have
   remained stable. The fix is to correct your code, not update the golden.
2. **An intended change** — your change was supposed to alter this output (e.g.,
   a new feature, a bug fix that changes emitted code). The fix is to regenerate
   the golden at the same commit so the gate stays green.

### Relationship to `known_failures.txt`

The by-design-red baseline in `tests/known_failures.txt` is for the **broader
pytest suite**, not the characterization gate. Characterization tests that fail
are always treated as regressions — they are **not** added to `known_failures.txt`.
If a characterization test is expected to fail (e.g., an emitter is known to
produce non-identical output), use `_emitter_xfail.txt` instead (see §5).

### Golden drift vs fixture drift

- **Emitter goldens** (`.py.golden`) — byte-for-byte string comparison after
  path neutralization. Any difference means the emitted Python source changed.
- **Compile-API snapshots** (`.json`) — structural JSON equality. Any difference
  means the compiled API representation changed.
- **Agent-edit expected.json** — field-by-field JSON comparison. Any difference
  means the EditSession roundtrip outcome changed.
- **API surface snapshot** — byte-for-byte line comparison of
  `sorted(vibecomfy.__all__)`. Any difference means the public-API surface
  changed.

### Workflow for an intended golden update

1. Make your code change.
2. Regenerate the affected goldens (see §2).
3. Review the golden diff with `git diff --no-color`.
4. Confirm every change is expected and explained by your code change.
5. Commit code + regenerated goldens together.

---

## 4. PYTHONHASHSEED=0 enforcement

### Why

Python's hash randomization (enabled by default since Python 3.3) causes dict
iteration, set ordering, and other hash-dependent behavior to vary between
process invocations. The characterization gate depends on deterministic,
byte-identical output across runs — `PYTHONHASHSEED=0` is the standard
CPython mechanism to disable hash randomization.

### How it's enforced

**`tests/characterization/conftest.py`** installs an autouse fixture:

```python
@pytest.fixture(autouse=True)
def _require_pythonhashseed_zero() -> None:
    seed = os.environ.get("PYTHONHASHSEED")
    if seed != "0":
        pytest.fail(
            "PYTHONHASHSEED must be '0' to run characterization tests.\n"
            f"Current value: {seed!r}\n"
            "Re-run with: PYTHONHASHSEED=0 pytest -m characterization"
        )
```

This fixture fires at collection time for every test in the
`tests/characterization/` directory. If the env var is missing or set to
anything other than `"0"`, the test fails immediately with a clear message.

### Running the characterization suite

Always:

```bash
PYTHONHASHSEED=0 python -m pytest -m characterization tests/characterization/ -v
```

The `PYTHONHASHSEED=0` must be set in the parent process environment — the
autouse fixture checks it but cannot set it retroactively. Shell aliases or
`.env` files are recommended for local development.

---

## 5. `_emitter_xfail.txt` semantics

**File:** `tests/characterization/_emitter_xfail.txt`

### Purpose

When an emitter stem is known to produce non-identical output (e.g., the
scratchpad emitter is still evolving and a stem is known to have a specific
divergence), the stem can be listed in this file so the characterization test
reports `XFAIL` (expected failure) instead of `FAIL`.

This is **not** a general-purpose skip mechanism. It is a deliberate, reviewed
acknowledgment that a particular stem's emitter output is currently unstable.

### Format

```
# Comment lines start with #.
<stem>  # optional explanation of why this stem is xfail'd
```

Example:

```
# z_image scratchpad has floating-point formatting drift
z_image
```

Only stems — not `stem/kind` pairs — are listed. If a stem is in the xfail set,
*both* its scratchpad and ready golden comparisons become XFAIL (if they would
otherwise fail). Stems not listed are expected to match byte-for-byte.

### When to add or remove entries

- **Add**: When a code change intentionally alters emitter output for a stem and
  you cannot regenerate goldens immediately (e.g., a WIP branch). This is a
  temporary concession — the xfail entry should be resolved before merge.
- **Remove**: When the emitter is fixed or the golden is regenerated. Run the
  suite to confirm the stem now passes, then remove the line.

### How XFAIL is handled in the test

The test (`test_emitter_snapshots.py`) reads `_emitter_xfail.txt` via
`_load_xfail_set()` at runtime:

- If a golden is missing **and** the stem is xfail'd → `pytest.xfail("No golden yet")`.
- If the golden exists but doesn't match **and** the stem is xfail'd → `pytest.xfail("Golden mismatch (expected per _emitter_xfail.txt)")`.
- If a stem is xfail'd but the golden **does** match → the test passes
  (XFAIL-strict is not used; a passing xfail is silently accepted).

---

## 6. `--known-failures-audit` invocation

### What it does

`--known-failures-audit` is a pytest flag (registered in
`tests/conftest.py:pytest_addoption`) that checks whether every entry in
`tests/known_failures.txt` still maps to an actual collected test ID. Entries
that reference tests that no longer exist (renamed, removed, or misspelled) are
reported as **STALE FAILURES**.

The audit is **read-only** — it never modifies `known_failures.txt`.

### How to run

```bash
PYTHONHASHSEED=0 python -m pytest --known-failures-audit tests/characterization/ -q --tb=no --no-header
```

The flag can be combined with any test target — scope to a single file for a
fast check:

```bash
PYTHONHASHSEED=0 python -m pytest --known-failures-audit tests/characterization/test_compile_api_snapshots.py --tb=no -q
```

### Output interpretation

**No stale entries:**
```
known_failures.txt audit: all 213 entry(s) map to collected tests.
```

**Stale entries found:**
```
====== STALE FAILURES (in known_failures.txt but not collected) ======
  STALE: tests/test_this_does_not_exist.py::test_nonexistent
  STALE: tests/test_also_nonexistent.py::test_another_fake
2 stale entry(s) in known_failures.txt — remove or update them.
```

If stale entries are found, they should be removed from `known_failures.txt` or
updated to match the current test ID. The audit flag is useful in CI to catch
drift between the baseline and the actual test collection.

### Automation

The test `tests/characterization/test_known_failures_audit.py` verifies the
audit mechanism itself by temporarily injecting stale entries and asserting the
STALE FAILURES section appears. This is a meta-test that validates the tooling,
not a periodic audit — run the flag directly in CI for the latter.

---

## Appendix: Quick reference

| Action | Command |
|---|---|
| Run full characterization suite | `PYTHONHASHSEED=0 python -m pytest -m characterization tests/characterization/ -v` |
| Regenerate emitter & agent-edit goldens | `PYTHONHASHSEED=0 VIBECOMFY_CHARACTERIZATION_WRITE=1 python -m pytest -m characterization tests/characterization/test_emitter_snapshots.py tests/characterization/test_agent_edit_roundtrips.py -v` |
| Regenerate compile-API snapshots | `python scripts/regenerate_snapshots.py --write` |
| Audit known-failures baseline | `PYTHONHASHSEED=0 python -m pytest --known-failures-audit tests/characterization/test_compile_api_snapshots.py --tb=no -q` |
| Check API surface snapshot | `python -c "import vibecomfy; print('\n'.join(sorted(vibecomfy.__all__)))"` |
