"""T5.1 assessor-side artifact lineage checks.

The harness assessor consumes the executor-built artifact lineage manifest
(``vibecomfy.comfy_nodes.agent.artifact_lineage``) plus the comparison lane's
``binding`` block and verifies:

* the manifest is present, typed-valid, and its ``manifest_digest`` matches
  its content (no tampering);
* the sidecar is CORRELATED against the current response envelope (same
  manifest content fingerprint) — a stale or foreign sidecar is rejected, it
  can never win over the envelope by merely existing;
* the binding's scenario identity matches the assessed scenario AND the
  manifest's own ``lineage`` block, and the manifest's session/turn identity
  matches the terminal response when both carry one (no stale-path or
  cross-turn assessment);
* fallback rows never impersonate a landed product: an envelope that claims an
  applied edit (positive ``landed_operation_count`` / ``graph_unchanged``
  false on an edit route) must carry PRIMARY accepted-delta / candidate /
  replay-proof rows — typed fallbacks there are a contradiction, not a pass;
* absence of any manifest is recorded as an ``undetermined`` issue — missing
  lineage evidence never grades green silently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from vibecomfy.comfy_nodes.agent.artifact_lineage import (
    validate_artifact_lineage,
)

_LINEAGE_SIDECAR_NAME = "artifact_lineage.json"

#: Rows that MUST be primary when the envelope claims a landed edit.
_LANDED_EDIT_ROW_KINDS = ("accepted_delta", "candidate", "replay_proof")

#: Exact validation-failure text produced by
#: ``vibecomfy.comfy_nodes.agent.artifact_lineage.validate_artifact_lineage``
#: when a structurally-valid manifest's self-consistency digest does not
#: recompute over its content (P7 Sub-fix A demotion key).
_DIGEST_MISMATCH_ERROR = "manifest_digest does not match manifest content"


def _envelope_manifest(response: Mapping[str, Any] | None) -> Mapping[str, Any] | None:
    """Extract the response-envelope copy of the artifact lineage manifest."""
    if not isinstance(response, Mapping):
        return None
    report = response.get("report")
    if not isinstance(report, Mapping):
        return None
    executor = report.get("executor")
    if not isinstance(executor, Mapping):
        return None
    manifest = executor.get("artifact_lineage")
    return manifest if isinstance(manifest, Mapping) else None


def _read_sidecar(output_dir: Path | str) -> Mapping[str, Any] | None:
    sidecar_path = Path(output_dir) / _LINEAGE_SIDECAR_NAME
    if not sidecar_path.is_file():
        return None
    try:
        loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, Mapping) else None


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Content fingerprint over exactly the digest-participating fields."""
    from vibecomfy.comfy_nodes.agent.artifact_lineage import (
        canonical_lineage_digest,
    )

    rows = manifest.get("rows")
    rows = [dict(row) for row in rows] if isinstance(rows, list) else []
    lineage = manifest.get("lineage")
    return canonical_lineage_digest(
        {
            "schema_version": manifest.get("schema_version"),
            "lineage": dict(lineage) if isinstance(lineage, Mapping) else {},
            "rows": rows,
        }
    )


def load_artifact_lineage(
    output_dir: Path | str,
    response: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, str]:
    """Return ``(manifest, provenance)`` for the assessed output directory.

    Provenance is one of ``"sidecar_correlated"``, ``"sidecar_unverified"``,
    ``"sidecar_digest_mismatch"``, ``"envelope"``, or ``"absent"``. A sidecar
    is trusted as scenario-bound evidence ONLY when its manifest content
    fingerprints identical to the current response envelope's copy; a
    same-scenario sidecar from an earlier turn has different content and is
    reported as ``"sidecar_digest_mismatch"``. A sidecar with no envelope copy
    to correlate against is returned as ``"sidecar_unverified"`` so the
    assessor can grade the leg ``undetermined`` instead of failing open.
    """
    sidecar = _read_sidecar(output_dir)
    envelope = _envelope_manifest(response)
    if sidecar is not None and envelope is not None:
        if _manifest_fingerprint(sidecar) == _manifest_fingerprint(envelope):
            # Same underlying manifest; the sidecar adds the harness binding.
            return sidecar, "sidecar_correlated"
        return None, "sidecar_digest_mismatch"
    if sidecar is not None:
        return sidecar, "sidecar_unverified"
    if envelope is not None:
        return envelope, "envelope"
    return None, "absent"


def _claims_landed_edit(response: Mapping[str, Any]) -> bool:
    """True when the envelope itself claims an applied, landed edit."""
    if response.get("graph_unchanged") is not False:
        return False
    change_details = response.get("change_details")
    landed = (
        change_details.get("landed_operation_count")
        if isinstance(change_details, Mapping)
        else None
    )
    if not (isinstance(landed, int) and not isinstance(landed, bool) and landed > 0):
        return False
    gates = response.get("gates")
    if isinstance(gates, Mapping) and gates.get("queue_validate_ok") is False:
        # A withheld batch is not a landed product.
        return False
    return True


