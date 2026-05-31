from __future__ import annotations

from pathlib import Path

import pytest

from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    load_agent_generated_scratchpad,
    scan_agent_generated_python,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context
from vibecomfy.security.provenance import PROVENANCE_KEY, read as read_provenance

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
    "fixture_name,expected_codes,max_bytes",
    [
        ("command_execution.py", {"forbidden_call"}, None),
        ("hidden_import.py", {"forbidden_import"}, None),
        ("encoded_import_trick.py", {"forbidden_call", "forbidden_name"}, None),
        ("dunder_traversal.py", {"dunder_access"}, None),
        ("file_read.py", {"forbidden_call"}, None),
        ("network_call.py", {"forbidden_import"}, None),
        ("socket_call.py", {"forbidden_import"}, None),
        ("subprocess_call.py", {"forbidden_import"}, None),
        ("env_read.py", {"forbidden_import"}, None),
        ("dynamic_attribute_access.py", {"forbidden_call"}, None),
        ("huge_payload.py", {"source_too_large"}, 128),
        ("malformed_syntax.txt", {"syntax_error"}, None),
    ],
)
def test_hostile_fixture_load_rejects_before_exec_and_before_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _headless_gate_context: GateContext,
    fixture_name: str,
    expected_codes: set[str],
    max_bytes: int | None,
) -> None:
    if max_bytes is not None:
        monkeypatch.setattr(
            "vibecomfy.security.agent_generated_loader.MAX_AGENT_GENERATED_SOURCE_BYTES",
            max_bytes,
        )
    path = _materialize_fixture(tmp_path, fixture_name)

    with pytest.raises(AgentGeneratedLoadError) as exc_info:
        load_agent_generated_scratchpad(path)

    report = exc_info.value.report
    assert not report.ok
    assert {failure.phase for failure in report.failures} == {"load_python"}
    assert expected_codes <= {failure.code for failure in report.failures}
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


# ── T5: Benign generated scratchpad fixture + provenance tests ────────────


def test_benign_fixture_scan_passes() -> None:
    """The representative benign fixture passes the AST policy scan."""
    source = _fixture_source("benign_scratchpad.py")
    report = scan_agent_generated_python(source)

    assert report.ok
    assert report.failures == ()


def test_benign_fixture_load_returns_validating_workflow(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Loading the benign fixture produces a VibeWorkflow that validates."""
    path = _materialize_fixture(tmp_path, "benign_scratchpad.py")

    workflow = load_agent_generated_scratchpad(path)

    # Must be a VibeWorkflow with the expected identity.
    assert workflow.id == "agent-scratchpad-fixture"

    # Validation must pass (no error-severity issues).
    report = workflow.validate()
    assert report.ok, f"Validation failed: {[i.message for i in report.issues if i.severity == 'error']}"


def test_benign_fixture_nodes_carry_agent_generated_provenance(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Every node created during agent-generated loading carries agent_generated provenance."""
    path = _materialize_fixture(tmp_path, "benign_scratchpad.py")

    workflow = load_agent_generated_scratchpad(path)

    assert len(workflow.nodes) >= 3, "Expected at least 3 nodes in the fixture"
    for node_id, node in workflow.nodes.items():
        prov = read_provenance(node)
        assert prov == "agent_generated", (
            f"Node {node_id} ({node.class_type}) has provenance {prov!r}, "
            f"expected 'agent_generated'"
        )


def test_confirm_node_does_not_promote_agent_generated(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """VibeWorkflow.confirm_node() must leave agent_generated nodes unchanged."""
    path = _materialize_fixture(tmp_path, "benign_scratchpad.py")

    workflow = load_agent_generated_scratchpad(path)

    # Record provenance before confirmation.
    before = {nid: read_provenance(node) for nid, node in workflow.nodes.items()}
    for nid in before:
        assert before[nid] == "agent_generated"

    # Confirm every node — this should be a no-op for agent_generated.
    for nid in workflow.nodes:
        workflow.confirm_node(nid)

    # After confirmation, every node must still carry agent_generated.
    for nid, node in workflow.nodes.items():
        after = read_provenance(node)
        assert after == "agent_generated", (
            f"confirm_node({nid!r}) promoted {before[nid]!r} → {after!r}; "
            f"agent_generated must remain non-promoted"
        )


def test_benign_fixture_gate_audit_shape(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """The gate audit log shows agent_generated provenance for the scratchpad_exec
    operation and any side-effecting node additions."""
    path = _materialize_fixture(tmp_path, "benign_scratchpad.py")

    _headless_gate_context.audit.clear()
    workflow = load_agent_generated_scratchpad(path)  # noqa: F841

    # The scratchpad_exec gate entry must be present.
    exec_entries = [
        e for e in _headless_gate_context.audit
        if e["operation"] == "scratchpad_exec"
    ]
    assert len(exec_entries) == 1
    assert exec_entries[0]["provenance"] == "agent_generated"
    assert exec_entries[0]["decision"] == "allow"
    assert "code_exec" in exec_entries[0]["capabilities"]

    # Every add_node entry for side-effecting nodes must carry agent_generated.
    add_node_entries = [
        e for e in _headless_gate_context.audit
        if e["operation"] == "add_node"
    ]
    for entry in add_node_entries:
        assert entry["provenance"] == "agent_generated", (
            f"add_node for {entry['class_type']} has provenance "
            f"{entry['provenance']!r}, expected 'agent_generated'"
        )
        assert entry["decision"] == "allow"
