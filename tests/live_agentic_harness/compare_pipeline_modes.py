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
        return
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
        "staged": {"cost_usd": round(staged_cost, 6), "latency_s": round(staged_latency, 6)},
        "threaded": {
            "cost_usd": round(threaded_cost, 6),
            "latency_s": round(threaded_latency, 6),
        },
        "threaded_minus_staged": {
            "cost_usd": round(threaded_cost - staged_cost, 6),
            "latency_s": round(threaded_latency - staged_latency, 6),
        },
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
) -> dict[str, Any]:
    """Run the locked comparison lane once threaded adapter wiring is ready.


    ``concurrency=1`` retains the historical scenario-major,
    staged-then-threaded execution order.  Higher values submit every
    scenario/mode leg before awaiting any result, then compare and serialize
    results on the parent thread in manifest order.
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
            for mode in PIPELINE_MODES:
                descriptors.append((scenario_id, mode, descriptor, lock))

        # Submit all legs before awaiting any result.  Deep-copy at submission
        # time so workers cannot share mutable descriptor state.
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
                # Await in submission order for deterministic reconstruction
                # while allowing every submitted future to run concurrently.
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

        # No comparison or IR projection occurs until every leg has finished.
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
        # Compatibility path: preserve the original nested loop and call
        # behavior when no explicit concurrency is requested.
        for entry in manifest["entries"]:
            scenario_id = str(entry["id"])
            descriptor = _load_json(REPO / str(canonical[scenario_id]["path"])) or {}
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
) -> None:
    """Persist one leg's full execution spec (the subprocess's only input)."""
    spec = {
        "scenario": dict(scenario),
        "mode": mode,
        "locked_input_sha256": locked_input_sha256,
        "output_base": str(output_base),
        "tag": tag,
        "transport": transport,
        "source_commit": _SOURCE_COMMIT[0] if _SOURCE_COMMIT else "",
    }
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
            tag=str(spec["tag"]),
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
    """
    import signal  # noqa: PLC0415
    import subprocess  # noqa: PLC0415

    max_live = max(1, int(concurrency))
    specs_dir = output_base / "_legs"
    specs_dir.mkdir(parents=True, exist_ok=True)
    handles: dict[int, subprocess.Popen[Any]] = {}
    out_paths: dict[int, Path] = {}
    leg_results: list[dict[str, Any] | None] = [None] * len(descriptors)
    deadline_by_index = [0.0] * len(descriptors)
    next_to_launch = 0

    def _launch(index: int) -> None:
        scenario_id, mode, scenario, lock = descriptors[index]
        spec_path = specs_dir / f"leg_{index:04d}_{scenario_id}_{mode}.json"
        out_path = specs_dir / f"result_{index:04d}_{scenario_id}_{mode}.json"
        _write_leg_spec(
            spec_path,
            scenario=dict(scenario),
            mode=mode,
            locked_input_sha256=lock,
            output_base=output_base,
            tag=tag,
            transport=transport,
        )
        command = [
            os.sys.executable,
            "-m",
            "tests.live_agentic_harness.compare_pipeline_modes",
            "--run-leg",
            str(spec_path),
            "--leg-out",
            str(out_path),
        ]
        env = dict(os.environ)
        env["VIBECOMFY_HEADLESS"] = "1"
        if _SOURCE_COMMIT:
            env[SOURCE_COMMIT_ENV_VAR] = _SOURCE_COMMIT[0]
        handles[index] = subprocess.Popen(
            command,
            cwd=str(REPO),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        out_paths[index] = out_path
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
            out_path = out_paths.pop(index)
            scenario_id, mode, _scenario, lock = descriptors[index]
            timed_out = time.monotonic() > deadline_by_index[index]
            if timed_out and handle.poll() is None:
                try:
                    os.killpg(os.getpgid(handle.pid), signal.SIGTERM)
                    handle.wait(timeout=LEG_KILL_GRACE_SECONDS)
                except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(os.getpgid(handle.pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
            payload = _load_json(out_path) if out_path.is_file() else None
            if isinstance(payload, Mapping) and payload.get("ok") is True and isinstance(
                payload.get("summary"), Mapping
            ):
                leg_results[index] = dict(payload["summary"])
                continue
            error_text = (
                str(payload.get("error"))
                if isinstance(payload, Mapping) and payload.get("error")
                else (
                    f"leg process timed out after {LEG_TIMEOUT_SECONDS}s"
                    if timed_out
                    else f"leg process exited with code {code}"
                )
            )
            leg_results[index] = _leg_exception_summary(
                scenario_id,
                mode=mode,
                locked_input_sha256=lock,
                output_base=output_base,
                tag=tag,
                error=RuntimeError(error_text),
            )
    return leg_results




def _render_markdown(payload: Mapping[str, Any]) -> str:
    aggregate = payload["aggregate"]
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
            # G5-B4-MUST-008: paid legs never run on the shared-process
            # thread lane. Concurrent runs default to process isolation;
            # an explicit --leg-isolation thread is refused.
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
