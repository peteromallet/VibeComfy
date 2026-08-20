"""Single 57-failure owner ledger for the IR-everywhere sprint.

This is the only ledger.  ``tests/test_ir_laws.py`` and
``vibecomfy.intent._fixture`` both import it.  There is no second id set.

Reconstruction source
---------------------
The 57 unique scenario ids are the first-attempt failures of the host
recovery rerun:

    /Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run/out/agentic/recovery-rerun/run_summary.json

``failed`` / ``raw_first_attempt_failed`` = 57, ``raw_first_attempt_success``
is False on exactly those 57 unique ids.  All 57 ids are recoverable from
that artifact.

v1 (``ir-everywhere-57``) and v2 (``ir-everywhere-57-v2``) are INVALID
and must not be used for reconciliation: v1 imported the recovery-run
package via cwd-on-sys.path; v2 measured a dirty moving tree.

The only valid post-migration artifact is ``ir-everywhere-57-v3``, now
``complete: true`` with ``final_score: 16/57``.  Judge verdicts come from
each scenario's ``assessment.json`` ``passed`` field, not executor-level
``ok`` on the run_summary row.

A prior planning reconstruction (``.oracle/findings/failure-partition.txt``)
built 48 family-doc ids + 9 case-note ids.  That is a *different* 57
(partial overlap with this run).  This ledger does not mix the two sets
and does not invent the missing planning-partition ids.

Status rules
------------
- ``resolved`` requires the actual ids, the owning mechanism, and a v3
  judge pass (``assessment.json`` ``passed=true``).
- ``capability_floor`` is used only with named evidence (Class D hard floor
  or the variance family doc) that v3 still confirms as product_fail.
  ``cc0df7``, ``90a1d5``, and the variance id live only here.
  ``5b31ce`` is not a named floor.
- ``infra_out_of_scope`` is a v3 ``failure_class=infra_timeout`` /
  ``score_class=infra_blocked`` (8 ids).
- remaining v3 product_fail ids stay ``pending_live_rerun``.
"""

from __future__ import annotations

from dataclasses import dataclass


LEDGER_RECONSTRUCTION_SOURCE = (
    "/Users/peteromalley/Documents/reigh-workspace/vibecomfy-recovery-run/"
    "out/agentic/recovery-rerun/run_summary.json"
)
V3_ARTIFACT = (
    "/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/"
    "out/agentic/ir-everywhere-57-v3/run_summary.json"
)
V3_ATTEMPTS = (
    "/Users/peteromalley/Documents/vibecomfy-ir-everywhere/vibecomfy/"
    "out/agentic/ir-everywhere-57-v3/attempts"
)
LEDGER_ID_COUNT = 57
LEDGER_UNRECOVERABLE_COUNT = 0
CLASS_D_HARD_FLOOR_IDS = frozenset(
    {
        "3d-3d-model-generation-and-preview-workflow-cc0df7",
        "3d-3d-model-generation-and-rigging-workflow-90a1d5",
    }
)
_EXIT_STATUSES = frozenset(
    {"resolved", "capability_floor", "infra_out_of_scope", "pending_live_rerun"}
)
_V3_MECHANISM = "v3 live rerun on ir-everywhere branch"
_V3_PASS_EVIDENCE = (
    "v3 assessment.json passed=true for each id at "
    f"{V3_ATTEMPTS}/<id>/attempt_1/<id>/assessment.json; "
    f"{V3_ARTIFACT} complete=true, final_score=16/57."
)
_V3_INFRA_EVIDENCE = (
    "v3 assessment.json passed=false; run_summary failure_class=infra_timeout "
    f"/ score_class=infra_blocked (8 of 57). Artifact: {V3_ARTIFACT}."
)


@dataclass(frozen=True, slots=True)
class FailureLedgerRow:
    family: str
    owner: str
    scenario_ids: tuple[str, ...]
    status: str
    evidence: str
    mechanism: str = ""

    @property
    def count(self) -> int:
        return len(self.scenario_ids)


