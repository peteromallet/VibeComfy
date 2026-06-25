"""S4 — capability fence on install_pack (Step 9 / T10).

Validates:
  * gate fires AFTER parameter validation (bad args raise ValueError, not
    CapabilityFenceError) and BEFORE any subprocess call (no `git clone` /
    `pip install` / cm-cli invocation is recorded when the gate raises).
  * headless + ``with untrusted_scope():`` raises ``CapabilityFenceError``.
  * ``--yes`` (``assume_yes=True``) allows the operation through and records
    an audit entry for the bypass.
  * the three current callers (``commands/nodes.py``, ``runtime/session.py``)
    inherit ``agent_authored`` via the safe ContextVar default, so the gate
    allows under that ambient provenance.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Sequence

import pytest

import vibecomfy.comfy_nodes.agent.routes as agent_routes
import vibecomfy.node_packs as node_packs
import vibecomfy.node_packs._install as node_packs_install
from vibecomfy.node_packs import install_pack
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    requesting_provenance,
    set_gate_context,
    untrusted_scope,
)


class _RecordingRunner:
    """Fake ``subprocess.run`` that records argv and never actually executes."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(
        self,
        args: Sequence[str],
        *,
        check: bool,
        capture_output: bool,
        text: bool,
        cwd: str | Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        return subprocess.CompletedProcess(list(args), 0, stdout="", stderr="")


def _no_cm_cli(install_root: Path, runner: Any) -> list[str] | None:
    return None


def _install_proposal(
    *,
    expected_classes: list[str] | None = None,
    validation_mode: str = "class_validatable",
    stable_install_hash: str | None = None,
    confirmed: bool = True,
) -> dict[str, Any]:
    pack = {
        "slug": "ComfyUI-VideoHelperSuite",
        "source": "comfyui-manager",
        "url": "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git",
        "name": "ComfyUI-VideoHelperSuite",
    }
    classes = expected_classes if expected_classes is not None else ["VHS_VideoCombine"]
    candidate = {
        "pack": pack,
        "expected_classes": classes,
        "validation_mode": validation_mode,
        "stable_install_hash": stable_install_hash
        or agent_routes._install_intent_hash(pack, classes, validation_mode),
    }
    return {"candidate": candidate, "user_confirmed": confirmed}


@pytest.fixture(autouse=True)
def _isolated_gate_context():
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        # Re-installing prior context via reset; tests share process state.
        try:
            from vibecomfy.security.gate import _gate_context_var
            _gate_context_var.reset(token)
        except Exception:
            pass


def test_gate_raises_in_headless_under_untrusted_scope(tmp_path):
    runner = _RecordingRunner()
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    lockfile = tmp_path / "custom_nodes.lock"

    with untrusted_scope():
        with pytest.raises(CapabilityFenceError) as excinfo:
            install_pack(
                name=None,
                repo="https://github.com/attacker/evil-pack.git",
                install_root=install_root,
                lockfile_path=lockfile,
                runner=runner,
                cm_cli_resolver=_no_cm_cli,
            )

    detail = excinfo.value.detail
    assert detail["operation"] == "install_pack"
    assert detail["provenance"] == "untrusted_source"
    assert set(detail["capabilities"]) == {"code_exec", "network", "filesystem_write"}
    # No subprocess call was made — gate fired before git clone / pip install.
    assert runner.calls == []


def test_parameter_validation_errors_raise_before_gate(tmp_path):
    """Invariant: bad args produce ValueError, not CapabilityFenceError."""
    runner = _RecordingRunner()
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    lockfile = tmp_path / "custom_nodes.lock"

    # Both name and repo None — fails the first validation check in install_pack.
    with untrusted_scope():
        with pytest.raises(ValueError):
            install_pack(
                name=None,
                repo=None,
                install_root=install_root,
                lockfile_path=lockfile,
                runner=runner,
                cm_cli_resolver=_no_cm_cli,
            )

    # Unknown registry name with no repo — also a ValueError, fired before gate.
    with untrusted_scope():
        with pytest.raises(ValueError):
            install_pack(
                name="definitely-not-a-real-pack-xyz-9999",
                repo=None,
                install_root=install_root,
                lockfile_path=lockfile,
                runner=runner,
                cm_cli_resolver=_no_cm_cli,
            )

    assert runner.calls == []


def test_assume_yes_allows_install_and_audits_bypass(tmp_path, monkeypatch, _isolated_gate_context):
    """--yes flag passes the gate and records an audit entry for the bypass."""
    ctx = _isolated_gate_context
    ctx.assume_yes = True

    runner = _RecordingRunner()
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    lockfile = tmp_path / "custom_nodes.lock"

    # Short-circuit downstream helpers so the call returns without needing a real
    # git repo on disk after the gate decision.
    monkeypatch.setattr(node_packs_install, "_git_head", lambda *_a, **_k: "deadbeef" * 5)
    monkeypatch.setattr(
        node_packs_install,
        "_lock_entry_for_pack",
        lambda *a, **k: None,  # forces an InstallResult("failed", ...) AFTER clone
    )

    with untrusted_scope():
        result = install_pack(
            name=None,
            repo="https://github.com/example/some-pack.git",
            install_root=install_root,
            lockfile_path=lockfile,
            runner=runner,
            cm_cli_resolver=_no_cm_cli,
        )

    # Gate allowed → install path proceeded into _install_pack_via_clone, which
    # invoked the runner (this proves the gate did NOT raise).
    assert runner.calls, "runner should have been invoked once the gate allowed"
    assert runner.calls[0][0:2] == ["git", "clone"]
    # Audit entry recorded the assume_yes bypass.
    bypass_entries = [
        e
        for e in ctx.audit
        if e["operation"] == "install_pack" and e["reason"] == "assume_yes_bypass"
    ]
    assert len(bypass_entries) == 1
    assert bypass_entries[0]["decision"] == "allow"
    assert bypass_entries[0]["provenance"] == "untrusted_source"
    # The InstallResult propagated downstream failure but the gate-side audit is what we assert.
    assert result.name  # sanity


