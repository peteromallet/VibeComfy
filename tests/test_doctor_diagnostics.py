"""Snapshot tests for readability diagnostic stability (T5).

Pins diagnostic code names, severities, and the JSON field set via a snapshot
over a representative template (z_image.py) plus a synthetic fixture that
triggers each of the 5 first-wave codes.  Asserts text/JSON consistency and
that the ``known_codes`` catalog is present — the stability contract before
any future CI promotion.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.diagnostics.readability import (
    ReadabilityDiagnostic,
    ReadabilityReport,
    run_readability_checks,
    run_readability_checks_for_file,
    _KNOWN_CODES,
)
from vibecomfy.commands.doctor import (
    _format_readability_text,
    _render_readability_from_payload,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]

# The five code names that must always appear in known_codes.
ALL_FIVE_CODES = frozenset(_KNOWN_CODES)

# Severity value that every first-wave check emits.
SEVERITY_WARNING = "warning"

# ---------------------------------------------------------------------------
# Synthetic fixture source that triggers all 5 first-wave diagnostic codes
# ---------------------------------------------------------------------------

_FULL_FIXTURE_SOURCE = """\
# Synthetic source that triggers all 5 readability diagnostic codes.
from vibecomfy.templates import (
    ModelAsset,
    OutputSpec,
    ReadyMetadata,
    new_workflow,
    node as raw_call,
)
from vibecomfy.nodes.core import CheckpointLoaderSimple, CLIPTextEncode, EmptyLatentImage, KSampler, SaveImage, VAEDecode, VAELoader

# (1) model_filename_not_declared — defined but not in MODELS dict
UNDECLARED_MODEL = "undisclosed.safetensors"

# MODELS dict does NOT include undisclosed.safetensors
MODELS = {
    "vae": ModelAsset(url="https://example.test/vae.safetensors", subdir="vae"),
}

OUTPUT_SPEC = OutputSpec(name="image", artifact_kind="image", mime_type="image/png")

READY_METADATA = ReadyMetadata.build(
    capability="text_to_image",
    models=MODELS,
)

# (5) generated_template_has_local_node_helper — extra function def
def my_local_helper(x):
    return x * 2

def build():
    with new_workflow(READY_METADATA) as wf:
        loader = CheckpointLoaderSimple(ckpt_name="stable.safetensors")
        latent = EmptyLatentImage(width=512, height=512)

        # (3) uuid_class_type_in_ready_template — UUID as class_type
        uuid_node = raw_call(
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "99",
            widget_0="hello",
        )

        # (2) schema_backed_widget_alias_not_resolved — positional widget inputs
        another = raw_call("SomeNode", "100", widget_1="value")

        positive = CLIPTextEncode(text="prompt", clip=loader)
        negative = CLIPTextEncode(text="", clip=loader)
        ksampler = KSampler(
            seed=42,
            steps=20,
            cfg=7.0,
            sampler_name="euler",
            latent_image=latent,
            model=loader,
            negative=negative,
            positive=positive,
        )
        decoded = VAEDecode(samples=ksampler, vae=VAELoader(vae_name="vae.safetensors"))
        output_img = SaveImage(filename_prefix="out", images=decoded)

        # (4) avoidable_positional_output — no output_node= kwarg
        wf.finalize({})
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_code_names(report: ReadabilityReport) -> set[str]:
    """Return every distinct diagnostic code name in the report."""
    codes: set[str] = set()
    for sc in report.subchecks:
        for f in sc.findings:
            codes.add(f.code)
    return codes


def _collect_code_names_from_text(text: str) -> set[str]:
    """Extract code names from the formatted text output."""
    codes: set[str] = set()
    # Lines look like: "- warning: code_name node=... field=...: message"
    for line in text.splitlines():
        m = re.match(r"-\s+(?:warning|error):\s+(\S+)", line)
        if m:
            codes.add(m.group(1))
    return codes


