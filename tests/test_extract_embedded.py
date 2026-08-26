"""Tests for rung 3: extract_by_embedded (throwaway venv, no server)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from collections import OrderedDict

import pytest

from vibecomfy.schema.extract import extract_by_embedded, extract_pack_schemas


def _write_runtime_built_pack(root: Path, *, class_name: str = "RuntimeBuiltNode") -> Path:
    """A pack whose INPUT_TYPES is built at runtime so static AST CANNOT parse it."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "__init__.py").write_text(
        f"""
class {class_name}:
    @classmethod
    def INPUT_TYPES(cls):
        return {{"required": {{k: ("FLOAT", {{"default": 0.5}}) for k in ("alpha", "beta")}}}}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "sample/runtime"


NODE_CLASS_MAPPINGS = {{"{class_name}": {class_name}}}
""",
        encoding="utf-8",
    )
    return root


def test_extract_by_embedded_installs_pinned_comfyui_and_does_not_serve(tmp_path: Path) -> None:
    scratch = tmp_path / "embedded_env"
    venv_dir = scratch / "venv"
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    bin_dir.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text("", encoding="utf-8")
    python_path = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    python_path.write_text("", encoding="utf-8")

    pack_dir = tmp_path / "pack"
    pack_dir.mkdir()
    (pack_dir / "__init__.py").write_text("", encoding="utf-8")

    commands: list[list[str]] = []

    def fake_runner(command) -> subprocess.CompletedProcess[str]:
        commands.append(list(command))
        if "-c" in command:
            payload = {
                "EasyInt": {
                    "inputs": {"required": {"value": ["INT", {"default": 1}]}},
                    "return_types": ["INT"],
                    "return_names": ["INT"],
                    "output_is_list": [],
                    "category": "easy",
                    "function": "run",
                    "module": "pack",
                }
            }
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    entries, method = extract_by_embedded(
        pack_dir,
        pack_name="pack",
        version="on-demand",
        comfy_version="0.24.0.1",
        scratch_dir=scratch,
        runner=fake_runner,
        timeout=180,
    )

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
    script = commands[1][2]
    assert "main.main" not in script
    assert "urlopen" not in script
    assert "8188" not in script
    # also ensure not using urllib.request
    assert "urllib" not in script
    assert method == "embedded"
    assert "EasyInt" in entries
    # venv should be cleaned up after call
    assert not venv_dir.exists()


def test_extract_pack_schemas_skips_embedded_when_import_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = _write_runtime_built_pack(tmp_path / "runtime-pack")

    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("extract_by_embedded must not run when import succeeded")

    monkeypatch.setattr("vibecomfy.schema.extract.extract_by_embedded", boom)
    res = extract_pack_schemas(pack, pack_name="runtime-pack", allow_import=True, allow_embedded=True, comfy_version="0.24.0.1")
    assert res.method == "import"
    assert "RuntimeBuiltNode" in res.entries
    assert called["n"] == 0


def test_extract_pack_schemas_empty_pack_reaches_embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = tmp_path / "empty-pack"
    pack.mkdir()
    (pack / "__init__.py").write_text("# empty pack\n", encoding="utf-8")

    # monkeypatch extract_by_embedded to simulate rung 3 success
    dummy_entries = {
        "X": OrderedDict(
            [
                ("pack", "empty-pack"),
                ("pack_version", "on-demand"),
                ("python_module", "empty-pack"),
                ("category", ""),
                ("name", "X"),
                ("display_name", "X"),
                ("description", ""),
                ("inputs", {}),
                ("input_order", {}),
                ("input_order_all", []),
                ("object_info_widget_order", []),
                ("outputs", []),
                ("function", "X"),
            ]
        )
    }

    def fake_embedded(*a, **k):
        return (dummy_entries, "embedded")

    monkeypatch.setattr("vibecomfy.schema.extract.extract_by_embedded", fake_embedded)
    res = extract_pack_schemas(pack, pack_name="empty-pack", allow_import=True, allow_embedded=True, comfy_version="0.24.0.1")
    assert res.method == "embedded"
    assert "X" in res.entries

    # allow_embedded=False (default) must NOT call embedded
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("should not be called when allow_embedded=False")

    monkeypatch.setattr("vibecomfy.schema.extract.extract_by_embedded", boom)
    res2 = extract_pack_schemas(pack, pack_name="empty-pack", allow_import=True, allow_embedded=False, comfy_version="0.24.0.1")
    assert called["n"] == 0
    # entries empty because pack is empty, method may be "" or "ast" (empty)
    assert not res2.entries


