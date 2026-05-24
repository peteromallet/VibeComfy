# Strict Ready Exceptions

This inventory is the only place for temporary strict-ready exceptions on
protected repo templates. A protected template is one where `app_active` is
`true` or `coverage_tier` is `required`.

As of May 24, 2026, the strict-ready gate reports 15 protected-template
violations tracked as exact temporary exceptions below. All protected-template
entries are categorized as `blocked` because they belong to required/app-active
templates and must be removed before those templates can be considered clean
strict-ready examples. The Phase 0 sprint added exception-loading support to
the gate tool (`check_strict_ready_templates.py`) so documented exceptions
suppress enforced errors without hiding them from the diagnostic output. The 4
Phase 0 entries (added 2026-05-24) are `legacy_vocabulary_call` violations for
`wf.register_input` calls emitted by the Phase 0 emitter; they will be resolved
by the Phase 1 emitter migration to `public()` inline registration.

One additional `scratchpad-only` entry (added 2026-05-24 for Family I / T8)
documents the opaque UUID component in the porting test fixture
(`tests/fixtures/porting/opaque_component.json`). It is not a protected
template and is documented here as a policy artifact per SD1: the component
cannot be materialized without a subgraph definition.

## Entry Rules

Exceptions must be exact, violation-scoped records in
`docs/strict_ready_exceptions.json`. Matching uses all three fields:

- `ready_id`
- `violation_code`
- `target`

Each entry must include:

- `id`: stable exception id.
- `ready_id`: template id, such as `video/wan_t2v`.
- `violation_code`: strict-ready diagnostic code.
- `target`: exact node, field, output, or descriptor target for the violation.
- `owner`: default `workflow-porting` unless another owner is accountable.
- `ticket`: follow-up ticket id or issue URL.
- `reason`: why the violation cannot be fixed now.
- `allowed_until`: concrete expiry date.
- `removal_condition`: objective condition that removes the exception.
- `final_category`: one of `reference`, `supplemental`, `blocked`, or `scratchpad-only`.

False positives caused by static extraction drift are not valid exceptions.
Fix the extractor, static index, or ready template so static and built
contracts agree before adding any exception.

## Current Inventory

| Exception | Template | Violation | Target | Owner | Ticket | Until | Category |
|---|---|---|---|---|---|---|---|
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5020-widget3` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5020.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5021-widget2` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5021.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-hdr-hidden-model-5021-widget3` | `video/ltx2_3_lightricks_iclora_hdr` | `hidden_model_filename` | `node:5021.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5020-widget3` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5020.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5021-widget2` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5021.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-hidden-model-5021-widget3` | `video/ltx2_3_lightricks_iclora_motion_track` | `hidden_model_filename` | `node:5021.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-iclora-motion-widget-5044-widget1` | `video/ltx2_3_lightricks_iclora_motion_track` | `strict_ready_unresolved_widgets` | `node:5044.widget_1` | `workflow-porting` | `01KRKQGP81Z5XR0FAK19T5CAC8` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4980-widget2` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4980.widget_2` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4980-widget3` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4980.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-hidden-model-4981-widget3` | `video/ltx2_3_lightricks_two_stage` | `hidden_model_filename` | `node:4981.widget_3` | `workflow-porting` | `01KRNDP7S3BW6DMNKAWPNVVYMB` | 2026-06-30 | `blocked` |
| `sre-20260516-ltx23-two-stage-widget-4988-widget1` | `video/ltx2_3_lightricks_two_stage` | `strict_ready_unresolved_widgets` | `node:4988.widget_1` | `workflow-porting` | `01KRKQGP81Z5XR0FAK19T5CAC8` | 2026-06-30 | `blocked` |
| `sre-20260524-qwen-image-2512-legacy-register-input-112` | `image/qwen_image_2512` | `legacy_vocabulary_call` | `ready_templates/image/qwen_image_2512.py:112` | `workflow-porting` | `phase-1-emitter-register-input-migration` | 2026-07-31 | `blocked` |
| `sre-20260524-ltx23-first-last-iclora-control-legacy-register-input-379` | `video/ltx2_3_first_last_frame_travel_iclora_control` | `legacy_vocabulary_call` | `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py:379` | `workflow-porting` | `phase-1-emitter-register-input-migration` | 2026-07-31 | `blocked` |
| `sre-20260524-ltx23-first-last-iclora-control-legacy-register-input-380` | `video/ltx2_3_first_last_frame_travel_iclora_control` | `legacy_vocabulary_call` | `ready_templates/video/ltx2_3_first_last_frame_travel_iclora_control.py:380` | `workflow-porting` | `phase-1-emitter-register-input-migration` | 2026-07-31 | `blocked` |
| `sre-20260524-wan-i2v-legacy-register-input-106` | `video/wan_i2v` | `legacy_vocabulary_call` | `ready_templates/video/wan_i2v.py:106` | `workflow-porting` | `phase-1-emitter-register-input-migration` | 2026-07-31 | `blocked` |
| `sre-20260524-opaque-component-fixture-a1b2c3d4` | `test/family_i_opaque` | `opaque_component_node_class` | `node:2` | `workflow-porting` | `phase-1-family-i-opaque-materialization` | 2026-08-31 | `scratchpad-only` |

Removal conditions are stored on each JSON entry. In summary:

- `01KRNDP7S3BW6DMNKAWPNVVYMB`: expose the hidden
  `ltx-2.3-22b-dev-fp8.safetensors` Gemma text encoder selections as named
  public inputs or authored model assets.
- `01KRKQGP81Z5XR0FAK19T5CAC8`: rewrite the remaining schema-backed
  `PrimitiveInt` positional widgets with named inputs or add committed widget
  schema alias evidence.
- `phase-1-emitter-register-input-migration`: update the emitter to emit
  `public()` inline calls for model-picker inputs and regenerate all affected
  templates so `wf.register_input` is no longer emitted by the Phase 1 emitter.
- `phase-1-family-i-opaque-materialization`: provide subgraph definitions for
  UUID-class opaque components so the emitter can materialize them as inline
  Python functions per the Family I (SD1) policy, or replace them with
  first-class replacement nodes.

Generated-template style warnings are not strict-ready exceptions and are not
listed here. They remain reported by the strict-ready gate as non-enforced
warnings.
