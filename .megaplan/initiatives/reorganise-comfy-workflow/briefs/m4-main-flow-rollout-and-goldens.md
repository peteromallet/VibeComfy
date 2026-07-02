# M4: Main-Flow Rollout And Golden Validation

## Outcome

Roll the reorganiser into the main flow conservatively as suggestion-only behavior, and prove it across golden fixtures and browser/e2e scenarios.

## Scope

In scope:

- Integrate deterministic `assess_layout_quality(ui_json)` into the main agent flow as a cheap pre-classify or classify-context hint.
- Add classifier/routing support for explicit organisational intent, e.g. "organise this workflow", "clean up the canvas", "make this readable", and `/reorganise_comfy_workflow`, so a purely organisational request can route to the reorganise candidate path without being mistaken for a functional graph edit.
- Add post-execution layout assessment after successful functional candidate generation: if the edited graph is structurally valid but visually degraded or crosses the layout-quality threshold, surface a follow-up suggestion or optional reorganise candidate rather than silently running another edit step.
- Base post-execution layout decisions on edit magnitude and visual impact, not only the absolute final layout score:
  - nodes added/removed;
  - links rewired;
  - number of touched groups;
  - new helper/reroute/Set/Get nodes;
  - candidate node bounding boxes outside existing groups;
  - overlap/backwards-edge/spacing delta versus the submitted graph;
  - whether the edit introduced or expanded a parallel branch/sampler/output path.
- Feed ambiguous layout cases into the message/humanization stage as an "offer reorganisation" recommendation instead of forcing a candidate. The final reply should be able to say, in plain language, that the edit was applied and the canvas may benefit from reorganisation, with an explicit next action.
- Keep default behavior at `suggest`; do not auto-apply or silently rewrite layouts.
- Add config:
  - `VIBECOMFY_REORGANISE_AUTO=off|suggest|candidate`
  - default `suggest`
- Add golden fixtures for representative workflows:
  - simple text-to-image;
  - positive/negative prompt pair;
  - ControlNet depth/pose branches;
  - IPAdapter/reference chain;
  - sequential base/refiner samplers;
  - parallel sampler variations;
  - alternative muted sampler;
  - shared model/VAE;
  - Set/Get and reroute helpers;
  - existing coherent and incoherent groups;
  - disconnected islands;
  - subgraph scopes.
- Add browser/e2e or screenshot-level checks where feasible:
  - candidate appears;
  - Apply is blocked/allowed correctly;
  - canvas reflects layout changes;
  - no overlapping UI elements in representative viewport.
- Update docs and release notes.
- Add rollout guidance: explicit skill first, suggestion-only auto integration, candidate mode only after goldens pass.

Out of scope:

- Auto-apply in main flow.
- New frontend design work beyond existing panel/candidate behavior.
- Runtime execution of reorganised workflows on ComfyUI.

## Locked Decisions

- Main-flow integration starts suggestion-only.
- Reorganisation remains preview/candidate based.
- Automatic classifier hint cannot override user intent.
- If user asks for a functional edit, reorganisation should be offered only when layout quality is a blocker for review or the user explicitly asks for readability.
- A purely organisational user request is first-class intent, not a vague revise/adapt fallback. It should create a layout-only candidate with apply eligibility governed by the same candidate lifecycle as other graph changes.
- Post-execution reorganisation is a follow-up decision, not an implicit hidden phase. The system may suggest or prepare a candidate when configured, but it must not loop into another agent step without explicit route/config support.
- Small, local edits should not trigger noisy reorganisation offers unless they materially worsen layout metrics. Large edits that add branches, outputs, samplers, or many nodes should be assessed more aggressively even if the original workflow was already passable.
- Ambiguity resolves toward messaging, not mutation: when the system is unsure whether reorganisation is warranted, it should pass an `offer_reorganisation` advisory to the final message stage and avoid creating a second candidate unless the user asks or config permits.

## Open Questions

- Which golden fixtures should be committed versus generated in test setup?
- Do we need Playwright screenshots in CI or only local/manual browser tier?
- What threshold promotes `VIBECOMFY_REORGANISE_AUTO=candidate` from experimental to supported?

## Constraints

- Keep main-flow overhead low; assessment must be cheap or cached by graph hash.
- Do not inflate classify prompts with large layout projections.
- Do not create latest applyable candidates on non-applyable routes.
- Preserve all existing agent-edit stale-candidate safety.

## Done Criteria

- Main-flow assessment hint appears in structured evidence when layout quality is poor.
- Classifier tests cover explicit organisational requests and prove they route to the reorganise path without requiring research or functional graph edits.
- Post-execution assessment records whether the resulting candidate layout is still acceptable, should suggest reorganisation, or should produce an optional reorganise candidate under configured modes.
- Post-execution assessment uses edit-magnitude features and before/after layout deltas, with tests for small prompt edits, one-node additions, branch additions, multi-sampler edits, and output-path additions.
- Ambiguous post-edit cases produce an `offer_reorganisation` message-stage advisory without creating an unexpected layout candidate in default `suggest` mode.
- Default `suggest` mode never mutates or creates surprise candidates.
- Explicit readability requests can produce reorganise candidates through the normal candidate path.
- Golden fixtures pass numeric aesthetic gates.
- Browser/e2e coverage proves at least one explicit `/reorganise_comfy_workflow` flow and one main-flow suggestion flow.
- Docs explain explicit use, automatic suggestion behavior, limits, and no-topology-change guarantee.

## Touchpoints

- `vibecomfy/executor/core.py`
- `vibecomfy/executor/contracts.py`
- `vibecomfy/comfy_nodes/agent/*`
- `vibecomfy/comfy_nodes/web/*`
- `vibecomfy/porting/reorganise/*`
- `tests/e2e/*`
- `tests/test_comfy_nodes_agent_edit.py`
- `tests/test_reorganise_goldens.py`
- `docs/agent-skill/*`
- `docs/plans/reorganise-comfy-workflow-plan.md`

## Anti-Scope

- Do not add auto-apply.
- Do not require ComfyUI runtime or model files in ordinary tests.
- Do not rework the panel UI into route-specific controls.

## Rubric

Overall plan difficulty: 4/5; selected profile: partnered-4; because the risk is subtle integration with the existing agent flow, candidate lifecycle, and user-visible layout quality rather than raw implementation size.
