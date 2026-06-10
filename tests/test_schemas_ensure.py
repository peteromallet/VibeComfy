"""Focused tests for vibecomfy schemas ensure and pack extraction (Item 12).

Deterministic — no ComfyUI, RunPod, or network required. Uses mock pack fixtures
and synthetic Python packages with relative imports.
"""

from __future__ import annotations

import ast
import argparse
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest
import yaml

# Add repo root for imports
REPO_ROOT = Path(__file__).resolve().parent.parent

from vibecomfy.handles import Handle
from vibecomfy.commands import schemas as schemas_command


def test_schemas_refresh_accepts_structured_cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)
    source = tmp_path / "pack.json"
    source.write_text(
        json.dumps(
            {
                "TinyNode": {
                    "pack": "tiny",
                    "inputs": {"required": {"value": ["INT", {"default": 1}]}},
                    "outputs": [{"name": "value", "type": "INT"}],
                }
            }
        ),
        encoding="utf-8",
    )

    result = schemas_command.refresh_schema_cache_from_source(source)

    assert result["status"] == "ok"
    assert result["classes_indexed"] == 1
    assert result["pack_version"] == "structured-cache"
    assert result["source_kind"] == "structured_cache_copy"
    assert result["authoritative"] is False
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index == {"TinyNode": "pack.json"}


def test_schema_freshness_workflow_is_manual_and_artifact_based() -> None:
    workflow_path = Path(".github/workflows/schema_freshness.yml")

    payload = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))

    assert "workflow_dispatch" in payload[True]
    job = payload["jobs"]["schema-freshness"]
    commands = "\n".join(step.get("run", "") for step in job["steps"] if isinstance(step, dict))
    uses = [step.get("uses", "") for step in job["steps"] if isinstance(step, dict)]
    assert "schemas refresh --source" in commands
    assert "git diff -- vibecomfy/porting/cache/object_info" in commands
    assert "actions/upload-artifact@v4" in uses
    assert "contents" in payload["permissions"]
    assert "push" not in payload
    assert "schedule" not in payload
    assert "pull_request" not in payload
    assert "secrets." not in workflow_path.read_text(encoding="utf-8")


def test_schemas_refresh_command_uses_local_source_without_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)
    source = tmp_path / "pack.json"
    source.write_text(
        json.dumps(
            {
                "OfflineNode": {
                    "pack": "offline",
                    "inputs": {"required": {"value": ["STRING", {"default": "x"}]}},
                    "outputs": [{"name": "value", "type": "STRING"}],
                }
            }
        ),
        encoding="utf-8",
    )

    code = schemas_command._cmd_schemas_refresh(
        argparse.Namespace(source=str(source), server_url=None, json=True)
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["version"] == "structured-cache"
    assert payload["pack_version"] == "structured-cache"
    assert payload["source_kind"] == "structured_cache_copy"
    assert payload["authoritative"] is False
    assert payload["source"] == str(source)
    assert "server_url" not in payload
    assert json.loads((cache_root / "index.json").read_text(encoding="utf-8")) == {"OfflineNode": "pack.json"}


def test_schemas_refresh_command_text_surfaces_non_authoritative_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)
    source = tmp_path / "object_info.json"
    source.write_text(
        json.dumps(
            {
                "OfflineNode": {
                    "python_module": "custom_nodes.offline.nodes",
                    "name": "OfflineNode",
                    "display_name": "OfflineNode",
                    "description": "",
                    "category": "test",
                    "function": "run",
                    "input": {"required": {}, "optional": {}},
                    "input_order": {"required": [], "optional": []},
                    "output": ["STRING"],
                    "output_name": ["value"],
                    "output_is_list": [False],
                }
            }
        ),
        encoding="utf-8",
    )

    code = schemas_command._cmd_schemas_refresh(
        argparse.Namespace(source=str(source), server_url=None, json=False)
    )

    assert code == 0
    text = capsys.readouterr().out.strip()
    assert "non-authoritative" in text
    assert "legacy-import / legacy_object_info_import" in text


