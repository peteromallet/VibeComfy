"""Tests for the obligation ledger vocabulary and schema.

Covers:
- class_present, class_absent, value_match, edge_exists, terminal_output_domain
- scope_preserved, obligation_declared
- plan states, stable ids, structural targets, required flags, status/evidence
- deterministic hashable serialization
- unknown/unsupported handling
"""

from __future__ import annotations

import json
import re

import pytest

from vibecomfy.comfy_nodes.agent.obligation_ledger import (
    OBLIGATION_KIND_CLASS_PRESENT,
    OBLIGATION_KIND_CLASS_ABSENT,
    OBLIGATION_KIND_EDGE_EXISTS,
    OBLIGATION_KIND_OBLIGATION_DECLARED,
    OBLIGATION_KIND_SCOPE_PRESERVED,
    OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN,
    OBLIGATION_KIND_VALUE_MATCH,
    OBLIGATION_KINDS,
    OBLIGATION_LEDGER_CONTRACT_VERSION,
    OBLIGATION_SEVERITY_OPTIONAL,
    OBLIGATION_SEVERITY_RECOMMENDED,
    OBLIGATION_SEVERITY_REQUIRED,
    OBLIGATION_SEVERITIES,
    OBLIGATION_STATUS_NOT_EVALUATED,
    OBLIGATION_STATUS_SATISFIED,
    OBLIGATION_STATUS_UNKNOWN,
    OBLIGATION_STATUS_UNSATISFIED,
    OBLIGATION_STATUS_UNSUPPORTED,
    OBLIGATION_STATUSES,
    Obligation,
    ObligationLedger,
    StructuralTarget,
    is_not_evaluated,
    is_required,
    is_satisfied,
    is_unknown,
    is_unsatisfied,
    is_unsupported,
)

# ---------------------------------------------------------------------------
# StructuralTarget
# ---------------------------------------------------------------------------


class TestStructuralTarget:
    def test_to_dict_omits_none(self) -> None:
        target = StructuralTarget(node_id="42", class_type="KSampler")
        payload = target.to_dict()
        assert payload == {"node_id": "42", "class_type": "KSampler"}
        assert "input_name" not in payload

    def test_to_dict_includes_all_set_fields(self) -> None:
        target = StructuralTarget(
            node_id="7",
            class_type="CLIPTextEncode",
            input_name="text",
            output_name="CONDITIONING",
            field="width",
            source_node_id="1",
            source_output="IMAGE",
            target_node_id="2",
            target_input="images",
            role="encoder",
        )
        payload = target.to_dict()
        assert payload["node_id"] == "7"
        assert payload["class_type"] == "CLIPTextEncode"
        assert payload["input_name"] == "text"
        assert payload["output_name"] == "CONDITIONING"
        assert payload["field"] == "width"
        assert payload["source_node_id"] == "1"
        assert payload["source_output"] == "IMAGE"
        assert payload["target_node_id"] == "2"
        assert payload["target_input"] == "images"
        assert payload["role"] == "encoder"

    def test_from_dict_roundtrip(self) -> None:
        original = StructuralTarget(node_id="99", class_type="VAEDecode", role="decoder")
        restored = StructuralTarget.from_dict(original.to_dict())
        assert restored == original

    def test_class_ref_factory(self) -> None:
        target = StructuralTarget.class_ref("CheckpointLoaderSimple")
        assert target.class_type == "CheckpointLoaderSimple"
        assert target.node_id is None

    def test_node_ref_factory(self) -> None:
        target = StructuralTarget.node_ref("10", class_type="EmptyLatentImage")
        assert target.node_id == "10"
        assert target.class_type == "EmptyLatentImage"

    def test_edge_ref_factory(self) -> None:
        target = StructuralTarget.edge_ref("1", "2", source_output="IMAGE", target_input="images")
        assert target.source_node_id == "1"
        assert target.target_node_id == "2"
        assert target.source_output == "IMAGE"
        assert target.target_input == "images"

    def test_value_ref_factory(self) -> None:
        target = StructuralTarget.value_ref("5", field="steps", input_name=None)
        assert target.node_id == "5"
        assert target.field == "steps"
        assert target.input_name is None

    def test_equality_same_values(self) -> None:
        a = StructuralTarget(node_id="1", class_type="Foo")
        b = StructuralTarget(node_id="1", class_type="Foo")
        assert a == b

    def test_inequality_different_values(self) -> None:
        a = StructuralTarget(node_id="1")
        b = StructuralTarget(node_id="2")
        assert a != b

    def test_hashable(self) -> None:
        a = StructuralTarget(node_id="1", class_type="Foo")
        b = StructuralTarget(node_id="1", class_type="Foo")
        assert hash(a) == hash(b)
        # Can be used in a set
        s = {a, b}
        assert len(s) == 1


# ---------------------------------------------------------------------------
# Obligation kind / status / severity constants
# ---------------------------------------------------------------------------


