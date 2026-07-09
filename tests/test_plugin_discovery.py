from __future__ import annotations

from pathlib import Path
import warnings

import pytest

from vibecomfy import extras
from vibecomfy.ops import registry as op_registry
from vibecomfy.ops import image
from vibecomfy.registry import ready as ready_registry
from vibecomfy.registry.ready import (
    ReadyTemplateLoadError,
    dynamic_ready_template_rows,
    ready_template_ids,
    workflow_from_ready,
)
from vibecomfy.security.gate import GateContext, _gate_context_var, set_gate_context


def test_project_local_plugin_registers_op_route_and_ready_root(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "plugin_ready"
    _write_ready_template(root / "project_smoke.py")
    plugin = tmp_path / "vibecomfy_extras" / "ops" / "project_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n"
        "    api.register_op('image', 'project_verb', lambda value: ('project', value))\n"
        "    api.register_route('image', 'project', lambda inputs: True, 'project_smoke')\n",
        encoding="utf-8",
    )

    assert image.project_verb("ok") == ("project", "ok")
    assert "project_smoke" in ready_template_ids()
    assert workflow_from_ready("project_smoke").metadata["ready_template"] == "project_smoke"


def test_user_global_plugin_registers_ready_template(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    root = home / "user_ready"
    _write_ready_template(root / "user_smoke.py")
    plugin = home / ".vibecomfy" / "ops" / "user_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n"
        "    api.register_op('image', 'user_verb', lambda value: ('user', value))\n",
        encoding="utf-8",
    )

    assert image.user_verb("ok") == ("user", "ok")
    assert workflow_from_ready("user_smoke").metadata["ready_template"] == "user_smoke"


def test_entry_point_plugin_registers_op_and_ready_root(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "entry_ready"
    _write_ready_template(root / "entry_smoke.py")

    def register(api):
        api.register_ready_root(root)
        api.register_op("image", "entry_verb", lambda value: ("entry", value))

    class EntryPoint:
        def load(self):
            return register

    class EntryPoints(list):
        def select(self, *, group: str):
            return self if group == "vibecomfy.plugins" else []

    monkeypatch.setattr("importlib.metadata.entry_points", lambda: EntryPoints([EntryPoint()]))

    assert image.entry_verb("ok") == ("entry", "ok")
    assert workflow_from_ready("entry_smoke").metadata["ready_template"] == "entry_smoke"


def test_dynamic_ready_template_rows_are_explicit_and_unindexed(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "dynamic_ready"
    _write_ready_template(root / "dynamic_smoke.py")
    plugin = tmp_path / "vibecomfy_extras" / "ops" / "dynamic_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n",
        encoding="utf-8",
    )

    rows = dynamic_ready_template_rows()

    assert rows == [
        {
            "id": "dynamic_smoke",
            "path": str(root / "dynamic_smoke.py"),
            "source_scope": "dynamic",
            "indexed": False,
        }
    ]


def test_dynamic_ready_template_is_scanned_before_exec_module(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    marker = tmp_path / "dynamic-ready-scan-marker.txt"
    root = tmp_path / "dynamic_ready"
    root.mkdir(parents=True, exist_ok=True)
    (root / "dangerous_ready.py").write_text(
        "from pathlib import Path\n"
        f"Path(r'{marker}').write_text('should-not-run', encoding='utf-8')\n"
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    return VibeWorkflow('dangerous', WorkflowSource('dangerous'))\n",
        encoding="utf-8",
    )
    plugin = tmp_path / "vibecomfy_extras" / "ops" / "dangerous_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n",
        encoding="utf-8",
    )
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)

    try:
        with pytest.raises(ReadyTemplateLoadError) as excinfo:
            workflow_from_ready("dangerous_ready")
    finally:
        _gate_context_var.reset(token)

    assert not marker.exists()
    assert ctx.audit == []
    report = excinfo.value.report
    assert not report.ok
    assert {failure.phase for failure in report.failures} == {"load_python"}
    assert {"forbidden_import", "forbidden_call"} & {failure.code for failure in report.failures}


def test_plugin_op_override_wins_for_builtin_module_attribute(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    monkeypatch.setattr(op_registry, "_OPS", dict(op_registry._OPS))
    monkeypatch.setattr(op_registry, "_OVERRIDE_WARNED", set(op_registry._OVERRIDE_WARNED))

    def override(prompt: str, **kwargs):
        return ("override", prompt, kwargs)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        op_registry.register_op("image", "t2i", override)

    from vibecomfy import image as public_image

    assert image.t2i("ok", model="demo") == (
        "override",
        "ok",
        {"model": "demo", "width": 1024, "height": 1024, "steps": None, "seed": None},
    )
    assert public_image.t2i("also-ok") == (
        "override",
        "also-ok",
        {"model": None, "width": 1024, "height": 1024, "steps": None, "seed": None},
    )
    assert any("Overriding vibecomfy op image.t2i" in str(item.message) for item in caught)


def test_ready_template_collision_warns_and_builtin_wins(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "plugin_ready"
    _write_ready_template(root / "image" / "z_image.py")
    plugin = tmp_path / "vibecomfy_extras" / "ops" / "collision_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n",
        encoding="utf-8",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ids = ready_template_ids()

    assert "image/z_image" in ids
    assert any("Ready template id collision" in str(item.message) for item in caught)
    assert workflow_from_ready("image/z_image").metadata["ready_template"] == "image/z_image"


def test_ensure_plugins_loaded_is_idempotent_when_empty(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    calls = 0

    def fake_load_plugins():
        nonlocal calls
        calls += 1
        return extras.plugin_api()

    monkeypatch.setattr(extras, "load_plugins", fake_load_plugins)

    extras.ensure_plugins_loaded()
    extras.ensure_plugins_loaded()

    assert calls == 1


def _reset_plugin_state(monkeypatch, cwd: Path) -> None:
    monkeypatch.chdir(cwd)
    monkeypatch.setenv("HOME", str(cwd / "home"))
    monkeypatch.setattr("importlib.metadata.entry_points", lambda: [])
    extras._reset_for_tests()
    ready_registry._reset_for_tests()


def _write_ready_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "from vibecomfy.workflow import VibeWorkflow, WorkflowSource\n\n"
        "def build():\n"
        "    wf = VibeWorkflow('plugin', WorkflowSource('plugin'))\n"
        "    image = wf.node('EmptyImage', width=64, height=64, batch_size=1).out(0)\n"
        "    wf.node('SaveImage', images=image)\n"
        "    return wf.finalize_metadata()\n",
        encoding="utf-8",
    )