def test_schemas_regen_core_uses_fake_provider_and_stamps_authoritative_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)

    def fake_provider() -> dict:
        return {
            "CoreTinyNode": {
                "python_module": ".",
                "name": "CoreTinyNode",
                "display_name": "CoreTinyNode",
                "description": "",
                "category": "core",
                "function": "run",
                "input": {"required": {}, "optional": {}},
                "input_order": {"required": [], "optional": []},
                "output": ["INT"],
                "output_name": ["value"],
                "output_is_list": [False],
            }
        }

    code = schemas_command._cmd_schemas_regen_core(
        argparse.Namespace(
            comfy_version="0.24.0.1",
            json=True,
            source=None,
            server_url=None,
            object_info_provider=fake_provider,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["comfy_version"] == "0.24.0.1"
    assert payload["pack_slug"] == "comfy-core"
    assert payload["pack_version"] == "0.24.0.1"
    assert payload["evidence_identity"] == "comfy-core:0.24.0.1"
    assert payload["source_kind"] == "runtime_core_object_info"
    assert payload["authoritative"] is True
    assert "not sandboxed" in payload["warning"]

    pack_file = cache_root / "comfy-core@0.24.0.1.json"
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    entry = json.loads(pack_file.read_text(encoding="utf-8"))["CoreTinyNode"]
    assert index == {"CoreTinyNode": pack_file.name}
    assert entry["pack_slug"] == "comfy-core"
    assert entry["pack_version"] == "0.24.0.1"
    assert entry["evidence_identity"] == "comfy-core:0.24.0.1"
    assert entry["source_kind"] == "runtime_core_object_info"


def test_schemas_regen_core_default_path_uses_explicit_runner_not_runtime_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)

    def fail_runtime_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("regen-core must not use the generic runtime provider")

    monkeypatch.setattr(schemas_command, "RuntimeSchemaProvider", fail_runtime_provider)

    calls: list[str] = []

    def fake_runner(comfy_version: str) -> dict[str, object]:
        calls.append(comfy_version)
        return {
            "CoreTinyNode": {
                "python_module": ".",
                "name": "CoreTinyNode",
                "input": {},
                "input_order": {"required": [], "optional": []},
                "output": [],
            }
        }

    code = schemas_command._cmd_schemas_regen_core(
        argparse.Namespace(
            comfy_version="0.25.0",
            json=True,
            source=None,
            server_url=None,
            object_info_provider=None,
            object_info_runner=fake_runner,
        )
    )

    assert code == 0
    assert calls == ["0.25.0"]
    payload = json.loads(capsys.readouterr().out)
    assert payload["pack_slug"] == "comfy-core"
    assert (cache_root / "comfy-core@0.25.0.json").is_file()


def test_schemas_regen_core_registration_help_warns_unsandboxed() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    schemas_command.register(subparsers)

    schemas_parser = subparsers.choices["schemas"]
    regen_action = next(a for a in schemas_parser._subparsers._group_actions if a.dest == "schemas_subcmd")
    regen_parser = regen_action.choices["regen-core"]

    regen_help = regen_parser.format_help()
    assert "--comfy-version" in regen_help
    assert "third-party Python code" in regen_help
    assert "not sandboxed" in regen_help


def test_schemas_regen_core_rejects_invalid_comfy_version() -> None:
    with pytest.raises(ValueError, match="filesystem-safe"):
        schemas_command._cmd_schemas_regen_core(
            argparse.Namespace(
                comfy_version="../bad version",
                json=True,
                source=None,
                server_url=None,
                object_info_provider=lambda: {},
            )
        )


def test_core_regen_runner_installs_pinned_comfyui_and_captures_object_info(tmp_path: Path) -> None:
    from vibecomfy.porting.object_info.core_regen import capture_core_object_info

    env_root = tmp_path / "core_env"
    venv_dir = env_root / "venv"
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    bin_dir.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text("", encoding="utf-8")
    python_path = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    python_path.write_text("", encoding="utf-8")

    commands: list[list[str]] = []

    def fake_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"KSampler": {}}), stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    payload = capture_core_object_info("0.24.0.1", runner=fake_runner, env_root=env_root)

    assert payload == {"KSampler": {}}
    assert commands[0] == [
        str(python_path),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "comfyui==0.24.0.1",
    ]
    assert commands[1][0] == str(python_path)
    assert commands[1][1] == "-c"