def _collect_code_names_from_payload_json(
    payload: dict[str, Any],
) -> set[str]:
    """Extract code names from a doctor/port JSON payload's readability block."""
    readability = payload.get("readability")
    if not isinstance(readability, dict):
        return set()
    codes: set[str] = set()
    for sc in readability.get("subchecks") or []:
        for f in sc.get("findings") or []:
            code = f.get("code")
            if code:
                codes.add(code)
    return codes


def _findings_by_code(
    report: ReadabilityReport,
) -> dict[str, list[ReadabilityDiagnostic]]:
    """Return findings grouped by code name."""
    out: dict[str, list[ReadabilityDiagnostic]] = {}
    for sc in report.subchecks:
        for f in sc.findings:
            out.setdefault(f.code, []).append(f)
    return out


# ---------------------------------------------------------------------------
# Snapshot: representative template (z_image.py)
# ---------------------------------------------------------------------------


def test_z_image_snapshot_diagnostic_shape():
    """Pin diagnostic code names, severities, and JSON field set for z_image.py.

    This is the primary stability contract — if the emitter or readability
    checks change such that the shape of findings against this representative
    template shifts, this test must be updated intentionally.
    """
    report = run_readability_checks_for_file(
        REPO_ROOT / "ready_templates" / "image" / "z_image.py"
    )

    # -- known_codes catalog is present and complete -------------------------
    assert list(report.known_codes) == list(_KNOWN_CODES), (
        f"known_codes drift: {report.known_codes} vs {_KNOWN_CODES}"
    )

    findings_map = _findings_by_code(report)

    # -- z_image.py triggers these 3 codes -----------------------------------
    # z_image's finalize call lacks an explicit output_node= kwarg, so
    # avoidable_positional_output fires. schema_backed_widget_alias_not_resolved
    # fires on widget_0/widget_1 patterns. generated_template_has_local_node_helper
    # fires on the _node() helper in the subgraph function.
    # uuid_class_type_in_ready_template and model_filename_not_declared are clean.
    triggered_codes = set(findings_map.keys())
    assert "avoidable_positional_output" in triggered_codes, (
        f"avoidable_positional_output should trigger on z_image; got {triggered_codes}"
    )
    assert "schema_backed_widget_alias_not_resolved" in triggered_codes, (
        f"Expected schema_backed_widget_alias_not_resolved; got {triggered_codes}"
    )
    assert "generated_template_has_local_node_helper" in triggered_codes, (
        f"Expected generated_template_has_local_node_helper; got {triggered_codes}"
    )

    # -- schema_backed_widget_alias_not_resolved ------------------------------
    widgets = findings_map["schema_backed_widget_alias_not_resolved"]
    assert len(widgets) == 2, f"z_image has widget_0 and widget_1; got {len(widgets)}"
    for wf in widgets:
        assert wf.severity == SEVERITY_WARNING
        assert wf.field in ("widget_0", "widget_1")
        assert wf.node_id is None
        j = wf.to_json()
        assert "field" in j
        assert "node_id" not in j

    # -- avoidable_positional_output -----------------------------------------
    apo = findings_map["avoidable_positional_output"]
    assert len(apo) == 1, f"z_image finalize misses output_node=; got {len(apo)}"
    a = apo[0]
    assert a.severity == SEVERITY_WARNING
    assert a.field == "output_node"
    assert a.node_id is None
    aj = a.to_json()
    assert aj["field"] == "output_node"
    assert "node_id" not in aj  # None → omitted

    # -- generated_template_has_local_node_helper -----------------------------
    helpers = findings_map["generated_template_has_local_node_helper"]
    assert len(helpers) == 1
    h = helpers[0]
    assert h.severity == SEVERITY_WARNING
    assert h.node_id == "text_to_image_z_image_base"
    assert h.field is None

    j = h.to_json()
    assert j["node_id"] == "text_to_image_z_image_base"
    assert "field" not in j  # None → omitted
    # next_action is None for this code → omitted
    assert "next_action" not in j

    # -- deterministic ordering: subchecks in definition order (matches _KNOWN_CODES)
    subcheck_names = [sc.name for sc in report.subchecks]
    assert subcheck_names == list(_KNOWN_CODES), (
        f"subchecks not in definition order: {subcheck_names} vs {list(_KNOWN_CODES)}"
    )

    # -- text / JSON consistency ---------------------------------------------
    text = _format_readability_text(report)
    json_payload = report.to_json()
    text_codes = _collect_code_names_from_text(text)
    json_codes = _collect_code_names_from_payload_json({"readability": json_payload})
    assert text_codes == json_codes, (
        f"text codes {text_codes} != JSON codes {json_codes}"
    )