def test_agent_authored_default_allows_without_prompt(tmp_path, monkeypatch, _isolated_gate_context):
    """The three current callers run under the safe default → agent_authored → allow."""
    ctx = _isolated_gate_context
    runner = _RecordingRunner()
    install_root = tmp_path / "custom_nodes"
    install_root.mkdir()
    lockfile = tmp_path / "custom_nodes.lock"

    monkeypatch.setattr(node_packs_install, "_git_head", lambda *_a, **_k: "cafe" * 10)
    monkeypatch.setattr(node_packs_install, "_lock_entry_for_pack", lambda *a, **k: None)

    # No untrusted_scope — ambient ContextVar default is "agent_authored".
    assert requesting_provenance.get() == "agent_authored"

    install_pack(
        name=None,
        repo="https://github.com/example/agent-pack.git",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=runner,
        cm_cli_resolver=_no_cm_cli,
    )

    # Gate allowed under trusted_provenance.
    allow_entries = [
        e
        for e in ctx.audit
        if e["operation"] == "install_pack" and e["reason"] == "trusted_provenance"
    ]
    assert len(allow_entries) == 1
    assert allow_entries[0]["provenance"] == "agent_authored"
    # And the install path actually ran (so the gate did not silently raise).
    assert runner.calls, "runner should have been invoked under agent_authored"


def test_node_pack_install_route_rejects_evidence_only_normal_cta_before_install(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(node_packs, "install_pack", lambda **kwargs: calls.append(kwargs))

    response = agent_routes._handle_node_pack_install(
        _install_proposal(expected_classes=[], validation_mode="evidence_only")
    )

    assert response["ok"] is False
    assert response["status"] == "rejected"
    assert response["error"] == "evidence_only_rejected"
    assert "evidence_only" in response["message"]
    assert calls == []


def test_node_pack_install_route_requires_explicit_user_confirmation(monkeypatch):
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(node_packs, "install_pack", lambda **kwargs: calls.append(kwargs))

    response = agent_routes._handle_node_pack_install(_install_proposal(confirmed=False))

    assert response["ok"] is False
    assert response["status"] == "rejected"
    assert response["error"] == "confirmation_required"
    assert calls == []


def test_node_pack_install_route_surfaces_capability_gate_rejection(monkeypatch):
    calls: list[dict[str, Any]] = []

    def _blocked_install(**kwargs):
        calls.append(kwargs)
        raise CapabilityFenceError(
            {
                "operation": "install_pack",
                "provenance": "untrusted_source",
                "capabilities": ["code_exec", "network", "filesystem_write"],
                "reason": "non_interactive_confirmation_required",
            }
        )

    monkeypatch.setattr(node_packs, "install_pack", _blocked_install)
    monkeypatch.setattr(
        agent_routes,
        "_fetch_object_info_for_install_validation",
        lambda: pytest.fail("post-install validation must not run after a gate rejection"),
    )

    response = agent_routes._handle_node_pack_install(_install_proposal())

    assert response["ok"] is False
    assert response["status"] == "rejected"
    assert response["error"] == "capability_gate_rejected"
    assert response["gate_detail"]["operation"] == "install_pack"
    assert len(calls) == 1


def test_node_pack_install_route_calls_existing_installer_for_confirmed_class_validatable(monkeypatch):
    calls: list[dict[str, Any]] = []

    def _fake_install_pack(**kwargs):
        calls.append(kwargs)
        return node_packs_install.InstallResult(
            name="ComfyUI-VideoHelperSuite",
            status="installed",
            git_commit_sha="abc123",
            error=None,
        )

    monkeypatch.setattr(node_packs, "install_pack", _fake_install_pack)
    monkeypatch.setattr(
        agent_routes,
        "_fetch_object_info_for_install_validation",
        lambda: {"VHS_VideoCombine": {}},
    )

    response = agent_routes._handle_node_pack_install(_install_proposal())

    assert response["ok"] is True
    assert response["status"] == "installed"
    assert response["validation_status"] == "installed"
    assert response["validated"] is True
    assert response["expected_classes"] == ["VHS_VideoCombine"]
    assert response["validation_mode"] == "class_validatable"
    assert len(calls) == 1
    assert calls[0]["name"] == "ComfyUI-VideoHelperSuite"
    assert calls[0]["repo"] == "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
    assert calls[0]["pack_ref"].slug == "ComfyUI-VideoHelperSuite"
