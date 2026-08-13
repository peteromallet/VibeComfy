The ordering is broadly right, and the canonical 100-scenario lane should not run before B07. First, B03 still needs a formal `PASS`; checkpoint discipline says B05 must wait.

## B05-lite

Most likely FAILs:

1. **Rollback boundary starts too late.** Model request/response and message artifacts are already changed at [edit_batch_repl.py:1512](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1512), well before mutation at [edit_batch_repl.py:1918](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1918). A snapshot immediately before `apply_batch` will not restore loop-entry bytes.

2. **Incomplete state restoration.** The session has graph, ledger, landed/touched sets, name maps, `value_default_context`, render caches and counters at [session.py:132](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/session.py:132). Oracle will inject faults after render, candidate write, `done()` and evidence finalization at [edit_batch_repl.py:2428](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2428) and [edit_batch_repl.py:2471](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2471), then compare all of these—not merely `working_ui`.

3. **Irreversible success telemetry.** WS events send immediately and swallow errors at [_frag_entrypoint.py:626](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:626). A fault after the `"done"` event at [edit_batch_repl.py:2512](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2512) can leave committed-looking telemetry for rolled-back work.

Precommit a fault matrix with absent/empty/non-empty files, exact byte comparison, closed aborted turn, bounded abort record and unchanged model-call count. Keep every rework on Sol.

## B06

Most likely FAILs:

1. **“Universal” evidence misses non-edit routes.** Headless synthesis only copies whatever durable JSON happens to exist at [artifacts.py:467](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:467); executor-only routes explicitly lack the normal edit turn at [service.py:207](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/service.py:207). Require route-matrix fixtures proving both files exist and `final == original` for respond/research/inspect/clarify/refusal.

2. **Refusal remains label-first.** `safe_refusal_accepted` is currently established before judging at [assessor.py:641](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:641), and non-`desired` allowlisted refusals bypass the judge. Replace this exemption universally; identical plausible prose with contradictory schema/graph evidence must fail.

3. **Tri-state gets collapsed to Boolean.** Assessment currently returns only `passed` at [assessor.py:964](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:964), and the guard maps directly to pass/product-fail. Persist `pass|fail|undetermined`; outage is `undetermined` but still cannot satisfy the scenario. Preserve D13’s rule that malformed judge verdicts fail, rather than being mislabeled outages.

The 35 `answer_rubric` scenarios presently never enter a judge because judging is gated on expected edits at [assessor.py:821](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:821). Keep B06 and its reworks on Sol.

## B07-lite

Most likely FAILs:

1. **Selector does not survive subprocess isolation.** `run_tag()` constructs child commands at [runner.py:543](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:543); transport must be passed explicitly through CLI → child → adapter → every profile phase.

2. **Ambient credentials still win.** The adapter hydrates a local `.env` and rewrites the base URL at [adapter.py:20](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/adapter.py:20), while runtime imports `~/.hermes/.env` at [runtime.py:196](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/runtime.py:196). Use a pinned child environment; test conflicting keys/base URLs.

3. **False comparability.** Precommit the ten IDs, model/profile/concurrency/timeout and configuration digest. Assert every B01 attempt’s observed transport matches selection. Since historical typed-empty evidence is absent, call this a deterministic probe—not “empty-heavy”—unless the selection basis is restored.

Flash is acceptable for mechanical wiring; any provenance/transport ambiguity should return to Sol.

## B08-cut

Most likely FAILs:

1. **Schema still authorizes a ghost output.** The fallback at [resolution.py:641](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/resolution.py:641) can return an index absent from working outputs; mutation writes it at [apply_mutate.py:197](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_mutate.py:197), and projection finally fails at [projection_registry_v1.py:115](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/projection_registry_v1.py:115).

2. **Dynamic contract becomes carte blanche.** Require positive and one-past-boundary fixtures for every named family. “Has dynamic `INPUT_TYPES`” alone cannot authorize arbitrary names; helpers such as Get/Set/Reroute need their actual directional semantics.

3. **Materialization shifts physical slots.** New-node inputs are empty at [ui.py:1325](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/emit/ui.py:1325). Materialize socket inputs in schema order, excluding literal widgets; otherwise KSampler-like nodes acquire wrong indices. Replace silent returns at [apply_links.py:303](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_links.py:303) with propagated typed diagnostics.

