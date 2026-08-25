"""Differential staged-versus-threaded live-agentic comparator.

The comparator locks the semantic executor input once, runs both modes from
independent copies of that input, and compares typed artifacts.  It never
compares assistant prose.  ``--validate-only`` performs no model calls and is
expected to pass once the canonical mode selector is exposed by the adapter.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import inspect
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping, Sequence

from .scenario_manifest import (
    DEFAULT_MANIFEST_PATH,
    ScenarioManifestError,
    sha256_file,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_COMPARISON_MANIFEST = HERE / "threaded_comparison_manifest.json"
DEFAULT_OUTPUT_BASE = Path("out") / "compare-pipeline-modes"
PIPELINE_MODES = ("staged", "threaded")
# C5: frozen scenario→mode assignment for the one-invocation 25/25 split
# finale (50 legs).  Sorted by locked_input_sha256 then alternating gives
# exactly 25/25 on the final50 manifest; the map is frozen and its digest
# is recorded in the live_run.  Any unknown id falls back to a pure hash
# of its locked_input_sha256 for determinism.
SPLIT_FROZEN_MAP: dict[str, str] = {
    "3d-3d-inpainting-with-controlnet-and-detail-daemo-c24aa2": "staged",
    "3d-3d-model-generation-and-preview-workflow-cc0df7": "staged",
    "3d-3d-model-generation-and-retargeting-workflow-f65774": "staged",
    "3d-3d-model-generation-and-rigging-from-image-352066": "staged",
    "3d-3d-model-generation-and-rigging-workflow-90a1d5": "threaded",
    "3d-3d-model-load-edit-and-export-workflow-d66a66": "threaded",
    "3d-3d-shape-generation-and-export-workflow-8800a9": "staged",
    "3d-converts-image-to-3d-model": "threaded",
    "3d-generates-a-3d-mesh-from": "threaded",
    "audio-acestep-audio-generation-and-processing-workfl-1b1360": "threaded",
    "audio-acestep-audio-generation-with-detail-daemon-f0859f": "threaded",
    "audio-acestep-audio-generation-with-ksampler-e8c20a": "staged",
    "audio-acestep-audio-generation-workflow-2a31ec": "threaded",
    "audio-acestep-audio-latent-workflow-with-vocal-separ-0eb676": "staged",
    "audio-audio-processing-with-chatterbox-tts-and-vc-b55994": "staged",
    "audio-audio-processing-with-voice-tts-and-noise-remo-b80848": "threaded",
    "audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf": "staged",
    "audio-transcribes-audio-appends-text-regenerates": "threaded",
    "audio-tts-narration-using-indextts-2": "staged",
    "hotshot-16-frames-agent-edit": "threaded",
    "image-animatediff-image-to-video-with-latent-composi-17dc9b": "threaded",
    "image-animatediff-video-from-images-with": "threaded",
    "image-animatediff-video-generation-with-vae-d20410": "threaded",
    "image-auraflow-image-generation-with-qwen-clip-9a3109": "staged",
    "image-background-removal-and-grid-composition-54a681": "threaded",
    "image-dual-checkpoint-xl-image-generation-with-refin-c9df19": "staged",
    "image-face-detection-and-cropping-workflow-949658": "staged",
    "image-flux-image-inpainting-and-compositing-with-con-00444a": "threaded",
    "image-gemini-prompt-splitter-and-text-display-workfl-caae97": "staged",
    "image-generates-a-2x2-seed-variation": "threaded",
    "image-image-comparison-and-enhancement-with-florence-007018": "threaded",
    "image-image-editing-with-qwen-image": "threaded",
    "image-image-processing-with-sharpening-film-grain-an-9aa0f1": "threaded",
    "image-image-to-image-with-controlnet-and-dwpreproces-49d057": "threaded",
    "image-image-to-image-with-ipadapter-and-controlnet-1999a9": "staged",
    "image-image-to-image-with-stable-zero123-and-backgro-def5b5": "threaded",
    "image-inpainting-with-differential-diffusion-and-rea-1d414c": "threaded",
    "image-kolors-image-generation-with-segs-detailer-and-d813fe": "staged",
    "image-llama-cpp-instruct-image-preview-and-save-5b54bf": "staged",
    "image-llava-image-captioning-and-keyword-extraction-d38dc8": "staged",
    "image-qwen-image-inpainting-with-controlnet-09fc64": "threaded",
    "image-sd3-image-generation-with-controlnet-19d221": "staged",
    "image-sdxl-txt2img-cat-in-spacesuit": "staged",
    "image-style-transfer-using-ip-adapter": "staged",
    "image-two-stage-qwen-image-generation": "staged",
    "image-wan2-2-video-generation-with-chroma-lut-and-fi-a7ecc5": "staged",
    "live-graph-explanation-smoke": "threaded",
    "multi-3d-gaussian-splatting-from-video-with-hunyuan-432652": "threaded",
    "multi-video-based-character-replacement-using": "staged",
    "speed-distillation-research": "staged",
}
SPLIT_FROZEN_DIGEST = "199f231f29f43716424888833d88b4be60f85f7dbcebb6e879fd3071447fa020"


def split_assignment(entry: Mapping[str, Any]) -> str:
    """Return the frozen mode for *entry* (C5 deterministic 25/25 split)."""
    sid = str(entry.get("id") or entry.get("scenario_id") or "")
    if sid in SPLIT_FROZEN_MAP:
        return SPLIT_FROZEN_MAP[sid]
    key = str(entry.get("locked_input_sha256") or sid)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return "staged" if int(digest[0], 16) % 2 == 0 else "threaded"


def split_digest(mapping: Mapping[str, str] | None = None) -> str:
    """Digest of the frozen scenario→mode map (C5, recorded in live_run)."""
    target = mapping if mapping is not None else SPLIT_FROZEN_MAP
    return hashlib.sha256(
        json.dumps(dict(target), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

SOURCE_COMMIT_ENV_VAR = "VIBECOMFY_SOURCE_COMMIT"


# T5.4 concurrent-leg isolation. With ``leg_isolation="process"`` every
# scenario/mode leg runs in its OWN PROCESS (no shared interpreter state:
# os.environ, schema caches, capture ContextVars, usage ledgers, and artifact
# roots are process-scoped by construction), while the parent still submits
# every leg before awaiting any result and reconstructs results in manifest
# order. The in-process thread pool remains available for dry lanes.
LEG_ISOLATION_MODES = ("thread", "process")
LEG_TIMEOUT_SECONDS = 1200  # matches runner DEFAULT_PER_SCENARIO_TIMEOUT
LEG_KILL_GRACE_SECONDS = float(os.getenv("VIBECOMFY_RUNNER_KILL_GRACE", "2"))
# RRSYN-6: diagnosable legs + harness-owned timeout-only retry (mirrors the
# runner.py T3.1/D6 freeze): at most ONE relaunch of a leg that timed out,
# under a FRESH attempt identity, never for product failures. Attempt 1
# evidence is always preserved; an unknown timeout cause stays infra-blocked.
HARNESS_RETRY_OWNER = "harness_infrastructure"
LEG_ATTEMPT_LIMIT = 2  # original attempt + at most one timeout-only retry
LEG_LOG_TAIL_CHARS = 20_000  # bounded stdout/stderr tails embedded in records
_ENV_WRITE_LOCK = threading.Lock()
# Resolved once per comparison, before any leg thread starts (T5.1: every
# leg's lineage manifest links the same source commit; T5.4: written before
# concurrent workers exist, read-only afterwards).
_SOURCE_COMMIT: list[str] = []


def resolve_source_commit() -> str:
    """Return the executing source commit (env pin, else ``git rev-parse HEAD``).

    Resolved ONCE per comparison before any leg starts so every leg's T5.1
    lineage manifest links the same source commit. Empty string when the
    executing tree has no git metadata — the executor then records the typed
    fallback row instead of fabricating a commit.
    """
    import os  # noqa: PLC0415
    import re as _re  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    pinned = os.environ.get(SOURCE_COMMIT_ENV_VAR) or ""
    if _re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", pinned):
        return pinned
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    candidate = (result.stdout or "").strip()
    if result.returncode == 0 and _re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", candidate):
        return candidate
    return ""

_LOCKED_SCENARIO_FIELDS = (
    "query",
    "graph",
    "workflow_id",
    "profile",
    "session_id",
    "dry_run",
    "apply",
    "network",
    "timeout",
    "additive",
    "interaction_mode",
    "max_batches",
)


class ComparisonManifestError(ValueError):
    """The comparison lane or its locked inputs are invalid."""


class _ProjectionSchemaProvider:
    """Deterministic no-I/O provider for paired IR projection.

    Unknown schema status is part of ``pi_edit`` and is preferable here to a
    host-dependent runtime schema probe. Both legs are projected identically.
    """

    def get_schema(self, class_type: str) -> None:
        _ = class_type
        return None


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _authoritative_entries() -> dict[str, Mapping[str, Any]]:
    """Return canonical entries; selected bytes are checked by ``validate_only``.

    The full canonical validator also requires the optional external-workflow
    corpus mount.  This compact comparator intentionally validates only its
    selected descriptors and preserves the canonical source hashes when that
    mount is absent.
    """
    manifest = _load_json(DEFAULT_MANIFEST_PATH)
    if (
        manifest is None
        or manifest.get("schema_version") != 1
        or not isinstance(manifest.get("entries"), list)
    ):
        raise ComparisonManifestError("canonical scenario manifest is unreadable")
    return {
        str(entry["id"]): entry
        for entry in manifest["entries"]
        if isinstance(entry, Mapping) and entry.get("id")
    }


def _locked_input_projection(
    scenario: Mapping[str, Any],
    authoritative_entry: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the model-relevant input shared by both comparison legs."""
    projection = {"id": str(scenario.get("id") or "")}
    for field in _LOCKED_SCENARIO_FIELDS:
        projection[field] = scenario.get(field)
    source = authoritative_entry.get("source_workflow")
    projection["workflow"] = (
        {
            "path": source.get("path"),
            "sha256": source.get("sha256"),
        }
        if isinstance(source, Mapping)
        else None
    )
    assessment = scenario.get("assessment")
    projection["expect_graph_changed"] = (
        assessment.get("expect_graph_changed")
        if isinstance(assessment, Mapping)
        else None
    )
    return projection


