# Agent Edit Complete Robustness — Current Execution State

Updated: 2026-07-17 Europe/Berlin

## Goal and routing

Execute `docs/plans/agent-edit-complete-robustness-architecture.md` end to end.

- Easy: DeepSeek Pro
- Medium: Claude Code routed through GLM 5.2
- Hard: Claude Code routed through GLM 5.2 with higher reasoning
- Exceptional escalation only: GPT-5.6 Sol

The executable profiles use parser-valid effort-only `claude:*` specs. The
active Claude Code provider must be configured for GLM 5.2 before medium or
hard execution.

## Integration-first execution policy

The full M0–M6 outcome and final nine-point audit are unchanged. Within that
outcome, use an integration-first diminishing-returns rule for bounded units:

- two independent acceptances, focused adversarial coverage, and broad green
  gates close the bounded unit;
- do not request a third or fourth review unless new contradictory evidence
  appears;
- after closure, prioritize the next integration boundary instead of polishing
  the already-accepted unit in isolation; and
- an isolated timing flake requires one exact rerun and then one full relevant
  rerun. If those are green, record the flake and continue; do not enter an
  unlimited polishing loop without reproducible failure evidence.

This rule controls execution effort, not scope or quality. It cannot waive a
declared milestone proof, ownership cut, real-ComfyUI scenario, recovery path,
or final audit item.

## Milestone state

- M0 is committed, proven, and closed.
- M1 is committed, proven, and closed.
- M2 Slices 1–2 are implemented and independently accepted. The observation-
  only Family-A preparation and the C0–C1 contract checkpoint are also
  accepted. The adjacent panel/workflow scheduler activation fence is proven
  and accepted. The bounded C2a receipt core has two independent acceptances
  and passes its focused 20/20 suite, but it remains uncommitted and
  unintegrated. It has not changed the production adapter or ownership ledger.
  C2b native resolver work is next. None of these closes native ownership:
  0/27 coupled S3 rows have transferred, all seven S4-debt rows remain open,
  and the C2 atomic native-owner cutover is pending. Slices 3–6 remain open,
  so M2 is not complete.
- M3–M6 and the final nine-point audit remain pending.

## Active work

M2 Slices 1–2 established the source-derived native-access ledger and the
dependency-injected typed public adapter boundary. The bounded acceptance
proved 77/77 focused adapter/ownership/projection/M1 tests, 519/519 browser
contracts, and 238 roundtrip passes with 2 intentional legacy skips. The sole
machine ledger contains 78 unique stable rows and 120 unique
file/region/kind mappings; its schema, alias-bypass, duplicate, stale-row, and
count-drift sentinels are green. `git diff --check` and production parsing of
both Arnold profiles (68 agent specs) are also green.

The M2 Family-A preparation is accepted as a lossless observation checkpoint:
the exact `eb45e0ef…` incident fixture is provenance-pinned and reproducible,
detached normalized capture and stable-ID draw evidence fail closed, and the
seven persistent-write/harness rows are truthfully classified as S4 debt.
Acceptance evidence is 65/65 focused adapter/ownership tests, 532/532 browser
contracts, and 1,413 browser-smoke passes with 2 intentional skips. This
checkpoint performs no coupled owner cut: the transfer count is **0/27**, S3
is **not closed**, and `vibecomfy_roundtrip.js` remains the truthful owner of
the coupled legacy behavior pending the atomic cut.

The C0–C1 checkpoint is accepted as a contract and private-plan proof only.
It adds the cross-language `layout_operation_v1`,
`mutation_materialization_v1`, and inverse-relation contracts; shared goldens;
strict numeric parity; prepared-authority/restoration binding; legacy
authority migration; the dependency-closure guard; and a pure private prepared
plan builder. The builder is externally proven to make zero native calls. The
shared browser authority factory preserves the exact operation list and order;
it does not deduplicate rewires or any other operations. Acceptance evidence is
156/156 focused JavaScript, 118/118 focused Python, 294/294 lifecycle, 60/60
repair/compatibility, and 569/569 browser-contract tests. Canonical parity is
green for 64 templates and both Arnold profiles parse all 68 configured agent
specs.

The scheduler activation fence is accepted as an adjacent release-safety fix,
not as C2 mutation ownership. Queued render work is fenced by the concrete
panel and workflow activation; late callbacks from replaced panels or departed
workflows are revoked, and render diagnostics are panel-affine. Browser smoke
passes 1,531 tests with 2 intentional skips, and the full roundtrip file passes
238 tests with 2 intentional skips in two consecutive full-file runs. This
changes scheduling/observability only; it does not route native mutation,
transfer a ledger row, or claim S3/S4 closure.

M2 continues at C2 in the coupled S3+S4 work described by
`briefs/m2-slices-3-4-implementation.md`. The versioned contracts and private
plan proof are landed prerequisites. The bounded C2a receipt core is accepted
on 20/20 focused tests but remains an uncommitted, unintegrated private draft;
it is not a production checkpoint and transfers no ownership. The next
integration boundary is C2b: resolve the exact native targets and capabilities
behind that receipt without exposing live objects or routing a consumer. C2c
then performs the indivisible consumer/deletion/ledger cut moving stable
identity, index/link mechanics, canonical mutation, inverse, and restoration
behind the adapter. Slices 5–6 then prove real incident behavior and final
ownership.

## M1 proof

- Browser contracts: 467/467.
- Roundtrip: 242 passed, 2 intentional legacy skips.
- Python backend spine: 288/288.
- Focused Python M1/session: 69/69.
- Full Python fast gate: 584 passed, 1 intentional skip.
- Concurrent accept/reject race: 10/10 consecutive runs.
- Static ownership/identity/version searches: clean.
- Python compilation and `git diff --check`: clean.
- Claude Code through GLM 5.2: architecture accepted after the race-fixture
  correction; no production blocker remained.

`scorecard.png` remains unrelated and must not be staged or modified.
`docs/plans/vibecomfy-screen-share-recording-brief.md` is likewise protected
and remains outside this initiative commit.
