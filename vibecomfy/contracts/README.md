# Contracts

Semantic contracts, validation policies, and runtime contract models live here.

Use [`RUNTIME_CONTRACT.md`](RUNTIME_CONTRACT.md) for the runtime-specific
contract reference. The Python modules in this package define reusable issue
codes, validation reports, doctor contracts, and higher-level workflow intent
checks.

## Temporal delivery

`vibecomfy.contracts.temporal` contains model-independent planning objects for
video workflows: `FrameSlice`, `TemporalPlan`, `TerminalConstraint`, and
`DecodedMediaExpectation`. They capture half-open frame arithmetic, delivery
versus working/context accounting, caller-supplied alignment positions, and
decoded-output expectations. Model-specific latent grids and editorial choices
belong in the caller; these contracts only validate the supplied plan and
serialize JSON-safe evidence for a later runtime verifier.
