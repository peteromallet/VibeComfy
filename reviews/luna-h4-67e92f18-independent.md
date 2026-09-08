# Luna independent review: H4 rehearsal `67e92f18`

## Verdict: REWORK

Review was performed from a clean detached worktree at exactly
`67e92f189d482814d236c846c80a6790c4142cb7`, with parent
`3145a9a3f6f4cd8063e6bb449b0996858b545944`. The requested integration target
`da2baf58e07ce5f1581cf1cf782de8a52b1fa547` was used for candidate-vs-parent
classification. The dirty `/tmp/vc-h4-rehearsal-20260830` checkout was not
used; the committed candidate contains no review documents or other review
contamination.

## Blocking findings

1. **The committed schema provider calls an undefined method.**
   `vibecomfy/schema/provider.py:609` and `:681` call
   `ObjectInfoIndexSchemaProvider._validated_pack_path`, but that method is
   absent in the committed candidate. Consequently indexed `schemas()`
   listing, focused schema loads, ingress snapshots, compatibility search,
   executor node lookup, and plugin discovery fail through a wrapped
   `AttributeError`. The same conflict resolution also reverted
   `Path(root).resolve()` and the validated source path behavior from the
   approved schema stack, so simply adding a method without restoring those
   invariants is insufficient. This is candidate-only; the comparable parent
   command passed 116 tests.

2. **Schema authority regression coverage was dropped during integration.**
   Candidate `tests/test_schema_alias_authority.py` has 4 tests, versus 28 in
   the approved schema/compatible source (`977049f`). Missing coverage includes
   exact raw-ID precedence, ambiguous case-fold aliases, unique aliases,
   one-snapshot/immutable surfaces, NFC normalization, index confinement,
   typed provider/getter/enumeration failures, deep-freeze/digest behavior, and
   graph cycle/depth/item bounds. This is not an acceptable integration of the
   two schema lineages; restore the full authoritative tests and ensure they
   run without quarantine.

3. **The alias collision test is from the pre-alias contract.**
   Candidate `tests/test_plugin_discovery.py:170-188` still expects a warning
   and built-in winner. The approved alias contract requires deterministic
   fail-closed collision refusal and has 4 additional exact-vs-folded,
   collision, and source-info tests; candidate coverage is 8 tests versus 12
   in `72359d7`. The runtime manual probe did preserve the desired behavior:
   two distinct roots with `image/Foo.py` and `image/foo.py` produced both
   exact IDs; exact lookups selected their raw ID, while folded/short lookups
   raised an ambiguity error listing both candidates. Carry the alias test
   replacement rather than weakening runtime behavior.

4. **The f66 CLI parser/help contract was lost.**
   Candidate `vibecomfy/commands/port/_register.py` makes `workflow` required,
   so `port convert --all --dry-run --json` fails argparse although the
   candidate test requires it to parse with `workflow is None`. Its `--all`
   help also omits the bounded human/JSON outcome wording asserted by
   `tests/test_cli_port.py:129-132`. Both exact tests fail on H4; the same help
   test passes on the f66 control checkout. Restore the f66 registration/help
   changes while retaining the bounded normalizer and truthful aggregate
   envelope.

## Evidence

The combined candidate focus command

```text
tests/test_schema_alias_authority.py
tests/test_porting_emit_signatures.py
tests/test_object_info_schema.py
tests/test_cli_sources_workflows_nodes.py
tests/test_executor_lookup_tools.py
tests/test_plugin_discovery.py
tests/test_templates_module.py
tests/test_imagebatch_widget_lens.py
tests/test_graph_inspection.py
tests/test_ready_templates.py
```

returned `357 passed, 25 failed, 1 skipped`; the gate classified 8 new
candidate failures (the undefined provider method and its consumer cascades)
and 17 known quarantined ready-template failures. The comparable parent focus
(`tests/test_cli_sources_workflows_nodes.py`, `test_executor_lookup_tools.py`,
`test_plugin_discovery.py`, `test_porting_emit_signatures.py`) returned
`116 passed, 3 warnings`.

The nearby schema command returned `136 passed, 7 failed`: six were the
candidate-only undefined-method failures; the remaining
`test_touched_schema_classes_fail_closed_and_preserve_untouched` is the known
parent `ops.py:549` `UnboundLocalError` baseline. The two direct CLI tests
above returned `2 failed`; the two ContextVar finalizer isolation tests
returned `2 passed`. `python -m compileall -q vibecomfy tests` and
`git diff --check da2baf58 67e92f18` passed.

## Surviving contracts / residuals

The committed ready registry and executor lookup path use the shared discovery
authority (no independent lookup walk); the hostile two-root exact/case-fold
probe passed. ContextVar token release before finalization passed its two
regressions. The ImageBatch widget-lens removal passed its focused tests and
the candidate has no ImageBatch-specific failures. No overengineering was
observed. These passes do not offset the missing provider method, dropped
schema/alias coverage, and CLI integration failures.

