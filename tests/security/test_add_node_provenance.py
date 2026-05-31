"""T6: `_provenance` reserved kwarg on add_node/node/add_block_node.

Verifies:
* outside any scope, `add_node` tags `agent_authored`;
* inside `untrusted_scope()`, it tags `untrusted_source`;
* explicit `_provenance=...` overrides the ContextVar default;
* `_provenance` never leaks into `node.inputs` via add_node, node(), or
  add_block_node.
"""

from __future__ import annotations

from vibecomfy.blocks._utils import add_block_node
from vibecomfy.security.gate import requesting_provenance, untrusted_scope
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import VibeWorkflow, WorkflowSource


def _new_wf() -> VibeWorkflow:
    return VibeWorkflow(id="test-wf", source=WorkflowSource(id="test-wf"))


def test_add_node_outside_scope_is_agent_authored():
    wf = _new_wf()
    node = wf.add_node("CLIPTextEncode")
    assert node.metadata[PROVENANCE_KEY] == "agent_authored"
    assert "_provenance" not in node.inputs


def test_add_node_inside_untrusted_scope_is_untrusted_source():
    wf = _new_wf()
    with untrusted_scope():
        node = wf.add_node("CLIPTextEncode")
    assert node.metadata[PROVENANCE_KEY] == "untrusted_source"
    assert "_provenance" not in node.inputs
    # ContextVar restored
    assert requesting_provenance.get() == "agent_authored"


def test_explicit_provenance_overrides_contextvar():
    wf = _new_wf()
    with untrusted_scope():
        node = wf.add_node("CLIPTextEncode", _provenance="user_confirmed")
    assert node.metadata[PROVENANCE_KEY] == "user_confirmed"
    assert "_provenance" not in node.inputs

    wf2 = _new_wf()
    node2 = wf2.add_node("CLIPTextEncode", _provenance="untrusted_source")
    assert node2.metadata[PROVENANCE_KEY] == "untrusted_source"
    assert "_provenance" not in node2.inputs

    wf3 = _new_wf()
    node3 = wf3.add_node("CLIPTextEncode", _provenance="agent_generated")
    assert node3.metadata[PROVENANCE_KEY] == "agent_generated"
    assert "_provenance" not in node3.inputs


def test_add_node_does_not_leak_provenance_into_inputs():
    wf = _new_wf()
    node = wf.add_node("CLIPTextEncode", text="hello", _provenance="agent_authored")
    assert node.inputs == {"text": "hello"}
    assert "_provenance" not in node.inputs


def test_node_builder_does_not_leak_provenance_into_inputs():
    wf = _new_wf()
    builder = wf.node("CLIPTextEncode", text="hi", _provenance="user_confirmed")
    node = builder.node  # _NodeBuilder.node attr
    assert "_provenance" not in node.inputs
    assert node.metadata[PROVENANCE_KEY] == "user_confirmed"


def test_node_builder_default_provenance_is_agent_authored():
    wf = _new_wf()
    builder = wf.node("CLIPTextEncode", text="hi")
    node = builder.node
    assert node.metadata[PROVENANCE_KEY] == "agent_authored"
    assert "_provenance" not in node.inputs


def test_node_builder_inside_untrusted_scope():
    wf = _new_wf()
    with untrusted_scope():
        builder = wf.node("CLIPTextEncode", text="hi")
    node = builder.node
    assert node.metadata[PROVENANCE_KEY] == "untrusted_source"
    assert "_provenance" not in node.inputs


def test_add_block_node_does_not_leak_provenance_into_inputs():
    wf = _new_wf()
    node = add_block_node(
        wf,
        dotted_name="blocks.test.dummy",
        class_type="CLIPTextEncode",
        inputs={"text": "hi", "_provenance": "user_confirmed"},
    )
    assert "_provenance" not in node.inputs
    assert node.inputs == {"text": "hi"}
    assert node.metadata[PROVENANCE_KEY] == "user_confirmed"


def test_add_block_node_default_provenance_is_agent_authored():
    wf = _new_wf()
    node = add_block_node(
        wf,
        dotted_name="blocks.test.dummy",
        class_type="CLIPTextEncode",
        inputs={"text": "hi"},
    )
    assert node.metadata[PROVENANCE_KEY] == "agent_authored"
    assert "_provenance" not in node.inputs


def test_add_block_node_inside_untrusted_scope():
    wf = _new_wf()
    with untrusted_scope():
        node = add_block_node(
            wf,
            dotted_name="blocks.test.dummy",
            class_type="CLIPTextEncode",
            inputs={"text": "hi"},
        )
    assert node.metadata[PROVENANCE_KEY] == "untrusted_source"
    assert "_provenance" not in node.inputs