class TestObligationConstants:
    def test_kinds_are_seven(self) -> None:
        assert len(OBLIGATION_KINDS) == 7
        assert OBLIGATION_KIND_CLASS_PRESENT in OBLIGATION_KINDS
        assert OBLIGATION_KIND_CLASS_ABSENT in OBLIGATION_KINDS
        assert OBLIGATION_KIND_VALUE_MATCH in OBLIGATION_KINDS
        assert OBLIGATION_KIND_EDGE_EXISTS in OBLIGATION_KINDS
        assert OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN in OBLIGATION_KINDS
        assert OBLIGATION_KIND_SCOPE_PRESERVED in OBLIGATION_KINDS
        assert OBLIGATION_KIND_OBLIGATION_DECLARED in OBLIGATION_KINDS

    def test_statuses_are_five(self) -> None:
        assert len(OBLIGATION_STATUSES) == 5
        assert OBLIGATION_STATUS_SATISFIED in OBLIGATION_STATUSES
        assert OBLIGATION_STATUS_UNSATISFIED in OBLIGATION_STATUSES
        assert OBLIGATION_STATUS_UNKNOWN in OBLIGATION_STATUSES
        assert OBLIGATION_STATUS_NOT_EVALUATED in OBLIGATION_STATUSES
        assert OBLIGATION_STATUS_UNSUPPORTED in OBLIGATION_STATUSES

    def test_severities_are_three(self) -> None:
        assert len(OBLIGATION_SEVERITIES) == 3
        assert OBLIGATION_SEVERITY_REQUIRED in OBLIGATION_SEVERITIES
        assert OBLIGATION_SEVERITY_RECOMMENDED in OBLIGATION_SEVERITIES
        assert OBLIGATION_SEVERITY_OPTIONAL in OBLIGATION_SEVERITIES

    def test_status_helper_functions(self) -> None:
        assert is_satisfied("satisfied") is True
        assert is_satisfied("unknown") is False
        assert is_unsatisfied("unsatisfied") is True
        assert is_unsatisfied("satisfied") is False
        assert is_unknown("unknown") is True
        assert is_unknown("satisfied") is False
        assert is_not_evaluated("not_evaluated") is True
        assert is_not_evaluated("unknown") is False
        assert is_unsupported("unsupported") is True
        assert is_unsupported("unknown") is False
        assert is_required("required") is True
        assert is_required("optional") is False


# ---------------------------------------------------------------------------
# Obligation construction and validation
# ---------------------------------------------------------------------------


class TestObligationConstruction:
    def test_default_status_is_unknown(self) -> None:
        o = Obligation(obligation_id="ob-1", kind=OBLIGATION_KIND_CLASS_PRESENT)
        assert o.status == OBLIGATION_STATUS_UNKNOWN

    def test_default_severity_is_required(self) -> None:
        o = Obligation(obligation_id="ob-1", kind=OBLIGATION_KIND_CLASS_PRESENT)
        assert o.severity == OBLIGATION_SEVERITY_REQUIRED
        assert o.is_required is True

    def test_rejects_invalid_kind(self) -> None:
        with pytest.raises(ValueError, match="invalid_kind"):
            Obligation(obligation_id="x", kind="invalid_kind")

    def test_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError, match="invalid_status"):
            Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="invalid_status")

    def test_rejects_invalid_severity(self) -> None:
        with pytest.raises(ValueError, match="invalid_severity"):
            Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, severity="invalid_severity")

    def test_rejects_invalid_plan_state(self) -> None:
        with pytest.raises(ValueError, match="invalid_plan"):
            Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, plan_state="invalid_plan")

    def test_accepts_none_plan_state(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, plan_state=None)
        assert o.plan_state is None

    def test_accepts_valid_plan_state(self) -> None:
        o = Obligation(
            obligation_id="x",
            kind=OBLIGATION_KIND_CLASS_PRESENT,
            plan_state="required_supported",
        )
        assert o.plan_state == "required_supported"

    def test_evidence_frozen_to_mappingproxy(self) -> None:
        from types import MappingProxyType

        o = Obligation(
            obligation_id="ob-1",
            kind=OBLIGATION_KIND_CLASS_PRESENT,
            evidence={"reason": "found", "count": 3},
        )
        assert isinstance(o.evidence, MappingProxyType)
        assert o.evidence["reason"] == "found"


# ---------------------------------------------------------------------------
# Obligation properties
# ---------------------------------------------------------------------------


class TestObligationProperties:
    def test_is_satisfied(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="satisfied")
        assert o.is_satisfied is True
        assert o.is_unsatisfied is False
        assert o.is_unknown is False
        assert o.is_not_evaluated is False
        assert o.is_unsupported is False

    def test_is_unsatisfied(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="unsatisfied")
        assert o.is_unsatisfied is True
        assert o.is_satisfied is False

    def test_is_unknown(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="unknown")
        assert o.is_unknown is True

    def test_is_not_evaluated(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="not_evaluated")
        assert o.is_not_evaluated is True

    def test_is_unsupported(self) -> None:
        o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status="unsupported")
        assert o.is_unsupported is True

    def test_is_complete_only_true_for_satisfied(self) -> None:
        for status in OBLIGATION_STATUSES:
            o = Obligation(obligation_id="x", kind=OBLIGATION_KIND_CLASS_PRESENT, status=status)
            if status == OBLIGATION_STATUS_SATISFIED:
                assert o.is_complete is True, f"status={status}"
            else:
                assert o.is_complete is False, f"status={status}"