EXIT_FAILURE_LEDGER: tuple[FailureLedgerRow, ...] = (
    FailureLedgerRow(
        family="class_d_hard_floor",
        owner="capability floor; not a sprint phase",
        scenario_ids=(
            "3d-3d-model-generation-and-preview-workflow-cc0df7",
            "3d-3d-model-generation-and-rigging-workflow-90a1d5",
        ),
        status="capability_floor",
        evidence=(
            "scripts/b09_reducer.py CLASS_D_HARD_FLOOR: cc0df7 Rodin has no "
            "model selector; 90a1d5 TripoRig has no joint control.  v3 "
            "assessment.json passed=false, score_class=product_fail (not "
            "infra).  These ids are not resolved via Law 4 or interpret."
        ),
    ),
    FailureLedgerRow(
        family="semantic: variance",
        owner="phase 5",
        scenario_ids=("multi-wan-vace-video-retargeting-driven",),
        status="capability_floor",
        evidence=(
            "docs/failure-analysis/variance.md — model-variance capability "
            "floor.  v3 assessment.json passed=false, score_class=product_fail.  "
            "The Class D hard-floor ids live only in class_d_hard_floor."
        ),
    ),
    FailureLedgerRow(
        family="v3_live_pass",
        owner="v3 live rerun",
        scenario_ids=(
            "audio-acestep-audio-generation-with-detail-daemon-f0859f",
            "image-dual-checkpoint-xl-image-generation-with-refin-c9df19",
            "image-gemini-prompt-splitter-and-text-display-workfl-caae97",
            "image-image-processing-with-sharpening-film-grain-an-9aa0f1",
            "image-qwen-image-inpainting-with-controlnet-09fc64",
            "live-graph-explanation-smoke",
            "multi-3d-gaussian-splatting-from-video-with-hunyuan-432652",
            "multi-animatediff-video-generation-with-controlnet-a7e2af",
            "multi-flux2-image-and-video-generation-with-outpaint-435de2",
            "multi-svd-image-to-video-with-animation-builder-99e2a9",
            "video-animatediff-video-to-video-with-controlnet-and-3c978e",
            "video-animatediff-video-with-controlnet-and-depth-89b02a",
            "video-inpaint-and-video-composition-with-spline-path-0c2716",
            "video-video-loading-and-saving-workflow-1c7ad8",
            "video-video-output-workflow-f855de",
            "video-wanvideo-text-to-video-generation-71f825",
        ),
        status="resolved",
        evidence=_V3_PASS_EVIDENCE,
        mechanism=_V3_MECHANISM,
    ),
    FailureLedgerRow(
        family="infra",
        owner="out of scope: phase 7 is cut",
        scenario_ids=(
            "3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2",
            "image-generates-a-2x2-seed-variation",
            "image-kolors-image-generation-with-segs-detailer-and-d813fe",
            "image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5",
            "multi-wanvideo-vace-inpainting-and-compositing-workf-b11a56",
            "video-hunyuanvideo-image-to-video-generation-with-en-ff076a",
            "video-ltx-video-with-audio-and-inpainting-b3ba8a",
            "video-seedvr2-video-upscaling-workflow-052e59",
        ),
        status="infra_out_of_scope",
        evidence=_V3_INFRA_EVIDENCE,
    ),
    FailureLedgerRow(
        family="semantic: gen_hard_missing_precedents",
        owner="phase 6",
        scenario_ids=(
            "multi-wan2-2-animate-video-with-pose-and-segmentatio-1cc457",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/gen_hard_missing_precedents.md.  v3 "
            "assessment.json passed=false, score_class=product_fail."
        ),
        mechanism="ResearchAttempt never/empty/thin/grounded",
    ),
    FailureLedgerRow(
        family="semantic: gen_hard_missing_schemas",
        owner="phase 5",
        scenario_ids=(
            "3d-3d-shape-generation-and-export-workflow-8800a9",
            "audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf",
            "image-face-detection-and-cropping-workflow-949658",
            "image-image-comparison-and-enhancement-with-florence-007018",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/gen_hard_missing_schemas.md requires a schema "
            "source.  v3 assessment.json passed=false, score_class=product_fail.  "
            "cc0df7 is Class D and is not in this family."
        ),
        mechanism="render census/surface (Law 4)",
    ),
    FailureLedgerRow(
        family="edit: pre_existing_bug",
        owner="phase 3",
        scenario_ids=(
            "3d-3d-model-generation-and-rigging-from-image-352066",
            "multi-animatediff-video-face-swapping-with-deflicker-506ebd",
            "multi-image-to-video-generation-with-2",
            "video-video-frame-by-frame-style",
            "video-video-generation-from-resized-image",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/pre_existing_bug.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="interpret + EditableSurface",
    ),
    FailureLedgerRow(
        family="edit: cross_domain_over_rejection",
        owner="phase 3",
        scenario_ids=(
            "hotshot-16-frames-agent-edit",
            "multi-deforum-stable-diffusion-animation-with-ip-ada-78afac",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/cross_domain_over_rejection.md.  v3 "
            "assessment.json passed=false, score_class=product_fail.  "
            "90a1d5 is Class D and is not in this family."
        ),
        mechanism="unknown-schema typed refusal on interpret",
    ),
    FailureLedgerRow(
        family="edit: widget_shape_guard",
        owner="phase 3",
        scenario_ids=(
            "multi-crops-face-previews-it-sets",
            "multi-image-to-video-with-upscaling-and-color-matchi-359848",
            "video-svd-image-to-video-generation-fc240f",
        ),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/widget_shape_guard.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="widget_shape_fence + interpret CAS",
    ),
    FailureLedgerRow(
        family="edit: revision_evidence_fix",
        owner="phase 4",
        scenario_ids=("video-wan-alpha-video-generation-with-lora-and-gguf-6a9e20",),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/revision_evidence_fix.md.  v3 assessment.json "
            "passed=false, score_class=product_fail."
        ),
        mechanism="canonical Δ (Law 3)",
    ),
    FailureLedgerRow(
        family="other",
        owner="capability-floor candidate; reclassify with evidence",
        scenario_ids=("video-video-combine-with-image-loading-5b31ce",),
        status="pending_live_rerun",
        evidence=(
            "docs/failure-analysis/other.md is an ambiguous bucket, not named "
            "Class-D or variance floor evidence.  v3 assessment.json "
            "passed=false, score_class=product_fail: research_attempt=never + "
            "agent refused, no edit (.oracle/findings/v3-batch-5.md)."
        ),
    ),
    FailureLedgerRow(
        family="recovery_rerun_unpartitioned",
        owner="host live rerun",
        scenario_ids=(
            "3d-3d-model-generation-and-retargeting-workflow-f65774",
            "audio-audio-processing-with-voice-tts-and-noise-remo-b80848",
            "image-animatediff-video-from-images-with",
            "image-animatediff-video-generation-with-vae-d20410",
            "image-flux-image-inpainting-and-compositing-with-con-00444a",
            "image-image-to-image-with-ipadapter-and-controlnet-1999a9",
            "multi-ai-video-upscaling-with-detail-daemon-sampler-673197",
            "multi-wan2-2-text-to-video-with-lora-and-post-proces-9d28c6",
            "video-image-to-video-with-svd-and-webp-output-1882aa",
            "video-video-inpainting-with-spline-based-cut-and-dra-485ff2",
            "video-wan-video-generation-with-vace-and-multi-outpu-d1caec",
            "video-wan2-2-i2v-video-generation-with-lora-and-nois-374aa9",
            "video-wan2-2-text-to-video-with-lora-and-dual-noise-82ffb9",
        ),
        status="pending_live_rerun",
        evidence=(
            "Present in the recovery-rerun 57; v3 assessment.json passed=false, "
            "score_class=product_fail.  Not a named Class-D or variance floor."
        ),
    ),
)