# ---------------------------------------------------------------------------
# Synthetic fixture: triggers all 5 codes
# ---------------------------------------------------------------------------


def test_synthetic_fixture_triggers_all_five_codes():
    """A synthetic source that triggers every first-wave diagnostic code.

    This is the canary — if any check regresses to the point where its
    pattern never fires, this test catches it.
    """
    report = run_readability_checks(_FULL_FIXTURE_SOURCE, workflow_id="synthetic")

    # -- known_codes catalog is present --------------------------------------
    assert list(report.known_codes) == list(_KNOWN_CODES)

    triggered = _collect_code_names(report)
    expected = ALL_FIVE_CODES

    missing = expected - triggered
    assert not missing, (
        f"Synthetic fixture missed {len(missing)} code(s): {missing}. "
        f"Triggered: {triggered}"
    )

    # -- every finding is severity "warning" ---------------------------------
    for sc in report.subchecks:
        for f in sc.findings:
            assert f.severity == SEVERITY_WARNING, (
                f"Unexpected severity {f.severity!r} for code {f.code}"
            )

    # -- text / JSON consistency ---------------------------------------------
    text = _format_readability_text(report)
    json_payload = report.to_json()
    text_codes = _collect_code_names_from_text(text)
    json_codes = _collect_code_names_from_payload_json({"readability": json_payload})
    assert text_codes == json_codes, (
        f"text codes {text_codes} != JSON codes {json_codes}"
    )

    # -- each code produces at least the fields the schema promises -----------
    for sc in report.subchecks:
        for f in sc.findings:
            j = f.to_json()
            assert j["severity"] == SEVERITY_WARNING
            assert j["code"] == sc.name  # code matches subcheck name
            assert isinstance(j["message"], str) and j["message"], (
                f"Empty message for {f.code}"
            )
            # node_id and field are optional; verify they're present when set
            if f.node_id is not None:
                assert j["node_id"] == f.node_id
            else:
                assert "node_id" not in j
            if f.field is not None:
                assert j["field"] == f.field
            else:
                assert "field" not in j
            if f.next_action is not None:
                assert j["next_action"] == f.next_action
            else:
                assert "next_action" not in j

    # -- report-level ok is False because all codes triggered findings --------
    assert report.ok is False

    # -- verify specific counts ----------------------------------------------
    findings_map = _findings_by_code(report)

    # model_filename_not_declared: UNDECLARED_MODEL not in MODELS
    assert len(findings_map["model_filename_not_declared"]) == 1
    assert findings_map["model_filename_not_declared"][0].field == "undisclosed.safetensors"

    # avoidable_positional_output: wf.finalize({}) without output_node=
    assert len(findings_map["avoidable_positional_output"]) == 1

    # uuid_class_type_in_ready_template: one raw_call with UUID
    assert len(findings_map["uuid_class_type_in_ready_template"]) == 1
    assert findings_map["uuid_class_type_in_ready_template"][0].node_id is not None

    # schema_backed_widget_alias_not_resolved: widget_0 and widget_1
    assert len(findings_map["schema_backed_widget_alias_not_resolved"]) == 2

    # generated_template_has_local_node_helper: my_local_helper
    assert len(findings_map["generated_template_has_local_node_helper"]) == 1
    assert findings_map["generated_template_has_local_node_helper"][0].node_id == "my_local_helper"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_clean_template_has_empty_findings_but_known_codes_present():
    """A minimal correct template should have zero findings but still expose known_codes."""
    clean_source = """\
from vibecomfy.templates import ModelAsset, OutputSpec, ReadyMetadata, new_workflow
from vibecomfy.nodes.core import CheckpointLoaderSimple, EmptyLatentImage, SaveImage, KSampler

ckpt = "stable.safetensors"
MODELS = {"ckpt": ModelAsset(url="https://example.test/stable.safetensors", subdir="checkpoints")}
OUTPUT_SPEC = OutputSpec(name="image", artifact_kind="image", mime_type="image/png")
READY_METADATA = ReadyMetadata.build(capability="text_to_image", models=MODELS)

def build():
    with new_workflow(READY_METADATA) as wf:
        loader = CheckpointLoaderSimple(ckpt_name=ckpt)
        latent = EmptyLatentImage(width=512, height=512)
        ksampler = KSampler(seed=42, steps=20, cfg=7.0, sampler_name="euler", latent_image=latent, model=loader, negative=loader, positive=loader)
        output_img = SaveImage(filename_prefix="out", images=ksampler)
        wf.finalize({}, output_node=output_img)
"""
    report = run_readability_checks(clean_source, workflow_id="clean")

    # known_codes must be present even when all findings are empty
    assert list(report.known_codes) == list(_KNOWN_CODES)

    # All subchecks should be ok
    assert report.ok is True

    total_findings = sum(len(sc.findings) for sc in report.subchecks)
    assert total_findings == 0, f"Expected 0 findings on clean template, got {total_findings}"

    # Text output should say ok
    text = _format_readability_text(report)
    assert "Readability: ok" in text
    assert "finding" not in text.lower().replace("ok (no findings)", "")

    # JSON payload still has all 5 known_codes
    json_payload = report.to_json()
    assert json_payload["known_codes"] == list(_KNOWN_CODES)
    assert json_payload["ok"] is True
    for sc in json_payload["subchecks"]:
        assert sc["ok"] is True
        assert sc["findings"] == []


