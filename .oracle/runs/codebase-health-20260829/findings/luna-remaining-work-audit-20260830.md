# Remaining-work audit — 2026-08-30

The campaign is not complete. HTTP authorization has an independent Sol PASS at `c2b08774` and is eligible for exact-tree admission. B15 same-key pre-publication idempotency is an architecture reset, not an incremental patch; keep its session/route/browser boundary isolated. After HTTP admission, run only non-HTTP/non-B15 owners in parallel, then converge exact PASSed tips at one gate.

Evidence: `reviews/luna-continuation-backlog-v3.md`, `status.md`, `reviews/sol-http-authorization-c2b08774-independent.md`, `reviews/sol-big-picture-oracle-20260830.md`, `reviews/sol-process-ownership-oracle-20260830.md`, and `reviews/luna-concurrency-state-wave.md`.

## Matrix

| Area | State | Evidence / next action |
|---|---|---|
| Environment; fixture provider; schema-cache; bounded simulation; rollback journal; object-info hermeticity; registry aliases | DONE/admitted | Exact reviewed successors replayed as `a3d9e36d`, `de9dc858`, `fb83802e`, `5e9d7ed3`, `fc1b43ec`, `ee1d6316`, `8fbd2c79`; gates are recorded in backlog/checkpoints. |
| Final-gate comparator | DONE (evidence-only) | Attempt 2 PASS; eight mechanically enumerated fixtures and immutable baseline checks; does not replace broad gates. |
| HTTP authorization | ACTIVE ADMISSION | Exact `c2b08774` Sol PASS after seven adversarial iterations; admit only exact tree and bind focused receipts; no attempt 8. |
| B15 same-key pre-publication claim | ARCHITECTURE RESET/ACTIVE | Sol rejected the 1,383-line draft: authority came after provider/research work, with fence-less downgrade, incomplete recovery, and export loss. Rebuild with reservation before executor/model work, one typed fence through publication, auth before mutation, and route 202/409 plus polling. |
| Final delivery truth | BLOCKED BY DEPENDENCY | Exact final SHA needs repository-wide pytest, `make check`, mechanical baseline comparison, clean/hash receipts, final Sol/oracle PASS, and ref sync. Baseline: 8517 passed, 530 failed, 137 skipped, 1 xfailed, 40 errors; no waiver. |
| Extraction/full descendant containment | EXPLICIT HOLD | Sol ruling is fail-closed: detached/Windows non-Job descendants unverified; no destructive cleanup or “all gone” claim. |
| Z-Image/provider-derived maximum; wheel templates; lock provisioning | EXPLICIT HOLD | Requires product authority; checkout owns corpus and lock packages are inventory, not provisioning authority. |
| P2 refactors | HOLD | Wait for correctness closure and characterization coverage. |

## Maximum-parallel wave after HTTP admission

Keep B15 in its own worktree. Start these disjoint owners:

1. **Registry staging/source identity (P1/high impact):** serialize/revalidate same-target staging, restrict fallback to `EXDEV`, and reject or explicitly pin duplicate shipped targets. Own registry/model-assets files exclusively.
2. **Under-keyed caches (P1):** add two-environment/two-workflow/changing-`CURRENT` regressions and smallest identity/invalidation fixes; do not reopen admitted schema-transaction ownership.
3. **Lazy node-pack/plugin initialization (P1):** atomically publish module maps and make concurrent registration success/failure/retry explicit.
4. **Schema-provider/terminal projection (P1):** first reproduce event-loop sync-provider failure and round-trip provider drift; make narrow fixes, keeping staged-undetermined terminal behavior separate.
5. **Evidence/test truth (P1/P2):** optional-dependency collection, corpus/layout failure classification, and a fresh-interpreter harness subprocess contract may run in parallel when ownership is disjoint. Do not run broad pytest in these lanes.

## Safe independent P1 implementations now

- **Vision MIME labeling:** `judge_vision` accepts JPEG bytes but labels PNG. Add PNG/JPEG/base64/invalid-byte handling and focused tests; isolated from HTTP, B15, registry, and schema transaction owners.
- **Durable JSON type validation:** validate `DiagnosticRecord.from_dict` and durable-turn iteration with typed corruption diagnostics at reader boundaries; do not alter B15 claim/publication state.

Cache, lazy-init, provider, and warm-up items are valid P1 work, but require a short contract/ownership probe first and should not be bundled.

## Risk-weighted completion

Accepted-backlog coverage is approximately **70–80%**. Delivery readiness is only approximately **45–55%**, because remaining work is concentrated in HTTP security admission, B15 idempotency authority, and exact-final broad/oracle gates.