def ledger_scenario_ids() -> tuple[str, ...]:
    return tuple(
        scenario_id
        for row in EXIT_FAILURE_LEDGER
        for scenario_id in row.scenario_ids
    )


def assert_ledger_integrity() -> None:
    ids = ledger_scenario_ids()
    if len(ids) != LEDGER_ID_COUNT:
        raise AssertionError(f"ledger has {len(ids)} ids, expected {LEDGER_ID_COUNT}")
    if len(ids) != len(set(ids)):
        raise AssertionError("ledger scenario ids are not unique")
    if CLASS_D_HARD_FLOOR_IDS != frozenset(
        sid
        for row in EXIT_FAILURE_LEDGER
        if row.family == "class_d_hard_floor"
        for sid in row.scenario_ids
    ):
        raise AssertionError("Class D hard-floor ids are not isolated in class_d_hard_floor")
    for row in EXIT_FAILURE_LEDGER:
        if row.status not in _EXIT_STATUSES:
            raise AssertionError(f"{row.family}: invalid status {row.status!r}")
        if not row.scenario_ids or not row.evidence or not row.owner:
            raise AssertionError(f"{row.family}: missing ids/owner/evidence")
        if row.status == "resolved" and not row.mechanism:
            raise AssertionError(f"{row.family}: resolved without a mechanism")
        if row.status == "capability_floor" and not row.evidence:
            raise AssertionError(f"{row.family}: capability_floor without named evidence")
        if row.family != "class_d_hard_floor" and CLASS_D_HARD_FLOOR_IDS.intersection(row.scenario_ids):
            raise AssertionError(f"{row.family}: contains Class D hard-floor ids")
