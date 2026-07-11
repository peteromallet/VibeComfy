# Corrective 1 review recovery

Date: 2026-07-10 UTC

## Decision

Resume the existing `vibecomfy-trust-corrective-2026-07` chain without a human-approval override after the corrective gate is green. This is an automatic recovery under the initiative's existing `merge_policy: auto` and `driver.auto_approve: true`; it is not evidence of a human approval.

## Evidence

- The canonical plan gate recommends `PROCEED`.
- `user_actions.md` records no human actions.
- The prior T16 blockers were automatable: the missing authoritative gate surface and successful-artifact path sanitation.
- Commit `a7cfc25207ecf486e78f953e29640d4d661a1c93` added the locked, runner-separated gate and durable verification evidence.
- A fresh operator rerun found one timing-sensitive Node assertion that observed persisted provider selection before the route control settled. The test now waits for both sides of that contract; it does not waive or quarantine the assertion.

## Recovery invariant

Advance only after `make corrective-trust-gate` passes with nonzero Python, Node, and Playwright collection, no unexpected/flaky/skipped Playwright result, unchanged quarantine hashes, and sanitized artifacts. Preserve genuine human-only or security gates if a later milestone introduces one.

## Remaining human boundary

The fresh canonical review moved the plan to `awaiting_human_verify`. Do not synthesize those verdicts from automated tests. The three pending must-level checks are criterion 4 (observe runtime security/redaction logs), criterion 5 (inspect the runtime info/panel identity UI), and criterion 7 (drive and visually inspect the real ComfyUI overlay while observing its logs). Criterion 10 is also classified human-only but is a should-level artifact-quality judgment rather than a must-level advancement gate.
