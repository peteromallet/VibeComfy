"""Tests for vibecomfy.security.provenance — S4 capability fence."""

from __future__ import annotations

import pytest

from vibecomfy.security import provenance
from vibecomfy.security.provenance import PROVENANCE_KEY
from vibecomfy.workflow import VibeNode, VibeWorkflow, WorkflowSource


def _node(**meta) -> VibeNode:
    return VibeNode(id="n1", class_type="CLIPTextEncode", metadata=dict(meta))


def _wf(node: VibeNode) -> VibeWorkflow:
    wf = VibeWorkflow(id="t", source=WorkflowSource(id="t"))
    wf.nodes[node.id] = node
    return wf


# --- read() fail-closed ----------------------------------------------------


def test_read_missing_key_returns_untrusted_source():
    node = _node()
    assert provenance.read(node) == "untrusted_source"


def test_read_none_value_returns_untrusted_source():
    node = _node(provenance=None)
    assert provenance.read(node) == "untrusted_source"


def test_read_unknown_value_returns_untrusted_source():
    node = _node(provenance="bogus")
    assert provenance.read(node) == "untrusted_source"


def test_read_no_metadata_attr_returns_untrusted_source():
    class Bare:
        pass

    assert provenance.read(Bare()) == "untrusted_source"


# --- round-trip set/read ---------------------------------------------------


@pytest.mark.parametrize(
    "value", ["untrusted_source", "agent_authored", "agent_generated", "user_confirmed"]
)
def test_tag_then_read_roundtrip(value):
    node = _node()
    provenance.tag(node, value)
    assert node.metadata[PROVENANCE_KEY] == value
    assert provenance.read(node) == value


def test_tag_rejects_invalid_value():
    node = _node()
    with pytest.raises(ValueError):
        provenance.tag(node, "fully_trusted")  # type: ignore[arg-type]


# --- confirm() promotion + idempotency ------------------------------------


def test_confirm_promotes_untrusted_to_user_confirmed():
    node = _node(provenance="untrusted_source")
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_idempotent_on_user_confirmed():
    node = _node(provenance="user_confirmed")
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_idempotent_on_agent_authored():
    node = _node(provenance="agent_authored")
    provenance.confirm(node)
    assert provenance.read(node) == "agent_authored"


def test_confirm_idempotent_on_agent_generated():
    node = _node(provenance="agent_generated")
    provenance.confirm(node)
    assert provenance.read(node) == "agent_generated"


def test_confirm_promotes_missing_key():
    """Fresh node with no provenance reads as untrusted_source — confirm promotes it."""
    node = _node()
    provenance.confirm(node)
    assert provenance.read(node) == "user_confirmed"


def test_confirm_never_raises_on_missing_metadata():
    class Bare:
        pass

    provenance.confirm(Bare())  # must not raise


# --- fresh-node read default -----------------------------------------------


def test_fresh_vibenode_reads_untrusted_source():
    """A freshly constructed VibeNode has no provenance metadata — fail-closed."""
    node = VibeNode(id="x", class_type="CLIPTextEncode")
    assert provenance.read(node) == "untrusted_source"
    assert node.provenance == "untrusted_source"


# --- VibeWorkflow.confirm_node + VibeNode.provenance property -------------


def test_vibenode_provenance_property_reads_through():
    node = _node(provenance="agent_authored")
    assert node.provenance == "agent_authored"


def test_vibenode_provenance_property_reads_agent_generated():
    node = _node(provenance="agent_generated")
    assert node.provenance == "agent_generated"


def test_vibeworkflow_confirm_node_promotes():
    node = _node(provenance="untrusted_source")
    wf = _wf(node)
    result = wf.confirm_node("n1")
    assert result is wf
    assert wf.nodes["n1"].provenance == "user_confirmed"


def test_vibeworkflow_confirm_node_idempotent_on_trusted():
    node = _node(provenance="user_confirmed")
    wf = _wf(node)
    wf.confirm_node("n1")
    assert wf.nodes["n1"].provenance == "user_confirmed"


def test_vibeworkflow_confirm_node_leaves_agent_generated_unpromoted():
    node = _node(provenance="agent_generated")
    wf = _wf(node)
    wf.confirm_node("n1")
    assert wf.nodes["n1"].provenance == "agent_generated"


def test_vibeworkflow_confirm_node_unknown_raises_keyerror():
    wf = _wf(_node(provenance="untrusted_source"))
    with pytest.raises(KeyError):
        wf.confirm_node("missing")


# --- agent_generated non-promotion boundary ---------------------------------

@pytest.mark.parametrize(
    "start, expected",
    [
        ("agent_generated", "agent_generated"),
        ("untrusted_source", "user_confirmed"),
        ("user_confirmed", "user_confirmed"),
        ("agent_authored", "agent_authored"),
    ],
)
def test_confirm_promotion_boundary_table(start, expected):
    """Full promotion table: only untrusted_source promotes to user_confirmed;
    agent_generated, agent_authored, and user_confirmed remain unchanged."""
    node = _node(provenance=start)
    provenance.confirm(node)
    assert provenance.read(node) == expected


def test_agent_generated_survives_multiple_confirm_calls():
    """Multiple confirm() calls must not accumulate into a promotion."""
    node = _node(provenance="agent_generated")
    for _ in range(5):
        provenance.confirm(node)
    assert provenance.read(node) == "agent_generated"