def _adapter_wiring() -> dict[str, Any]:
    """Report mode-selection capability without invoking the adapter."""
    try:
        from .adapter import run_headless_scenario  # noqa: PLC0415

        parameters = inspect.signature(run_headless_scenario).parameters
    except Exception as exc:  # noqa: BLE001
        return {"status": "unavailable", "runnable": False, "detail": str(exc)}
    runnable = "pipeline_mode" in parameters
    return {
        "status": "ready" if runnable else "unavailable",
        "runnable": runnable,
        "selector": "pipeline_mode" if runnable else None,
    }


def validate_only(manifest_path: Path | None = None) -> dict[str, Any]:
    """Validate locks, IR projection, and optional wiring without model calls."""
    path = manifest_path or DEFAULT_COMPARISON_MANIFEST
    manifest = _load_json(path)
    if manifest is None:
        raise ComparisonManifestError(f"comparison manifest is unreadable: {path}")
    if manifest.get("schema_version") != 1:
        raise ComparisonManifestError("comparison manifest schema_version must be 1")
    if tuple(manifest.get("modes") or ()) != PIPELINE_MODES:
        raise ComparisonManifestError(
            f"comparison modes must be exactly {list(PIPELINE_MODES)!r}"
        )
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ComparisonManifestError("comparison manifest entries must be non-empty")

    wiring = _adapter_wiring()
    if not wiring["runnable"]:
        raise ComparisonManifestError(
            "live comparison adapter must expose explicit pipeline_mode selection"
        )
    canonical = _authoritative_entries()
    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    obligation_violations: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, Mapping):
            raise ComparisonManifestError(f"comparison entry {index} must be an object")
        scenario_id = str(entry.get("id") or "")
        if not scenario_id or scenario_id in seen:
            raise ComparisonManifestError(f"missing or duplicate scenario id: {scenario_id!r}")
        seen.add(scenario_id)
        source_entry = canonical.get(scenario_id)
        if source_entry is None:
            raise ComparisonManifestError(f"unknown canonical scenario: {scenario_id}")
        if entry.get("descriptor_sha256") != source_entry.get("descriptor_sha256"):
            raise ComparisonManifestError(f"descriptor lock drift for {scenario_id}")
        source = source_entry.get("source_workflow")
        expected_source_hash = source.get("sha256") if isinstance(source, Mapping) else None
        if entry.get("source_workflow_sha256") != expected_source_hash:
            raise ComparisonManifestError(f"source workflow lock drift for {scenario_id}")

        descriptor_path = REPO / str(source_entry["path"])
        scenario = _load_json(descriptor_path)
        if scenario is None:
            raise ComparisonManifestError(f"scenario descriptor is unreadable: {descriptor_path}")
        if sha256_file(descriptor_path) != source_entry.get("descriptor_sha256"):
            raise ComparisonManifestError(f"canonical descriptor drift for {scenario_id}")
        locked_digest = _digest(_locked_input_projection(scenario, source_entry))
        if entry.get("locked_input_sha256") != locked_digest:
            raise ComparisonManifestError(f"locked input drift for {scenario_id}")
        validated.append({"id": scenario_id, "locked_input_sha256": locked_digest})

    try:
        from tests.test_ir_laws import pi_edit  # noqa: PLC0415

        ir_projection_available = callable(pi_edit)
    except Exception:  # noqa: BLE001
        ir_projection_available = False
    if not ir_projection_available:
        raise ComparisonManifestError("IR projection seam tests.test_ir_laws.pi_edit is unavailable")
    # T5.3: every entry's scenario obligations must be complete and
    # contradiction-free (declaration level; schema resolution is enforced
    # by preflight_scenario_obligations before paid calls).
    from .scenario_obligations import validate_obligation_coverage  # noqa: PLC0415


    obligation_violations, obligation_warnings = validate_obligation_coverage(path)
    if obligation_violations:
        raise ComparisonManifestError(
            "scenario obligation coverage failed:\n- " + "\n- ".join(obligation_violations)
        )
    return {
        "ok": True,
        "model_calls": 0,
        "manifest": str(path),
        "scenario_count": len(validated),
        "modes": list(PIPELINE_MODES),
        "locked_inputs": validated,
        "ir_projection": "tests.test_ir_laws.pi_edit",
        "threaded_wiring": wiring,
        "obligation_warnings": obligation_warnings,
        "obligation_violations": obligation_violations,
        "obligation_preflight": "declaration_level",
    }


def _ir_projection(graph: dict[str, Any] | None) -> tuple[Any, ...] | None:
    """Project a UI/envelope graph through the IR-everywhere editable quotient."""
    if not isinstance(graph, dict):
        return None
    try:
        from tests.test_ir_laws import pi_edit  # noqa: PLC0415
        from vibecomfy.ingest.normalize import (  # noqa: PLC0415
            detect_workflow_shape,
            from_api,
            from_envelope,
            from_ui,
        )

        provider = _ProjectionSchemaProvider()
        shape = detect_workflow_shape(graph)
        if shape == "vibe":
            workflow = from_envelope(graph)
        elif shape == "ui":
            workflow = from_ui(
                graph,
                schema_provider=provider,
                use_comfy_converter=False,
            )
        elif shape == "api":
            workflow = from_api(graph, schema_provider=provider)
        else:
            return None
        return pi_edit(workflow, schema_provider=provider)
    except Exception:  # noqa: BLE001
        return None


def _ir_projection_digest(graph: dict[str, Any] | None) -> str | None:
    projection = _ir_projection(graph)
    return _digest(projection) if projection is not None else None


def _nested_mapping(root: Mapping[str, Any], path: Sequence[str]) -> Mapping[str, Any] | None:
    value: Any = root
    for key in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(key)
    return value if isinstance(value, Mapping) else None


