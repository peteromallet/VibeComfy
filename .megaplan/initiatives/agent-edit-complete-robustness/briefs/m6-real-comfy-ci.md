# M6 — Clean Real-ComfyUI Composition and Anti-Regression Gate

## Outcome

Industrialize deterministic real-ComfyUI proof and CI guardrails so every
complete-robustness claim is backed by authoritative integration evidence.

## Scope

Build pinned minimal and compatibility environments, exercise all supported
transactions through real ComfyUI success/failure/recovery paths, and enforce
architecture ownership in CI.

## Locked decisions

- Minimal-environment failures block release.
- Compatibility warnings are explicitly attributed/allowlisted.
- Static scans supplement rather than replace real behavior.
- Unsupported nested structures fail before mutation.
- Ambient console cleanliness is not itself product correctness.

## Open questions

- Representative node-pack list and versions.
- Supported ComfyUI/frontend version range.
- Per-PR versus scheduled compatibility budget.

## Constraints

Do not promise every third-party pack and do not add nested-scope support.
Separate VibeComfy, ComfyUI core, and extension failure attribution.

## Done criteria

- Every nine-point completion item has a direct test or static gate.
- All incident and adversarial fixtures pass through real ComfyUI.
- Success, failure, refresh, switching, rollback, and persistence are covered.
- CI runs the complete required browser/composition set.

## Touchpoints

Playwright/E2E, ComfyUI launcher, CI workflows, compatibility ledger,
ownership tests, incident fixtures, evidence artifacts.

## Anti-scope

No universal custom-node support, nested scopes, or console-cleanliness proxy.