# ---------------------------------------------------------------------------
# Obligation factory helpers
# ---------------------------------------------------------------------------


class TestObligationFactories:
    def test_class_present_factory(self) -> None:
        o = Obligation.class_present("cp-1", "KSampler", message="Need sampler")
        assert o.obligation_id == "cp-1"
        assert o.kind == OBLIGATION_KIND_CLASS_PRESENT
        assert o.severity == OBLIGATION_SEVERITY_REQUIRED
        assert o.target is not None
        assert o.target.class_type == "KSampler"
        assert o.message == "Need sampler"

    def test_class_present_factory_default_message(self) -> None:
        o = Obligation.class_present("cp-1", "KSampler")
        assert "KSampler" in o.message

    def test_class_absent_factory(self) -> None:
        o = Obligation.class_absent("ca-1", "DeprecatedNode")
        assert o.kind == OBLIGATION_KIND_CLASS_ABSENT
        assert o.target is not None
        assert o.target.class_type == "DeprecatedNode"

    def test_value_match_factory(self) -> None:
        o = Obligation.value_match("vm-1", "5", expected=20, field="steps")
        assert o.kind == OBLIGATION_KIND_VALUE_MATCH
        assert o.target is not None
        assert o.target.node_id == "5"
        assert o.target.field == "steps"
        assert o.expected == 20

    def test_edge_exists_factory(self) -> None:
        o = Obligation.edge_exists("ee-1", "1", "2", source_output="IMAGE", target_input="images")
        assert o.kind == OBLIGATION_KIND_EDGE_EXISTS
        assert o.target is not None
        assert o.target.source_node_id == "1"
        assert o.target.target_node_id == "2"
        assert o.target.source_output == "IMAGE"
        assert o.target.target_input == "images"

    def test_terminal_output_domain_factory(self) -> None:
        o = Obligation.terminal_output_domain("tod-1", "IMAGE")
        assert o.kind == OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN
        assert o.expected == "IMAGE"

    def test_scope_preserved_factory(self) -> None:
        o = Obligation.scope_preserved("sp-1")
        assert o.kind == OBLIGATION_KIND_SCOPE_PRESERVED
        assert o.target is None

    def test_obligation_declared_factory(self) -> None:
        o = Obligation.obligation_declared("od-1")
        assert o.kind == OBLIGATION_KIND_OBLIGATION_DECLARED
        assert o.target is None


# ---------------------------------------------------------------------------
# Obligation serialization
# ---------------------------------------------------------------------------


class TestObligationSerialization:
    def test_to_dict_full(self) -> None:
        o = Obligation(
            obligation_id="ob-full",
            kind=OBLIGATION_KIND_VALUE_MATCH,
            severity=OBLIGATION_SEVERITY_REQUIRED,
            status=OBLIGATION_STATUS_SATISFIED,
            target=StructuralTarget.value_ref("42", field="steps"),
            expected=20,
            message="Steps must be 20",
            evidence={"source": "graph_inspection"},
            plan_state="required_supported",
        )
        d = o.to_dict()
        assert d["obligation_id"] == "ob-full"
        assert d["kind"] == "value_match"
        assert d["severity"] == "required"
        assert d["status"] == "satisfied"
        assert d["target"]["node_id"] == "42"
        assert d["target"]["field"] == "steps"
        assert d["expected"] == 20
        assert d["message"] == "Steps must be 20"
        assert d["evidence"] == {"source": "graph_inspection"}
        assert d["plan_state"] == "required_supported"

    def test_to_dict_minimal(self) -> None:
        o = Obligation(obligation_id="min", kind=OBLIGATION_KIND_CLASS_PRESENT)
        d = o.to_dict()
        assert d["obligation_id"] == "min"
        assert d["kind"] == "class_present"
        assert d["severity"] == "required"
        assert d["status"] == "unknown"
        assert "target" not in d
        assert "expected" not in d
        assert "evidence" not in d
        assert "plan_state" not in d

    def test_from_dict_roundtrip(self) -> None:
        o = Obligation(
            obligation_id="rt",
            kind=OBLIGATION_KIND_EDGE_EXISTS,
            severity=OBLIGATION_SEVERITY_RECOMMENDED,
            status=OBLIGATION_STATUS_SATISFIED,
            target=StructuralTarget.edge_ref("a", "b"),
            expected=None,
            message="Edge a->b must exist",
            evidence={"ok": True},
            plan_state="not_required",
        )
        restored = Obligation.from_dict(o.to_dict())
        assert restored == o
        assert restored.obligation_id == o.obligation_id
        assert restored.kind == o.kind
        assert restored.status == o.status
        assert restored.severity == o.severity
        assert restored.target == o.target
        assert restored.plan_state == o.plan_state

    def test_from_dict_coerces_unknown_kind(self) -> None:
        d = {"obligation_id": "x", "kind": "bogus_kind", "severity": "required", "status": "unknown"}
        o = Obligation.from_dict(d, _coerce=True)
        assert o.kind == OBLIGATION_KIND_OBLIGATION_DECLARED

    def test_from_dict_coerces_unknown_status(self) -> None:
        d = {"obligation_id": "x", "kind": "class_present", "severity": "required", "status": "bogus"}
        o = Obligation.from_dict(d, _coerce=True)
        assert o.status == OBLIGATION_STATUS_UNKNOWN

    def test_from_dict_coerces_unknown_severity(self) -> None:
        d = {"obligation_id": "x", "kind": "class_present", "severity": "bogus", "status": "unknown"}
        o = Obligation.from_dict(d, _coerce=True)
        assert o.severity == OBLIGATION_SEVERITY_REQUIRED

    def test_from_dict_raises_without_coerce(self) -> None:
        d = {"obligation_id": "x", "kind": "bogus_kind", "severity": "required", "status": "unknown"}
        with pytest.raises(ValueError):
            Obligation.from_dict(d, _coerce=False)

    def test_json_roundtrip(self) -> None:
        o = Obligation.class_present("json-1", "CheckpointLoaderSimple")
        payload = json.dumps(o.to_dict(), sort_keys=True)
        reloaded = json.loads(payload)
        restored = Obligation.from_dict(reloaded)
        assert restored == o