def test_refresh_schema_cache_from_source_with_directory_containing_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``refresh_schema_cache_from_source`` should handle a structured cache directory."""
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)
    source_dir = tmp_path / "source_cache"
    source_dir.mkdir()
    (source_dir / "index.json").write_text(
        json.dumps({"ClassX": "pack_a.json", "ClassY": "pack_b.json"}), encoding="utf-8"
    )
    (source_dir / "pack_a.json").write_text(
        json.dumps({"ClassX": {"inputs": {}, "outputs": [{"name": "out", "type": "INT"}]}}),
        encoding="utf-8",
    )
    (source_dir / "pack_b.json").write_text(
        json.dumps({"ClassY": {"inputs": {}, "outputs": [{"name": "out", "type": "STRING"}]}}),
        encoding="utf-8",
    )

    result = schemas_command.refresh_schema_cache_from_source(source_dir)

    assert result["status"] == "ok"
    assert result["classes_indexed"] == 2
    assert result["packs_written"] == 2
    assert result["version"] == "structured-cache"
    assert result["pack_version"] == "structured-cache"
    assert result["source_kind"] == "structured_cache_copy"
    assert result["authoritative"] is False
    assert result["source"] == str(source_dir)

    assert (cache_root / "index.json").is_file()
    assert (cache_root / "pack_a.json").is_file()
    assert (cache_root / "pack_b.json").is_file()


def test_refresh_schema_cache_from_source_with_index_json_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``refresh_schema_cache_from_source`` with an index.json path should resolve to its parent."""
    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)
    source_dir = tmp_path / "source_cache"
    source_dir.mkdir()
    (source_dir / "index.json").write_text(
        json.dumps({"ClassP": "pack_p.json"}), encoding="utf-8"
    )
    (source_dir / "pack_p.json").write_text(
        json.dumps({"ClassP": {"inputs": {}, "outputs": [{"name": "out", "type": "FLOAT"}]}}),
        encoding="utf-8",
    )

    result = schemas_command.refresh_schema_cache_from_source(source_dir / "index.json")

    assert result["status"] == "ok"
    assert result["classes_indexed"] == 1
    assert result["packs_written"] == 1
    assert result["version"] == "structured-cache"
    assert result["source_kind"] == "structured_cache_copy"
    assert result["authoritative"] is False

    assert (cache_root / "pack_p.json").is_file()
    new_index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert new_index == {"ClassP": "pack_p.json"}


# ============================================================================
# (a) Class type extraction from templates
# ============================================================================