def test_readability_report_json_roundtrip_deterministic():
    """Running the same source twice produces byte-identical JSON."""
    report1 = run_readability_checks(_FULL_FIXTURE_SOURCE, workflow_id="synthetic")
    report2 = run_readability_checks(_FULL_FIXTURE_SOURCE, workflow_id="synthetic")

    json1 = json.dumps(report1.to_json(), sort_keys=True)
    json2 = json.dumps(report2.to_json(), sort_keys=True)
    assert json1 == json2, "ReadabilityReport JSON must be deterministic across runs"


def test_render_readability_from_payload_parity():
    """_render_readability_from_payload produces the same codes as the direct report."""
    report = run_readability_checks(_FULL_FIXTURE_SOURCE, workflow_id="synthetic")
    payload = {"readability": report.to_json()}
    payload_text = _render_readability_from_payload(payload)

    direct_text = _format_readability_text(report)

    # Both should mention the same codes
    payload_codes = _collect_code_names_from_text(payload_text)
    direct_codes = _collect_code_names_from_text(direct_text)
    assert payload_codes == direct_codes, (
        f"Payload-text codes {payload_codes} != direct-text codes {direct_codes}"
    )


def test_syntax_error_source_returns_empty_diagnostics():
    """A source that cannot be parsed should return zero findings gracefully."""
    report = run_readability_checks("this is not valid python @@@", workflow_id="broken")
    assert report.ok is True
    total = sum(len(sc.findings) for sc in report.subchecks)
    assert total == 0, f"Syntax-error source should yield 0 findings, got {total}"
    assert list(report.known_codes) == list(_KNOWN_CODES)