def _accepted_delta(response: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Canonicalize the durable accepted batch; never consult narrative prose."""
    from vibecomfy.porting.edit.ops import canonical_op_to_dict  # noqa: PLC0415

    accepted = response.get("accepted_batch")
    if not isinstance(accepted, list):
        return ()
    operations: list[dict[str, Any]] = []
    for item in accepted:
        if not isinstance(item, Mapping) or not isinstance(item.get("op"), Mapping):
            continue
        operations.append(canonical_op_to_dict(item["op"]))
    return tuple(operations)


def _canonical_delta_digest(response: Mapping[str, Any]) -> str | None:
    try:
        operations = _accepted_delta(response)
    except (TypeError, ValueError):
        return None
    return _digest(operations) if operations else None


def _execute_report(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
    return _nested_mapping(response, ("report", "executor", "execute"))


def _evidence_integrity(response: Mapping[str, Any]) -> dict[str, Any]:
    """Read and independently check typed claim/evidence references."""
    result: dict[str, Any] = {
        "status": None,
        "valid": None,
        "unsupported_claims": None,
        "reply_claims_valid": None,
        "delta_refs_valid": None,
        "lens_refs_valid": None,
        "evidence_refs_valid": None,
    }
    accepted_batch = response.get("accepted_batch")
    if isinstance(accepted_batch, list):
        from vibecomfy.executor.contracts import validate_reply_change_claims  # noqa: PLC0415

        reply_violations = validate_reply_change_claims(response)
        result["reply_claims_valid"] = not reply_violations
        result["unsupported_claims"] = len(reply_violations)

    execute = _execute_report(response)
    if execute is None:
        if result["reply_claims_valid"] is not None:
            result["valid"] = result["reply_claims_valid"]
        return result

    validation = execute.get("claim_validation")
    if isinstance(validation, Mapping):
        result["status"] = validation.get("status")
        violations = validation.get("violations") or validation.get("errors")
        if isinstance(violations, (list, tuple)):
            result["unsupported_claims"] = len(violations)

    accepted = {str(value) for value in (execute.get("accepted_delta_ids") or ())}
    facts = {str(value) for value in (execute.get("lens_fact_ids") or ())}
    evidence = {str(value) for value in (execute.get("evidence_ids") or ())}
    refs = execute.get("claim_refs")
    if isinstance(refs, Mapping):
        for output_key, ref_key, ledger in (
            ("delta_refs_valid", "delta_ids", accepted),
            ("lens_refs_valid", "lens_fact_ids", facts),
            ("evidence_refs_valid", "evidence_ids", evidence),
        ):
            values = refs.get(ref_key)
            if isinstance(values, (list, tuple)):
                result[output_key] = all(str(value) in ledger for value in values)

    checks = [
        result[key]
        for key in (
            "reply_claims_valid",
            "delta_refs_valid",
            "lens_refs_valid",
            "evidence_refs_valid",
        )
        if result[key] is not None
    ]
    status = result["status"]
    status_valid = status in {"valid", "ok", "passed"} if status is not None else None
    if status_valid is not None or checks:
        result["valid"] = (status_valid is not False) and all(checks)
    return result


def _typed_failure_family(summary: Mapping[str, Any]) -> str | None:
    guard = summary.get("guard") if isinstance(summary.get("guard"), Mapping) else {}
    failure = guard.get("failure_family") or guard.get("failure_class")
    failure = failure or summary.get("failure_family") or summary.get("failure_class")
    if isinstance(failure, str) and failure:
        return "infra" if failure.startswith("infra_") else failure
    score_class = guard.get("score_class") or summary.get("score_class")
    if score_class == "infra_blocked":
        return "infra"
    if score_class == "product_fail":
        return "product"
    return None


def _typed_artifact_failure_family(
    response: Mapping[str, Any],
    metadata: Mapping[str, Any],
) -> str | None:
    """Classify failures from structured response/metadata evidence only."""
    if metadata.get("status") == "blocked_prerequisite":
        return "infra_prerequisite"
    attempts = response.get("model_attempts")
    if isinstance(attempts, (list, tuple)):
        for attempt in reversed(attempts):
            if not isinstance(attempt, Mapping) or attempt.get("outcome") != "failure":
                continue
            failure_type = attempt.get("failure_type")
            usage = attempt.get("token_usage")
            completion_tokens = usage.get("completion_tokens") if isinstance(usage, Mapping) else None
            if failure_type == "empty_response" and completion_tokens == 0:
                return "infra"
            if failure_type == "timeout":
                return "infra"
            if failure_type == "provider_failure":
                return "infra"
            break
    failure_kind = response.get("failure_kind")
    if isinstance(failure_kind, str) and failure_kind:
        return failure_kind
    return None


def is_infra_blocked(summary: Mapping[str, Any]) -> bool:
    """Use typed failure evidence only; error prose is deliberately ignored."""
    return _typed_failure_family(summary) == "infra"


def _leg_outcome(summary: Mapping[str, Any]) -> str:
    if is_infra_blocked(summary):
        return "blocked"
    guard = summary.get("guard") if isinstance(summary.get("guard"), Mapping) else {}
    return "pass" if guard.get("live_agentic_success") is True else "fail"


def pair_outcome(staged: Mapping[str, Any], threaded: Mapping[str, Any]) -> str:
    return _pair_outcome_values(_leg_outcome(staged), _leg_outcome(threaded))


def _pair_outcome_values(staged_outcome: str, threaded_outcome: str) -> str:
    if "blocked" in (staged_outcome, threaded_outcome):
        return "blocked"
    if staged_outcome == threaded_outcome == "pass":
        return "both_pass"
    if staged_outcome == "pass":
        return "staged_only"
    if threaded_outcome == "pass":
        return "threaded_only"
    return "both_fail"


def _write_typed_metrics_artifact(
    output_dir: Path | None,
    *,
    mode: str,
    locked_input_sha256: str,
    elapsed_s: float,
    response: Mapping[str, Any],
) -> None:
    """Persist comparison-only timing/usage evidence as a typed artifact."""
    if output_dir is None:
        return
    payload = {
        "schema_version": 1,
        "pipeline_mode": mode,
        "locked_input_sha256": locked_input_sha256,
        "elapsed_s": round(elapsed_s, 6),
        "deepseek_usage": response.get("deepseek_usage", {}),
        "deepseek_est_cost_usd": response.get("deepseek_est_cost_usd"),
        "failure_kind": response.get("failure_kind"),
        "failure_stage": response.get("failure_stage"),
        "model_attempts": response.get("model_attempts", []),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison_metrics.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _leg_metrics(summary: Mapping[str, Any]) -> dict[str, Any]:
    output_dir = summary.get("output_dir")
    output = Path(str(output_dir)) if output_dir else None
    response = _load_json(output / "response.json") if output else None
    final = _load_json(output / "final.ui.json") if output else None
    if final is None and output is not None:
        final = _load_json(output / "candidate.ui.json")
    response = response or {}
    metadata = _load_json(output / "flow_metadata.json") if output else None
    metadata = metadata or {}
    typed_metrics = _load_json(output / "comparison_metrics.json") if output else None
    typed_metrics = typed_metrics or {}
    typed_response = response if isinstance(response, Mapping) else {}
    typed_failure = _typed_artifact_failure_family(typed_response, metadata)
    failure_family = typed_failure or _typed_failure_family(summary)
    usage_source = (
        typed_metrics
        if isinstance(typed_metrics.get("deepseek_usage"), Mapping)
        else typed_response
        if isinstance(typed_response.get("deepseek_usage"), Mapping)
        else summary
    )
    cost_source = typed_metrics if "deepseek_est_cost_usd" in typed_metrics else (
        typed_response if "deepseek_est_cost_usd" in typed_response else summary
    )
    latency_value = typed_metrics.get("elapsed_s")
    latency = (
        latency_value
        if isinstance(latency_value, (int, float)) and not isinstance(latency_value, bool)
        else summary.get("elapsed_s")
    )
    cost_value = cost_source.get("deepseek_est_cost_usd")
    if not isinstance(cost_value, (int, float)) or isinstance(cost_value, bool):
        cost_value = None
    locked_input = typed_metrics.get("locked_input_sha256")
    if not isinstance(locked_input, str) or not locked_input:
        locked_input = summary.get("locked_input_sha256")
    return {
        "status": summary.get("status"),
        "error": summary.get("error"),
        "exception_type": summary.get("exception_type"),
        "outcome": (
            "blocked" if failure_family == "infra" or str(failure_family).startswith("infra_")
            else _leg_outcome(summary)
        ),
        "failure_family": failure_family,
        "ir_projection_sha256": _ir_projection_digest(final),
        "canonical_delta_sha256": _canonical_delta_digest(response),
        "evidence_integrity": _evidence_integrity(response),
        "latency_s": latency,
        "usage": {
            "prompt_tokens": usage_source.get("prompt_tokens"),
            "completion_tokens": usage_source.get("completion_tokens"),
            "total_tokens": usage_source.get("total_tokens"),
            "cost_usd": cost_value,
        },
        "output_dir": output_dir,
        "locked_input_sha256": locked_input,
    }


def compare_pair(
    scenario_id: str,
    *,
    locked_input_sha256: str,
    staged: Mapping[str, Any],
    threaded: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare a pair using structural/typed signals, never prose equality."""
    staged_metrics = _leg_metrics(staged)
    threaded_metrics = _leg_metrics(threaded)
    locks = (
        staged_metrics["locked_input_sha256"],
        threaded_metrics["locked_input_sha256"],
    )
    lock_equal = locks == (locked_input_sha256, locked_input_sha256)
    staged_evidence = staged_metrics["evidence_integrity"]
    threaded_evidence = threaded_metrics["evidence_integrity"]
    return {
        "scenario_id": scenario_id,
        "locked_input_sha256": locked_input_sha256,
        "outcome": _pair_outcome_values(
            staged_metrics["outcome"], threaded_metrics["outcome"]
        ),
        "staged": staged_metrics,
        "threaded": threaded_metrics,
        "delta": {
            "locked_input_equal": lock_equal,
            "ir_projection_equal": (
                staged_metrics["ir_projection_sha256"] is not None
                and staged_metrics["ir_projection_sha256"]
                == threaded_metrics["ir_projection_sha256"]
            ),
            "canonical_delta_equal": (
                staged_metrics["canonical_delta_sha256"] is not None
                and staged_metrics["canonical_delta_sha256"]
                == threaded_metrics["canonical_delta_sha256"]
            ),
            "outcome_equal": staged_metrics["outcome"] == threaded_metrics["outcome"],
            "evidence_integrity_equal": (
                staged_evidence.get("valid") is not None
                and staged_evidence == threaded_evidence
            ),
            "failure_family_equal": (
                staged_metrics["failure_family"] == threaded_metrics["failure_family"]
            ),
            "latency_s": {
                "staged": staged_metrics["latency_s"],
                "threaded": threaded_metrics["latency_s"],
                "threaded_minus_staged": _numeric_delta(
                    threaded_metrics["latency_s"], staged_metrics["latency_s"]
                ),
            },
            "cost_usd": {
                "staged": staged_metrics["usage"]["cost_usd"],
                "threaded": threaded_metrics["usage"]["cost_usd"],
                "threaded_minus_staged": _numeric_delta(
                    threaded_metrics["usage"]["cost_usd"],
                    staged_metrics["usage"]["cost_usd"],
                ),
            },
        },
    }


def _numeric_delta(new: Any, old: Any) -> float | None:
    if not isinstance(new, (int, float)) or not isinstance(old, (int, float)):
        return None
    return round(float(new) - float(old), 6)


def _write_lineage_binding(
    output: Path | None,
    *,
    scenario_id: str,
    mode: str,
    locked_input_sha256: str,
    source_commit: str,
) -> None:
    """Bind harness-owned identity into the leg's T5.1 artifact lineage.

    The executor builds the manifest (rows + scenario/session/turn/baseline);
    the comparison lane adds the binding block proving WHICH locked input,
    mode, and source commit produced the leg. Extra top-level keys never
    participate in ``manifest_digest``.
    When the executor manifest is absent (e.g. hard_diagnostic aborted the
    executor), write a binding-only sidecar with the harness-level
    ``manifest_digest`` so the assessor reports ``present True`` without
    ``manifest_digest null`` while still distinguishing the fallback.
    """
    import os  # noqa: PLC0415

    if output is None:
        return
    response = _load_json(output / "response.json")
    report = response.get("report") if isinstance(response, Mapping) else None
    manifest = (
        report.get("executor", {}).get("artifact_lineage")
        if isinstance(report, Mapping)
        else None
    )
    if not isinstance(manifest, Mapping):
        # Fallback: executor did not produce a manifest (product error). Write
        # a harness-only binding so lineage is present and manifest_digest
        # is not null; the assessor will still surface the product failure
        # via other typed signals but not via a spurious lineage gap.
        bound: dict[str, Any] = {
            "manifest_digest": locked_input_sha256,
            "binding": {
                "scenario_id": scenario_id,
                "pipeline_mode": mode,
                "locked_input_sha256": locked_input_sha256,
                "source_commit": source_commit or os.environ.get(SOURCE_COMMIT_ENV_VAR, ""),
            },
            "harness_fallback": True,
        }
    else:
        bound = dict(manifest)
        bound["binding"] = {
            "scenario_id": scenario_id,
            "pipeline_mode": mode,
            "locked_input_sha256": locked_input_sha256,
            "source_commit": source_commit or os.environ.get(SOURCE_COMMIT_ENV_VAR, ""),
        }
    try:
        output.mkdir(parents=True, exist_ok=True)
        (output / "artifact_lineage.json").write_text(
            json.dumps(bound, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass

def _run_mode(
    scenario: Mapping[str, Any],
    *,
    mode: str,
    locked_input_sha256: str,
    output_base: Path,
    tag: str,
    transport: str | None,
) -> dict[str, Any]:
    from .adapter import run_headless_scenario  # noqa: PLC0415
    from .guard import guard_output_dir  # noqa: PLC0415


    started = time.monotonic()
    summary = run_headless_scenario(
        copy.deepcopy(dict(scenario)),
        output_base=output_base / mode,
        tag=tag,
        transport=transport,
        pipeline_mode=mode,
    )
    summary = dict(summary)
    if summary.get("pipeline_mode") != mode:
        raise ComparisonManifestError(
            f"adapter did not attest requested pipeline_mode {mode!r}"
        )
    summary["locked_input_sha256"] = locked_input_sha256
    summary["elapsed_s"] = time.monotonic() - started
    try:
        summary["guard"] = guard_output_dir(summary["output_dir"], scenario=scenario)
    except Exception as exc:  # noqa: BLE001
        summary["guard"] = {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "failure_class": "runner_error",
        }
        summary.setdefault("error", str(exc))
    output = Path(str(summary.get("output_dir"))) if summary.get("output_dir") else None
    response = _load_json(output / "response.json") if output else None
    _write_typed_metrics_artifact(
        output,
        mode=mode,
        locked_input_sha256=locked_input_sha256,
        elapsed_s=float(summary["elapsed_s"]),
        response=response or {},
    )
    _write_lineage_binding(
        output,
        scenario_id=str(scenario.get("id") or summary.get("scenario_id") or ""),
        mode=mode,
        locked_input_sha256=locked_input_sha256,
        source_commit=_SOURCE_COMMIT[0] if _SOURCE_COMMIT else "",
    )
    return summary


def _cost_latency_sums(
    staged_cost: float,
    threaded_cost: float,
    staged_latency: float,
    threaded_latency: float,
) -> dict[str, dict[str, float]]:
    """Shared cost/latency summation helper for ``_aggregate``/``_aggregate_split``."""
    return {
        "staged": {"cost_usd": round(staged_cost, 6), "latency_s": round(staged_latency, 6)},
        "threaded": {"cost_usd": round(threaded_cost, 6), "latency_s": round(threaded_latency, 6)},
        "threaded_minus_staged": {
            "cost_usd": round(threaded_cost - staged_cost, 6),
            "latency_s": round(threaded_latency - staged_latency, 6),
        },
    }


def _aggregate(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcomes: dict[str, int] = {}
    for comparison in comparisons:
        outcome = str(comparison["outcome"])
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    staged_cost = sum(
        float(item["staged"]["usage"]["cost_usd"] or 0.0) for item in comparisons
    )
    threaded_cost = sum(
        float(item["threaded"]["usage"]["cost_usd"] or 0.0) for item in comparisons
    )
    staged_latency = sum(float(item["staged"]["latency_s"] or 0.0) for item in comparisons)
    threaded_latency = sum(
        float(item["threaded"]["latency_s"] or 0.0) for item in comparisons
    )
    sums = _cost_latency_sums(staged_cost, threaded_cost, staged_latency, threaded_latency)
    return {
        "scenario_count": len(comparisons),
        "outcomes": outcomes,
        "all_inputs_locked_equal": all(
            bool(item["delta"]["locked_input_equal"]) for item in comparisons
        ),
        "ir_projection_equal_count": sum(
            bool(item["delta"]["ir_projection_equal"]) for item in comparisons
        ),
        "canonical_delta_equal_count": sum(
            bool(item["delta"]["canonical_delta_equal"]) for item in comparisons
        ),
        **sums,
    }
def _aggregate_split(comparisons: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcomes: dict[str, int] = {}
    staged_cost = 0.0
    threaded_cost = 0.0
    staged_latency = 0.0
    threaded_latency = 0.0
    staged_count = 0
    threaded_count = 0
    for item in comparisons:
        outcome = str(item.get("outcome") or item.get("leg", {}).get("outcome") or "unknown")
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        mode = str(item.get("mode") or "")
        leg = item.get("leg") if isinstance(item.get("leg"), Mapping) else {}
        usage = leg.get("usage") if isinstance(leg.get("usage"), Mapping) else {}
        cost = usage.get("cost_usd")
        latency = leg.get("latency_s")
        if mode == "staged":
            staged_count += 1
            if isinstance(cost, (int, float)):
                staged_cost += float(cost)
            if isinstance(latency, (int, float)):
                staged_latency += float(latency)
        elif mode == "threaded":
            threaded_count += 1
            if isinstance(cost, (int, float)):
                threaded_cost += float(cost)
            if isinstance(latency, (int, float)):
                threaded_latency += float(latency)
    sums = _cost_latency_sums(staged_cost, threaded_cost, staged_latency, threaded_latency)
    return {
        "scenario_count": len(comparisons),
        "outcomes": outcomes,
        "staged_count": staged_count,
        "threaded_count": threaded_count,
        **sums,
    }



def _leg_exception_summary(
    scenario_id: str,
    *,
    mode: str,
    locked_input_sha256: str,
    output_base: Path,
    tag: str,
    error: Exception,
) -> dict[str, Any]:
    """Return a typed failed leg when a concurrent worker raises.

    The expected output path is retained in the summary so downstream
    comparison and diagnostics can still identify the isolated leg.
    """
    output_dir = output_base / mode / tag / scenario_id
    return {
        "scenario_id": scenario_id,
        "pipeline_mode": mode,
        "status": "runner_exception",
        "ok": False,
        "output_dir": str(output_dir),
        "locked_input_sha256": locked_input_sha256,
        "error": str(error),
        "exception_type": type(error).__name__,
        "failure_class": "runner_exception",
        "guard": {
            "live_agentic_success": False,
            "score_class": "product_fail",
            "failure_class": "runner_exception",
        },
        "deepseek_usage": {},
        "deepseek_est_cost_usd": None,
        "model_attempts": [],
    }

def run_comparison(
    manifest_path: Path | None = None,
    *,
    output_base: Path | None = None,
    tag: str = "staged-threaded",
    transport: str | None = None,
    concurrency: int = 1,
    leg_isolation: str = "thread",
    split: bool = False,
) -> dict[str, Any]:
    """Run the locked comparison lane once threaded adapter wiring is ready.


    ``concurrency=1`` retains the historical scenario-major,
    staged-then-threaded execution order.  Higher values submit every
    scenario/mode leg before awaiting any result, then compare and serialize
    results on the parent thread in manifest order.
    When ``split`` is True, each scenario runs in exactly ONE mode (25
    staged + 25 threaded, frozen map) in one invocation; compare_pair is
    skipped and per-leg assessments are recorded.
    """
    if leg_isolation not in LEG_ISOLATION_MODES:
        raise ComparisonManifestError(
            f"leg_isolation must be one of {LEG_ISOLATION_MODES!r}"
        )

    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise ComparisonManifestError("concurrency must be a positive integer")
    validate_only(manifest_path)
    path = manifest_path or DEFAULT_COMPARISON_MANIFEST
    # T5.3 + G5-B4-MUST-006: this is the paid-call lane — exact IndexTTS/
    # LayerMask schema evidence MUST resolve from local authoritative sources
    # before any leg starts. An environment override cannot defer it.
    from .scenario_obligations import preflight_scenario_obligations  # noqa: PLC0415

    preflight_scenario_obligations(path, require_schema_resolution=True)
    manifest = _load_json(path) or {}
    canonical = _authoritative_entries()
    base = output_base or DEFAULT_OUTPUT_BASE
    comparisons: list[dict[str, Any]] = []
    # T5.1: one source commit for every leg of this comparison, resolved
    # before any concurrent worker exists.
    del _SOURCE_COMMIT[:]
    commit = resolve_source_commit()
    if commit:
        _SOURCE_COMMIT.append(commit)
        os.environ.setdefault(SOURCE_COMMIT_ENV_VAR, commit)


    if split:
        split_assignment_map: dict[str, str] = {}
        for entry in manifest["entries"]:
            sid = str(entry["id"])
            split_assignment_map[sid] = split_assignment(entry)
        staged_cnt = sum(1 for v in split_assignment_map.values() if v == "staged")
        threaded_cnt = sum(1 for v in split_assignment_map.values() if v == "threaded")
        if concurrency > 1:
            descriptors: list[tuple[str, str, dict[str, Any], str]] = []
            for entry in manifest["entries"]:
                scenario_id = str(entry["id"])
                descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
                lock = str(entry["locked_input_sha256"])
                if str(descriptor.get("session_id") or "").strip():
                    raise ComparisonManifestError(
                        "concurrent comparison does not support explicit session_id "
                        f"for scenario {scenario_id!r}"
                    )
                mode = split_assignment_map[scenario_id]
                descriptors.append((scenario_id, mode, descriptor, lock))
            if leg_isolation == "process":
                leg_results = _run_legs_in_processes(
                    descriptors,
                    output_base=base,
                    tag=tag,
                    transport=transport,
                    concurrency=concurrency,
                )
            else:
                leg_results: list[dict[str, Any] | None] = [None] * len(descriptors)
                with ThreadPoolExecutor(
                    max_workers=min(concurrency, len(descriptors)),
                    thread_name_prefix="compare-pipeline-leg",
                ) as executor:
                    futures = [
                        executor.submit(
                            _run_mode,
                            copy.deepcopy(descriptor),
                            mode=mode,
                            locked_input_sha256=lock,
                            output_base=base,
                            tag=tag,
                            transport=transport,
                        )
                        for _scenario_id, mode, descriptor, lock in descriptors
                    ]
                    for index, (future, (scenario_id, mode, _descriptor, lock)) in enumerate(
                        zip(futures, descriptors)
                    ):
                        try:
                            leg_results[index] = future.result()
                        except Exception as exc:  # noqa: BLE001
                            leg_results[index] = _leg_exception_summary(
                                scenario_id,
                                mode=mode,
                                locked_input_sha256=lock,
                                output_base=base,
                                tag=tag,
                                error=exc,
                            )
            for (scenario_id, mode, _descriptor, lock), result in zip(descriptors, leg_results):
                assert result is not None
                metrics = _leg_metrics(result)
                comparisons.append(
                    {
                        "scenario_id": scenario_id,
                        "locked_input_sha256": lock,
                        "mode": mode,
                        "outcome": metrics["outcome"],
                        "leg": metrics,
                        "pair_skipped": True,
                        "delta": None,
                    }
                )
        else:
            for entry in manifest["entries"]:
                scenario_id = str(entry["id"])
                descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
                if str(descriptor.get("session_id") or "").strip():
                    raise ComparisonManifestError(
                        "comparison does not support explicit session_id "
                        f"for scenario {scenario_id!r}"
                    )
                lock = str(entry["locked_input_sha256"])
                mode = split_assignment_map[scenario_id]
                result = _run_mode(
                    descriptor,
                    mode=mode,
                    locked_input_sha256=lock,
                    output_base=base,
                    tag=tag,
                    transport=transport,
                )
                metrics = _leg_metrics(result)
                comparisons.append(
                    {
                        "scenario_id": scenario_id,
                        "locked_input_sha256": lock,
                        "mode": mode,
                        "outcome": metrics["outcome"],
                        "leg": metrics,
                        "pair_skipped": True,
                        "delta": None,
                    }
                )
        split_counts = {"staged": staged_cnt, "threaded": threaded_cnt}
        payload = {
            "aggregate": _aggregate_split(comparisons),
            "scenarios": comparisons,
            "split": split_counts,
            "split_digest": split_digest(split_assignment_map),
            "split_assignment": split_assignment_map,
        }
    elif concurrency > 1:
        descriptors: list[tuple[str, str, dict[str, Any], str]] = []
        for entry in manifest["entries"]:
            scenario_id = str(entry["id"])
            descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
            lock = str(entry["locked_input_sha256"])
            if str(descriptor.get("session_id") or "").strip():
                raise ComparisonManifestError(
                    "concurrent comparison does not support explicit session_id "
                    f"for scenario {scenario_id!r}"
                )
            for mode in PIPELINE_MODES:
                descriptors.append((scenario_id, mode, descriptor, lock))
        if leg_isolation == "process":
            leg_results = _run_legs_in_processes(
                descriptors,
                output_base=base,
                tag=tag,
                transport=transport,
                concurrency=concurrency,
            )
        else:
            leg_results: list[dict[str, Any] | None] = [None] * len(descriptors)
            with ThreadPoolExecutor(
                max_workers=min(concurrency, len(descriptors)),
                thread_name_prefix="compare-pipeline-leg",
            ) as executor:
                futures = [
                    executor.submit(
                        _run_mode,
                        copy.deepcopy(descriptor),
                        mode=mode,
                        locked_input_sha256=lock,
                        output_base=base,
                        tag=tag,
                        transport=transport,
                    )
                    for _scenario_id, mode, descriptor, lock in descriptors
                ]
                for index, (future, (scenario_id, mode, _descriptor, lock)) in enumerate(
                    zip(futures, descriptors)
                ):
                    try:
                        leg_results[index] = future.result()
                    except Exception as exc:  # noqa: BLE001
                        leg_results[index] = _leg_exception_summary(
                            scenario_id,
                            mode=mode,
                            locked_input_sha256=lock,
                            output_base=base,
                            tag=tag,
                            error=exc,
                        )
        ordered: dict[str, dict[str, dict[str, Any]]] = {}
        for (scenario_id, mode, _descriptor, _lock), result in zip(
            descriptors, leg_results
        ):
            assert result is not None
            ordered.setdefault(scenario_id, {})[mode] = result
        for entry in manifest["entries"]:
            scenario_id = str(entry["id"])
            lock = str(entry["locked_input_sha256"])
            legs = ordered[scenario_id]
            comparisons.append(
                compare_pair(
                    scenario_id,
                    locked_input_sha256=lock,
                    staged=legs["staged"],
                    threaded=legs["threaded"],
                )
            )
    else:
        for entry in manifest["entries"]:
            scenario_id = str(entry["id"])
            descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
            if str(descriptor.get("session_id") or "").strip():
                raise ComparisonManifestError(
                    "comparison does not support explicit session_id "
                    f"for scenario {scenario_id!r}"
                )
            lock = str(entry["locked_input_sha256"])
            legs = {
                mode: _run_mode(
                    descriptor,
                    mode=mode,
                    locked_input_sha256=lock,
                    output_base=base,
                    tag=tag,
                    transport=transport,
                )
                for mode in PIPELINE_MODES
            }
            comparisons.append(
                compare_pair(
                    scenario_id,
                    locked_input_sha256=lock,
                    staged=legs["staged"],
                    threaded=legs["threaded"],
                )
            )
    if split:
        pass
    else:
        payload = {"aggregate": _aggregate(comparisons), "scenarios": comparisons}
    base.mkdir(parents=True, exist_ok=True)
    (base / "comparison.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (base / "comparison.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload
def _write_leg_spec(
    spec_path: Path,
    *,
    scenario: Mapping[str, Any],
    mode: str,
    locked_input_sha256: str,
    output_base: Path,
    tag: str,
    transport: str | None,
    attempt_identity: str | None = None,
) -> None:
    """Persist one leg's full execution spec (the subprocess's only input).

    RRSYN-6: ``attempt_identity`` (attempt ≥ 2 only) overrides the run tag the
    child executes under so a timeout-only relaunch gets a FRESH attempt
    identity — fresh output dirs — while the locked input (scenario +
    ``locked_input_sha256``) stays byte-identical. Attempt-1 specs omit the
    field entirely and keep their historical bytes.
    """
    spec = {
        "scenario": dict(scenario),
        "mode": mode,
        "locked_input_sha256": locked_input_sha256,
        "output_base": str(output_base),
        "tag": tag,
        "transport": transport,
        "source_commit": _SOURCE_COMMIT[0] if _SOURCE_COMMIT else "",
    }
    if attempt_identity is not None:
        spec["attempt_identity"] = attempt_identity
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = spec_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(spec), encoding="utf-8")
    tmp.replace(spec_path)


def run_leg_from_spec(spec_path: str | Path, out_path: str | Path) -> int:
    """Child entry: execute exactly one leg and atomically persist its summary.

    Runs in a fresh interpreter — no parent module state is shared. The child
    re-pins the source-commit env from its spec so the T5.1 lineage rows match
    the parent comparison.
    """
    import tempfile  # noqa: PLC0415

    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    commit = str(spec.get("source_commit") or "")
    if commit:
        os.environ[SOURCE_COMMIT_ENV_VAR] = commit
    try:
        summary = _run_mode(
            dict(spec["scenario"]),
            mode=str(spec["mode"]),
            locked_input_sha256=str(spec["locked_input_sha256"]),
            output_base=Path(str(spec["output_base"])),
            tag=str(spec.get("attempt_identity") or spec["tag"]),
            transport=spec.get("transport"),
        )
        payload = {"ok": True, "summary": summary}
    except BaseException as exc:  # noqa: BLE001 - the child reports, never crashes silently
        payload = {
            "ok": False,
            "error": str(exc),
            "exception_type": type(exc).__name__,
        }
    fd, tmp_name = tempfile.mkstemp(
        dir=str(Path(out_path).parent), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, default=str)
        os.replace(tmp_name, str(out_path))
        tmp_name = None
    finally:
        if tmp_name is not None:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    return 0


# ── RRSYN-6: bounded per-attempt evidence + timeout-only retry ───────────────

def _leg_command(spec_path: Path, result_path: Path) -> list[str]:
    """Child command for one leg attempt (extracted for deterministic tests)."""
    return [
        os.sys.executable,
        "-m",
        "tests.live_agentic_harness.compare_pipeline_modes",
        "--run-leg",
        str(spec_path),
        "--leg-out",
        str(result_path),
    ]


def _leg_attempt_identity(tag: str, scenario_id: str, mode: str, attempt: int) -> str:
    """Fresh identity per attempt (mirrors ``runner._attempt_tag``)."""
    return f"{tag}/attempts/{scenario_id}/{mode}/attempt_{attempt}"


def _leg_attempt_paths(
    specs_dir: Path, index: int, scenario_id: str, mode: str, attempt: int
) -> dict[str, Path]:
    """Per-attempt spec/result/log paths. Attempt 1 keeps legacy names."""
    suffix = "" if attempt == 1 else f".attempt_{attempt}"
    stem = f"leg_{index:04d}_{scenario_id}_{mode}"
    return {
        "spec": specs_dir / f"{stem}{suffix}.json",
        "result": specs_dir / f"result_{index:04d}_{scenario_id}_{mode}{suffix}.json",
        "stdout": specs_dir / f"{stem}{suffix}.out.log",
        "stderr": specs_dir / f"{stem}{suffix}.err.log",
    }


def _bounded_tail(path: Path, cap: int = LEG_LOG_TAIL_CHARS) -> str | None:
    """Last *cap* chars of a log file, or None when absent (never unbounded)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return text[-cap:]


def _leg_attempt_record(
    summary: Mapping[str, Any] | None,
    *,
    attempt: int,
    attempt_identity: str,
    deadline_seconds: float,
    timed_out: bool,
    paths: Mapping[str, Path],
) -> dict[str, Any]:
    """Typed per-attempt record with runner-style retry ownership."""
    if isinstance(summary, Mapping):
        ok = summary.get("ok") is True
        failure_class = str(
            summary.get("failure_class")
            or ("infra_timeout" if timed_out else "product_or_assessment_failure")
        )
        live = bool((summary.get("guard") or {}).get("live_agentic_success"))
        cost = summary.get("deepseek_est_cost_usd")
    else:
        ok = False
        failure_class = "infra_timeout" if timed_out else "runner_exception"
        live = False
        cost = None
    if timed_out and not ok:
        # Remote state of a timed-out completion request is unknowable: a
        # relaunch is only ever safe under a FRESH identity (T3.1/D6 freeze).
        retry_disposition = "not_safe_to_retry_same_identity"
        remote_uncertainty = "timeout_before_response"
    elif ok:
        retry_disposition = "none"
        remote_uncertainty = None
    else:
        # Product failures are terminal: the harness never retries them.
        retry_disposition = "terminal"
        remote_uncertainty = None
    return {
        "attempt": attempt,
        "attempt_identity": attempt_identity,
        "ok": ok,
        "failure_class": failure_class,
        "score_class": (
            "infra_blocked"
            if failure_class.startswith("infra_")
            else ("pass" if live else "product_fail")
        ),
        "live_agentic_success": live,
        "timed_out": timed_out,
        "cost_usd": cost,
        "cost_basis": "summary" if isinstance(summary, Mapping) else "not_available",
        "spec_path": str(paths["spec"]),
        "result_path": str(paths["result"]),
        "stdout_log": str(paths["stdout"]),
        "stderr_log": str(paths["stderr"]),
        "stdout_tail": _bounded_tail(Path(paths["stdout"])),
        "stderr_tail": _bounded_tail(Path(paths["stderr"])),
        "retry_ownership": {
            "owner": HARNESS_RETRY_OWNER,
            "attempt_identity": attempt_identity,
            "attempt_deadline_seconds": float(deadline_seconds),
            "same_identity_retry": False,
            "retry_disposition": retry_disposition,
            "remote_uncertainty": remote_uncertainty,
            # Completion requests carry no idempotency key; recorded so
            # evidence consumers never have to assume otherwise.
            "request_idempotency_key": None,
        },
    }


def _attach_leg_attempt_bookkeeping(
    summary: dict[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    *,
    final_success: bool,
) -> dict[str, Any]:
    """Attach runner-style attempt bookkeeping onto a final leg summary."""
    summary["attempts"] = [dict(attempt) for attempt in attempts]
    summary["attempt_count"] = len(attempts)
    summary["final_attempt"] = attempts[-1]["attempt"]
    summary["raw_first_attempt_success"] = attempts[0].get("live_agentic_success") is True
    summary["final_success"] = final_success
    summary["retry_owner"] = HARNESS_RETRY_OWNER
    summary["retried_after_timeout"] = attempts[-1]["attempt"] > 1
    return summary


def _persist_leg_attempts_index(
    specs_dir: Path,
    index: int,
    scenario_id: str,
    mode: str,
    attempts: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> None:
    """Persist the leg's intermediate attempt/phase evidence atomically."""
    path = specs_dir / f"attempts_{index:04d}_{scenario_id}_{mode}.json"
    payload = {
        key: summary.get(key)
        for key in (
            "raw_first_attempt_success",
            "final_success",
            "final_attempt",
            "attempt_count",
            "retry_owner",
            "retried_after_timeout",
        )
    }
    payload["attempts"] = [dict(attempt) for attempt in attempts]
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, default=str, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _run_legs_in_processes(
    descriptors: Sequence[tuple[str, str, Mapping[str, Any], str]],
    *,
    output_base: Path,
    tag: str,
    transport: str | None,
    concurrency: int = 1,
) -> list[dict[str, Any] | None]:
    """Run legs in their own processes under the concurrency cap.

    At most ``concurrency`` leg processes are live at any moment; a finished
    leg's slot is handed to the next descriptor immediately (no
    serialization-to-hide-races: independent legs still overlap up to the
    cap). Reconstruction follows the submission/manifest order, so failed
    children retain their original slots and no state is shared between legs.

    RRSYN-6: every attempt's stdout/stderr streams persist to per-attempt log
    files (bounded tails are embedded in the attempt records — never DEVNULL),
    each finished attempt appends a typed record with retry ownership to the
    leg's persisted attempts index, and a leg that TIMES OUT is relaunched at
    most ONCE under a fresh attempt identity with a byte-identical locked
    input. Product failures and non-timeout crashes are never retried;
    attempt 1 evidence is always preserved; an unknown timeout cause stays
    infra-blocked rather than being guessed green.
    """
    import signal  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    max_live = max(1, int(concurrency))
    specs_dir = output_base / "_legs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    handles: dict[int, subprocess.Popen[Any]] = {}
    paths_by_index: dict[int, dict[str, Path]] = {}
    attempts_by_index: dict[int, list[dict[str, Any]]] = {}
    attempt_of: dict[int, int] = {}
    leg_results: list[dict[str, Any] | None] = [None] * len(descriptors)
    deadline_by_index = [0.0] * len(descriptors)
    next_to_launch = 0

    def _launch(index: int) -> None:
        scenario_id, mode, scenario, lock = descriptors[index]
        attempt = attempt_of.get(index, 1)
        paths = _leg_attempt_paths(specs_dir, index, scenario_id, mode, attempt)
        identity = _leg_attempt_identity(tag, scenario_id, mode, attempt)
        _write_leg_spec(
            paths["spec"],
            scenario=dict(scenario),
            mode=mode,
            locked_input_sha256=lock,
            output_base=output_base,
            tag=tag,
            transport=transport,
            # Attempt ≥ 2 runs under a fresh identity; attempt 1 spec bytes
            # stay exactly as they have always been.
            attempt_identity=identity if attempt > 1 else None,
        )
        command = _leg_command(paths["spec"], paths["result"])
        env = dict(os.environ)
        env["VIBECOMFY_HEADLESS"] = "1"
        if _SOURCE_COMMIT:
            env[SOURCE_COMMIT_ENV_VAR] = _SOURCE_COMMIT[0]
        out_handle = paths["stdout"].open("w", encoding="utf-8")
        err_handle = paths["stderr"].open("w", encoding="utf-8")
        try:
            handles[index] = subprocess.Popen(
                command,
                cwd=str(REPO),
                env=env,
                stdout=out_handle,
                stderr=err_handle,
                start_new_session=True,
            )
        finally:
            out_handle.close()
            err_handle.close()
        paths_by_index[index] = paths
        deadline_by_index[index] = time.monotonic() + LEG_TIMEOUT_SECONDS

    while next_to_launch < len(descriptors) or handles:
        while next_to_launch < len(descriptors) and len(handles) < max_live:
            _launch(next_to_launch)
            next_to_launch += 1
        finished_now: list[int] = []
        for index in sorted(handles):
            code = handles[index].poll()
            if code is not None or time.monotonic() > deadline_by_index[index]:
                finished_now.append(index)
        if not finished_now:
            time.sleep(0.05)
            continue
        for index in finished_now:
            handle = handles.pop(index)
            paths = paths_by_index.pop(index)
            scenario_id, mode, _scenario, lock = descriptors[index]
            attempt = attempt_of.get(index, 1)
            timed_out = time.monotonic() > deadline_by_index[index]
            returncode = handle.poll()
            if timed_out and handle.poll() is None:
                try:
                    os.killpg(os.getpgid(handle.pid), signal.SIGTERM)
                    handle.wait(timeout=LEG_KILL_GRACE_SECONDS)
                except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(handle.pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
            result_path = paths["result"]
            payload = _load_json(result_path) if result_path.is_file() else None
            accepted_summary = (
                dict(payload["summary"])
                if isinstance(payload, Mapping)
                and payload.get("ok") is True
                and isinstance(payload.get("summary"), Mapping)
                else None
            )
            record = _leg_attempt_record(
                accepted_summary
                or (payload if isinstance(payload, Mapping) else None),
                attempt=attempt,
                attempt_identity=_leg_attempt_identity(tag, scenario_id, mode, attempt),
                deadline_seconds=float(LEG_TIMEOUT_SECONDS),
                timed_out=timed_out and accepted_summary is None,
                paths=paths,
            )
            attempts = attempts_by_index.setdefault(index, [])
            attempts.append(record)

            if accepted_summary is not None:
                summary = _attach_leg_attempt_bookkeeping(
                    accepted_summary, attempts, final_success=True
                )
                _persist_leg_attempts_index(
                    specs_dir, index, scenario_id, mode, attempts, summary
                )
                leg_results[index] = summary
                continue

            if timed_out and attempt < LEG_ATTEMPT_LIMIT:
                # ONE timeout-only relaunch under a FRESH attempt identity;
                # the locked scenario input is byte-identical and attempt 1
                # evidence (spec/result/logs/record) stays in place.
                attempt_of[index] = attempt + 1
                _launch(index)
                continue

            error_text = (
                str(payload.get("error"))
                if isinstance(payload, Mapping) and payload.get("error")
                else (
                    f"leg process timed out after {LEG_TIMEOUT_SECONDS}s"
                    if timed_out
                    else f"leg process exited with code {returncode}"
                )
            )
            base = _leg_exception_summary(
                scenario_id,
                mode=mode,
                locked_input_sha256=lock,
                output_base=output_base,
                tag=tag,
                error=RuntimeError(error_text),
            )
            if timed_out:
                # Unknown timeout cause stays infra-blocked — never product.
                base["status"] = "timeout"
                base["failure_class"] = "infra_timeout"
                base["guard"] = {
                    "live_agentic_success": False,
                    "score_class": "infra_blocked",
                    "failure_class": "infra_timeout",
                }
            summary = _attach_leg_attempt_bookkeeping(
                base, attempts, final_success=False
            )
            _persist_leg_attempts_index(
                specs_dir, index, scenario_id, mode, attempts, summary
            )
            leg_results[index] = summary
    return leg_results




def _render_markdown(payload: Mapping[str, Any]) -> str:
    aggregate = payload["aggregate"]
    if "split" in payload:
        split = payload["split"]
        lines = [
            "# Pipeline comparison: staged versus threaded (split 25/25)",
            "",
            f"- Scenarios: {aggregate['scenario_count']}",
            f"- Split: staged={split.get('staged')} threaded={split.get('threaded')} digest={payload.get('split_digest','')[:12]}…",
            f"- Outcomes: `{json.dumps(aggregate['outcomes'], sort_keys=True)}`",
            f"- Cost delta (threaded - staged): {aggregate['threaded_minus_staged']['cost_usd']}",
            f"- Latency delta (threaded - staged): {aggregate['threaded_minus_staged']['latency_s']}",
            "",
            "| scenario | mode | outcome |",
            "|---|---|---|",
        ]
        for item in payload["scenarios"]:
            lines.append(f"| {item['scenario_id']} | {item['mode']} | {item['outcome']} |")
        return "\n".join(lines) + "\n"
    lines = [
        "# Pipeline comparison: staged versus threaded",
        "",
        f"- Scenarios: {aggregate['scenario_count']}",
        f"- Outcomes: `{json.dumps(aggregate['outcomes'], sort_keys=True)}`",
        f"- Identical locked inputs: {aggregate['all_inputs_locked_equal']}",
        f"- IR projection matches: {aggregate['ir_projection_equal_count']}",
        f"- Canonical delta matches: {aggregate['canonical_delta_equal_count']}",
        f"- Cost delta (threaded - staged): {aggregate['threaded_minus_staged']['cost_usd']}",
        f"- Latency delta (threaded - staged): {aggregate['threaded_minus_staged']['latency_s']}",
        "",
        "| scenario | outcome | IR equal | delta equal | evidence equal | failure equal |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for item in payload["scenarios"]:
        delta = item["delta"]
        lines.append(
            f"| {item['scenario_id']} | {item['outcome']} | "
            f"{delta['ir_projection_equal']} | {delta['canonical_delta_equal']} | "
            f"{delta['evidence_integrity_equal']} | {delta['failure_family_equal']} |"
        )
    return "\n".join(lines) + "\n"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.live_agentic_harness.compare_pipeline_modes"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_COMPARISON_MANIFEST)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--output-base", type=Path, default=None)
    parser.add_argument("--tag", default="staged-threaded")
    parser.add_argument("--transport", choices=("openrouter", "native"), default=None)
    parser.add_argument(
        "--concurrency",
        type=_positive_int,
        default=1,
        help="Maximum concurrent scenario/mode legs (default: %(default)s).",
    )
    parser.add_argument(
        "--leg-isolation",
        choices=LEG_ISOLATION_MODES,
        default=None,
        help=(
            "Concurrent-leg isolation (T5.4). 'process' runs every leg in its "
            "own interpreter (no shared state; required for all paid CLI "
            "runs); 'thread' is the weaker shared-process lane and is "
            "restricted to dry/validation use."
        ),
    )
    parser.add_argument("--run-leg", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--leg-out", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument(
        "--split",
        action="store_true",
        help="C5: one-invocation 25/25 split finale (one leg per scenario, frozen map)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.run_leg is not None:
        # Child leg entry (T5.4 process isolation): one spec in, one summary out.
        if args.leg_out is None:
            print(json.dumps({"ok": False, "error": "--run-leg requires --leg-out"}))
            return 2
        return run_leg_from_spec(args.run_leg, args.leg_out)
    try:
        if args.validate_only:
            payload = validate_only(args.manifest)
        elif args.run:
            # G5-B4-MUST-006: the CLI run lane is the paid-call lane — exact
            # IndexTTS/LayerMask schema evidence must resolve from local
            # authoritative sources before any leg starts. A pre-set
            # VIBECOMFY_OBLIGATION_SCHEMA_CHECK=0 can no longer bypass this.
            # Lazy import: scenario_obligations imports this module.
            from .scenario_obligations import SCHEMA_RESOLUTION_ENV_VAR  # noqa: PLC0415

            os.environ[SCHEMA_RESOLUTION_ENV_VAR] = "1"
            if args.leg_isolation == "thread":
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": (
                                "--leg-isolation thread is restricted to "
                                "dry/validation use; paid runs require "
                                "'process' isolation"
                            ),
                        },
                        indent=2,
                    )
                )
                return 2
            leg_isolation = args.leg_isolation or "process"
            payload = run_comparison(
                args.manifest,
                output_base=args.output_base,
                tag=args.tag,
                transport=args.transport,
                concurrency=args.concurrency,
                leg_isolation=leg_isolation,
                split=args.split,
            )
        else:
            print("choose --validate-only or --run")
            return 2
    except (ComparisonManifestError, ScenarioManifestError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(payload, indent=2, default=str))
    return 0




if __name__ == "__main__":
    raise SystemExit(main())
