from __future__ import annotations

import ast
from pathlib import Path

from vibecomfy._widget_aliases import (
    COMPILE_WIDGET_ALIAS_CLASS_TYPES,
    WIDGET_SCHEMA,
    apply_positional_widget_aliases,
    resolve_widget_key_with_provenance,
)
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


ROOT = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_workflow_imports_ir_neutral_widget_aliases_not_porting() -> None:
    source = (ROOT / "vibecomfy" / "workflow.py").read_text()
    imports = _imports(ROOT / "vibecomfy" / "workflow.py")

    assert "vibecomfy.porting.widget_aliases" not in imports
    assert "from vibecomfy import _widget_aliases as widget_aliases" in source


def test_ir_neutral_widget_aliases_do_not_import_porting_or_object_info() -> None:
    imports = _imports(ROOT / "vibecomfy" / "_widget_aliases.py")

    assert not any(name.startswith("vibecomfy.porting") for name in imports)


def test_compile_widget_alias_classes_have_committed_static_coverage() -> None:
    missing = sorted(COMPILE_WIDGET_ALIAS_CLASS_TYPES.difference(WIDGET_SCHEMA))

    assert missing == []


def test_compile_alias_precedence_keeps_named_inputs_over_widget_aliases() -> None:
    wf = VibeWorkflow(id="aliases", source=WorkflowSource(id="aliases"))
    wf.nodes["1"] = VibeNode(
        id="1",
        class_type="LoadImage",
        inputs={"image": "named wins"},
        widgets={"widget_0": "widget loses"},
    )

    api = wf.compile("api")

    assert api["1"]["inputs"] == {"image": "named wins"}


def test_ir_neutral_resolution_never_uses_object_info_fallback() -> None:
    resolved = resolve_widget_key_with_provenance("ObjectInfoOnlyClass", "widget_0")

    assert resolved.resolved is False
    assert resolved.source == "unresolved"


def test_compile_alias_applies_input_aliases_before_static_schema() -> None:
    inputs = {"widget_0": "custom"}

    apply_positional_widget_aliases(
        inputs,
        "CLIPTextEncode",
        input_aliases=("custom_text",),
    )

    assert inputs == {"custom_text": "custom"}


def test_exec_widget_aliases_map_source_and_io_without_positional_drift() -> None:
    wf = VibeWorkflow(id="exec-aliases", source=WorkflowSource(id="exec-aliases"))
    wf.nodes["1"] = VibeNode(
        id="1",
        class_type="vibecomfy.exec",
        inputs={"widget_0": "return {'result': value}", "widget_1": {"outputs": [["result", "INT"]]}},
    )

    api = wf.compile("api")

    assert api["1"]["inputs"] == {
        "source": "return {'result': value}",
        "io": {"outputs": [["result", "INT"]]},
    }