# ---------------------------------------------------------------------------
# ObligationLedger - construction and queries
# ---------------------------------------------------------------------------


class TestObligationLedgerConstruction:
    def test_empty_ledger(self) -> None:
        ledger = ObligationLedger.empty()
        assert len(ledger.obligations) == 0
        assert ledger.all_required_satisfied is True
        assert ledger.any_required_incomplete is False
        assert ledger.any_unknown is False

    def test_ledger_with_obligations(self) -> None:
        o1 = Obligation.class_present("cp-1", "KSampler")
        o2 = Obligation.value_match("vm-1", "5", expected=20, field="steps", severity=OBLIGATION_SEVERITY_OPTIONAL)
        ledger = ObligationLedger(obligations=(o1, o2))
        assert len(ledger.obligations) == 2

    def test_get_by_id(self) -> None:
        o1 = Obligation.class_present("cp-1", "KSampler")
        o2 = Obligation.class_present("cp-2", "VAEDecode")
        ledger = ObligationLedger(obligations=(o1, o2))
        assert ledger.get("cp-1") is o1
        assert ledger.get("cp-2") is o2
        assert ledger.get("nonexistent") is None


class TestObligationLedgerQueries:
    def _ledger(self) -> ObligationLedger:
        return ObligationLedger(obligations=(
            Obligation(obligation_id="r-sat", kind="class_present", severity="required", status="satisfied"),
            Obligation(obligation_id="r-unsat", kind="class_present", severity="required", status="unsatisfied"),
            Obligation(obligation_id="r-unk", kind="class_present", severity="required", status="unknown"),
            Obligation(obligation_id="r-ne", kind="class_present", severity="required", status="not_evaluated"),
            Obligation(obligation_id="r-unsup", kind="class_present", severity="required", status="unsupported"),
            Obligation(obligation_id="rec-sat", kind="class_present", severity="recommended", status="satisfied"),
            Obligation(obligation_id="opt-sat", kind="class_present", severity="optional", status="satisfied"),
        ))

    def test_required_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.required_obligations) == 5

    def test_satisfied_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.satisfied_obligations) == 3  # r-sat, rec-sat, opt-sat

    def test_unsatisfied_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.unsatisfied_obligations) == 1

    def test_unknown_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.unknown_obligations) == 1

    def test_not_evaluated_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.not_evaluated_obligations) == 1

    def test_unsupported_obligations(self) -> None:
        ledger = self._ledger()
        assert len(ledger.unsupported_obligations) == 1

    def test_all_required_satisfied_false_when_any_required_not_satisfied(self) -> None:
        ledger = self._ledger()
        assert ledger.all_required_satisfied is False

    def test_all_required_satisfied_true_when_all_satisfied(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="satisfied"),
            Obligation(obligation_id="r2", kind="class_present", severity="required", status="satisfied"),
        ))
        assert ledger.all_required_satisfied is True

    def test_all_required_satisfied_true_when_no_required(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="opt", kind="class_present", severity="optional", status="unsatisfied"),
        ))
        assert ledger.all_required_satisfied is True

    def test_any_required_incomplete_true_when_any_required_not_satisfied(self) -> None:
        ledger = self._ledger()
        assert ledger.any_required_incomplete is True

    def test_any_required_incomplete_false_when_all_required_satisfied(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="satisfied"),
        ))
        assert ledger.any_required_incomplete is False

    def test_any_unknown(self) -> None:
        ledger = self._ledger()
        assert ledger.any_unknown is True

    def test_any_unsupported(self) -> None:
        ledger = self._ledger()
        assert ledger.any_unsupported is True

    def test_any_not_evaluated(self) -> None:
        ledger = self._ledger()
        assert ledger.any_not_evaluated is True


