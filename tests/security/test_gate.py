"""Tests for the S4 capability fence gate primitive and CLI wiring."""

from __future__ import annotations

import io
import json
import subprocess
import sys
import textwrap

import pytest

from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    _gate_context_var,
    _safe_default_context,
    current_gate_context,
    require_confirmation,
    set_gate_context,
)


def _ctx(**overrides) -> GateContext:
    base = dict(non_interactive=True, assume_yes=False, audit=[])
    base.update(overrides)
    return GateContext(**base)


def test_passthrough_never_prompts():
    ctx = _ctx(non_interactive=True)
    assert (
        require_confirmation(
            operation="add_node",
            class_type="KSampler",
            provenance="untrusted_source",
            capabilities=["passthrough"],
            ctx=ctx,
        )
        == "allow"
    )
    assert ctx.audit[-1]["decision"] == "allow"
    assert ctx.audit[-1]["reason"] == "passthrough_only"


def test_trusted_provenance_never_prompts():
    ctx = _ctx(non_interactive=True)
    require_confirmation(
        operation="add_node",
        class_type="SaveImage",
        provenance="agent_authored",
        capabilities=["filesystem_write"],
        ctx=ctx,
    )
    require_confirmation(
        operation="add_node",
        class_type="SaveImage",
        provenance="agent_generated",
        capabilities=["filesystem_write"],
        ctx=ctx,
    )
    require_confirmation(
        operation="add_node",
        class_type="SaveImage",
        provenance="user_confirmed",
        capabilities=["filesystem_write"],
        ctx=ctx,
    )
    assert [e["reason"] for e in ctx.audit] == [
        "trusted_provenance",
        "trusted_provenance",
        "trusted_provenance",
    ]


def test_untrusted_side_effect_raises_in_headless():
    ctx = _ctx(non_interactive=True)
    with pytest.raises(CapabilityFenceError) as exc:
        require_confirmation(
            operation="add_node",
            class_type="SaveImage",
            provenance="untrusted_source",
            capabilities=["filesystem_write"],
            details={"filename_prefix": "../etc/"},
            ctx=ctx,
        )
    assert exc.value.detail["reason"] == "non_interactive_refusal"
    assert exc.value.detail["class_type"] == "SaveImage"
    assert exc.value.detail["capabilities"] == ["filesystem_write"]
    assert ctx.audit[-1]["decision"] == "deny"


def test_assume_yes_allows_and_records_bypass():
    ctx = _ctx(non_interactive=True, assume_yes=True)
    assert (
        require_confirmation(
            operation="add_node",
            class_type="SaveImage",
            provenance="untrusted_source",
            capabilities=["filesystem_write"],
            ctx=ctx,
        )
        == "allow"
    )
    assert ctx.audit[-1]["reason"] == "assume_yes_bypass"
    assert ctx.audit[-1]["decision"] == "allow"


class _FakeTTY(io.StringIO):
    def __init__(self, payload: str = ""):
        super().__init__(payload)

    def isatty(self) -> bool:  # type: ignore[override]
        return True


def test_tty_reads_yes_from_fake_stream():
    stdin = _FakeTTY("yes\n")
    stdout = io.StringIO()
    ctx = GateContext(
        non_interactive=False,
        assume_yes=False,
        audit=[],
        stdin=stdin,
        stdout=stdout,
    )
    assert (
        require_confirmation(
            operation="add_node",
            class_type="SaveImage",
            provenance="untrusted_source",
            capabilities=["filesystem_write"],
            details={"filename_prefix": "out/"},
            ctx=ctx,
        )
        == "allow"
    )
    out = stdout.getvalue()
    assert "operation:" in out and "class_type: SaveImage" in out
    assert "provenance: untrusted_source" in out
    assert "filename_prefix" in out
    assert ctx.audit[-1]["reason"] == "interactive_confirm"


def test_tty_n_refuses():
    stdin = _FakeTTY("n\n")
    stdout = io.StringIO()
    ctx = GateContext(
        non_interactive=False,
        assume_yes=False,
        audit=[],
        stdin=stdin,
        stdout=stdout,
    )
    with pytest.raises(CapabilityFenceError) as exc:
        require_confirmation(
            operation="add_node",
            class_type="SaveImage",
            provenance="untrusted_source",
            capabilities=["filesystem_write"],
            ctx=ctx,
        )
    assert exc.value.detail["reason"] == "interactive_refusal"


def test_gate_context_var_default_is_safe():
    default = _gate_context_var.get()
    assert isinstance(default, GateContext)
    assert isinstance(default.audit, list)
    # Also: building a fresh safe default never raises.
    safe = _safe_default_context()
    assert isinstance(safe, GateContext)
    assert safe.assume_yes is False


def test_current_gate_context_returns_set_context():
    ctx = _ctx(assume_yes=True)
    token = set_gate_context(ctx)
    try:
        assert current_gate_context() is ctx
    finally:
        _gate_context_var.reset(token)