def assess_artifact_lineage(
    output_dir: Path | str,
    response: Mapping[str, Any] | None,
    scenario: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assess the artifact lineage evidence for one leg.

    Returns ``{"issues": [...], "present": bool, "manifest_digest": ...,
    "binding": {...}}``. Issue severities follow the assessor vocabulary:
    ``error`` fails the leg, ``warning``/``undetermined`` surface honestly
    without fabricating a pass.
    """
    issues: list[dict[str, str]] = []
    manifest, provenance = load_artifact_lineage(output_dir, response)
    result: dict[str, Any] = {
        "issues": issues,
        "present": manifest is not None,
        "manifest_digest": None,
        "binding": {},
        "provenance": provenance,
    }
    if manifest is None or provenance in ("sidecar_digest_mismatch", "sidecar_unverified"):
        # Fail closed (G5-B4-MUST-003): absent or uncorrelatable lineage is
        # surfaced honestly — it can never be a silent green.
        if provenance == "sidecar_digest_mismatch":
            issues.append(
                {
                    "check": "artifact_lineage_sidecar_stale",
                    "severity": "error",
                    "detail": (
                        "artifact_lineage.json sidecar does not match the "
                        "current response envelope (stale-path or cross-turn "
                        "evidence); refusing to grade against it"
                    ),
                }
            )
        elif provenance == "sidecar_unverified":
            issues.append(
                {
                    "check": "artifact_lineage_sidecar_unverified",
                    "severity": "undetermined",
                    "detail": (
                        "artifact_lineage.json sidecar could not be correlated "
                        "against the current response envelope; its binding "
                        "cannot prove this run produced it"
                    ),
                }
            )
        else:
            issues.append(
                {
                    "check": "artifact_lineage_absent",
                    "severity": "undetermined",
                    "detail": (
                        "no artifact lineage manifest is present for this leg; "
                        "product evidence cannot be bound to accepted-delta "
                        "authority"
                    ),
                }
            )
        return result

    ok, error = validate_artifact_lineage(manifest)
    # P7 Sub-fix A: a stale self-consistency digest over otherwise
    # structurally-valid content ("manifest_digest does not match manifest
    # content") must not fail the leg by itself.  Assessment CONTINUES through
    # every remaining check below; the issue is appended at the end with
    # warning severity ONLY when no other check errored (anti-gaming: any
    # failing product check keeps it an error).  Every other validation
    # failure stays a hard error.
    digest_stale_only = bool(not ok and error == _DIGEST_MISMATCH_ERROR)
    if not ok and not digest_stale_only:
        issues.append(
            {
                "check": "artifact_lineage",
                "severity": "error",
                "detail": f"invalid lineage manifest ({provenance}): {error}",
            }
        )
        return result

    result["manifest_digest"] = manifest.get("manifest_digest")

    binding = manifest.get("binding")
    if isinstance(binding, Mapping):
        result["binding"] = dict(binding)
        scenario_id = str(scenario.get("id") or "") if isinstance(scenario, Mapping) else ""
        bound_scenario = str(binding.get("scenario_id") or "")
        if scenario_id and bound_scenario and bound_scenario != scenario_id:
            issues.append(
                {
                    "check": "artifact_lineage_binding",
                    "severity": "error",
                    "detail": (
                        "lineage binding scenario_id "
                        f"{bound_scenario!r} does not match assessed scenario "
                        f"{scenario_id!r} (stale-path or cross-turn evidence)"
                    ),
                }
            )
        # The binding must also agree with the manifest's own executor-built
        # lineage identity, not just with the assessed scenario label.
        lineage_block = manifest.get("lineage")
        manifest_scenario = (
            str(lineage_block.get("scenario_id") or "")
            if isinstance(lineage_block, Mapping)
            else ""
        )
        if bound_scenario and manifest_scenario and bound_scenario != manifest_scenario:
            issues.append(
                {
                    "check": "artifact_lineage_binding",
                    "severity": "error",
                    "detail": (
                        f"lineage binding scenario_id {bound_scenario!r} does "
                        "not match the manifest's own executor lineage "
                        f"scenario_id {manifest_scenario!r}; binding was "
                        "re-stapled onto another run's manifest"
                    ),
                }
            )
        # Correlate the manifest's turn identity against the terminal
        # response: a sidecar from an earlier turn of the same scenario
        # carries a different session/turn identity than this response.
        for key in ("session_id", "turn_id"):
            response_value = str(response.get(key) or "") if isinstance(response, Mapping) else ""
            lineage_value = (
                str(lineage_block.get(key) or "")
                if isinstance(lineage_block, Mapping)
                else ""
            )
            if response_value and lineage_value and response_value != lineage_value:
                issues.append(
                    {
                        "check": "artifact_lineage_binding",
                        "severity": "error",
                        "detail": (
                            f"lineage {key} {lineage_value!r} does not match "
                            f"the terminal response {key} {response_value!r} "
                            "(stale same-scenario evidence)"
                        ),
                    }
                )

    if isinstance(response, Mapping) and _claims_landed_edit(response):
        rows = {
            str(row.get("kind")): row
            for row in manifest.get("rows", [])
            if isinstance(row, Mapping)
        }
        for kind in _LANDED_EDIT_ROW_KINDS:
            row = rows.get(kind)
            if isinstance(row, Mapping) and row.get("row_class") == "fallback":
                issues.append(
                    {
                        "check": "artifact_lineage_fallback_impersonation",
                        "severity": "error",
                        "detail": (
                            f"envelope claims a landed edit but lineage row "
                            f"{kind!r} is a typed fallback "
                            f"(reason={row.get('reason')!r}); a fallback can "
                            "never stand in for the landed product"
                        ),
                    }
                )
    if digest_stale_only:
        # P7 Sub-fix A: every other check has now run.  Demote to warning
        # ONLY when none of them produced an error; otherwise the stale
        # digest stays error-severity alongside the failing evidence.
        no_other_errors = not any(
            issue.get("severity") == "error" for issue in issues
        )
        issues.append(
            {
                "check": "artifact_lineage",
                "severity": "warning" if no_other_errors else "error",
                "detail": (
                    f"invalid lineage manifest ({provenance}): {error}"
                    + (
                        "; demoted to warning because every other lineage "
                        "and product check passed"
                        if no_other_errors
                        else ""
                    )
                ),
            }
        )
    return result


__all__ = ["assess_artifact_lineage", "load_artifact_lineage"]