class TestObligationLedgerEdgeCases:
    def test_unknown_status_prevents_all_required_satisfied(self) -> None:
        """Unknown is fail-closed: it prevents all_required_satisfied."""
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="unknown"),
        ))
        assert ledger.all_required_satisfied is False
        assert ledger.any_required_incomplete is True

    def test_unsupported_status_prevents_all_required_satisfied(self) -> None:
        """Unsupported is fail-closed."""
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="unsupported"),
        ))
        assert ledger.all_required_satisfied is False

    def test_not_evaluated_status_prevents_all_required_satisfied(self) -> None:
        """Not_evaluated is fail-closed."""
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="not_evaluated"),
        ))
        assert ledger.all_required_satisfied is False

    def test_unsatisfied_prevents_all_required_satisfied(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="unsatisfied"),
        ))
        assert ledger.all_required_satisfied is False


# ---------------------------------------------------------------------------
# ObligationLedger serialization
# ---------------------------------------------------------------------------


class TestObligationLedgerSerialization:
    def _sample_ledger(self) -> ObligationLedger:
        return ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.value_match(
                    "vm-1", "5", expected=20, field="steps",
                    severity=OBLIGATION_SEVERITY_RECOMMENDED,
                    status=OBLIGATION_STATUS_SATISFIED,
                ),
                Obligation.edge_exists("ee-1", "1", "2"),
            ),
            turn_id="turn-42",
        )

    def test_to_dict_structure(self) -> None:
        ledger = self._sample_ledger()
        d = ledger.to_dict()
        assert d["contract_version"] == OBLIGATION_LEDGER_CONTRACT_VERSION
        assert d["turn_id"] == "turn-42"
        assert len(d["obligations"]) == 3
        assert d["obligations"][0]["obligation_id"] == "cp-1"
        assert d["obligations"][1]["obligation_id"] == "vm-1"
        assert d["obligations"][2]["obligation_id"] == "ee-1"

    def test_from_dict_roundtrip(self) -> None:
        ledger = self._sample_ledger()
        restored = ObligationLedger.from_dict(ledger.to_dict())
        assert restored.contract_version == ledger.contract_version
        assert restored.turn_id == ledger.turn_id
        assert len(restored.obligations) == len(ledger.obligations)
        for a, b in zip(restored.obligations, ledger.obligations):
            assert a == b

    def test_to_json_is_valid_json(self) -> None:
        ledger = self._sample_ledger()
        raw = ledger.to_json()
        parsed = json.loads(raw)
        assert parsed["contract_version"] == OBLIGATION_LEDGER_CONTRACT_VERSION

    def test_to_json_sort_keys_makes_deterministic_output(self) -> None:
        """Two ledgers with the same data must produce identical JSON."""
        ledger_a = ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.class_present("cp-2", "VAEDecode"),
            ),
            turn_id="turn-1",
        )
        ledger_b = ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.class_present("cp-2", "VAEDecode"),
            ),
            turn_id="turn-1",
        )
        assert ledger_a.to_json(sort_keys=True) == ledger_b.to_json(sort_keys=True)

    def test_to_json_different_data_produces_different_output(self) -> None:
        ledger_a = ObligationLedger(
            obligations=(Obligation.class_present("cp-1", "KSampler"),),
        )
        ledger_b = ObligationLedger(
            obligations=(Obligation.class_present("cp-1", "VAEDecode"),),
        )
        assert ledger_a.to_json(sort_keys=True) != ledger_b.to_json(sort_keys=True)


# ---------------------------------------------------------------------------
# Deterministic hashable serialization
# ---------------------------------------------------------------------------


class TestDeterministicHashing:
    def test_content_hash_is_stable(self) -> None:
        """Same data must produce the same hash every time."""
        ledger = ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.value_match("vm-1", "5", expected=20, field="steps", status="satisfied"),
            ),
        )
        h1 = ledger.content_hash()
        h2 = ledger.content_hash()
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex digest

    def test_content_hash_differs_for_different_data(self) -> None:
        ledger_a = ObligationLedger(
            obligations=(Obligation.class_present("cp-1", "KSampler"),),
        )
        ledger_b = ObligationLedger(
            obligations=(Obligation.class_present("cp-1", "VAEDecode"),),
        )
        assert ledger_a.content_hash() != ledger_b.content_hash()

    def test_content_hash_differs_for_different_status(self) -> None:
        ledger_a = ObligationLedger(
            obligations=(Obligation(obligation_id="r1", kind="class_present", severity="required", status="satisfied"),),
        )
        ledger_b = ObligationLedger(
            obligations=(Obligation(obligation_id="r1", kind="class_present", severity="required", status="unknown"),),
        )
        assert ledger_a.content_hash() != ledger_b.content_hash()

    def test_content_hash_same_for_identical_complex_ledger(self) -> None:
        def make_ledger() -> ObligationLedger:
            return ObligationLedger(
                obligations=(
                    Obligation(
                        obligation_id="ob-1",
                        kind=OBLIGATION_KIND_CLASS_PRESENT,
                        severity=OBLIGATION_SEVERITY_REQUIRED,
                        status=OBLIGATION_STATUS_SATISFIED,
                        target=StructuralTarget.node_ref("42", class_type="KSampler"),
                        message="Sampler must exist",
                        evidence={"found": True},
                        plan_state="required_supported",
                    ),
                    Obligation(
                        obligation_id="ob-2",
                        kind=OBLIGATION_KIND_VALUE_MATCH,
                        severity=OBLIGATION_SEVERITY_RECOMMENDED,
                        status=OBLIGATION_STATUS_UNSATISFIED,
                        target=StructuralTarget.value_ref("5", field="steps"),
                        expected=20,
                        message="Steps should be 20",
                    ),
                    Obligation(
                        obligation_id="ob-3",
                        kind=OBLIGATION_KIND_TERMINAL_OUTPUT_DOMAIN,
                        severity=OBLIGATION_SEVERITY_REQUIRED,
                        status=OBLIGATION_STATUS_UNKNOWN,
                        expected="IMAGE",
                        message="Must output IMAGE domain",
                    ),
                ),
                turn_id="turn-complex",
            )

        h1 = make_ledger().content_hash()
        h2 = make_ledger().content_hash()
        assert h1 == h2

    def test_json_roundtrip_stable(self) -> None:
        """Serializing and re-parsing must yield the same JSON."""
        ledger = ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.value_match("vm-1", "5", expected=20, field="steps"),
                Obligation.edge_exists("ee-1", "1", "2", target_input="images"),
            ),
            turn_id="turn-stable",
        )
        assert ledger.json_roundtrip_stable() is True

    def test_json_roundtrip_stable_preserves_hash(self) -> None:
        """Round-tripped ledger must produce identical content hash."""
        ledger = ObligationLedger(
            obligations=(
                Obligation(
                    obligation_id="hash-test",
                    kind=OBLIGATION_KIND_EDGE_EXISTS,
                    severity=OBLIGATION_SEVERITY_REQUIRED,
                    status=OBLIGATION_STATUS_SATISFIED,
                    target=StructuralTarget.edge_ref("src", "dst", source_output="out", target_input="in"),
                ),
            ),
        )
        original_hash = ledger.content_hash()
        reparsed = ObligationLedger.from_dict(json.loads(ledger.to_json()))
        assert reparsed.content_hash() == original_hash