def test_agent_generated_survives_confirm_node_multiple_calls():
    """Multiple VibeWorkflow.confirm_node() calls must not promote agent_generated."""
    node = _node(provenance="agent_generated")
    wf = _wf(node)
    for _ in range(5):
        wf.confirm_node("n1")
    assert wf.nodes["n1"].provenance == "agent_generated"


def test_agent_generated_node_tagged_after_confirm_stays_agent_generated():
    """A node tagged agent_generated after a prior confirm() must not be
    promoted by a subsequent confirm() — the tag itself determines the outcome."""
    node = _node()
    provenance.confirm(node)  # promotes missing → user_confirmed
    assert provenance.read(node) == "user_confirmed"
    provenance.tag(node, "agent_generated")
    assert provenance.read(node) == "agent_generated"
    provenance.confirm(node)
    assert provenance.read(node) == "agent_generated"


def test_provenance_literal_includes_agent_generated():
    """The agent_generated literal is in the Provenance type's valid set."""
    from vibecomfy.security.provenance import Provenance

    valid = set(Provenance)
    assert "agent_generated" in valid
    assert "agent_generated" in provenance._VALID


# --- Law 5 (batch 5): closed typed set + monotone lattice -------------------


def test_provenance_is_a_closed_typed_enum():
    """Provenance is a closed typed set (str enum), not an open string."""
    import enum

    assert issubclass(provenance.Provenance, str)
    assert issubclass(provenance.Provenance, enum.Enum)
    assert set(provenance.Provenance) == {
        provenance.Provenance.UNTRUSTED_SOURCE,
        provenance.Provenance.AGENT_AUTHORED,
        provenance.Provenance.AGENT_GENERATED,
        provenance.Provenance.USER_CONFIRMED,
    }
    # The closed set is exactly the taxonomy — nothing else is valid.
    for bogus in ("fully_trusted", "template", "user_edited", ""):
        assert provenance.coerce(bogus) == provenance.Provenance.UNTRUSTED_SOURCE


def test_coerce_fails_closed_on_none_and_bogus():
    assert provenance.coerce(None) == provenance.Provenance.UNTRUSTED_SOURCE
    assert provenance.coerce("bogus") == provenance.Provenance.UNTRUSTED_SOURCE
    assert provenance.coerce(42) == provenance.Provenance.UNTRUSTED_SOURCE
    # Known plain strings normalize to the typed member.
    assert provenance.coerce("untrusted_source") is provenance.Provenance.UNTRUSTED_SOURCE
    assert provenance.coerce("agent_generated") is provenance.Provenance.AGENT_GENERATED


def test_ordering_is_reflexive_antisymmetric_and_transitive():
    """The taint ordering is a partial order (here a total order)."""
    members = list(provenance.Provenance)
    # Reflexive.
    for member in members:
        assert provenance.dominates(member, member)
    # Antisymmetric: dominates(a, b) and dominates(b, a) implies a == b.
    for a in members:
        for b in members:
            if provenance.dominates(a, b) and provenance.dominates(b, a):
                assert a == b
    # Transitive: dominates(a, b) and dominates(b, c) implies dominates(a, c).
    for a in members:
        for b in members:
            for c in members:
                if provenance.dominates(a, b) and provenance.dominates(b, c):
                    assert provenance.dominates(a, c)


def test_ordering_has_untrusted_source_at_max_taint():
    """untrusted_source dominates every other provenance (fail-closed top)."""
    for member in provenance.Provenance:
        assert provenance.dominates("untrusted_source", member)
        if member is not provenance.Provenance.UNTRUSTED_SOURCE:
            assert not provenance.dominates(member, "untrusted_source")
    # The trust ladder matches the existing confirm() promotion table.
    assert provenance.dominates(
        provenance.Provenance.AGENT_GENERATED, provenance.Provenance.USER_CONFIRMED
    )


def test_join_is_idempotent_commutative_and_associative():
    """join is a semilattice: idempotent, commutative, associative."""
    members = list(provenance.Provenance)
    for a in members:
        # Idempotent.
        assert provenance.join(a, a) == a
        for b in members:
            # Commutative.
            assert provenance.join(a, b) == provenance.join(b, a)
            for c in members:
                # Associative.
                left = provenance.join(provenance.join(a, b), c)
                right = provenance.join(a, provenance.join(b, c))
                assert left == right


def test_join_is_max_taint_and_never_downgrades():
    """join returns the max-taint operand and dominates both operands."""
    members = list(provenance.Provenance)
    for a in members:
        for b in members:
            joined = provenance.join(a, b)
            assert joined == provenance.join(b, a)
            # Never downgraded: the result dominates each operand.
            assert provenance.dominates(joined, a)
            assert provenance.dominates(joined, b)
            # Max-taint: the result is one of the operands, and it is the
            # operand with the higher taint rank.
            assert joined in (a, b)
    # The canonical examples: untrusted input poisons the join; an agent edit
    # on an untrusted node keeps it untrusted (no laundering).
    assert provenance.join("untrusted_source", "user_confirmed") == "untrusted_source"
    assert provenance.join("untrusted_source", "agent_generated") == "untrusted_source"
    assert provenance.join("user_confirmed", "agent_generated") == "agent_generated"


def test_join_accepts_mixed_strings_and_members_and_empty_join_fails_closed():
    assert provenance.join("user_confirmed", provenance.Provenance.AGENT_GENERATED) == (
        provenance.Provenance.AGENT_GENERATED
    )
    assert provenance.join() == provenance.Provenance.UNTRUSTED_SOURCE
    # Invalid operands coerce fail-closed to untrusted and poison the join.
    assert provenance.join("bogus", "user_confirmed") == "untrusted_source"
