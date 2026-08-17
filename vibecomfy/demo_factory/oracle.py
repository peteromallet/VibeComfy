"""Oracle evaluation for demo_factory.

Six mechanical gates from the runbook, followed by an additive LLM judge when
the repaired predicate describes an additive witness.
"""
from __future__ import annotations

from vibecomfy.ingest.door_access import door_get_links, door_get_nodes
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from vibecomfy.demo_factory import additive_judge
from vibecomfy.demo_factory.predicates import (
    AdditiveWitnessVerdict,
    evaluate_predicate,
    grade_additive_witness,
)


class Verdict(Enum):
    """Oracle verdict outcomes."""
    ACCEPTED = "accepted"
    ALTERNATIVE_REPAIR = "alternative_repair"
    REJECTED = "rejected"
    FIXER_FAILED = "fixer_failed"
    BASELINE_REJECTED = "baseline_rejected"
    INFRA_BLOCKED = "infra_blocked"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class GateResult:
    """Result of a single gate evaluation."""
    name: str
    passed: bool
    reason: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OracleResult:
    """Full oracle evaluation result."""
    verdict: Verdict
    gates: tuple[GateResult, ...]
    candidate: dict[str, Any]
    golden: dict[str, Any]
    broken: dict[str, Any]
    fault_predicate: dict[str, Any]
    repaired_predicate: dict[str, Any]
    execution_safe: bool = False
    compile_error: str | None = None
    output_reachable: bool = False
    alternative_to_golden: bool = False