# ---------------------------------------------------------------------------
# Plan state handling in obligations
# ---------------------------------------------------------------------------


class TestObligationPlanStates:
    def test_obligation_with_not_required_plan_state(self) -> None:
        o = Obligation(obligation_id="p1", kind="class_present", plan_state="not_required")
        assert o.plan_state == "not_required"
        d = o.to_dict()
        assert d["plan_state"] == "not_required"

    def test_obligation_with_required_supported_plan_state(self) -> None:
        o = Obligation(obligation_id="p2", kind="class_present", plan_state="required_supported")
        assert o.plan_state == "required_supported"

    def test_obligation_with_required_unsupported_plan_state(self) -> None:
        o = Obligation(obligation_id="p3", kind="class_present", plan_state="required_unsupported")
        assert o.plan_state == "required_unsupported"

    def test_obligation_without_plan_state_omits_from_dict(self) -> None:
        o = Obligation(obligation_id="p4", kind="class_present")
        assert "plan_state" not in o.to_dict()

    def test_from_dict_restores_plan_state(self) -> None:
        d = {
            "obligation_id": "p5",
            "kind": "class_present",
            "severity": "required",
            "status": "unknown",
            "plan_state": "required_unsupported",
        }
        o = Obligation.from_dict(d)
        assert o.plan_state == "required_unsupported"

    def test_from_dict_coerces_invalid_plan_state_to_none(self) -> None:
        d = {
            "obligation_id": "p6",
            "kind": "class_present",
            "severity": "required",
            "status": "unknown",
            "plan_state": "bogus",
        }
        o = Obligation.from_dict(d)
        assert o.plan_state is None


# ---------------------------------------------------------------------------
# All obligation kinds covered
# ---------------------------------------------------------------------------


class TestAllObligationKinds:
    def test_every_kind_can_be_constructed_and_serialized(self) -> None:
        """Each obligation kind must serialize and deserialize without error."""
        for kind in OBLIGATION_KINDS:
            o = Obligation(
                obligation_id=f"kind-test-{kind}",
                kind=kind,
                status=OBLIGATION_STATUS_UNKNOWN,
            )
            d = o.to_dict()
            restored = Obligation.from_dict(d)
            assert restored.kind == kind
            assert restored.obligation_id == f"kind-test-{kind}"

    def test_every_kind_factory_exists(self) -> None:
        """Each obligation kind must have a corresponding factory method."""
        Obligation.class_present("t1", "Foo")
        Obligation.class_absent("t2", "Bar")
        Obligation.value_match("t3", "1", expected="x")
        Obligation.edge_exists("t4", "a", "b")
        Obligation.terminal_output_domain("t5", "IMAGE")
        Obligation.scope_preserved("t6")
        Obligation.obligation_declared("t7")

    def test_every_status_is_representable(self) -> None:
        for status in OBLIGATION_STATUSES:
            o = Obligation(obligation_id=f"s-{status}", kind="class_present", status=status)
            assert o.status == status
            d = o.to_dict()
            assert d["status"] == status
            restored = Obligation.from_dict(d)
            assert restored.status == status

    def test_every_severity_is_representable(self) -> None:
        for severity in OBLIGATION_SEVERITIES:
            o = Obligation(obligation_id=f"sev-{severity}", kind="class_present", severity=severity)
            assert o.severity == severity


# ---------------------------------------------------------------------------
# Structural target coverage for all obligation kinds
# ---------------------------------------------------------------------------


