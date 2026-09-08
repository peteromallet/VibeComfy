# Publication and portability checks

These checks concern packaging, not product correctness. The working source was snapshotted without modifying the original checkout. Both GitHub destinations are public. Selected source and the unpublished commit were audited; no concrete credential blocker was identified. Existing public history contains historical developer-path examples; no automatic history rewrite was performed. Raw operational logs/caches were omitted.

Native capability evidence and recipient unknowns are in dependencies.md. A clean recipient-path check validates artifact links, pins, configuration and source hashes; it does not run the product test matrix.

# Public handover source audit

Date: 2026-09-08  
Candidate: `handover/canonical-workflow-integrity-20260908` at the snapshot rooted at `6254cf5e`  
Baseline: `origin/otto/canonical-workflow-source-20260903` (`1556b300`)

## Decision

The selected handover source is publishable from a credential and private-data perspective after the selected-path snapshot is taken. I found no private-key material, GitHub token, AWS access key, bearer credential, or credential assignment containing a non-placeholder value in the selected 70 paths (65 tracked edits plus 5 untracked `tests/*.py` files). No concrete secret redaction is required.

The selected paths contain operational temporary-path assertions and fixtures, which are test behavior and do not expose a user path or host. One inherited test fixture has a credential-shaped synthetic URL at `tests/test_headless_agent_artifacts.py:514`; it uses test-only placeholder data. Treat this as a hygiene follow-up only, not a publication blocker.

## Checks performed

- Read-only `git status`, `git diff --stat`, `git diff --name-status`, and selected-path manifest review.
- Reviewed reachable unpublished history with `git rev-list origin/otto/canonical-workflow-source-20260903..HEAD`: one commit, `6254cf5e` (`Catch ready-template UI materialize failures and match sidecar native slots.`). Its two changed paths are `tests/test_template_roundtrip.py` and `vibecomfy/porting/emit/ui.py`; no high-risk filename or secret material was found.
- Scanned all selected candidate paths and the tracked tree for private-key markers, common GitHub/AWS token forms, credential assignments, absolute user-home paths, email addresses, and private connection URLs. Secret-shaped examples were classified as documentation/test placeholders; no secret value was reproduced here.
- Excluded raw `.oracle/`, `.otto/`, and cache material from the audit and publication candidate as requested.

## Inherited history and portability sensitivity

The inherited tracked tree contains approximately 163 absolute `[historical-machine-path]` or `/home/...` path occurrences, concentrated in historical `.megaplan` records, audit evidence, fixtures, and development documentation. Representative locations include `.megaplan/briefs/messaging-boundary-cleanup-v2/GOAL.md`, `docs/audits/m1-safety-gate.md`, `docs/loose-work-consolidation-plan.md`, and `vibecomfy/intent/_ledger.py`. These are existing public-history portability/documentation concerns, not evidence of credentials or private operational access. They do not justify a wholesale history rewrite for this handover. Future cleanup may replace machine-specific examples with repository-relative or generic paths.

## Limits and blockers

This was a bounded static, read-only audit. I did not run tests, contact the network, inspect external services, execute scanners such as gitleaks, or attempt credential validation. Generated/raw `.oracle/` and `.otto/` material was intentionally excluded. No publication blocker was found within the authorized selected source and reachable unpublished history.

## Git publication clarification

This handover consists of ordinary source and documentation commits on a GitHub branch. No ZIP, tarball, or archive bundle was created. The pinned handover skill now explicitly requires this default. Independent portability inspection found the documents needed committing before publication; they are included in the handover commit. Local checks resolved all document links, parsed the seven roles and two review stages, preserved budgets, and matched all 70 selected source hashes. Product acceptance evidence remains NOT RUN.
