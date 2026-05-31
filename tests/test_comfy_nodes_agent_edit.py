from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vibecomfy.comfy_nodes.agent_edit import handle_agent_edit
from vibecomfy.porting.ui_emitter import emit_ui_json
from vibecomfy.security.agent_generated_loader import (
    AgentGeneratedLoadError,
    load_agent_generated_scratchpad,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context
from vibecomfy.security.provenance import PROVENANCE_KEY, confirm, read as read_provenance
from vibecomfy.schema.provider import NodeSchema, OutputSpec
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


# ── shared helpers ────────────────────────────────────────────────────────


class _Provider:
    def __init__(self, schemas: dict[str, NodeSchema]) -> None:
        self._schemas = schemas

    def get_schema(self, class_type: str) -> NodeSchema | None:
        return self._schemas.get(class_type)


def _schema(class_type: str, outputs: list[OutputSpec] | None = None) -> NodeSchema:
    return NodeSchema(
        class_type=class_type,
        pack=None,
        inputs={},
        outputs=outputs or [],
        source_provider="test",
        confidence=1.0,
    )


def _ui_graph() -> dict:
    wf = VibeWorkflow("agent-edit-test", WorkflowSource("agent-edit-test"))
    wf.nodes["1"] = VibeNode("1", "LoadImage", inputs={"image": "input.png"})
    wf.nodes["2"] = VibeNode("2", "SaveImage", inputs={"filename_prefix": "before"})
    wf.connect("1.0", "2.images")
    return emit_ui_json(
        wf,
        schema_provider=_Provider(
            {"LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")])}
        ),
    )


def _fake_deepseek_replace(
    replace_from: str, replace_to: str, message: str
):
    """Return a deepseek-client callable that mirrors the original Python
    but with one string replacement, matching the existing agent-edit test
    pattern (the model edits one widget value and preserves the rest)."""

    def _fake(messages):
        source = (
            messages[-1]["content"]
            .split("```python\n", 1)[1]
            .rsplit("\n```", 1)[0]
        )
        return {
            "python": source.replace(replace_from, replace_to),
            "message": message,
        }

    return _fake


def _fixture_source(name: str) -> str:
    fixture_dir = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "agent_generated_loader"
    )
    return (fixture_dir / name).read_text(encoding="utf-8")


# ── gate context fixture ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _headless_gate_context() -> GateContext:
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        _gate_context_var.reset(token)


# ── existing T6 regression tests (refactored) ────────────────────────────


def test_handle_agent_edit_round_trips_deepseek_python(tmp_path: Path) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t1",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    assert result["message"] == "Changed the save prefix."
    assert result["session_id"] == "t1"
    assert (
        Path(result["artifacts"]["python"])
        .read_text(encoding="utf-8")
        .count("after")
        >= 1
    )
    assert result["graph"]["nodes"]
    assert result["report"]["change"]


def test_handle_agent_edit_uses_agent_generated_loader(
    tmp_path: Path,
) -> None:
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    with patch(
        "vibecomfy.security.agent_generated_loader.load_agent_generated_scratchpad"
    ) as load_generated:
        generated = VibeWorkflow(
            "agent-edit-generated", WorkflowSource("agent-edit-generated")
        )
        generated.nodes["1"] = VibeNode(
            "1",
            "LoadImage",
            inputs={"image": "input.png"},
            metadata={"provenance": "agent_generated"},
        )
        generated.nodes["2"] = VibeNode(
            "2",
            "SaveImage",
            inputs={"filename_prefix": "after"},
            metadata={"provenance": "agent_generated"},
        )
        generated.connect("1.0", "2.images")
        load_generated.return_value = generated

        result = handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "change the save prefix to after",
                "session_id": "t2",
            },
            schema_provider=provider,
            deepseek_client=_fake_deepseek_replace(
                "before", "after", "Changed the save prefix."
            ),
            session_root=tmp_path,
        )

    load_generated.assert_called_once()
    for node in generated.nodes.values():
        assert node.metadata.get("provenance") == "agent_generated"
        confirm(node)
        assert node.metadata.get("provenance") == "agent_generated"
    assert result["graph"]["nodes"]


def test_handle_agent_edit_requires_task(tmp_path: Path) -> None:
    try:
        handle_agent_edit(
            {"graph": _ui_graph()},
            session_root=tmp_path,
            deepseek_client=lambda _: {},
        )
    except ValueError as exc:
        assert "`task` is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")


# ── T7: focused agent-edit provenance & hostile-rejection tests ──────────


