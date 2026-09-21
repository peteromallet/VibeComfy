"""External facts must never come from the interpreter running the CLI."""
from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest

from vibecomfy.contracts.runtime import RuntimeRequirements
from vibecomfy.runtime import dependencies
from vibecomfy.runtime.run import _dependency_check
from vibecomfy.runtime.session import SessionConfig


ARGV = ["main.py", "--listen", "0.0.0.0", "--port", "8188", "--enable-cors-header"]
SYSTEM = {
    "comfyui_version": "0.36.0",
    "python_version": "3.12.3 (main, Jul 15 2026) [GCC 13.3.0]",
    "pytorch_version": "2.10.0+cu130",
    "comfy_package_versions": [
        {"name": "comfy-kitchen", "installed": "0.2.34", "required": "0.2.34"},
        {"name": "comfy-aimdo", "installed": "0.5.3", "required": "0.5.3"},
    ],
    "argv": ARGV,
}
REQUIREMENTS = {
    "comfy_commit": "ee71d5c4993f29086b27fde1629a945ae48425bf",
    "comfy_version": "==0.36.0",
    "packages": {"torch": "==2.10.0+cu130", "comfy-kitchen": "==0.2.34", "comfy-aimdo": "==0.5.3"},
    "launch_flags": ["--use-ck-attention", "--disable-comfy-compiler"],
}


@pytest.fixture
def remote(monkeypatch):
    def request(url, *, timeout):
        assert url == "http://comfy.test/system_stats"
        assert timeout == 2
        return io.StringIO(json.dumps({"system": SYSTEM}))

    monkeypatch.setattr(dependencies.urllib.request, "urlopen", request)
    monkeypatch.setattr(dependencies.subprocess, "run", lambda *a, **kw: pytest.fail("local process probe"))
    monkeypatch.setattr(dependencies.importlib.metadata, "version", lambda *a: pytest.fail("local package probe"))
    monkeypatch.setattr(dependencies, "_discover_models", lambda *a: pytest.fail("local model probe"))
    monkeypatch.setattr(dependencies, "_discover_custom_nodes", lambda *a: pytest.fail("local node probe"))
    return dependencies.inspect_external_runtime("http://comfy.test")


def test_live_external_facts_and_launch_intent_are_distinct(remote, tmp_path):
    report = dependencies.compare_runtime(REQUIREMENTS, target=remote, runtime_root=tmp_path)
    assert report["ok"] is True
    assert report["status"] == "unverified"
    assert report["warnings"]
    assert report["mismatches"] == []
    assert report["actual"]["observed_argv"] == ARGV
    assert report["actual"]["python_version"] == "3.12.3"
    assert report["declared_runtime"]["launch_flags"] == REQUIREMENTS["launch_flags"]
    checks = {row["path"]: row for row in report["checks"]}
    assert checks["comfy_commit"]["status"] == "unverified"
    assert checks["launch_flags"]["status"] == "unverified"
    for name in ["comfy_version", "packages.torch", "packages.comfy-kitchen", "packages.comfy-aimdo"]:
        assert checks[name]["status"] == "matching"


def test_external_partial_package_inventory_is_not_missing(remote):
    report = dependencies.compare_runtime({"packages": {"not-reported": "==1"}}, target=remote)
    assert report["checks"][0]["status"] == "unverified"
    assert report["ok"] is True


def test_external_known_incompatible_version_still_blocks(remote):
    report = dependencies.compare_runtime({"packages": {"torch": "==1.0"}}, target=remote)
    assert report["ok"] is False
    assert report["status"] == "incompatible"


def test_external_launch_flags_can_be_strictly_enforced(remote):
    report = dependencies.compare_runtime(REQUIREMENTS, target=remote, strict_external_launch_flags=True)
    assert report["ok"] is False
    assert next(row for row in report["checks"] if row["path"] == "launch_flags")["status"] == "incompatible"


def test_managed_launch_flags_remain_enforced():
    report = dependencies.compare_runtime(
        {"launch_flags": REQUIREMENTS["launch_flags"]},
        target={"managed": True, "launch_flags": ARGV},
    )
    assert report["ok"] is False
    assert report["status"] == "incompatible"
    matching = dependencies.compare_runtime(
        {"launch_flags": REQUIREMENTS["launch_flags"]},
        target={"managed": True, "launch_flags": [*ARGV, *REQUIREMENTS["launch_flags"]]},
    )
    assert matching["status"] == "matching"


def test_runtime_gate_ignores_helper_report_and_root(remote, tmp_path):
    workflow = SimpleNamespace(requirements=SimpleNamespace(runtime=RuntimeRequirements.from_dict(REQUIREMENTS)), metadata={})
    report = _dependency_check(
        workflow, config=SessionConfig(runtime_root=str(tmp_path)),
        dependency_mode="reuse", server_url="http://comfy.test",
        target={"packages": {"torch": "wrong-helper-version"}},
        dependency_report={"status": "incompatible", "ok": False, "mode": "reuse"},
    )
    assert report["ok"] is True
    assert report["actual"] == remote


def test_unavailable_external_server_remains_unverified(monkeypatch):
    def unavailable(*a, **kw):
        raise OSError("not reachable")
    monkeypatch.setattr(dependencies.urllib.request, "urlopen", unavailable)
    actual = dependencies.inspect_external_runtime("http://comfy.test")
    assert actual["target_probe"] == "unverified"
    report = dependencies.compare_runtime(REQUIREMENTS, target=actual)
    assert report["ok"] is True
    assert report["status"] == "unverified"
