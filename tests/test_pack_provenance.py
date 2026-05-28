from __future__ import annotations

from pathlib import Path

from tools import check_pack_provenance as provenance
from vibecomfy.node_packs_lockfile import LockEntry


def _template(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "template.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_extract_node_class_uses_covers_supported_call_shapes() -> None:
    uses = provenance.extract_node_class_uses(
        """
def build():
    node(wf, "ClassA", "1")
    wf.node("ClassB", "2")
    _node(wf, "ClassC", "3")
    wf.node(class_type="ClassD", node_id="4")
"""
    )

    assert [(use.class_type, use.node_id, use.call) for use in uses] == [
        ("ClassA", "1", "node"),
        ("ClassB", "2", "node"),
        ("ClassC", "3", "_node"),
        ("ClassD", "4", "node"),
    ]


def test_declared_structured_ref_satisfies_locked_class_set(tmp_path: Path) -> None:
    path = _template(
        tmp_path,
        """
READY_REQUIREMENTS = {
    "models": [],
    "custom_nodes": ["ExamplePack"],
    "custom_node_refs": [{"slug": "ExamplePack", "source": "git", "commit": "abc"}],
}
def build():
    node(wf, "ExampleNode", "1")
""",
    )
    entry = LockEntry("ExamplePack", commit="abc", class_set=("ExampleNode",))

    diagnostics = provenance.diagnostics_for_template(
        ready_id="image/example",
        path=path,
        marker="generated",
        strict_ready_protected=True,
        lock_entries=[entry],
    )

    assert diagnostics == []


def test_missing_declared_ref_for_locked_class_fails(tmp_path: Path) -> None:
    path = _template(
        tmp_path,
        """
READY_REQUIREMENTS = {"models": [], "custom_nodes": ["ExamplePack"]}
def build():
    node(wf, "ExampleNode", "1")
""",
    )
    entry = LockEntry("ExamplePack", class_set=("ExampleNode",))

    diagnostics = provenance.diagnostics_for_template(
        ready_id="image/example",
        path=path,
        marker="generated",
        strict_ready_protected=True,
        lock_entries=[entry],
    )

    assert [item["code"] for item in diagnostics] == ["pack_provenance_missing_declared_ref"]
    assert diagnostics[0]["detail"]["class_type"] == "ExampleNode"


def test_known_pack_missing_from_lock_is_reported(monkeypatch, tmp_path: Path) -> None:
    path = _template(
        tmp_path,
        """
READY_REQUIREMENTS = {"models": [], "custom_nodes": ["StaticPack"]}
def build():
    _node(wf, "StaticNode", "1")
""",
    )
    monkeypatch.setattr(
        provenance,
        "get_known_node_packs",
        lambda: (
            type("Pack", (), {"name": "StaticPack", "classes": frozenset({"StaticNode"})})(),
        ),
    )

    diagnostics = provenance.diagnostics_for_template(
        ready_id="image/example",
        path=path,
        marker="generated",
        strict_ready_protected=True,
        lock_entries=[],
    )

    assert [item["code"] for item in diagnostics] == ["pack_provenance_pack_missing_from_lock"]
    assert diagnostics[0]["detail"]["pack"] == "StaticPack"


def test_cli_report_only_exits_zero_when_issues_exist(monkeypatch, tmp_path: Path, capsys) -> None:
    path = _template(
        tmp_path,
        """
READY_REQUIREMENTS = {"models": [], "custom_nodes": ["ExamplePack"]}
def build():
    node(wf, "ExampleNode", "1")
""",
    )
    monkeypatch.setattr(
        provenance,
        "_select_targets",
        lambda: [provenance.BackfillTarget("image/example", path, "generated", True)],
    )
    monkeypatch.setattr(
        provenance,
        "read_lockfile",
        lambda: [LockEntry("ExamplePack", class_set=("ExampleNode",))],
    )

    exit_code = provenance.main(["--json"])
    payload = capsys.readouterr().out

    assert exit_code == 0
    assert '"pack_provenance_missing_declared_ref"' in payload


def test_cli_strict_exits_nonzero_when_issues_exist(monkeypatch, tmp_path: Path, capsys) -> None:
    path = _template(
        tmp_path,
        """
READY_REQUIREMENTS = {"models": [], "custom_nodes": ["ExamplePack"]}
def build():
    node(wf, "ExampleNode", "1")
""",
    )
    monkeypatch.setattr(
        provenance,
        "_select_targets",
        lambda: [provenance.BackfillTarget("image/example", path, "generated", True)],
    )
    monkeypatch.setattr(
        provenance,
        "read_lockfile",
        lambda: [LockEntry("ExamplePack", class_set=("ExampleNode",))],
    )

    exit_code = provenance.main(["--json", "--strict"])
    capsys.readouterr()

    assert exit_code == 1
