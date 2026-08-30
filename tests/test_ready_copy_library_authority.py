from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import vibecomfy.commands.copy_to_recipe as copy_cmd
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.commands.copy_to_recipe import _cmd_copy_to_recipe
from vibecomfy.registry import ready
from vibecomfy.registry.library import workflow_from_id


def _write_template(path: Path, marker: str = "ENUMERATED") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# {marker}\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "def build():\n"
        "    return VibeWorkflow('alias', WorkflowSource('alias'))\n",
        encoding="utf-8",
    )


def _write_api(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"1": {"class_type": "CLIPTextEncode", "inputs": {"text": text}}}),
        encoding="utf-8",
    )


def _use_roots(monkeypatch: pytest.MonkeyPatch, roots: list[Path]) -> None:
    monkeypatch.setattr(ready, "_ready_roots", lambda: roots)
    monkeypatch.setattr(ready, "_dynamic_ready_roots", lambda: roots)


def _install_copy_discovery(monkeypatch: pytest.MonkeyPatch, roots: list[Path]) -> None:
    snapshot = ready._discover_ready_templates(roots=roots)
    monkeypatch.setattr(
        copy_cmd,
        "repo_ready_template_discovery",
        lambda root=None, _snapshot=snapshot: _snapshot,
    )


def _copy_args(template_id: str, out: Path) -> argparse.Namespace:
    return argparse.Namespace(
        id=template_id,
        out=str(out),
        strip_markers=False,
        with_runner=False,
    )


def test_copy_alias_resolves_enumerated_not_cwd_or_suffix_decoy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_root = tmp_path / "ready_templates"
    enumerated = ready_root / "image" / "Foo.py"
    _write_template(enumerated, "ENUMERATED")
    decoy = tmp_path / "IMAGE" / "FOO.py"
    _write_template(decoy, "DECOY")
    monkeypatch.chdir(tmp_path)
    _install_copy_discovery(monkeypatch, [ready_root])

    for query in ("IMAGE/FOO", r"image\Foo", "image/Foo"):
        assert copy_cmd._resolve_template_path(query) == enumerated

    out = tmp_path / "out.py"
    assert _cmd_copy_to_recipe(_copy_args("IMAGE/FOO", out)) == 0
    text = out.read_text(encoding="utf-8")
    assert "# ENUMERATED" in text
    assert "# DECOY" not in text

    out_slash = tmp_path / "out_slash.py"
    assert _cmd_copy_to_recipe(_copy_args(r"image\Foo", out_slash)) == 0
    assert "# ENUMERATED" in out_slash.read_text(encoding="utf-8")


def test_copy_exact_ids_win_and_folded_collision_is_order_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upper = tmp_path / "upper" / "image" / "Foo.py"
    lower = tmp_path / "lower" / "image" / "foo.py"
    _write_template(upper, "UPPER")
    _write_template(lower, "LOWER")
    first_roots = [upper.parents[1], lower.parents[1]]
    second_roots = [lower.parents[1], upper.parents[1]]

    _install_copy_discovery(monkeypatch, first_roots)
    assert copy_cmd._resolve_template_path("image/Foo") == upper
    assert copy_cmd._resolve_template_path("image/foo") == lower
    with pytest.raises(ValueError, match="Ambiguous ready template id") as first:
        copy_cmd._resolve_template_path("IMAGE/FOO")
    with pytest.raises(ValueError):
        copy_cmd._resolve_template_path(r"image\FOO")

    _install_copy_discovery(monkeypatch, second_roots)
    assert copy_cmd._resolve_template_path("image/Foo") == upper
    assert copy_cmd._resolve_template_path("image/foo") == lower
    with pytest.raises(ValueError) as second:
        copy_cmd._resolve_template_path("IMAGE/FOO")
    assert str(first.value) == str(second.value)
    assert str(upper) in str(first.value) and str(lower) in str(first.value)


def test_copy_direct_filesystem_path_does_not_impersonate_ready_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready_root = tmp_path / "ready_templates"
    ready_root.mkdir()
    direct = tmp_path / "hand_edit.py"
    _write_template(direct, "DIRECT")
    decoy = tmp_path / "IMAGE" / "FOO.py"
    _write_template(decoy, "DECOY")
    monkeypatch.chdir(tmp_path)
    _install_copy_discovery(monkeypatch, [ready_root])

    assert copy_cmd._resolve_template_path(str(direct)) == direct
    assert copy_cmd._resolve_template_path("IMAGE/FOO") is None
    out = tmp_path / "copied.py"
    assert _cmd_copy_to_recipe(_copy_args(str(direct), out)) == 0
    assert "# DIRECT" in out.read_text(encoding="utf-8")


def test_library_ready_backslash_alias_does_not_fall_through_to_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "Foo.py"
    _write_template(candidate)
    _use_roots(monkeypatch, [candidate.parents[1]])
    monkeypatch.chdir(tmp_path)
    decoy = tmp_path / "decoy.json"
    _write_api(decoy, "corpus-decoy")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "image/Foo", "path": str(decoy)}]),
        encoding="utf-8",
    )
    workflow = workflow_from_id(r"IMAGE\FOO")
    assert workflow.metadata["ready_template"] == "image/Foo"


