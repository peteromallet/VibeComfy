from __future__ import annotations

import json
import unicodedata
from pathlib import Path
import pytest

import vibecomfy.commands.workflows as workflows_cmd
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.registry import ready
from vibecomfy.registry.ready import workflow_from_ready


def _write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "def build():\n"
        "    return VibeWorkflow('alias', WorkflowSource('alias'))\n",
        encoding="utf-8",
    )


def _use_roots(monkeypatch: pytest.MonkeyPatch, roots: list[Path]) -> None:
    monkeypatch.setattr(ready, "_ready_roots", lambda: roots)
    monkeypatch.setattr(ready, "_dynamic_ready_roots", lambda: roots)


def test_canonical_ids_preserve_enumerated_case_and_alias_queries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "Foo.py"
    _write_template(candidate)
    nfc_candidate = candidate.parent / (unicodedata.normalize("NFD", "Café") + ".py")
    _write_template(nfc_candidate)
    _use_roots(monkeypatch, [candidate.parents[1]])

    assert ready.ready_template_ids() == ["image/Café", "image/Foo"]
    assert load_workflow_any("IMAGE\\CAFÉ").metadata["ready_template"] == "image/Café"
    assert load_workflow_any("image\\foo").metadata["ready_template"] == "image/Foo"


def test_case_sensitive_distinct_files_keep_exact_ids_and_folded_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upper = tmp_path / "upper" / "image" / "Foo.py"
    lower = tmp_path / "lower" / "image" / "foo.py"
    _write_template(upper)
    _write_template(lower)
    _use_roots(monkeypatch, [upper.parents[1], lower.parents[1]])
    assert ready.ready_template_ids() == ["image/Foo", "image/foo"]
    workflow_from_ready("image/Foo")
    workflow_from_ready("image/foo")
    with pytest.raises(ValueError) as exc_info:
        workflow_from_ready("image/FOO")
    with pytest.raises(ValueError):
        load_workflow_any("image/FOO")
    message = str(exc_info.value)
    assert str(upper) in message and str(lower) in message

    def collision_message(roots: list[Path]) -> str:
        with pytest.raises(ValueError) as collision:
            workflow_from_ready("image/FOO", _discovery=ready._discover_ready_templates(roots=roots))
        return str(collision.value)

    assert collision_message([upper.parents[1], lower.parents[1]]) == collision_message(
        [lower.parents[1], upper.parents[1]]
    )

def test_linux_distinct_case_files_remain_exact_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "ready"
    upper = root / "image" / "Foo.py"
    lower = root / "image" / "foo.py"
    _write_template(upper)
    if lower.exists():
        pytest.skip("filesystem is case-insensitive")
    _write_template(lower)
    _use_roots(monkeypatch, [root])

    assert ready.ready_template_ids() == ["image/Foo", "image/foo"]
    with pytest.raises(ValueError):
        workflow_from_ready("image/FOO")




def test_physical_root_aliases_are_order_independent(tmp_path: Path) -> None:
    root = tmp_path / "ReadyRoot"
    _write_template(root / "image" / "only.py")
    symlink = tmp_path / "ready-link"
    symlink.symlink_to(root, target_is_directory=True)

    first = ready._discover_ready_templates(roots=[root, symlink])
    second = ready._discover_ready_templates(roots=[symlink, root])
    first_rows = workflows_cmd._ready_rows_without_index(first)
    second_rows = workflows_cmd._ready_rows_without_index(second)
    assert json.dumps(first_rows, sort_keys=True) == json.dumps(second_rows, sort_keys=True)



def test_missing_case_variant_roots_remain_distinct(tmp_path: Path) -> None:
    first = tmp_path / "CaseRoot"
    second = tmp_path / "caseroot"
    assert not first.exists() and not second.exists()
    expected = sorted([first.resolve(), second.resolve()], key=ready._path_sort_key)
    assert ready._dedupe_roots([first, second]) == expected


def test_cold_warm_and_indexed_listing_use_snapshot_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "Foo.py"
    _write_template(candidate)
    discovery = ready._discover_ready_templates(roots=[candidate.parents[1]])
    cold = workflows_cmd._ready_rows_without_index(discovery)
    warm = workflows_cmd._ready_rows_without_index(discovery)
    monkeypatch.setattr(workflows_cmd, "TEMPLATE_INDEX_PATH", tmp_path / "template_index.json")
    (tmp_path / "template_index.json").write_text(
        json.dumps({"templates": [{"id": "IMAGE/FOO", "path": "fabricated.py"}]}),
        encoding="utf-8",
    )
    indexed, diagnostic = workflows_cmd._ready_rows_from_template_index(discovery)
    assert diagnostic is None
    assert [(row["id"], row["path"]) for row in cold] == [("image/Foo", str(candidate))]
    assert [(row["id"], row["path"]) for row in warm] == [(row["id"], row["path"]) for row in cold]
    assert [(row["id"], row["path"]) for row in indexed] == [("image/Foo", str(candidate))]


def test_indexed_listing_drops_zero_match_stale_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "actual.py"
    stale_path = tmp_path / "stale" / "image" / "missing.py"
    _write_template(candidate)
    discovery = ready._discover_ready_templates(roots=[candidate.parents[1]])
    monkeypatch.setattr(workflows_cmd, "TEMPLATE_INDEX_PATH", tmp_path / "template_index.json")
    (tmp_path / "template_index.json").write_text(
        json.dumps({"templates": [{"id": "image/missing", "path": str(stale_path)}]}),
        encoding="utf-8",
    )

    rows, diagnostic = workflows_cmd._ready_rows_from_template_index(discovery)

    assert diagnostic is None
    assert rows == []
    assert str(stale_path) not in json.dumps(rows)