class TestStructuralTargetCoverage:
    def test_class_present_uses_class_ref(self) -> None:
        o = Obligation.class_present("cp", "Foo")
        assert o.target is not None
        assert o.target.class_type == "Foo"
        assert o.target.node_id is None

    def test_class_absent_uses_class_ref(self) -> None:
        o = Obligation.class_absent("ca", "Bar")
        assert o.target is not None
        assert o.target.class_type == "Bar"

    def test_value_match_uses_value_ref(self) -> None:
        o = Obligation.value_match("vm", "5", expected=42, field="steps")
        assert o.target is not None
        assert o.target.node_id == "5"
        assert o.target.field == "steps"
        assert o.expected == 42

    def test_edge_exists_uses_edge_ref(self) -> None:
        o = Obligation.edge_exists("ee", "1", "2", source_output="out", target_input="in")
        assert o.target is not None
        assert o.target.source_node_id == "1"
        assert o.target.target_node_id == "2"

    def test_terminal_output_domain_uses_expected(self) -> None:
        o = Obligation.terminal_output_domain("tod", "LATENT")
        assert o.expected == "LATENT"
        assert o.target is None  # domain only, no structural target needed

    def test_scope_preserved_no_target(self) -> None:
        o = Obligation.scope_preserved("sp")
        assert o.target is None

    def test_obligation_declared_no_target(self) -> None:
        o = Obligation.obligation_declared("od")
        assert o.target is None


# ---------------------------------------------------------------------------
# Evidence handling
# ---------------------------------------------------------------------------


class TestEvidenceHandling:
    def test_evidence_is_preserved_in_serialization(self) -> None:
        o = Obligation(
            obligation_id="ev-1",
            kind="class_present",
            evidence={"source": "graph_inspection", "nodes_found": 1},
        )
        d = o.to_dict()
        assert d["evidence"] == {"source": "graph_inspection", "nodes_found": 1}

    def test_evidence_roundtrip(self) -> None:
        o = Obligation(
            obligation_id="ev-2",
            kind="class_present",
            evidence={"reason": "not_found", "searched": ["node_1", "node_2"]},
        )
        restored = Obligation.from_dict(o.to_dict())
        # Lists are frozen to tuples during construction; thawed back during to_dict.
        # The round-trip through from_dict re-freezes, so we check the dict form.
        restored_dict = restored.to_dict()
        assert restored_dict["evidence"] == {"reason": "not_found", "searched": ["node_1", "node_2"]}

    def test_empty_evidence_omitted(self) -> None:
        o = Obligation(obligation_id="ev-3", kind="class_present", evidence={})
        d = o.to_dict()
        assert "evidence" not in d


# ---------------------------------------------------------------------------
# ObligationLedger with unknown/unsupported/not_evaluated obligations
# ---------------------------------------------------------------------------


class TestObligationLedgerFailClosed:
    def test_required_unknown_obligation_means_incomplete(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="unknown"),
        ))
        assert ledger.any_required_incomplete is True
        assert ledger.all_required_satisfied is False
        assert ledger.any_unknown is True

    def test_required_unsupported_obligation_means_incomplete(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="unsupported"),
        ))
        assert ledger.any_required_incomplete is True
        assert ledger.any_unsupported is True

    def test_required_not_evaluated_obligation_means_incomplete(self) -> None:
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="not_evaluated"),
        ))
        assert ledger.any_required_incomplete is True
        assert ledger.any_not_evaluated is True

    def test_mixed_status_required_obligations(self) -> None:
        """If any required obligation is not satisfied, the ledger is incomplete."""
        ledger = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required", status="satisfied"),
            Obligation(obligation_id="r2", kind="class_present", severity="required", status="unknown"),
            Obligation(obligation_id="r3", kind="class_present", severity="required", status="unsatisfied"),
        ))
        assert ledger.all_required_satisfied is False
        assert ledger.any_required_incomplete is True
        assert ledger.any_unknown is True


# ---------------------------------------------------------------------------
# Schema validation (against existing V2 schema patterns)
# ---------------------------------------------------------------------------


class TestObligationLedgerSchema:
    def test_schema_file_exists(self) -> None:
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "vibecomfy",
            "porting",
            "edit",
            "schemas",
            "v2",
            "obligation_ledger.schema.json",
        )
        assert os.path.isfile(schema_path), f"Schema file not found at {schema_path}"

    def test_schema_is_valid_json(self) -> None:
        import os
        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "vibecomfy",
            "porting",
            "edit",
            "schemas",
            "v2",
            "obligation_ledger.schema.json",
        )
        with open(schema_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        parsed = json.loads(content)
        assert parsed["$id"].endswith("obligation_ledger.schema.json")

    def test_sample_ledger_validates_against_schema(self) -> None:
        """Validate a sample ledger dict against the JSON schema."""
        import os

        schema_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "vibecomfy",
            "porting",
            "edit",
            "schemas",
            "v2",
            "obligation_ledger.schema.json",
        )
        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)

        ledger = ObligationLedger(
            obligations=(
                Obligation.class_present("cp-1", "KSampler"),
                Obligation.value_match("vm-1", "5", expected=20, field="steps",
                                       status="satisfied", severity="recommended"),
                Obligation.edge_exists("ee-1", "1", "2"),
                Obligation.terminal_output_domain("tod-1", "IMAGE", status="unknown"),
            ),
            turn_id="turn-schema-test",
        )
        payload = ledger.to_dict()

        # Basic structural checks (without a full JSON Schema validator)
        assert payload["contract_version"] == "obligation_ledger_v1"
        assert payload["turn_id"] == "turn-schema-test"
        assert isinstance(payload["obligations"], list)
        assert len(payload["obligations"]) == 4

        for ob in payload["obligations"]:
            assert "obligation_id" in ob
            assert "kind" in ob
            assert ob["kind"] in OBLIGATION_KINDS
            assert "severity" in ob
            assert ob["severity"] in OBLIGATION_SEVERITIES
            assert "status" in ob
            assert ob["status"] in OBLIGATION_STATUSES


