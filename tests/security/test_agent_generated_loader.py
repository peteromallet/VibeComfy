from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    load_agent_generated_scratchpad,
    scan_agent_generated_python,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context
from vibecomfy.security.provenance import PROVENANCE_KEY

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "agent_generated_loader"


@pytest.fixture(autouse=True)
def _headless_gate_context():
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        _gate_context_var.reset(token)


def _benign_generated_source() -> str:
    return """
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def build() -> VibeWorkflow:
    wf = VibeWorkflow(
        "agent-generated",
        WorkflowSource(id="agent-generated", path=__file__, source_type="scratchpad"),
    )
    wf.node("SaveImage", filename_prefix="agent-generated")
    wf.finalize_metadata()
    return wf
"""


def _write(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def _fixture_source(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _materialize_fixture(
    tmp_path: Path,
    name: str,
    *,
    replacements: dict[str, str] | None = None,
) -> Path:
    source = _fixture_source(name)
    for old, new in (replacements or {}).items():
        source = source.replace(old, new)
    return _write(tmp_path / name, source)


def test_scan_accepts_current_generated_template_subset() -> None:
    report = scan_agent_generated_python(_benign_generated_source())

    assert report.ok
    assert report.failures == ()


def test_load_scans_before_exec_and_mints_agent_generated(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    path = _write(tmp_path / "generated.py", _benign_generated_source())

    workflow = load_agent_generated_scratchpad(path)

    assert workflow.id == "agent-generated"
    assert workflow.nodes["1"].metadata[PROVENANCE_KEY] == "agent_generated"
    scratchpad_exec = [
        entry
        for entry in _headless_gate_context.audit
        if entry["operation"] == "scratchpad_exec"
    ]
    assert scratchpad_exec == [
        {
            "decision": "allow",
            "operation": "scratchpad_exec",
            "class_type": None,
            "provenance": "agent_generated",
            "capabilities": ["code_exec"],
            "reason": "trusted_provenance",
            "details": {"path": str(path), "loader": "agent_generated"},
        }
    ]


def test_malformed_syntax_is_load_python_failure() -> None:
    report = scan_agent_generated_python("def build(:\n    pass\n")

    assert not report.ok
    assert report.failures[0].phase == "load_python"
    assert report.failures[0].code == "syntax_error"


def test_oversized_source_is_load_python_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vibecomfy.security.agent_generated_loader.MAX_AGENT_GENERATED_SOURCE_BYTES",
        128,
    )

    report = scan_agent_generated_python(_fixture_source("huge_payload.py"))

    assert not report.ok
    assert report.failures[0].phase == "load_python"
    assert report.failures[0].code == "source_too_large"


def test_malformed_fixture_is_load_python_failure() -> None:
    report = scan_agent_generated_python(_fixture_source("malformed_syntax.txt"))

    assert not report.ok
    assert report.failures[0].phase == "load_python"
    assert report.failures[0].code == "syntax_error"


def test_module_side_effect_canary_is_rejected_before_exec(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    marker = tmp_path / "should_not_exist.txt"
    path = _materialize_fixture(
        tmp_path,
        "module_side_effect_canary.py",
        replacements={"__CANARY_PATH__": str(marker)},
    )

    with pytest.raises(AgentGeneratedLoadError) as exc_info:
        load_agent_generated_scratchpad(path)

    report = exc_info.value.report
    assert not report.ok
    assert {failure.phase for failure in report.failures} == {"load_python"}
    assert "forbidden_call" in {failure.code for failure in report.failures}
    assert not marker.exists()
    assert _headless_gate_context.audit == []


@pytest.mark.parametrize(
    "fixture_name,expected_codes",
    [
        ("command_execution.py", {"forbidden_call"}),
        ("hidden_import.py", {"forbidden_import"}),
        ("encoded_import_trick.py", {"forbidden_call", "forbidden_name"}),
        ("dunder_traversal.py", {"dunder_access"}),
        ("file_read.py", {"forbidden_call"}),
        ("network_call.py", {"forbidden_import"}),
        ("socket_call.py", {"forbidden_import"}),
        ("subprocess_call.py", {"forbidden_import"}),
        ("env_read.py", {"forbidden_import"}),
        ("dynamic_attribute_access.py", {"forbidden_call"}),
    ],
)
def test_hostile_fixture_scan_rejects_bypass_classes(
    fixture_name: str,
    expected_codes: set[str],
) -> None:
    report = scan_agent_generated_python(_fixture_source(fixture_name))

    assert not report.ok
    assert {failure.phase for failure in report.failures} == {"load_python"}
    assert expected_codes <= {failure.code for failure in report.failures}
