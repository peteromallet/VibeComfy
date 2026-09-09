# Review packet: {{stage_id}} / round {{round_number}}

## Assignment
Reviewer role and configured model/reasoning binding: {{resolved_reviewer_role}}. The role and stage determine packet content and lens; the model binding is execution metadata and does not create criteria or authority.
Lens: {{lens}}. Stage trigger: {{after}}.
Scope tasks: {{scope_tasks}}. Criteria: {{criteria_ids}}.
Round budget: {{round_number}} of {{stage_max}}; overall review calls {{used}} of {{total_max}}.
Goal: independently determine whether the scoped deliverable satisfies these criteria. You are a leaf reviewer, not the coordinator or oracle. Do not delegate, mutate the candidate, widen scope, reset counters or treat a prior PASS as proof.

## Authoritative contract
{{complete_northstar}}
{{agent_goal_and_explicit_scope_authorization}}
{{scoped_implementation_criteria_with_expected_behaviors_and_dependencies}}
{{applicable_plan_decisions_non_goals_and_task_requirements}}

## Frozen candidate and artifacts
Base SHA/snapshot: {{base_identity}}.
Candidate SHA/tree or snapshot manifest: {{candidate_identity}}.
Read-only source location: {{source_location}}.
Packet/source/evidence manifest: {{manifest_location_and_digest}}.
Changed-path census and relevant integration paths: {{path_census}}.
Full scoped diff for first round: {{diff_location}}.
Correction delta for later rounds: {{delta_location_or_not_applicable}}.

Evidence coverage (one row per scoped criterion):
| Criterion | Required behavior/scenario | Exact command/input/environment | Result | Evidence path + digest |
| --- | --- | --- | --- | --- |
{{coverage_rows}}

Missing evidence is explicitly marked MISSING, not inferred from a worker narrative. Test results prove only the behavior they exercise; inspect source/integration for untested failure paths. Existing valid receipts can be reused if identities match. Inspect files as needed, but do not repeat broad tests or discovery just because you are a new reviewer.

## Completion review — every executable review
- Is each scoped requirement actually implemented and wired through the relevant entrypoints?
- Does behavior match the contract, including negative/error cases, authorization, data integrity and interactions relevant to this change?
- Do the artifacts demonstrate the claimed result, or merely mocks, process success or an implementation-shaped assertion?
- Are there concrete defects/regressions, missing pieces or required evidence gaps?
- Are interfaces and documentation in scope consistent with the actual behavior?

Do not demand later-stage work in an intermediate review. Check the full declared scope, not only the last changed file. Report source/evidence-backed findings, not generic hardening suggestions.

## Strategic review — only strategic or completion_and_strategy lens
- Does the integrated outcome advance the North Star and the agreed user goal?
- Do components, data identities, approvals and responsibilities fit together without contradictions or hidden assumptions?
- Has necessary existing behavior been preserved, and has the implementation stayed within scope?
- Are new abstractions, duplicated mechanisms, services or handoffs justified by current requirements? Identify concrete removals/reuse that preserve the goal.
- Did local implementation choices create systemic complexity or an integration defect that local tests miss?

Do not reopen settled product design merely because another approach is possible. Unnecessary complexity is a blocker only when it violates an explicit criterion/non-goal or causes a concrete defect; otherwise classify it as optional. Strategic approval cannot override failed completion criteria.

## Prior decisions and correction scope
{{accepted_findings_and_oracle_dispositions_or_none}}
{{changed_criteria_and_dependency_closure_or_first_round}}
Include the concrete issue/evidence and accepted resolution, not persuasive prior reviewer verdict prose. Later rounds verify the correction and affected integration; preserve unrelated approvals. Flag a newly discovered real blocker with evidence, not a reset of the whole scope.

## Required result
Verdict: PASS / REWORK / UNKNOWN.
- PASS: all scoped required criteria have adequate evidence and no unresolved blockers.
- REWORK: at least one evidenced contract violation or implementation defect, or a required proof gap attributable to the deliverable.
- UNKNOWN: inaccessible/mismatched candidate or evidence prevents a reliable review; never invent PASS.
For each finding: criterion ID, classification (contract_violation / implementation_defect / required_evidence_gap / optional_improvement / out_of_scope / stale_or_repeated), exact source/evidence, actual versus required behavior, and smallest required outcome. Do not prescribe a new architecture without necessity.
Return criterion dispositions with evidence references. State North Star alignment (aligned / concrete conflict / not assessable); for completion-only scope, limit this to the applicable invariants rather than a new strategic audit. Separate optional suggestions from blockers. The coordinator follows the mandate and routes contested judgments to the configured oracle.