# ---------------------------------------------------------------------------
# ObligationLedger - empty and edge cases
# ---------------------------------------------------------------------------


class TestObligationLedgerEdge:
    def test_empty_ledger_to_dict(self) -> None:
        ledger = ObligationLedger.empty()
        d = ledger.to_dict()
        assert d["contract_version"] == OBLIGATION_LEDGER_CONTRACT_VERSION
        assert d["obligations"] == []

    def test_empty_ledger_from_dict(self) -> None:
        d = {"contract_version": OBLIGATION_LEDGER_CONTRACT_VERSION, "obligations": []}
        ledger = ObligationLedger.from_dict(d)
        assert len(ledger.obligations) == 0

    def test_empty_ledger_json_roundtrip_stable(self) -> None:
        ledger = ObligationLedger.empty()
        assert ledger.json_roundtrip_stable() is True

    def test_empty_ledger_content_hash(self) -> None:
        ledger = ObligationLedger.empty()
        h = ledger.content_hash()
        assert len(h) == 64
        # Same empty ledger always produces same hash
        assert ObligationLedger.empty().content_hash() == h

    def test_ledger_without_turn_id_omits_from_dict(self) -> None:
        ledger = ObligationLedger(obligations=(Obligation.class_present("cp-1", "Foo"),))
        d = ledger.to_dict()
        assert "turn_id" not in d

    def test_from_dict_without_turn_id(self) -> None:
        d = {
            "contract_version": OBLIGATION_LEDGER_CONTRACT_VERSION,
            "obligations": [
                {"obligation_id": "cp-1", "kind": "class_present", "severity": "required", "status": "unknown"}
            ],
        }
        ledger = ObligationLedger.from_dict(d)
        assert ledger.turn_id is None
        assert len(ledger.obligations) == 1

    def test_from_dict_handles_non_list_obligations(self) -> None:
        d = {
            "contract_version": OBLIGATION_LEDGER_CONTRACT_VERSION,
            "obligations": "not_a_list",
        }
        ledger = ObligationLedger.from_dict(d)
        assert len(ledger.obligations) == 0

    def test_from_dict_handles_missing_obligations(self) -> None:
        d = {"contract_version": OBLIGATION_LEDGER_CONTRACT_VERSION}
        ledger = ObligationLedger.from_dict(d)
        assert len(ledger.obligations) == 0


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


class TestImmutability:
    def test_obligation_is_frozen(self) -> None:
        o = Obligation(obligation_id="frozen", kind="class_present")
        with pytest.raises(Exception):
            o.obligation_id = "changed"  # type: ignore[misc]

    def test_structural_target_is_frozen(self) -> None:
        t = StructuralTarget(node_id="1")
        with pytest.raises(Exception):
            t.node_id = "2"  # type: ignore[misc]

    def test_obligation_ledger_is_frozen(self) -> None:
        ledger = ObligationLedger.empty()
        with pytest.raises(Exception):
            ledger.contract_version = "changed"  # type: ignore[misc]

    def test_ledger_obligations_tuple_immutable(self) -> None:
        ledger = ObligationLedger(obligations=(Obligation.class_present("cp-1", "Foo"),))
        assert isinstance(ledger.obligations, tuple)


# ---------------------------------------------------------------------------
# Hashing corner cases
# ---------------------------------------------------------------------------


class TestHashingCorners:
    def test_hash_changes_when_obligation_order_differs(self) -> None:
        a = ObligationLedger(obligations=(
            Obligation.class_present("a", "Foo"),
            Obligation.class_present("b", "Bar"),
        ))
        b = ObligationLedger(obligations=(
            Obligation.class_present("b", "Bar"),
            Obligation.class_present("a", "Foo"),
        ))
        assert a.content_hash() != b.content_hash()

    def test_hash_changes_when_evidence_differs(self) -> None:
        a = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required",
                       status="satisfied", evidence={"found": True}),
        ))
        b = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", severity="required",
                       status="satisfied", evidence={"found": False}),
        ))
        assert a.content_hash() != b.content_hash()

    def test_hash_changes_when_message_differs(self) -> None:
        a = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", message="hello"),
        ))
        b = ObligationLedger(obligations=(
            Obligation(obligation_id="r1", kind="class_present", message="world"),
        ))
        assert a.content_hash() != b.content_hash()
