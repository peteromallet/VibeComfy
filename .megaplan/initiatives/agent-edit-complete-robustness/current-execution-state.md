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

## Milestone state

- M0 is committed, proven, and closed.
- M1 is committed, proven, and closed.
- M2 Slices 1–2 are implemented and independently accepted. The observation-
  only Family-A preparation for the coupled S3+S4 work is also accepted, but
  S3 is not closed: 0/27 coupled ownership rows have transferred. Slices 3–6
  remain open, so M2 is not complete.
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

M2 continues from the coupled S3+S4 contract/cutover work in
`briefs/m2-slices-3-4-implementation.md`. The versioned
`layout_operation_v1` and `mutation_materialization_v1` contracts must land
before one atomic consumer/deletion/ledger cut moves stable identity,
index/link mechanics, canonical mutation, inverse, and restoration behind the
adapter. Slices 5–6 then prove real incident behavior and final ownership.

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
