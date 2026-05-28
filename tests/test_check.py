from __future__ import annotations

from pathlib import Path

from vibecomfy.checks import (
    check_known_node_packs_usage_scan,
    check_legacy_file_presence,
    check_non_vendor_stale_legacy_references,
    run_checks,
)


def test_non_vendor_stale_legacy_references_ignores_vendor_and_reports_live_matches(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "docs").mkdir()
    legacy_dir = tmp_path / "vibecomfy" / "nodes"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "comfyui_kjnodes.py").write_text("# canonical legacy file\n", encoding="utf-8")
    (legacy_dir / "comfyui_ltxvideo.py").write_text("# canonical legacy file\n", encoding="utf-8")
    (legacy_dir / "rgthree_comfy.py").write_text("# canonical legacy file\n", encoding="utf-8")
    (tmp_path / "scripts" / "demo.py").write_text("from vibecomfy.nodes.rgthree_comfy import Context_rgthree\n", encoding="utf-8")
    (tmp_path / "vendor" / "ignored.py").write_text("KNOWN_NODE_PACKS = 1\n", encoding="utf-8")
    (tmp_path / "docs" / "ignored.md").write_text("comfyui_ltxvideo\n", encoding="utf-8")

    result = check_non_vendor_stale_legacy_references(tmp_path)

    assert result.ok is False
    assert [match["path"] for match in result.details["matches"]] == ["scripts/demo.py"]


def test_known_node_packs_usage_scan_ignores_vendor(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "vendor").mkdir()
    (tmp_path / "app" / "use.py").write_text("KNOWN_NODE_PACKS = ()\n", encoding="utf-8")
    (tmp_path / "vendor" / "ignored.py").write_text("KNOWN_NODE_PACKS = ()\n", encoding="utf-8")

    result = check_known_node_packs_usage_scan(tmp_path)

    assert result.ok is False
    assert [match["path"] for match in result.details["matches"]] == ["app/use.py"]


def test_legacy_file_presence_is_state_not_failure(tmp_path: Path) -> None:
    legacy_dir = tmp_path / "vibecomfy" / "nodes"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "comfyui_kjnodes.py").write_text("x\n", encoding="utf-8")

    result = check_legacy_file_presence(tmp_path)

    assert result.ok is True
    assert result.status == "state"
    assert result.details["present"][0]["path"] == "vibecomfy/nodes/comfyui_kjnodes.py"
    assert "vibecomfy/nodes/comfyui_ltxvideo.py" in result.details["missing"]


def test_run_checks_reports_stub_inventory_and_state_check() -> None:
    report = run_checks()

    assert isinstance(report.schema_cache_class_count, int)
    assert report.schema_cache_class_count > 0
    assert isinstance(report.pack_file_count, int)
    assert report.pack_file_count > 0
    assert "kjnodes" in report.stub_pack_inventory
    assert any(check.name == "legacy_file_presence" and check.status == "state" for check in report.checks)