def test_indexed_listing_prefers_exact_physical_id_and_is_order_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upper = tmp_path / "upper" / "image" / "Foo.py"
    lower = tmp_path / "lower" / "image" / "foo.py"
    _write_template(upper)
    _write_template(lower)
    monkeypatch.setattr(workflows_cmd, "TEMPLATE_INDEX_PATH", tmp_path / "template_index.json")
    (tmp_path / "template_index.json").write_text(
        json.dumps({"templates": [{"id": "image/Foo", "path": "fabricated.py"}]}),
        encoding="utf-8",
    )

    first, first_diagnostic = workflows_cmd._ready_rows_from_template_index(
        ready._discover_ready_templates(roots=[upper.parents[1], lower.parents[1]])
    )
    second, second_diagnostic = workflows_cmd._ready_rows_from_template_index(
        ready._discover_ready_templates(roots=[lower.parents[1], upper.parents[1]])
    )

    assert first_diagnostic is None and second_diagnostic is None
    assert [(row["id"], row["path"]) for row in first] == [("image/Foo", str(upper))]
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_template_index_producer_uses_discovered_record_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tools import refresh_template_index as refresh

    candidate = tmp_path / "ready_templates" / "image" / "CaseSensitive.py"
    _write_template(candidate)
    discovery = ready._discover_ready_templates(roots=[candidate.parents[1]])
    monkeypatch.setattr(refresh, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(refresh, "repo_ready_template_discovery", lambda: discovery)
    monkeypatch.setattr(refresh, "_load_coverage_by_template_id", lambda _path: {})

    payload = refresh.build_template_index(generated_at="2026-01-01T00:00:00+00:00")

    assert payload["template_count"] == 1
    assert payload["templates"][0]["id"] == "image/CaseSensitive"
    assert payload["templates"][0]["path"] == (
        "ready_templates/image/CaseSensitive.py"
    )


def test_indexed_listing_reports_physical_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upper = tmp_path / "upper" / "image" / "Foo.py"
    lower = tmp_path / "lower" / "image" / "foo.py"
    _write_template(upper)
    _write_template(lower)
    discovery = ready._discover_ready_templates(roots=[upper.parents[1], lower.parents[1]])
    monkeypatch.setattr(workflows_cmd, "TEMPLATE_INDEX_PATH", tmp_path / "template_index.json")
    (tmp_path / "template_index.json").write_text(
        json.dumps({"templates": [{"id": "IMAGE/FOO", "path": "fabricated.py"}]}),
        encoding="utf-8",
    )
    rows, diagnostic = workflows_cmd._ready_rows_from_template_index(discovery)
    assert diagnostic is None
    assert len(rows) == 1
    assert rows[0]["collision"] is True
    assert rows[0]["collision_candidates"] == sorted([str(upper), str(lower)])
    assert "path" not in rows[0]

    reversed_rows, reversed_diagnostic = workflows_cmd._ready_rows_from_template_index(
        ready._discover_ready_templates(roots=[lower.parents[1], upper.parents[1]])
    )
    assert reversed_diagnostic is None
    assert json.dumps(rows, sort_keys=True) == json.dumps(reversed_rows, sort_keys=True)


def test_dynamic_listing_reports_collisions_without_raising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first" / "image" / "Foo.py"
    second = tmp_path / "second" / "image" / "foo.py"
    _write_template(first)
    _write_template(second)
    _use_roots(monkeypatch, [first.parents[1], second.parents[1]])
    rows = ready.dynamic_ready_template_rows()
    assert len(rows) == 2
    assert all(row["collision"] is True for row in rows)
    assert all(row["collision_candidates"] == sorted([str(first), str(second)]) for row in rows)


def test_collision_remediation_distinguishes_qualified_and_short_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    duplicate_a = tmp_path / "a" / "image" / "dup.py"
    duplicate_b = tmp_path / "b" / "image" / "dup.py"
    _write_template(duplicate_a)
    _write_template(duplicate_b)
    _use_roots(monkeypatch, [duplicate_a.parents[1], duplicate_b.parents[1]])
    with pytest.raises(ValueError, match="Remove the duplicate or use one canonical source"):
        workflow_from_ready("image/dup")
    with pytest.raises(ValueError, match="Remove the duplicate or use one canonical source"):
        workflow_from_ready("dup")

    shared = tmp_path / "shared"
    _write_template(shared / "video" / "dup.py")
    _use_roots(monkeypatch, [duplicate_a.parents[1], shared])
    with pytest.raises(ValueError, match="Use a category-qualified id"):
        workflow_from_ready("dup")


def test_indexed_only_duplicates_diagnose_without_blocking_unique_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "dynamic" / "image" / "unique.py"
    _write_template(candidate)
    rows = [
        {"id": "image/unique", "path": "indexed-a.py"},
        {"id": "IMAGE/UNIQUE", "path": "indexed-b.py"},
    ]
    marked = workflows_cmd._mark_ready_listing_collisions(rows)
    assert all(row["collision"] for row in marked)
    monkeypatch.setattr(ready, "_ready_roots", lambda: [candidate.parents[1]])
    assert workflow_from_ready("image/unique").metadata["ready_template"] == "image/unique"


def test_lowercase_corpus_ids_need_no_migration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = tmp_path / "ready" / "image" / "lower.py"
    _write_template(candidate)
    _use_roots(monkeypatch, [candidate.parents[1]])

    assert ready.ready_template_ids() == ["image/lower"]
    assert ready.ready_template_source_info("IMAGE/LOWER").template_id == "image/lower"
    assert load_workflow_any("ImAgE\\LoWeR").metadata["ready_template"] == "image/lower"
