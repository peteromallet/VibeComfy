"""T5.1 assessor-side artifact lineage checks.

The harness assessor consumes the executor-built artifact lineage manifest
(``vibecomfy.comfy_nodes.agent.artifact_lineage``) plus the comparison lane's
``binding`` block and verifies:

* the manifest is present, typed-valid, and its ``manifest_digest`` matches
  its content (no tampering);
* the binding's scenario identity matches the assessed scenario (no stale-path
  or cross-turn assessment);
* fallback rows never impersonate a landed product: an envelope that claims an
  applied edit (positive ``landed_operation_count`` / ``graph_unchanged``
  false on an edit route) must carry PRIMARY accepted-delta / candidate /
  replay-proof rows — typed fallbacks there are a contradiction, not a pass.

Legacy artifacts produced before T5.1 carry no manifest; that is recorded as
absence, not fabricated evidence.
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


def load_artifact_lineage(
    output_dir: Path | str,
    response: Mapping[str, Any] | None,
) -> tuple[Mapping[str, Any] | None, str]:
    """Return ``(manifest, provenance)`` for the assessed output directory.

    Provenance is ``"sidecar"``, ``"envelope"``, or ``"absent"``. The sidecar
    (written by the headless service / comparison lane, optionally carrying the
    harness ``binding`` block) wins over the envelope copy because it is the
    one the harness bound scenario identity into.
    """
    sidecar_path = Path(output_dir) / _LINEAGE_SIDECAR_NAME
    if sidecar_path.is_file():
        try:
            loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = None
        if isinstance(loaded, Mapping):
            return loaded, "sidecar"
    if isinstance(response, Mapping):
        report = response.get("report")
        if isinstance(report, Mapping):
            executor = report.get("executor")
            if isinstance(executor, Mapping):
                manifest = executor.get("artifact_lineage")
                if isinstance(manifest, Mapping):
                    return manifest, "envelope"
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
    if manifest is None:
        # Legacy artifacts predate T5.1; absence is recorded, never guessed.
        return result

    ok, error = validate_artifact_lineage(manifest)
    if not ok:
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
    return result


__all__ = ["assess_artifact_lineage", "load_artifact_lineage"]