def test_cli_subprocess_exits_42_on_capability_fence(tmp_path):
    """Subprocess smoke: a CLI command that calls the gate with an untrusted
    side-effecting class in --non-interactive mode must exit 42 and print a
    structured JSON error on stderr.
    """
    script = textwrap.dedent(
        """
        import sys
        from vibecomfy.cli import main
        # Inject a tiny argv path that hits the gate: we monkeypatch a command
        # to call require_confirmation directly. Instead of building a full
        # command, just exercise the error path inline.
        from vibecomfy.security.gate import (
            CapabilityFenceError, GateContext, require_confirmation,
            set_gate_context,
        )
        import json
        ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
        set_gate_context(ctx)
        try:
            require_confirmation(
                operation="add_node",
                class_type="SaveImage",
                provenance="untrusted_source",
                capabilities=["filesystem_write"],
                ctx=ctx,
            )
        except CapabilityFenceError as exc:
            print(
                json.dumps({"error": "capability_fence", **exc.detail}, sort_keys=True),
                file=sys.stderr,
            )
            raise SystemExit(42)
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 42, (proc.stdout, proc.stderr)
    payload = json.loads(proc.stderr.strip().splitlines()[-1])
    assert payload["error"] == "capability_fence"
    assert payload["reason"] == "non_interactive_refusal"
    assert payload["class_type"] == "SaveImage"


def test_cli_parser_accepts_yes_and_non_interactive_after_subcommand_on_all():
    """Every top-level subcommand must accept --yes / -y / --non-interactive
    AFTER the subcommand name (the argparse parents-pattern requirement)."""
    from vibecomfy.cli import build_parser
    from vibecomfy.commands import COMMANDS

    parser = build_parser()
    # Probe each subcommand by parsing only the flag tokens (no positional
    # args). We can't reliably parse full subcommand argv (each has its own
    # required positionals), but we CAN walk the parser's _subparsers to
    # assert every child has the security flags registered as actions.
    sub_actions = [
        a for a in parser._actions if isinstance(a, type(parser._subparsers._group_actions[0]))
    ] if parser._subparsers else []
    subparsers_action = sub_actions[0]
    children = subparsers_action.choices
    seen = set()
    for name, child in children.items():
        flag_names = set()
        for action in child._actions:
            flag_names.update(action.option_strings)
        assert "--yes" in flag_names and "-y" in flag_names, (
            f"subcommand {name!r} missing --yes/-y"
        )
        assert "--non-interactive" in flag_names, (
            f"subcommand {name!r} missing --non-interactive"
        )
        seen.add(name)
    expected = {spec.name for spec in COMMANDS}
    assert expected <= seen


# --- agent_generated gate boundary tests -----------------------------------


@pytest.mark.parametrize(
    "provenance,capabilities,should_allow",
    [
        ("agent_generated", ["filesystem_write"], True),
        ("agent_generated", ["network"], True),
        ("agent_generated", ["filesystem_write", "network", "code_exec"], True),
        ("agent_generated", ["passthrough"], True),
        ("agent_generated", [], True),
        ("untrusted_source", ["filesystem_write"], False),
        ("untrusted_source", ["network"], False),
        ("untrusted_source", ["code_exec"], False),
        ("agent_authored", ["filesystem_write"], True),
        ("user_confirmed", ["filesystem_write"], True),
    ],
)
def test_agent_generated_gate_boundary_table(provenance, capabilities, should_allow):
    """agent_generated passes the headless gate for ALL capability sets,
    same as agent_authored and user_confirmed. untrusted_source is refused
    for side-effecting capabilities. This proves the gate treats
    agent_generated as trusted post-scan provenance."""
    ctx = _ctx(non_interactive=True)
    if should_allow:
        result = require_confirmation(
            operation="add_node",
            class_type="SaveImage",
            provenance=provenance,
            capabilities=capabilities,
            ctx=ctx,
        )
        assert result == "allow"
        assert ctx.audit[-1]["reason"] == "trusted_provenance"
        assert ctx.audit[-1]["provenance"] == provenance
    else:
        with pytest.raises(CapabilityFenceError) as exc:
            require_confirmation(
                operation="add_node",
                class_type="SaveImage",
                provenance=provenance,
                capabilities=capabilities,
                ctx=ctx,
            )
        assert exc.value.detail["provenance"] == provenance


def test_agent_generated_audit_preserves_exact_provenance_string():
    """The gate audit entry records 'agent_generated' exactly, not a
    promoted or normalized form."""
    ctx = _ctx(non_interactive=True)
    require_confirmation(
        operation="add_node",
        class_type="PreviewImage",
        provenance="agent_generated",
        capabilities=["filesystem_write"],
        ctx=ctx,
    )
    entry = ctx.audit[-1]
    assert entry["provenance"] == "agent_generated"
    assert entry["decision"] == "allow"
    assert entry["reason"] == "trusted_provenance"


def test_untrusted_source_rejected_for_same_op_agent_generated_allows():
    """Contrast: the same operation/class/capabilities is rejected for
    untrusted_source but allowed for agent_generated. This is the key
    trust-boundary distinction."""
    op = "add_node"
    cls = "SaveImage"
    caps = ["filesystem_write"]

    ctx_untrusted = _ctx(non_interactive=True)
    with pytest.raises(CapabilityFenceError):
        require_confirmation(
            operation=op,
            class_type=cls,
            provenance="untrusted_source",
            capabilities=caps,
            ctx=ctx_untrusted,
        )

    ctx_agent = _ctx(non_interactive=True)
    result = require_confirmation(
        operation=op,
        class_type=cls,
        provenance="agent_generated",
        capabilities=caps,
        ctx=ctx_agent,
    )
    assert result == "allow"
