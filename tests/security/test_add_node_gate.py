"""S4 T9 — capability fence pre-gate on VibeWorkflow.add_node.

Verifies the confused-deputy gate fires equally on the three IR-write entry
points: ``add_node``, ``node``, and ``add_block_node``. The compile path is
intentionally NOT gated (see comment in ``add_node``).
"""

from __future__ import annotations

import pytest

from vibecomfy.blocks._utils import add_block_node
from vibecomfy.security.gate import (
    CapabilityFenceError,
    GateContext,
    set_gate_context,
    untrusted_scope,
)
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


@pytest.fixture
def headless_ctx():
    ctx = GateContext(non_interactive=True, assume_yes=False, audit=[])
    token = set_gate_context(ctx)
    try:
        yield ctx
    finally:
        from vibecomfy.security.gate import _gate_context_var
        _gate_context_var.reset(token)


def _wf() -> VibeWorkflow:
    return VibeWorkflow(id="t9", source=WorkflowSource(id="t9"))


def test_confused_deputy_probe_raises_in_headless(headless_ctx):
    wf = _wf()
    with pytest.raises(CapabilityFenceError) as ei:
        with untrusted_scope():
            wf.add_node("SaveImage", filename_prefix="../../etc/x")
    detail = ei.value.detail
    assert detail["operation"] == "add_node"
    assert detail["class_type"] == "SaveImage"
    assert detail["provenance"] == "untrusted_source"
    assert "filesystem_write" in detail["capabilities"]
    assert detail["details"]["params"]["filename_prefix"] == "../../etc/x"
    # State is unchanged: the gate fired before the node was added.
    assert "SaveImage" not in {n.class_type for n in wf.nodes.values()}


def test_explicit_user_confirmed_succeeds(headless_ctx):
    wf = _wf()
    with untrusted_scope():
        node = wf.add_node(
            "SaveImage",
            filename_prefix="ok/",
            _provenance="user_confirmed",
        )
    assert node.metadata[PROVENANCE_KEY] == "user_confirmed"
    assert "_provenance" not in node.inputs


def test_explicit_agent_generated_succeeds(headless_ctx):
    wf = _wf()
    with untrusted_scope():
        node = wf.add_node(
            "SaveImage",
            filename_prefix="ok/",
            _provenance="agent_generated",
        )
    assert node.metadata[PROVENANCE_KEY] == "agent_generated"
    assert "_provenance" not in node.inputs


def test_passthrough_class_never_prompts(headless_ctx):
    wf = _wf()
    with untrusted_scope():
        node = wf.add_node("CLIPTextEncode", text="hi")
    assert node.metadata[PROVENANCE_KEY] == "untrusted_source"


def test_gate_fires_via_node_builder(headless_ctx):
    wf = _wf()
    with pytest.raises(CapabilityFenceError):
        with untrusted_scope():
            wf.node("SaveImage", filename_prefix="../../etc/x")


def test_gate_fires_via_add_block_node(headless_ctx):
    wf = _wf()
    with pytest.raises(CapabilityFenceError):
        with untrusted_scope():
            add_block_node(
                wf,
                "save.image",
                "SaveImage",
                inputs={"filename_prefix": "../../etc/x"},
            )


def test_node_builder_respects_explicit_user_confirmed(headless_ctx):
    wf = _wf()
    with untrusted_scope():
        builder = wf.node(
            "SaveImage",
            filename_prefix="ok/",
            _provenance="user_confirmed",
        )
    assert builder.node.metadata[PROVENANCE_KEY] == "user_confirmed"
    assert "_provenance" not in builder.node.inputs


def test_add_block_node_respects_explicit_user_confirmed(headless_ctx):
    wf = _wf()
    with untrusted_scope():
        node = add_block_node(
            wf,
            "save.image",
            "SaveImage",
            inputs={"filename_prefix": "ok/", "_provenance": "user_confirmed"},
        )
    assert node.metadata[PROVENANCE_KEY] == "user_confirmed"
    assert "_provenance" not in node.inputs


def test_agent_authored_default_succeeds(headless_ctx):
    wf = _wf()
    # Outside untrusted_scope: default provenance is agent_authored → allow.
    node = wf.add_node("SaveImage", filename_prefix="run/")
    assert node.metadata[PROVENANCE_KEY] == "agent_authored"