def test_library_duplicate_corpus_ids_refuse_order_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_roots(monkeypatch, [tmp_path / "ready"])
    monkeypatch.chdir(tmp_path)
    one = tmp_path / "one.json"
    two = tmp_path / "two.json"
    _write_api(one, "one")
    _write_api(two, "two")
    rows = [{"id": "dup", "path": str(one)}, {"id": "dup", "path": str(two)}]
    (tmp_path / "workflow_index.json").write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="Ambiguous workflow id 'dup'") as first:
        workflow_from_id("dup")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps(list(reversed(rows))), encoding="utf-8"
    )
    with pytest.raises(ValueError) as second:
        workflow_from_id("dup")
    assert str(first.value) == str(second.value)
    assert str(one) in str(first.value) and str(two) in str(first.value)


def test_library_exact_id_precedes_stem_and_folded_case_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_roots(monkeypatch, [tmp_path / "ready"])
    monkeypatch.chdir(tmp_path)
    from_id = tmp_path / "from_id.json"
    from_stem = tmp_path / "keep.json"
    lower = tmp_path / "lower.json"
    upper = tmp_path / "upper.json"
    _write_api(from_id, "from-id")
    _write_api(from_stem, "from-stem")
    _write_api(lower, "lower")
    _write_api(upper, "upper")

    (tmp_path / "workflow_index.json").write_text(
        json.dumps(
            [
                {"id": "other", "path": str(from_stem)},
                {"id": "keep", "path": str(from_id)},
            ]
        ),
        encoding="utf-8",
    )
    assert workflow_from_id("keep").nodes["1"].inputs["text"] == "from-id"
    assert workflow_from_id("KEEP").nodes["1"].inputs["text"] == "from-id"

    (tmp_path / "workflow_index.json").write_text(
        json.dumps(
            [
                {"id": "keep", "path": str(from_id)},
                {"id": "other", "path": str(from_stem)},
            ]
        ),
        encoding="utf-8",
    )
    assert workflow_from_id("keep").nodes["1"].inputs["text"] == "from-id"

    (tmp_path / "workflow_index.json").write_text(
        json.dumps(
            [
                {"id": "dup", "path": str(lower)},
                {"id": "DUP", "path": str(upper)},
            ]
        ),
        encoding="utf-8",
    )
    assert workflow_from_id("dup").nodes["1"].inputs["text"] == "lower"
    assert workflow_from_id("DUP").nodes["1"].inputs["text"] == "upper"
    with pytest.raises(ValueError, match="Ambiguous workflow id 'Dup'"):
        workflow_from_id("Dup")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps(
            [
                {"id": "DUP", "path": str(upper)},
                {"id": "dup", "path": str(lower)},
            ]
        ),
        encoding="utf-8",
    )
    assert workflow_from_id("dup").nodes["1"].inputs["text"] == "lower"
    assert workflow_from_id("DUP").nodes["1"].inputs["text"] == "upper"


def test_library_backslash_case_alias_and_duplicate_stems(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _use_roots(monkeypatch, [tmp_path / "ready"])
    monkeypatch.chdir(tmp_path)
    payload = tmp_path / "foo.json"
    _write_api(payload, "corpus")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps([{"id": "image/foo", "path": str(payload)}]),
        encoding="utf-8",
    )
    assert workflow_from_id(r"IMAGE\FOO").nodes["1"].inputs["text"] == "corpus"
    assert workflow_from_id("IMAGE/FOO").nodes["1"].inputs["text"] == "corpus"

    one = tmp_path / "a" / "same.json"
    two = tmp_path / "b" / "same.json"
    _write_api(one, "a")
    _write_api(two, "b")
    rows = [{"id": "one", "path": str(one)}, {"id": "two", "path": str(two)}]
    (tmp_path / "workflow_index.json").write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="Ambiguous workflow id 'same'") as first:
        workflow_from_id("same")
    (tmp_path / "workflow_index.json").write_text(
        json.dumps(list(reversed(rows))), encoding="utf-8"
    )
    with pytest.raises(ValueError) as second:
        workflow_from_id("same")
    assert str(first.value) == str(second.value)


def test_load_workflow_any_reuses_one_discovery_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "Foo.py"
    _write_template(candidate)
    _use_roots(monkeypatch, [candidate.parents[1]])
    calls = {"n": 0}
    original = ready._discover_ready_templates

    def wrapped(*args: object, **kwargs: object):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(ready, "_discover_ready_templates", wrapped)
    assert load_workflow_any("IMAGE/FOO").metadata["ready_template"] == "image/Foo"
    assert calls["n"] == 1
    assert load_workflow_any(r"image\Foo").metadata["ready_template"] == "image/Foo"
    assert calls["n"] == 2
