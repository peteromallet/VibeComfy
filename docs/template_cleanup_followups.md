# Template cleanup follow-ups — CLOSED (2026-05-25)

Captured 2026-05-23 after porting `desloppify/strict-score-push` work onto
`vibecomfy-v26-1` (branch `agentic-port-20260523`). Natural-Python ready
templates are now live again; this doc lists what's still worth doing.

**Status: CLOSED.** The Phase 2 sprint brief (plan_v1.meta.json) has addressed
or explicitly deferred all items. Section C recoverability checkpoints have
been resolved: stash@{0} and stash@{1} were inspected on 2026-05-25 and found
to contain unabsorbed work; stash@{1} originates from a different branch
(`fix/latentupscale-model-mmap-residency`) and holds unique unmerged changes
(39 files, 388 insertions, 1072 deletions) — both stashes are retained.
`/tmp/desloppify_lifeboat_20260523/` has been removed. The remaining B.1–B.4
items are tracked in the sprint plan.

## A. Cosmetic — could the `def build()` shape be cleaner?

### A.1 The "top" — `new_workflow(READY_METADATA, source_path=__file__)`

Current shape, repeated across every generated ready_template:

```python
def build() -> VibeWorkflow:
    """Build the workflow (auto-generated)."""
    with new_workflow(READY_METADATA, source_path=__file__) as wf:
```

**What each piece does:**

- `READY_METADATA` — module-level dict declared above (capability, models, provenance, inputs spec).
- `source_path=__file__` — records where the template file lives, used for error messages, provenance trails, and `analyze_source`.
- `with ... as wf:` — context-manager scoping (probably so emission errors get attributed to the right template).

**Is it cleaner-able?** Yes — three honest options, ranked:

1. **Best: implicit metadata + path discovery.** Replace the call with bare `with new_workflow() as wf:` and have `new_workflow` walk `inspect.stack()` to find `READY_METADATA` in the caller's module globals and `__file__` from the caller's frame. Removes 2 args from every template. The "magic" cost is justified because *every* template needs these two values exactly the same way — it's pure boilerplate, not a meaningful per-template choice.
2. **Drop the context manager.** `wf = new_workflow(READY_METADATA, source_path=__file__)` at the top, no `with`. Saves one level of indentation across the entire build body. The context manager isn't doing real work (no resource to release; emission errors can be wrapped one level up in the loader). One indentation level off ~80 lines of body code is a real readability win.
3. **Keep as-is.** It's not actually broken — the boilerplate is mechanical, only two args, and obvious to a reader. If we're spending fixed-cost cleanup budget elsewhere, this can wait.

**Recommended: option 1 (implicit discovery).** Templates are auto-generated; the slight magic is acceptable when the contract is "every template's first line is the same."

### A.2 The "bottom" — `return wf.finalize(PUBLIC_INPUTS, output_type=...)`

Current shape:

```python
return wf.finalize(
    PUBLIC_INPUTS,
    output_type='SaveImage',
    name='image',
    artifact_kind='image',
    mime_type='image/png',
    expected_cardinality='one',
    filename_prefix='z-image',
)
```

**Does it contain real information?** Yes — each kwarg encodes something the runtime / UI / app actually needs:

| Kwarg | Used for |
|---|---|
| `output_type='SaveImage'` | Which node class produces the artifact (compile path) |
| `name='image'` | Named-output routing in the IR |
| `artifact_kind='image'` | App-side classification (image vs video vs audio) |
| `mime_type='image/png'` | Content negotiation, file extension |
| `expected_cardinality='one'` | One artifact vs sequence (e.g. video frames) |
| `filename_prefix='z-image'` | SaveImage node prefix; surfaces in output paths |

None of these are gratuitous. So the question isn't "can we drop them" — it's **"can we arrange them more cleanly?"**

**Three options, ranked:**

1. **Best: lift to a `READY_OUTPUTS` dict at module level.** Mirror `PUBLIC_INPUTS`:
   ```python
   PUBLIC_INPUTS = {...}
   READY_OUTPUTS = {
       'image': OutputSpec(
           node=ref('saveimage'),
           type='SaveImage',
           artifact_kind='image',
           mime_type='image/png',
           expected_cardinality='one',
           filename_prefix='z-image',
       ),
   }
   READY_METADATA = ReadyMetadata.build(capability='text_to_image', inputs=PUBLIC_INPUTS, outputs=READY_OUTPUTS, ...)
   ```
   Then `return wf.finalize(PUBLIC_INPUTS, READY_OUTPUTS)` — symmetric with the inputs surface. Reads the same way at top *and* bottom: "here's what comes in, here's what goes out." A first-time reader gets the contract immediately without parsing kwarg soup.