B03’s 2,838-workflow zero-mismatch result does not reduce this scope: it proves preservation comparison, not edit endpoint construction. Keep B08/reworks on Sol and rerun B03 plus B05 fixtures.

## B09

Most likely FAILs:

1. **A second hash authority.** D13 already owns the 100-row manifest and 98 source hashes at [scenario_manifest.py:91](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:91). Extend/copy that exact authority with aggregate and `primary_source` data; do not regenerate a parallel manifest.

2. **Irreproducible arithmetic.** Current summary only counts aggregate passes at [runner.py:324](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:324). Add a standalone reducer that reloads persisted evidence and reproduces first/eventual/infra-adjusted, 98-product, two-control, refusal tri-state, UI/provenance coverage and 97/3 matched/revised results.

3. **Unsupported historical claims.** `out/agentic/` remains absent. Therefore item 9 is presently inapplicable: name no flaky IDs and make no regression-versus-variance claim.

## Sequencing and cumulative invariants

Keep the frozen order. B05 must precede B08 because B08 explicitly depends on clean rollback; B06/B07/B09 overlap `runner.py`, `adapter.py`, `assessor.py` and artifacts, so each later batch must rerun prior focused suites. B09 arithmetic/denominator reworks should stay on Sol.

Preserve throughout:

- exactly 100 IDs: 63 edits, 35 semantic products, two controls; 97 matched/three revised;
- one B01 provenance format, redacted and never inferred;
- only typed empty receives exactly one retry;
- aborted candidates never become final UI, committed telemetry or report observations;
- no prose-based acceptance; missing evidence/outage never passes;
- one endpoint invariant, no synthetic undeclared ports, with B03 pin identity preserved;
- all report claims reproducible by stable ID, descriptor SHA, commit/config/corpus digests.

The external corpus absence is stale: D13 verified the provisioned 2,827-file corpus. The three questionable edits are also resolved by D13. Historical run evidence is still absent.

**Do not run the canonical 100-scenario lane before B07.** Without the selector and experiment, its transport/configuration is unpinned and the expensive evidence may be incomparable. A tiny harness smoke is reasonable; the canonical lane is not.

Read-only review completed; no files were modified.
221,410
The ordering is broadly right, and the canonical 100-scenario lane should not run before B07. First, B03 still needs a formal `PASS`; checkpoint discipline says B05 must wait.

## B05-lite

Most likely FAILs:

1. **Rollback boundary starts too late.** Model request/response and message artifacts are already changed at [edit_batch_repl.py:1512](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1512), well before mutation at [edit_batch_repl.py:1918](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:1918). A snapshot immediately before `apply_batch` will not restore loop-entry bytes.

2. **Incomplete state restoration.** The session has graph, ledger, landed/touched sets, name maps, `value_default_context`, render caches and counters at [session.py:132](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/session.py:132). Oracle will inject faults after render, candidate write, `done()` and evidence finalization at [edit_batch_repl.py:2428](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2428) and [edit_batch_repl.py:2471](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2471), then compare all of these—not merely `working_ui`.

3. **Irreversible success telemetry.** WS events send immediately and swallow errors at [_frag_entrypoint.py:626](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/_frag_entrypoint.py:626). A fault after the `"done"` event at [edit_batch_repl.py:2512](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/edit_batch_repl.py:2512) can leave committed-looking telemetry for rolled-back work.

Precommit a fault matrix with absent/empty/non-empty files, exact byte comparison, closed aborted turn, bounded abort record and unchanged model-call count. Keep every rework on Sol.

## B06

Most likely FAILs:

1. **“Universal” evidence misses non-edit routes.** Headless synthesis only copies whatever durable JSON happens to exist at [artifacts.py:467](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/artifacts.py:467); executor-only routes explicitly lack the normal edit turn at [service.py:207](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/agent/service.py:207). Require route-matrix fixtures proving both files exist and `final == original` for respond/research/inspect/clarify/refusal.

2. **Refusal remains label-first.** `safe_refusal_accepted` is currently established before judging at [assessor.py:641](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:641), and non-`desired` allowlisted refusals bypass the judge. Replace this exemption universally; identical plausible prose with contradictory schema/graph evidence must fail.

3. **Tri-state gets collapsed to Boolean.** Assessment currently returns only `passed` at [assessor.py:964](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:964), and the guard maps directly to pass/product-fail. Persist `pass|fail|undetermined`; outage is `undetermined` but still cannot satisfy the scenario. Preserve D13’s rule that malformed judge verdicts fail, rather than being mislabeled outages.

