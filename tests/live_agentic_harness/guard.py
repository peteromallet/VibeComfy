"""Guard against structural/fake runs being counted as live agentic success."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from tests.harness_common import (
    FAKE_DISPATCHERS,
    FLOW_KIND_LIVE_AGENTIC_HEADLESS,
    LIVE_AGENTIC_DISPATCHERS,
    LIVE_AGENTIC_MODEL_BEHAVIORS,
    STATUS_SUCCESS,
)
from .assessor import assess_live_output_dir


def load_flow_metadata(output_dir: Path | str) -> dict[str, Any]:
    path = Path(output_dir) / "flow_metadata.json"
    if not path.is_file():
        raise ValueError(f"Missing flow_metadata.json in {output_dir}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def is_live_agentic_success(metadata: Mapping[str, Any]) -> bool:
    """Return True only when the evidence is real, agentic, and successful."""
    if metadata.get("flow_kind") != FLOW_KIND_LIVE_AGENTIC_HEADLESS:
        return False
    if metadata.get("live") is not True:
        return False
    if metadata.get("status") != STATUS_SUCCESS:
        return False
    if metadata.get("dispatcher") not in LIVE_AGENTIC_DISPATCHERS:
        return False
    if metadata.get("model_behavior") not in LIVE_AGENTIC_MODEL_BEHAVIORS:
        return False
    return True


def validate_live_agentic_artifact(metadata: Mapping[str, Any]) -> None:
    """Reject live-headless artifacts that came from fake or non-agentic paths."""
    if metadata.get("flow_kind") != FLOW_KIND_LIVE_AGENTIC_HEADLESS:
        return

    dispatcher = metadata.get("dispatcher")
    if dispatcher in FAKE_DISPATCHERS:
        raise ValueError(
            f"live_agentic_headless artifacts cannot use fake/faking dispatcher; "
            f"got {dispatcher!r}"
        )

    model_behavior = metadata.get("model_behavior")
    if model_behavior not in LIVE_AGENTIC_MODEL_BEHAVIORS:
        raise ValueError(
            "live_agentic_headless artifacts require agentic model behavior; "
            f"got {model_behavior!r}"
        )


def guard_output_dir(
    output_dir: Path | str,
    scenario: Mapping[str, Any] | None = None,
    *,
    judge_route: str | None = None,
    judge_model: str | None = None,
    assessment_path: Path | str | None = None,
) -> dict[str, Any]:
    """Inspect an artifact directory and return a strict verdict.

    The verdict combines the metadata boundary check with a deep artifact
    assessment (graph changed, errors, readiness blockers, upstream failures,
    etc.).  *scenario* is optional; when provided it can declare explicit
    expectations such as ``assessment.expect_graph_changed``.
    """
    metadata = load_flow_metadata(output_dir)
    validate_live_agentic_artifact(metadata)

    metadata_success = is_live_agentic_success(metadata)
    assessment = assess_live_output_dir(
        output_dir,
        scenario=scenario,
        judge_route=judge_route,
        judge_model=judge_model,
        assessment_path=assessment_path,
    )

    assessment_verdict = assessment.get("verdict")
    if assessment_verdict not in {"pass", "fail", "undetermined"}:
        assessment_verdict = "pass" if assessment.get("passed") else "fail"

    if assessment_verdict == "undetermined":
        live_agentic_success = False
        score_class = "undetermined"
    elif not metadata_success:
        live_agentic_success = False
        score_class = "product_fail"
    elif assessment_verdict == "pass":
        live_agentic_success = True
        score_class = "pass"
    else:
        live_agentic_success = False
        score_class = "product_fail"

    verdict: dict[str, Any] = {
        "output_dir": str(output_dir),
        "flow_kind": metadata.get("flow_kind"),
        "status": metadata.get("status"),
        "dispatcher": metadata.get("dispatcher"),
        "model_behavior": metadata.get("model_behavior"),
        "metadata_success": metadata_success,
        "assessment": assessment,
        "judge_config": assessment.get("judge_config"),
        "verdict": assessment_verdict,
        "live_agentic_success": live_agentic_success,
        "score_class": score_class,
    }
    return verdict