2. **Auto-derive from the SaveImage node.** `filename_prefix`, `mime_type`, and `output_type` are all knowable from the node itself once it's added to the graph. Reduces duplication but loses the explicit declaration — which makes the output contract harder to find when reading the template top-down.
3. **Keep as-is.** Inline kwargs are explicit; the bottom line is a single call. Costs nothing structurally, just visually noisy.

**Recommended: option 1.** Symmetry with `PUBLIC_INPUTS` is the win — both surfaces declared the same way, both consumed by `wf.finalize` cleanly. Reader sees the contract before reading the body. The current single-call kwarg-soup hides which kwargs are output-specific vs ergonomic.

### A.3 One more nit while we're here

Generated templates still emit `raw_call('MarkdownNote', '76', widget_0='...')` in the middle of the build body. `MarkdownNote` is a UI-only annotation node — never executed at runtime, stripped at compile. It pollutes the template body with noise that has no functional effect. Emission should drop `Note` and `MarkdownNote` calls entirely, not preserve them as `raw_call(...)`. One-line fix in the emitter's UI-strip set.

---

## B. Outstanding work from the agentic-port end-state

Carried forward from the wrap-up of the 2026-05-23 port. Ordered by size, smallest first.

### B.1 One failing test: import-cost contract

`tests/test_testing_dry_run.py::test_importing_dry_run_does_not_pull_runtime_at_import_time`

This is a structural contract: importing `vibecomfy.testing.dry_run` must not transitively load `vibecomfy.runtime.client` or `vibecomfy.runtime.server`. On `vibecomfy-v26-1`'s package topology, something in the dependency chain pulls them in.

**Fix path:** trace which import edge brings in `runtime.client/server`, make it lazy. The lazy-import pattern already applied to `parity.py`, `testing/assertions.py`, and `testing/_helpers.py` is the template — find the next eager edge in the chain and apply the same fix. Likely candidates: `vibecomfy.testing.snapshot`, `vibecomfy.testing.dry_run` itself, or `vibecomfy/__init__.py`'s eager imports.

Effort: 30 min — 1 hour. Mostly diagnosis, then a 3-line edit.

### B.2 Twelve `test_cli_port.py` failures (pre-existing on v26-1)

`test_port_validate_call_subprocess_*` (6 tests) and `test_port_doctor_all_*` (3 tests), plus a few others.

These test the agentic CLI surface (`port validate-call`, `port doctor-all`, `port lint`, `port simulate`) against an expected output shape that doesn't match v26-1's natural-Python templates. They were authored when the corpus emitted `widget_N` positional aliases; v26-1's templates emit canonical names via the typed wrappers.

**Fix path:** update each test's expected output to match the current natural-Python shape, OR adjust the CLI commands to also handle the old `widget_N` shape for backwards compat (probably not worth it — pin to current).

Effort: 1-2 hours per cluster (validate-call and doctor-all are independent fixtures).

### B.3 Graft `errors.py` agent-facing improvements

Desloppify's `vibecomfy/errors.py` had a richer agent-facing surface than v26-1's:

- `to_dict()` method on each error class — structured JSON for agentic consumption
- `severity` field — `error` / `warning` / `info` classification
- `default_next_action` — string hint for the agent's next CLI invocation
- Concrete subclasses with semantic names: `MissingModelAssetError`, `RuntimeNodeError`, `CanonicalParityFailure`, etc.

V26-1's version is `RuntimeError`-based with a simpler hierarchy.

**Fix path:** preserve v26-1's existing class hierarchy as the base. Add `to_dict()`, `severity`, and `default_next_action` to the base error class. Map desloppify's semantic subclass names onto v26-1's existing classes (alias where shapes match, add new subclass only where genuinely missing).

Effort: 2-3 hours including tests. Reference: `/tmp/desloppify_lifeboat_20260523/errors_desloppify.py` (full original).

### B.4 Wire scratchpad emitter to natural-Python form

This is the biggest item.