class Oracle:
    """Six-gate evaluator for candidate repairs."""

    def __init__(
        self,
        fault_predicate: dict[str, Any],
        repaired_predicate: dict[str, Any],
        broken: dict[str, Any],
        golden: dict[str, Any],
    ):
        """Initialize oracle with fault/repaired predicates and graphs."""
        self.fault_predicate = fault_predicate
        self.repaired_predicate = repaired_predicate
        self.broken = broken
        self.golden = golden

    def _additive_mode(self) -> str:
        """Return the predicate-selected grade path (single-node by default)."""
        return str(self.repaired_predicate.get("additive_mode", "practical"))

    def evaluate(
        self,
        candidate: dict[str, Any],
        *,
        execution_safe: bool = False,
        compile_error: str | None = None,
        output_reachable: bool = False,
        narrative_honesty: str | None = None,
    ) -> OracleResult:
        """Evaluate a candidate repair through all six gates."""
        gates: list[GateResult] = []

        # Gate 1: Execution safety
        gate1 = self._gate_execution_safety(candidate, execution_safe, compile_error, output_reachable)
        gates.append(gate1)

        if not gate1.passed:
            return OracleResult(
                verdict=Verdict.REJECTED,
                gates=tuple(gates),
                candidate=candidate,
                golden=self.golden,
                broken=self.broken,
                fault_predicate=self.fault_predicate,
                repaired_predicate=self.repaired_predicate,
                execution_safe=execution_safe,
                compile_error=compile_error,
                output_reachable=output_reachable,
            )

        # Gate 2: Fault removal
        gate2 = self._gate_fault_removal(candidate)
        gates.append(gate2)

        # Gate 3: Repair postcondition
        gate3 = self._gate_repair_postcondition(candidate)
        gates.append(gate3)

        # Gate 4: Collateral fence (soft)
        gate4 = self._gate_collateral_fence(candidate)
        gates.append(gate4)

        # Gate 5: Non-no-op
        gate5 = self._gate_non_noop(candidate)
        gates.append(gate5)

        # Gate 6: Narrative honesty (v1 stub)
        gate6 = GateResult(
            name="narrative_honesty",
            passed=True,
            reason="v1 stub - ungraded",
            detail={"grade": narrative_honesty or "ungraded"},
        )
        gates.append(gate6)

        # Determine verdict. Additive repairs first pass the complete existing
        # mechanical floor above. Only then may the qualitative judge select
        # the practical tier; it can never override a failed hard gate.
        all_passed = all(g.passed for g in gates)
        additive_loci = [
            item
            for item in self.repaired_predicate.get("locus", [])
            if item.get("type") == "additive_witness"
        ]

        if not all_passed:
            verdict = Verdict.REJECTED
        elif additive_loci:
            rule_grades = [
                grade_additive_witness(
                    candidate,
                    locus,
                    mode=self._additive_mode(),
                )
                for locus in additive_loci
            ]
            # Gate 3 should make this impossible, but retain a second explicit
            # anti-bypass assertion at the judge boundary.
            if any(not grade.passed for grade in rule_grades):
                verdict = Verdict.REJECTED
                gates.append(
                    GateResult(
                        name="additive_llm_judge",
                        passed=False,
                        reason="Additive hard floor failed before qualitative judging",
                        detail={"source": "hard_floor"},
                    )
                )
            else:
                judge_result = additive_judge.judge_additive_candidate(
                    candidate,
                    additive_loci,
                    rule_grades,
                    execution_safe=execution_safe,
                    output_reachable=output_reachable,
                )
                gates.append(
                    GateResult(
                        name="additive_llm_judge",
                        passed=(
                            judge_result.verdict
                            is not AdditiveWitnessVerdict.REJECTED
                        ),
                        reason=judge_result.reason,
                        detail={
                            "verdict": judge_result.verdict.value,
                            "source": judge_result.source,
                            "profile": judge_result.profile,
                            "fallback_error": judge_result.error,
                        },
                    )
                )
                verdict = Verdict(judge_result.verdict.value)
        elif self._matches_golden(candidate):
            verdict = Verdict.ACCEPTED
        elif gate2.passed and gate3.passed and gate5.passed:
            verdict = Verdict.ALTERNATIVE_REPAIR
        else:
            verdict = Verdict.REJECTED

        return OracleResult(
            verdict=verdict,
            gates=tuple(gates),
            candidate=candidate,
            golden=self.golden,
            broken=self.broken,
            fault_predicate=self.fault_predicate,
            repaired_predicate=self.repaired_predicate,
            execution_safe=execution_safe,
            compile_error=compile_error,
            output_reachable=output_reachable,
            alternative_to_golden=verdict == Verdict.ALTERNATIVE_REPAIR,
        )

    def _gate_execution_safety(
        self,
        candidate: dict[str, Any],
        execution_safe: bool,
        compile_error: str | None,
        output_reachable: bool,
    ) -> GateResult:
        """Gate 1: Execution safety."""
        if not execution_safe:
            return GateResult(
                name="execution_safety",
                passed=False,
                reason=f"Candidate failed UI→API conversion: {compile_error or 'unknown error'}",
                detail={"compile_error": compile_error},
            )

        if not output_reachable:
            return GateResult(
                name="execution_safety",
                passed=False,
                reason="Candidate has no reachable output node",
                detail={"output_reachable": False},
            )

        return GateResult(
            name="execution_safety",
            passed=True,
            reason="Candidate passed UI→API conversion and has reachable output",
            detail={"output_reachable": True},
        )

    def _gate_fault_removal(self, candidate: dict[str, Any]) -> GateResult:
        """Gate 2: Fault removal."""
        matches_fault = evaluate_predicate(
            candidate,
            self.fault_predicate,
            additive_mode=self._additive_mode(),
        )

        if matches_fault:
            return GateResult(
                name="fault_removal",
                passed=False,
                reason="Candidate still matches fault predicate - defect not removed",
                detail={"matches_fault": True},
            )

        return GateResult(
            name="fault_removal",
            passed=True,
            reason="Candidate does not match fault predicate - defect removed",
            detail={"matches_fault": False},
        )

    def _gate_repair_postcondition(self, candidate: dict[str, Any]) -> GateResult:
        """Gate 3: Repair postcondition."""
        matches_repaired = evaluate_predicate(
            candidate,
            self.repaired_predicate,
            additive_mode=self._additive_mode(),
        )

        if not matches_repaired:
            return GateResult(
                name="repair_postcondition",
                passed=False,
                reason="Candidate does not match repaired predicate - repair incomplete",
                detail={"matches_repaired": False},
            )

        additive_loci = [
            item
            for item in self.repaired_predicate.get("locus", [])
            if item.get("type") == "additive_witness"
        ]
        if additive_loci:
            output_path_ok, output_path_reason = (
                self._validate_additive_output_paths(candidate, additive_loci)
            )
            if not output_path_ok:
                return GateResult(
                    name="repair_postcondition",
                    passed=False,
                    reason=output_path_reason,
                    detail={
                        "matches_repaired": True,
                        "additive_output_path": False,
                    },
                )

        return GateResult(
            name="repair_postcondition",
            passed=True,
            reason="Candidate matches repaired predicate - repair complete",
            detail={
                "matches_repaired": True,
                **(
                    {"additive_output_path": True}
                    if additive_loci
                    else {}
                ),
            },
        )

    def _validate_additive_output_paths(
        self,
        candidate: dict[str, Any],
        additive_loci: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """Require every witness to retain its proven downstream terminals.

        A graph-global reachable output is insufficient: an unrelated branch
        could keep that flag true while the added feature sits on a dead branch.
        The golden is used only for topology/role here, never for widget values.
        """
        for locus in additive_loci:
            mode = self._additive_mode()
            golden_grade = grade_additive_witness(self.golden, locus, mode=mode)
            candidate_grade = grade_additive_witness(candidate, locus, mode=mode)
            if not golden_grade.passed or not candidate_grade.passed:
                return False, "Additive witness failed the structural hard floor"

            golden_witness = str(golden_grade.node_id)
            candidate_witness = str(candidate_grade.node_id)
            golden_reachable, golden_terminals = _reachable_and_terminal_nodes(
                self.golden, golden_witness
            )
            candidate_reachable, _ = _reachable_and_terminal_nodes(
                candidate, candidate_witness
            )
            if golden_witness not in golden_reachable:
                return False, "Golden additive witness has no valid topology"
            if not golden_terminals:
                return False, "Golden additive witness has no downstream terminal"

            expected_terminals = {
                candidate_witness if node_id == golden_witness else node_id
                for node_id in golden_terminals
            }
            missing = sorted(expected_terminals - candidate_reachable)
            if missing:
                return (
                    False,
                    "Additive witness is disconnected from its intended "
                    f"downstream terminal node(s): {', '.join(missing)}",
                )
        return True, "Additive witnesses reach their intended downstream terminals"

    def _gate_collateral_fence(self, candidate: dict[str, Any]) -> GateResult:
        """Gate 4: Collateral fence (v1 undetermined)."""
        return GateResult(
            name="collateral_fence",
            passed=True,
            reason="v1 undetermined - causal slice analysis deferred",
            detail={"status": "undetermined"},
        )

    def _gate_non_noop(self, candidate: dict[str, Any]) -> GateResult:
        """Gate 5: Non-no-op."""
        if candidate == self.broken:
            return GateResult(
                name="non_noop",
                passed=False,
                reason="Candidate is identical to broken - no-op repair",
                detail={"is_noop": True},
            )

        return GateResult(
            name="non_noop",
            passed=True,
            reason="Candidate differs from broken - non-no-op",
            detail={"is_noop": False},
        )

    def _matches_golden(self, candidate: dict[str, Any]) -> bool:
        """Check if candidate matches golden exactly."""
        return json.dumps(candidate, sort_keys=True) == json.dumps(self.golden, sort_keys=True)


def _reachable_and_terminal_nodes(
    graph: dict[str, Any],
    start_id: str,
) -> tuple[set[str], set[str]]:
    """Return forward-reachable ids and the reachable graph terminals."""
    node_ids = {
        str(node.get("id"))
        for node in door_get_nodes(graph, [])
        if isinstance(node, dict) and node.get("id") is not None
    }
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for link in door_get_links(graph, []):
        if not isinstance(link, list) or len(link) < 6:
            continue
        source, target = str(link[1]), str(link[3])
        if source in outgoing and target in node_ids:
            outgoing[source].add(target)

    if start_id not in node_ids:
        return set(), set()
    reachable: set[str] = set()
    pending = [start_id]
    while pending:
        node_id = pending.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        pending.extend(outgoing.get(node_id, ()))
    terminals = {
        node_id for node_id in reachable if not outgoing.get(node_id)
    }
    return reachable, terminals
