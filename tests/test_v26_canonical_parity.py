from __future__ import annotations

import json
import os
from pathlib import Path

from tools import check_canonical_parity as parity


def test_canonical_parity_baseline_matches_current_ready_templates() -> None:
    report = parity.check_baseline()

    assert report["ok"], report["errors"]


def test_canonical_parity_reports_hash_mismatch(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(parity.build_baseline(ready_root)), encoding="utf-8")

    _write_ready_template(tmp_path, literal=2)
    report = parity.check_baseline(baseline, ready_root=ready_root)

    assert not report["ok"]
    assert report["mismatched"][0]["id"] == "image/example"
    assert "canonical hash changed for image/example" in report["errors"][0]


def test_canonical_parity_reports_missing_and_extra_templates(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(parity.build_baseline(ready_root)), encoding="utf-8")

    (ready_root / "image" / "example.py").unlink()
    _write_ready_template(tmp_path, template_id="image/new_example", literal=1)
    report = parity.check_baseline(baseline, ready_root=ready_root)

    assert not report["ok"]
    assert report["missing"] == ["image/example"]
    assert report["extra"] == ["image/new_example"]


def test_canonical_parity_rejects_new_unbuildable_template(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(parity.build_baseline(ready_root)), encoding="utf-8")

    broken = ready_root / "image" / "new_broken.py"
    broken.write_text(
        "# vibecomfy: generated\n"
        "def build():\n"
        "    raise RuntimeError('broken ready template')\n",
        encoding="utf-8",
    )

    report = parity.check_baseline(baseline, ready_root=ready_root)

    assert not report["ok"]
    assert report["extra"] == []
    assert report["skipped"][0]["id"] == "image/new_broken"
    assert any(
        error.startswith("eligible template does not compile: image/new_broken")
        for error in report["errors"]
    )


def test_canonical_parity_update_rewrites_baseline(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    baseline = tmp_path / "baseline.json"

    assert parity.main(["--ready-root", str(ready_root), "--baseline", str(baseline), "--update"]) == 0

    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["template_count"] == 1
    assert payload["templates"][0]["id"] == "image/example"


def test_canonical_parity_update_refuses_unbuildable_template(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    (ready_root / "image" / "broken.py").write_text(
        "# vibecomfy: generated\n"
        "def build():\n"
        "    raise RuntimeError('broken ready template')\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"

    assert parity.main(["--ready-root", str(ready_root), "--baseline", str(baseline), "--update"]) == 1
    assert not baseline.exists()


def test_canonical_parity_excludes_manual_templates(tmp_path: Path) -> None:
    ready_root = _write_ready_template(tmp_path, literal=1)
    _write_ready_template(tmp_path, template_id="image/manual", literal=1, marker="# vibecomfy: manual")

    payload = parity.build_baseline(ready_root)

    assert [row["id"] for row in payload["templates"]] == ["image/example"]


def test_canonical_parity_is_offline_by_default_even_with_authoring_opt_in(
    monkeypatch, tmp_path: Path
) -> None:
    """Parity must not inherit the normal authoring provider's network default."""
    from vibecomfy.schema import on_demand

    class NetworkBomb:
        def __init__(self):
            raise AssertionError("canonical parity attempted on-demand resolution")

    monkeypatch.delenv("VIBECOMFY_PARITY_NETWORK", raising=False)
    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "1")
    monkeypatch.setattr(on_demand, "OnDemandInstallSchemaProvider", NetworkBomb)
    ready_root = _write_schema_probe_template(tmp_path)

    records, skipped = parity.collect_records_with_skips(ready_root)

    assert [record.id for record in records] == ["image/schema_probe"]
    assert skipped == []
    assert os.environ["VIBECOMFY_ON_DEMAND_SCHEMAS"] == "1"


def test_canonical_parity_network_opt_in_preserves_provider_timeout_boundary(
    monkeypatch, tmp_path: Path
) -> None:
    from vibecomfy.schema import on_demand

    seen: list[str | None] = []

    class CapturingProvider:
        def __init__(self):
            seen.append(os.environ.get("VIBECOMFY_ON_DEMAND_SCHEMAS"))

        def get_schema(self, _class_type):
            return None

    monkeypatch.setenv("VIBECOMFY_PARITY_NETWORK", "1")
    monkeypatch.setenv("VIBECOMFY_ON_DEMAND_SCHEMAS", "0")
    monkeypatch.setattr(on_demand, "OnDemandInstallSchemaProvider", CapturingProvider)
    ready_root = _write_schema_probe_template(tmp_path)

    records, skipped = parity.collect_records_with_skips(ready_root)

    assert [record.id for record in records] == ["image/schema_probe"]
    assert skipped == []
    assert seen == ["1"]
    assert os.environ["VIBECOMFY_ON_DEMAND_SCHEMAS"] == "0"


def _write_ready_template(
    tmp_path: Path,
    *,
    template_id: str = "image/example",
    literal: int,
    marker: str = "# vibecomfy: generated\n# For hand-editing, run: python -m vibecomfy.cli copy-to-recipe <id>",
) -> Path:
    ready_root = tmp_path / "ready_templates"
    path = ready_root / f"{template_id}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""{marker}
from __future__ import annotations

from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def build() -> VibeWorkflow:
    wf = VibeWorkflow("{template_id}", WorkflowSource("{template_id}", path=__file__, source_type="ready_template"))
    wf.add_node("Constant", _id="1", value={literal})
    wf.add_node("SaveImage", _id="2", filename_prefix="example")
    wf.connect("1.0", "2.images")
    return wf
""",
        encoding="utf-8",
    )
    return ready_root


def _write_schema_probe_template(tmp_path: Path) -> Path:
    ready_root = tmp_path / "schema_probe_root"
    path = ready_root / "image" / "schema_probe.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n"
        "\n"
        "def build() -> VibeWorkflow:\n"
        "    wf = VibeWorkflow('image/schema_probe', WorkflowSource('image/schema_probe'))\n"
        "    wf.node('UnknownSchemaNode').out(0)\n"
        "    return wf\n",
        encoding="utf-8",
    )
    return ready_root