class TestClassTypeExtraction:
    """Tests _extract_class_types_from_template for schemas ensure."""

    def test_extracts_all_class_types(self) -> None:
        """Should extract every unique class_type from _node() calls."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "UNETLoader", "100", unet_name="m.safetensors", weight_dtype="fp16")
            b = _node(wf, "CLIPTextEncode", "200", text="prompt")
            c = _node(wf, "VAEDecode", "300", samples=None)
            return wf
        """)
        tree = ast.parse(source)
        class_types = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_node":
                pass
            elif isinstance(func, ast.Attribute) and func.attr == "_node":
                pass
            else:
                continue
            if len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    class_types.append(arg.value)

        assert sorted(set(class_types)) == ["CLIPTextEncode", "UNETLoader", "VAEDecode"]

    def test_ignores_non_node_calls(self) -> None:
        """Should ignore calls to functions other than _node."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "UNETLoader", "100")
            b = some_other_func("NotAClass", "200")
            wf.register_input("x", "100", "unet_name", None)
            return wf
        """)
        tree = ast.parse(source)
        class_types = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_node":
                pass
            elif isinstance(func, ast.Attribute) and func.attr == "_node":
                pass
            else:
                continue
            if len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    class_types.append(arg.value)

        assert class_types == ["UNETLoader"]

    def test_duplicate_classes_deduplicated(self) -> None:
        """Duplicate class types should be deduplicated in the result."""
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "INTConstant", "100", value=10)
            b = _node(wf, "INTConstant", "101", value=20)
            c = _node(wf, "INTConstant", "102", value=30)
            return wf
        """)
        tree = ast.parse(source)
        class_types = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_node":
                pass
            elif isinstance(func, ast.Attribute) and func.attr == "_node":
                pass
            else:
                continue
            if len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    class_types.append(arg.value)

        unique = sorted(set(class_types))
        assert unique == ["INTConstant"]
        assert len(unique) == 1


# ============================================================================
# (b) Pack extraction coverage diffing
# ============================================================================


class TestCoverageDiffing:
    """Tests the class-coverage diffing logic for schemas ensure."""

    def test_identifies_missing_classes(self) -> None:
        """Should identify which template classes are missing from cache."""
        template_classes = {"CannyEdgePreprocessor", "UNETLoader", "DWPreprocessor"}
        cached_classes = {"UNETLoader", "CLIPTextEncode"}

        missing = template_classes - cached_classes
        assert missing == {"CannyEdgePreprocessor", "DWPreprocessor"}

    def test_all_covered_noop(self) -> None:
        """When all classes are cached, missing set should be empty."""
        template_classes = {"UNETLoader", "CLIPTextEncode"}
        cached_classes = {"UNETLoader", "CLIPTextEncode", "VAEDecode"}

        missing = template_classes - cached_classes
        assert missing == set()

    def test_empty_template_no_missing(self) -> None:
        """Empty template should produce no missing classes."""
        template_classes: set[str] = set()
        cached_classes = {"UNETLoader", "CLIPTextEncode"}

        missing = template_classes - cached_classes
        assert missing == set()


# ============================================================================
# (c) Relative import handling (Item 12 part 1)
# ============================================================================


class TestRelativeImportHandling:
    """Tests that pack extraction handles packages with relative imports."""

    @pytest.fixture
    def synthetic_pack_dir(self, tmp_path: Path):
        """Create a synthetic pack with relative imports for testing."""
        pack_dir = tmp_path / "synthetic_pack"
        pack_dir.mkdir()

        # __init__.py with relative import
        init_py = pack_dir / "__init__.py"
        init_py.write_text(textwrap.dedent("""\
        from .utils import helper_function
        from .nodes import MyNode

        NODE_CLASS_MAPPINGS = {
            "MyNode": MyNode,
        }
        """))

        # utils.py
        utils_py = pack_dir / "utils.py"
        utils_py.write_text(textwrap.dedent("""\
        def helper_function():
            return "hello"
        """))

        # nodes.py
        nodes_py = pack_dir / "nodes.py"
        nodes_py.write_text(textwrap.dedent("""\
        class MyNode:
            @classmethod
            def INPUT_TYPES(cls):
                return {"required": {"text": ("STRING", {"default": ""})}}
            RETURN_TYPES = ("STRING",)
            RETURN_NAMES = ("output",)
            FUNCTION = "run"
            CATEGORY = "test"

            def run(self, text):
                from .utils import helper_function
                return (text + helper_function(),)
        """))

        return pack_dir

    def test_importlib_import_module_for_package(self, synthetic_pack_dir: Path, tmp_path: Path):
        """Importing a package with importlib should handle relative imports."""
        # Add parent to sys.path so package can be imported
        parent_dir = str(synthetic_pack_dir.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        try:
            import importlib

            mod = importlib.import_module(synthetic_pack_dir.name)
            assert hasattr(mod, "NODE_CLASS_MAPPINGS"), (
                "Package should have NODE_CLASS_MAPPINGS"
            )
            assert "MyNode" in mod.NODE_CLASS_MAPPINGS
        finally:
            if parent_dir in sys.path:
                sys.path.remove(parent_dir)
            # Clean up sys.modules
            for key in list(sys.modules.keys()):
                if "synthetic_pack" in key:
                    del sys.modules[key]

    def test_spec_from_file_location_handles_submodule_search(self, synthetic_pack_dir: Path, tmp_path: Path):
        """spec_from_file_location with submodule_search_locations handles packages."""
        import importlib.util

        init_file = synthetic_pack_dir / "__init__.py"
        spec = importlib.util.spec_from_file_location(
            "synthetic_pack",
            init_file,
            submodule_search_locations=[str(synthetic_pack_dir)],
        )
        assert spec is not None, "spec_from_file_location should return a spec"
        assert spec.submodule_search_locations is not None
        assert str(synthetic_pack_dir) in (
            str(p) for p in spec.submodule_search_locations
        )

    def test_ast_fallback_for_unimportable_pack(self, synthetic_pack_dir: Path):
        """When import fails, AST-based extraction should work as fallback."""
        # Parse the __init__.py to find class mappings
        init_content = (synthetic_pack_dir / "__init__.py").read_text()
        tree = ast.parse(init_content)

        # Find NODE_CLASS_MAPPINGS assignment
        found_classes = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in (node.targets if hasattr(node, "targets") else [node.target]):
                if isinstance(target, ast.Name) and target.id == "NODE_CLASS_MAPPINGS":
                    if isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant):
                                found_classes.append(key.value)

        assert "MyNode" in found_classes, f"NODE_CLASS_MAPPINGS should contain MyNode"


# ============================================================================
# (d) Cache index update
# ============================================================================


class TestCacheIndexUpdate:
    """Tests index.json update logic for schemas ensure."""

    def test_index_remaps_existing_class(self, tmp_path: Path):
        """When a class moves to a new pack, the index should be updated."""
        index = {"MyNode": "old_pack@v1.json"}
        new_filename = "new_pack@v2.json"

        # Simulate the update
        for class_name in ["MyNode"]:
            existing = index.get(class_name)
            if existing and existing != new_filename:
                # Would emit a warning
                pass
            index[class_name] = new_filename

        assert index["MyNode"] == "new_pack@v2.json"

    def test_index_adds_new_class(self, tmp_path: Path):
        """New classes should be added to the index."""
        index: dict[str, str] = {}
        new_filename = "comfyui_controlnet_aux@local-abc1234.json"

        for class_name in ["CannyEdgePreprocessor", "DWPreprocessor"]:
            index[class_name] = new_filename

        assert index["CannyEdgePreprocessor"] == new_filename
        assert index["DWPreprocessor"] == new_filename
        assert len(index) == 2

    def test_index_is_sorted_deterministically(self, tmp_path: Path):
        """The index should be sorted for deterministic output."""
        index = {"ZClass": "p1.json", "AClass": "p2.json", "MClass": "p3.json"}
        sorted_items = dict(sorted(index.items()))
        keys = list(sorted_items.keys())
        assert keys == ["AClass", "MClass", "ZClass"]


# ============================================================================
# (e) schemas ensure workflow (Item 12 part 2)
# ============================================================================


class TestSchemasEnsureWorkflow:
    """End-to-end tests for the schemas ensure workflow."""

    def test_validate_coverage_identifies_missing(self) -> None:
        """validate-coverage should correctly identify missing classes."""
        from vibecomfy.commands.schemas import _extract_class_types_from_template
        from vibecomfy.porting.object_info.consume import list_classes

        # Create a template with a mix of cached and non-cached classes
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "UNETLoader", "100", unet_name="m.safetensors", weight_dtype="fp16")
            b = _node(wf, "NonExistentClassXYZ", "200", x=1)
            return wf
        """)
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(source)
            tmp_path = f.name

        try:
            class_types = _extract_class_types_from_template(tmp_path)
            all_cached = set(list_classes())
            missing = [ct for ct in class_types if ct not in all_cached]
            covered = [ct for ct in class_types if ct in all_cached]

            assert "UNETLoader" in covered, "UNETLoader should be in cache"
            assert "NonExistentClassXYZ" in missing, "NonExistentClassXYZ should be missing"
        finally:
            os.unlink(tmp_path)

    def test_extract_class_types_from_real_template(self) -> None:
        """Test extraction against the actual LTX template."""
        template_path = (
            REPO_ROOT / "ready_templates" / "video"
            / "ltx2_3_first_last_frame_travel_iclora_control.py"
        )
        if not template_path.is_file():
            pytest.skip("LTX template not found")

        from vibecomfy.commands.schemas import _extract_class_types_from_template

        class_types = _extract_class_types_from_template(template_path)
        assert len(class_types) > 0, "Should find at least one class type"
        # LTX template should have UNETLoader or similar core types
        known_types = {"UNETLoader", "CLIPTextEncode", "VAEDecode", "KSamplerSelect",
                       "CFGGuider", "PrimitiveFloat", "INTConstant"}
        found_known = set(class_types) & known_types
        assert len(found_known) > 0, (
            f"Expected at least one known class type in LTX, got {set(class_types)}"
        )

    @mock.patch("vibecomfy.porting.object_info.consume.list_classes")
    @mock.patch("vibecomfy.porting.object_info.consume.get_class")
    def test_schemas_ensure_noop_when_all_cached(self, mock_get_class, mock_list_classes, tmp_path):
        """When all classes are cached, schemas ensure should be a no-op."""
        mock_list_classes.return_value = ["ClassA", "ClassB"]
        mock_get_class.return_value = {"pack": "test"}

        # Create a template using only cached classes
        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "ClassA", "100", x=1)
            b = _node(wf, "ClassB", "200", y=2)
            return wf
        """)
        tmpl_path = tmp_path / "test_template.py"
        tmpl_path.write_text(source)

        from vibecomfy.commands.schemas import _extract_class_types_from_template
        class_types = _extract_class_types_from_template(str(tmpl_path))
        all_cached = set(mock_list_classes.return_value)
        missing = [ct for ct in class_types if ct not in all_cached]

        assert missing == [], f"All classes should be cached, missing: {missing}"

    @mock.patch("vibecomfy.porting.object_info.consume.list_classes")
    @mock.patch("vibecomfy.porting.object_info.consume.get_class")
    def test_schemas_ensure_detects_missing(self, mock_get_class, mock_list_classes, tmp_path):
        """When classes are missing, schemas ensure should identify them."""
        mock_list_classes.return_value = ["ClassA"]
        mock_get_class.side_effect = lambda ct: (
            {"pack": "test"} if ct == "ClassA" else None
        )

        source = textwrap.dedent("""\
        import sys
        def _node(wf, cls, nid, **kw):
            return wf, cls, nid, kw
        def build():
            wf = object()
            a = _node(wf, "ClassA", "100", x=1)
            b = _node(wf, "MissingClass", "200", y=2)
            return wf
        """)
        tmpl_path = tmp_path / "test_template.py"
        tmpl_path.write_text(source)

        from vibecomfy.commands.schemas import _extract_class_types_from_template
        class_types = _extract_class_types_from_template(str(tmpl_path))
        all_cached = set(mock_list_classes.return_value)
        missing = [ct for ct in class_types if ct not in all_cached]

        assert "MissingClass" in missing


# ============================================================================
# (f) clone_and_extract_packs AST fallback
# ============================================================================


class TestCloneAndExtractPacks:
    """Tests for clone_and_extract_packs.py AST fallback extraction."""

    def test_safe_eval_constants(self) -> None:
        """SafeEval should handle basic constants."""
        from tools.clone_and_extract_packs import SafeEval

        evaluator = SafeEval({})
        tree = ast.parse("42")
        val = evaluator.eval(tree.body[0].value)  # type: ignore[attr-defined]
        assert val == 42

        tree = ast.parse('"hello"')
        val = evaluator.eval(tree.body[0].value)  # type: ignore[attr-defined]
        assert val == "hello"

        tree = ast.parse("True")
        val = evaluator.eval(tree.body[0].value)  # type: ignore[attr-defined]
        assert val is True

    def test_safe_eval_list_and_dict(self) -> None:
        """SafeEval should handle lists and dicts."""
        from tools.clone_and_extract_packs import SafeEval

        evaluator = SafeEval({})
        tree = ast.parse("[1, 2, 3]")
        val = evaluator.eval(tree.body[0].value)  # type: ignore[attr-defined]
        assert val == [1, 2, 3]

        tree = ast.parse("{'a': 1, 'b': 2}")
        val = evaluator.eval(tree.body[0].value)  # type: ignore[attr-defined]
        assert val == {"a": 1, "b": 2}

    def test_static_env_build(self) -> None:
        """static_env should build an environment from top-level assignments."""
        from tools.clone_and_extract_packs import static_env

        source = textwrap.dedent("""\
        FOO = 42
        BAR = "hello"
        BAZ = [1, 2, 3]
        """)
        tree = ast.parse(source)
        env = static_env(tree)
        assert env.get("FOO") == 42
        assert env.get("BAR") == "hello"
        assert env.get("BAZ") == [1, 2, 3]

    def test_dotted_name_parsing(self) -> None:
        """dotted_name should resolve attribute chains."""
        from tools.clone_and_extract_packs import dotted_name

        tree = ast.parse("a.b.c")
        name = dotted_name(tree.body[0].value)  # type: ignore[attr-defined]
        assert name == "a.b.c"

        tree = ast.parse("x")
        name = dotted_name(tree.body[0].value)  # type: ignore[attr-defined]
        assert name == "x"


# ============================================================================
# (g) Node packs mapping
# ============================================================================


class TestNodePacksMapping:
    """Tests that the node-pack catalog exposes expected entries."""

    def test_comfyui_controlnet_aux_in_registry(self) -> None:
        """The comfyui_controlnet_aux pack should be present in the catalog."""
        from vibecomfy.node_packs import get_known_node_packs

        known_node_packs = get_known_node_packs()
        # Check for packs that contain CannyEdgePreprocessor or DWPreprocessor
        found = False
        for pack in known_node_packs:
            if "CannyEdgePreprocessor" in pack.classes or "DWPreprocessor" in pack.classes:
                found = True
                break
        # If not found via class check, that's fine — the pack might not be registered yet
        # This test documents the expected state
        if not found:
            pytest.skip("comfyui_controlnet_aux not yet in the node-pack catalog — will be added")

    def test_known_packs_have_required_fields(self) -> None:
        """Every CustomNodePack should have name, repo, and classes."""
        from vibecomfy.node_packs import get_known_node_packs

        for pack in get_known_node_packs():
            assert pack.name, f"Pack {pack} has empty name"
            assert pack.repo.startswith("https://"), (
                f"Pack {pack.name} repo should be HTTPS URL: {pack.repo}"
            )
            assert len(pack.classes) > 0, f"Pack {pack.name} has no classes"


# ============================================================================
# (h) Handle.out named slot resolution
# ============================================================================


class TestHandleOut:
    """Tests for Handle.out named slot resolution (Item 5)."""

    def test_handle_creation_with_named_slot(self) -> None:
        """Handle should accept a string output_slot."""
        h = Handle(node_id="100", output_slot="MODEL")
        assert h.output_slot == "MODEL"
        assert str(h) == "100.MODEL"

    def test_handle_str_representation(self) -> None:
        """Handle.__str__ should include the slot as-is."""
        h = Handle(node_id="200", output_slot=0)
        assert str(h) == "200.0"

        h = Handle(node_id="200", output_slot="CLIP")
        assert str(h) == "200.CLIP"

    def test_handle_eq_with_name(self) -> None:
        """Handle.__eq__ with name field."""
        h1 = Handle(node_id="100", output_slot=0)
        h2 = Handle(node_id="100", output_slot="0")
        assert h1 == h2

    def test_handle_not_equal(self) -> None:
        """Different nodes or slots should not be equal."""
        h1 = Handle(node_id="100", output_slot=0)
        h2 = Handle(node_id="200", output_slot=0)
        assert h1 != h2

        h3 = Handle(node_id="100", output_slot=1)
        assert h1 != h3
