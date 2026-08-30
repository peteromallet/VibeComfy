from __future__ import annotations

from pathlib import Path
import warnings

import pytest

from vibecomfy import extras
from vibecomfy.cli_loader import load_workflow_any
from vibecomfy.ops import registry as op_registry
from vibecomfy.ops import image
from vibecomfy.registry import ready as ready_registry
from vibecomfy.registry.library import workflow_from_id
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


def test_ready_template_collision_fails_closed_with_all_candidates(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "plugin_ready"
    candidate = root / "image" / "z_image.py"
    _write_ready_template(candidate)
    plugin = tmp_path / "vibecomfy_extras" / "ops" / "collision_plugin.py"
    plugin.parent.mkdir(parents=True)
    plugin.write_text(
        "def register(api):\n"
        "    api.register_ready_root(r'" + str(root) + "')\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Ambiguous ready template id 'image/z_image'") as exc_info:
        ready_template_ids()

    message = str(exc_info.value)
    assert str(candidate) in message
    assert str((ready_registry.READY_ROOT / "image/z_image.py").resolve()) in message


def test_ready_template_short_alias_collision_requires_qualified_id(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "ready_templates"
    image_candidate = root / "image" / "shared.py"
    video_candidate = root / "video" / "shared.py"
    _write_ready_template(image_candidate)
    _write_ready_template(video_candidate)
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])

    with pytest.raises(ValueError, match="Ambiguous ready template id 'shared'") as exc_info:
        workflow_from_ready("shared")
    message = str(exc_info.value)
    assert f"{image_candidate}, {video_candidate}" in message
    assert message.endswith("Use a category-qualified id.")
    assert ready_registry.ready_template_source_info("IMAGE\\SHARED").path == str(image_candidate)
    assert ready_registry.ready_template_source_info("video/shared").path == str(video_candidate)


def test_case_variant_registered_root_is_one_discovery_root(tmp_path: Path, monkeypatch) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "PluginReady"
    candidate = root / "image" / "only.py"
    _write_ready_template(candidate)
    variant = Path(str(root).swapcase())
    roots = ready_registry._dedupe_roots([root, variant])
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: roots)
    monkeypatch.setattr(ready_registry, "_dynamic_ready_roots", lambda: roots)

    assert roots == [root.resolve()]
    assert ready_template_ids() == ["image/only"]
    assert workflow_from_ready("IMAGE/ONLY").metadata["ready_template"] == "image/only"


def test_case_variant_qualified_ids_remain_exact_and_folded_aliases_collide(
    tmp_path: Path, monkeypatch
) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_candidate = first / "image" / "Foo.py"
    second_candidate = second / "image" / "foo.py"
    _write_ready_template(first_candidate)
    _write_ready_template(second_candidate)
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [first, second])

    assert ready_registry.ready_template_source_info("image/Foo").path == str(first_candidate)
    assert ready_registry.ready_template_source_info("image/foo").path == str(second_candidate)
    with pytest.raises(ValueError, match="Ambiguous ready template id 'IMAGE/FOO'") as exc_info:
        workflow_from_ready("IMAGE/FOO")
    message = str(exc_info.value)
    assert str(first_candidate) in message
    assert str(second_candidate) in message
    assert message.endswith("Use the exact canonical id.")
    with pytest.raises(ValueError, match="Ambiguous ready template id 'foo'"):
        workflow_from_ready("foo")


def test_unique_case_variant_aliases_preserve_enumerated_id(
    tmp_path: Path, monkeypatch
) -> None:
    _reset_plugin_state(monkeypatch, tmp_path)
    root = tmp_path / "ready_templates"
    candidate = root / "image" / "Foo.py"
    _write_ready_template(candidate)
    monkeypatch.setattr(ready_registry, "_ready_roots", lambda: [root])
    monkeypatch.setattr(ready_registry, "_dynamic_ready_roots", lambda: [root])

    assert ready_template_ids() == ["image/Foo"]
    assert ready_registry.ready_template_source_info("IMAGE/FOO").template_id == "image/Foo"
    assert workflow_from_ready("fOo").metadata["ready_template"] == "image/Foo"
    assert workflow_from_id("IMAGE\\FOO").metadata["ready_template"] == "image/Foo"
    assert load_workflow_any("IMAGE/FOO").metadata["ready_template"] == "image/Foo"
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