`port convert <source.json> --out scratchpad.py` still calls `emit_scratchpad_python`, which emits:

```python
subgraph_9b9009e4 = _node(wf, '9b9009e4-2d3d-445f-9be5-6063f465757e', '76',
    widget_0='...prompt text...',
    widget_1=1024,
    widget_2=1024,
    ...
)
```

The natural-Python form only emits through `emit_ready_template_python` (which `tools/convert_ready_templates.py` calls when promoting a workflow with `--ready-id`). Scratchpads are second-class.

**Fix path:** either
- Make `emit_scratchpad_python` go through the same typed-wrapper path as ready-templates (using `vibecomfy/templates.py` + `vibecomfy/nodes/core.py`), with the difference being no `READY_METADATA` / `PUBLIC_INPUTS` declarations — just `new_workflow(...) → build → return`. Probably the right design.
- OR: deprecate the scratchpad path entirely and route all `port convert` through ready-template emission, even for unpromoted candidates.

Effort: 4-8 hours. Touches the emitter, scratchpad tests, and the `port convert` CLI behavior. Coordinate with B.2 (the CLI test fixtures will need to update simultaneously).

### B.5 Branch cleanup ✅ DONE (2026-05-23)

Resolved via `/cleanup-loose-branches` on 2026-05-23. End state:
- **Local branches**: 5 (was 17) — `main`, `vibecomfy-v26-1`, `desloppify/strict-score-push`, `desloppify/user-testing-b`, `agentic-port-20260523`
- **Remote branches**: 4 (was 13)
- **Worktrees**: 2 (was 9) — current + v26-1 pin
- **Recoverability**: stash@{0}, stash@{1}, and `/tmp/desloppify_lifeboat_20260523/` preserved (see §C)

---

## C. Recoverability checkpoints — RESOLVED (2026-05-25)

- **`stash@{1}`** — RETAINED. Original desloppify `strict-score-push` worktree from branch `fix/latentupscale-model-mmap-residency`. Inspection on 2026-05-25 confirmed 39 files of unique unmerged work (388 insertions, 1072 deletions) including `_node` helper relocation, CLI additions (`validate-call`, `doctor-all`, `eval-node`, `inspect --node`, `nodes compatible-with`), AGENTS.md §1e, and template dedup. Not safe to drop.
- **`stash@{0}`** — RETAINED. Agentic-port WIP from mid-port (parity.py lazy-import + preview_types.py rewrite). 2 files unabsorbed. Not safe to drop.
- **`/tmp/desloppify_lifeboat_20260523/`** — REMOVED 2026-05-25. Out-of-repo copy of novel files and emitter diff patches. Contents verified redundant with stashes.

---

## T21 validation blockers (2026-05-24)

Final Phase 0 validation still has two large blockers that should be handled as follow-up work, not as a slack-budget patch:

1. `python -m pytest tests/ -q` stops during collection because `tests/test_agentic_affordances.py` imports `CanonicalParityFailure` from `vibecomfy.errors`. A quick compatibility probe showed the file also expects broader agentic affordance APIs (`plan_eval_node` export, `lookup_id(..., source_path=...)`, `port validate-call` JSON shape, `port doctor-all` test hooks), so this is the B.2/B.3/B.4 surface rather than a one-line import fix.
2. `python -m tools.check_strict_ready_templates --json` exits non-zero with current generated-template strict/style diagnostics. Representative enforced errors include `wf.register_input` legacy calls in generated templates (`image/qwen_image_2512`, `video/wan_i2v`, `video/ltx2_3_first_last_frame_travel_iclora_control`), unnamed `SaveVideo` public outputs, and unresolved schema-backed `widget_N` fields in LTX templates. These overlap with the known Phase 1 emitter cleanup families.

The index byte-identity gate still passes: `python -m tools.refresh_template_index --check`.

---

## D. Priority suggestion

If picking one item to do next: **A.2 (lift `READY_OUTPUTS` to module level)**. It's the highest leverage cosmetic win — every template gets visibly cleaner, the symmetry with `PUBLIC_INPUTS` makes the contract instantly readable, and it's a contained emitter change that doesn't risk runtime behavior.

If picking one item for "real" effort: **B.4 (scratchpad emitter → natural-Python form)**. Fixes the regression the user originally noticed (`port convert` previews still look ugly even on v26-1). Everything else is polish on top of an already-working base.