The 35 `answer_rubric` scenarios presently never enter a judge because judging is gated on expected edits at [assessor.py:821](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/assessor.py:821). Keep B06 and its reworks on Sol.

## B07-lite

Most likely FAILs:

1. **Selector does not survive subprocess isolation.** `run_tag()` constructs child commands at [runner.py:543](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:543); transport must be passed explicitly through CLI → child → adapter → every profile phase.

2. **Ambient credentials still win.** The adapter hydrates a local `.env` and rewrites the base URL at [adapter.py:20](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/adapter.py:20), while runtime imports `~/.hermes/.env` at [runtime.py:196](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/runtime.py:196). Use a pinned child environment; test conflicting keys/base URLs.

3. **False comparability.** Precommit the ten IDs, model/profile/concurrency/timeout and configuration digest. Assert every B01 attempt’s observed transport matches selection. Since historical typed-empty evidence is absent, call this a deterministic probe—not “empty-heavy”—unless the selection basis is restored.

Flash is acceptable for mechanical wiring; any provenance/transport ambiguity should return to Sol.

## B08-cut

Most likely FAILs:

1. **Schema still authorizes a ghost output.** The fallback at [resolution.py:641](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/resolution.py:641) can return an index absent from working outputs; mutation writes it at [apply_mutate.py:197](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_mutate.py:197), and projection finally fails at [projection_registry_v1.py:115](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/comfy_nodes/agent/projection_registry_v1.py:115).

2. **Dynamic contract becomes carte blanche.** Require positive and one-past-boundary fixtures for every named family. “Has dynamic `INPUT_TYPES`” alone cannot authorize arbitrary names; helpers such as Get/Set/Reroute need their actual directional semantics.

3. **Materialization shifts physical slots.** New-node inputs are empty at [ui.py:1325](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/emit/ui.py:1325). Materialize socket inputs in schema order, excluding literal widgets; otherwise KSampler-like nodes acquire wrong indices. Replace silent returns at [apply_links.py:303](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/vibecomfy/porting/edit/apply_links.py:303) with propagated typed diagnostics.

B03’s 2,838-workflow zero-mismatch result does not reduce this scope: it proves preservation comparison, not edit endpoint construction. Keep B08/reworks on Sol and rerun B03 plus B05 fixtures.

## B09

Most likely FAILs:

1. **A second hash authority.** D13 already owns the 100-row manifest and 98 source hashes at [scenario_manifest.py:91](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/scenario_manifest.py:91). Extend/copy that exact authority with aggregate and `primary_source` data; do not regenerate a parallel manifest.

2. **Irreproducible arithmetic.** Current summary only counts aggregate passes at [runner.py:324](/Users/peteromalley/Documents/reigh-workspace/vibecomfy-oracle/tests/live_agentic_harness/runner.py:324). Add a standalone reducer that reloads persisted evidence and reproduces first/eventual/infra-adjusted, 98-product, two-control, refusal tri-state, UI/provenance coverage and 97/3 matched/revised results.

3. **Unsupported historical claims.** `out/agentic/` remains absent. Therefore item 9 is presently inapplicable: name no flaky IDs and make no regression-versus-variance claim.

## Sequencing and cumulative invariants

Keep the frozen order. B05 must precede B08 because B08 explicitly depends on clean rollback; B06/B07/B09 overlap `runner.py`, `adapter.py`, `assessor.py` and artifacts, so each later batch must rerun prior focused suites. B09 arithmetic/denominator reworks should stay on Sol.

Preserve throughout:

- exactly 100 IDs: 63 edits, 35 semantic products, two controls; 97 matched/three revised;
- one B01 provenance format, redacted and never inferred;
- only typed empty receives exactly one retry;
- aborted candidates never become final UI, committed telemetry or report observations;
- no prose-based acceptance; missing evidence/outage never passes;
- one endpoint invariant, no synthetic undeclared ports, with B03 pin identity preserved;
- all report claims reproducible by stable ID, descriptor SHA, commit/config/corpus digests.

The external corpus absence is stale: D13 verified the provisioned 2,827-file corpus. The three questionable edits are also resolved by D13. Historical run evidence is still absent.

**Do not run the canonical 100-scenario lane before B07.** Without the selector and experiment, its transport/configuration is unpinned and the expensive evidence may be incomparable. A tiny harness smoke is reasonable; the canonical lane is not.

Read-only review completed; no files were modified.