def test_extract_pack_schemas_default_allow_embedded_is_false(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = tmp_path / "empty-default"
    pack.mkdir()
    (pack / "__init__.py").write_text("", encoding="utf-8")

    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("default allow_embedded must be False")

    monkeypatch.setattr("vibecomfy.schema.extract.extract_by_embedded", boom)
    res = extract_pack_schemas(pack, pack_name="empty-default")
    assert called["n"] == 0
    assert res.entries == {}


def test_embedded_timeout_does_not_crash_ladder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pack = tmp_path / "timeout-pack"
    pack.mkdir()
    (pack / "__init__.py").write_text("", encoding="utf-8")

    def raise_timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd=["python", "-c", "x"], timeout=1)

    monkeypatch.setattr("vibecomfy.schema.extract.extract_by_embedded", raise_timeout)
    res = extract_pack_schemas(pack, pack_name="timeout-pack", allow_import=True, allow_embedded=True, comfy_version="0.24.0.1")
    assert res.entries == {}
    assert any("timed out" in f.lower() for f in res.failures)


def test_extract_by_embedded_timeout_raises_runtime_error(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    pack.mkdir()
    (pack / "__init__.py").write_text("", encoding="utf-8")
    scratch = tmp_path / "scratch"
    venv_dir = scratch / "venv"
    bin_dir = venv_dir / ("Scripts" if sys.platform == "win32" else "bin")
    bin_dir.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text("", encoding="utf-8")
    python_path = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
    python_path.write_text("", encoding="utf-8")

    def timeout_runner(command):
        raise subprocess.TimeoutExpired(cmd=list(command), timeout=180)

    with pytest.raises(RuntimeError, match=r"timed out after 180s"):
        extract_by_embedded(
            pack,
            pack_name="pack",
            version="on-demand",
            comfy_version="0.24.0.1",
            scratch_dir=scratch,
            runner=timeout_runner,
            timeout=180,
        )
    # venv cleaned even on timeout
    assert not venv_dir.exists()


def test_schemas_ensure_passes_allow_embedded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Spy that _cmd_schemas_ensure passes allow_embedded correctly."""
    from vibecomfy.commands import schemas as schemas_mod

    # prepare minimal manifest/template path
    template_path = tmp_path / "tmpl.py"
    template_path.write_text("x=1\n", encoding="utf-8")

    # Stub cache and provider plumbing
    fake_cache_root = tmp_path / "cache"
    fake_cache_root.mkdir()

    import vibecomfy.porting.object_info.consume as consume_mod

    monkeypatch.setattr(consume_mod, "CACHE_DIR", fake_cache_root)

    # Stub missing_live_captures to return a fake class
    import vibecomfy.schema.ensure_capture as ec_mod

    monkeypatch.setattr(ec_mod, "missing_live_captures", lambda classes, cache_dir=None: ["FakeNode"])

    # Fake provider
    class FakeRef:
        slug = "fake-pack"
        url = "https://example.com/fake.git"
        version = "1.0.0"

    class FakeProvider:
        def _ensure_clone(self, ref):
            p = tmp_path / "clone"
            p.mkdir(exist_ok=True)
            (p / "__init__.py").write_text("", encoding="utf-8")
            return p

        def _enforce_cap(self):
            pass

    monkeypatch.setattr(schemas_mod, "_on_demand_provider", lambda: FakeProvider())
    monkeypatch.setattr(schemas_mod, "_resolve_pack_ref", lambda ct: FakeRef())
    # stub extract to capture kwargs
    captured = {}

    def fake_extract(pack_dir, **kwargs):
        captured.update(kwargs)
        from collections import OrderedDict

        return type("R", (), {"entries": {}, "method": "", "failures": ["empty"]})()

    # patch the module's extract_pack_schemas symbol used inside _capture_missing_classes
    import vibecomfy.schema.extract as extract_mod

    real_extract = extract_mod.extract_pack_schemas
    monkeypatch.setattr(extract_mod, "extract_pack_schemas", fake_extract)
    # also need the import inside schemas module
    # _capture_missing_classes does `from vibecomfy.schema import extract as extract_module`
    # so patching vibecomfy.schema.extract works

    # also stub persist and pin to avoid cache writes
    monkeypatch.setattr(schemas_mod, "_clone_pin", lambda a, b: ("https://example.com/fake.git", "abc123"))

    # Also stub _extract_class_types_from_template to return FakeNode for template path
    monkeypatch.setattr(schemas_mod, "_extract_class_types_from_template", lambda p: ["FakeNode"])

    # Stub reset_cache
    monkeypatch.setattr(consume_mod, "reset_cache", lambda: None)
    # also missing_live_captures after capture should return still missing (to trigger failure)
    # keep same stub

    # Test default (no --no-embedded) => allow_embedded True
    import argparse

    args = argparse.Namespace(template=str(template_path), manifest=None, json=True, comfy_version="0.24.0.1", no_embedded=False)
    schemas_mod._cmd_schemas_ensure(args)
    assert captured.get("allow_embedded") is True
    assert captured.get("comfy_version") == "0.24.0.1"

    captured.clear()
    args2 = argparse.Namespace(template=str(template_path), manifest=None, json=True, comfy_version="0.24.0.1", no_embedded=True)
    schemas_mod._cmd_schemas_ensure(args2)
    assert captured.get("allow_embedded") is False