def test_agent_edit_nodes_never_user_confirmed(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Prove that model-edited Python loaded through the agent-edit path
    carries ``agent_generated`` provenance, never ``user_confirmed``.

    Even after ``confirm()`` / ``confirm_node()`` the provenance must remain
    ``agent_generated`` because the restricted loader is the only minter and
    ``confirm`` is a no-op for this literal.
    """
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    result = handle_agent_edit(
        {
            "graph": _ui_graph(),
            "task": "change the save prefix to after",
            "session_id": "t3",
        },
        schema_provider=provider,
        deepseek_client=_fake_deepseek_replace(
            "before", "after", "Changed the save prefix."
        ),
        session_root=tmp_path,
    )

    # The agent-edit round-trip succeeded (no exception).
    assert result["graph"]["nodes"]
    assert result["report"]["change"]

    # Load the model-edited Python back through the restricted loader and
    # inspect provenance directly.
    py_path = Path(result["artifacts"]["python"])
    edited_wf = load_agent_generated_scratchpad(py_path)

    assert len(edited_wf.nodes) >= 2, "Expected at least 2 nodes in model-edited workflow"

    # 1. Every node must carry agent_generated, NOT user_confirmed.
    for node_id, node in edited_wf.nodes.items():
        prov = read_provenance(node)
        assert prov == "agent_generated", (
            f"Node {node_id} ({node.class_type}) has provenance {prov!r}; "
            f"expected 'agent_generated', must NOT be 'user_confirmed'"
        )

    # 2. Free-function confirm() must be a no-op on agent_generated.
    for node_id, node in edited_wf.nodes.items():
        before = read_provenance(node)
        confirm(node)
        after = read_provenance(node)
        assert after == "agent_generated", (
            f"confirm() on node {node_id} changed provenance "
            f"from {before!r} to {after!r}; must remain 'agent_generated'"
        )

    # 3. workflow.confirm_node() must be a no-op on agent_generated.
    for node_id in edited_wf.nodes:
        before = read_provenance(edited_wf.nodes[node_id])
        edited_wf.confirm_node(node_id)
        after = read_provenance(edited_wf.nodes[node_id])
        assert after == "agent_generated", (
            f"confirm_node({node_id!r}) changed provenance "
            f"from {before!r} to {after!r}; must remain 'agent_generated'"
        )

    # 4. Pre-existing test: confirm() called a second time is still a no-op.
    for node in edited_wf.nodes.values():
        confirm(node)
        assert read_provenance(node) == "agent_generated"


def test_agent_edit_rejects_hostile_model_output(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Hostile model output (command execution via ``os.system``) is rejected
    by the AST scanner before execution and before any gate interaction."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    hostile_source = _fixture_source("command_execution.py")

    def hostile_deepseek(_messages):
        return {"python": hostile_source, "message": "done"}

    with pytest.raises(AgentGeneratedLoadError) as exc_info:
        handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "run this hostile code",
                "session_id": "t4",
            },
            schema_provider=provider,
            deepseek_client=hostile_deepseek,
            session_root=tmp_path,
        )

    report = exc_info.value.report
    assert not report.ok
    assert {f.phase for f in report.failures} == {"load_python"}
    assert "forbidden_call" in {f.code for f in report.failures}


def test_agent_edit_rejects_hostile_canary_no_execution(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Hostile model output that writes a canary file at module level is
    rejected before execution — the canary file must not exist."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    canary = tmp_path / "should_not_exist.txt"
    hostile_source = _fixture_source("module_side_effect_canary.py").replace(
        "__CANARY_PATH__", str(canary)
    )

    def hostile_deepseek(_messages):
        return {"python": hostile_source, "message": "executed"}

    with pytest.raises(AgentGeneratedLoadError) as exc_info:
        handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "run this hostile canary code",
                "session_id": "t5",
            },
            schema_provider=provider,
            deepseek_client=hostile_deepseek,
            session_root=tmp_path,
        )

    report = exc_info.value.report
    assert not report.ok
    assert {f.phase for f in report.failures} == {"load_python"}
    assert "forbidden_call" in {f.code for f in report.failures}

    # The hostile module-level side effect must never have executed.
    assert not canary.exists(), (
        f"Canary file {canary} exists — hostile code was executed!"
    )


def test_agent_edit_rejects_multiple_hostile_bypass_classes(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """A representative set of hostile bypass classes is rejected before
    execution through the agent-edit path. Each fixture is fed as model
    output and must produce ``AgentGeneratedLoadError``."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    hostile_fixtures = [
        "file_read.py",
        "hidden_import.py",
        "dunder_traversal.py",
        "encoded_import_trick.py",
        "network_call.py",
        "socket_call.py",
        "subprocess_call.py",
        "env_read.py",
        "dynamic_attribute_access.py",
    ]

    for fixture_name in hostile_fixtures:
        hostile_source = _fixture_source(fixture_name)

        def hostile_deepseek(_messages, _src=hostile_source):
            return {"python": _src, "message": "done"}

        with pytest.raises(AgentGeneratedLoadError) as exc_info:
            handle_agent_edit(
                {
                    "graph": _ui_graph(),
                    "task": "run hostile code",
                    "session_id": f"t-{fixture_name}",
                },
                schema_provider=provider,
                deepseek_client=hostile_deepseek,
                session_root=tmp_path,
            )

        report = exc_info.value.report
        assert not report.ok, f"{fixture_name} passed scan but should have failed"
        assert {f.phase for f in report.failures} == {"load_python"}, (
            f"{fixture_name} failures not in load_python phase"
        )


def test_agent_edit_rejects_malformed_syntax_from_model(
    tmp_path: Path,
    _headless_gate_context: GateContext,
) -> None:
    """Malformed Python syntax from the model is caught in the load_python
    phase and never executed."""
    provider = _Provider(
        {
            "LoadImage": _schema("LoadImage", [OutputSpec("IMAGE", "image")]),
            "SaveImage": _schema("SaveImage"),
        }
    )

    def hostile_deepseek(_messages):
        return {"python": "def build(:\n    pass\n", "message": "syntax error"}

    with pytest.raises(AgentGeneratedLoadError) as exc_info:
        handle_agent_edit(
            {
                "graph": _ui_graph(),
                "task": "return malformed syntax",
                "session_id": "t6",
            },
            schema_provider=provider,
            deepseek_client=hostile_deepseek,
            session_root=tmp_path,
        )

    report = exc_info.value.report
    assert not report.ok
    assert report.failures[0].code == "syntax_error"
    assert report.failures[0].phase == "load_python"
