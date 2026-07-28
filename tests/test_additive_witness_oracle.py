"""Metamorphic controls for the witness-bound additive oracle.

These tests pin the additive witness's hard and soft contracts:

1. typed ``link_absent`` falling back to "any link into to_slot → False",
2. ``node_type_present(min_count=0)`` tautology on the fault side,
3. same-type nodes satisfying different edges (no single witness),
4. widget spelling/default materialization does not decide runnability,
5. meaningful widget differences are weaker repairs, not broken graphs,
6. restore-regression mode retains exact positional widget comparison.

The synthetic golden is a 3-node image pipeline: LoadImage → ManualSigmas →
KSampler, where ManualSigmas carries a positional sigma schedule.  Broken =
golden with ManualSigmas (id "20") and its two links removed.  The repair delta
is one add_node + two upsert_link ops, so the predicate builder emits exactly
one ``additive_witness``/``additive_absence`` pair.

Wrong type, wrong wiring, malformed structure, and failed execution/output gates
remain hard rejections.
"""
from __future__ import annotations

import copy
import json

import pytest

from vibecomfy.demo_factory import additive_judge
from vibecomfy.demo_factory.deltas import derive_repair_delta
from vibecomfy.demo_factory.oracle import Oracle, Verdict
from vibecomfy.demo_factory.predicates import (
    AdditiveWitnessVerdict,
    evaluate_predicate,
    grade_additive_witness,
)


@pytest.fixture(autouse=True)
def _keep_additive_judge_unit_tests_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing oracle controls use the documented rule fallback by default."""

    def unavailable(
        messages: list[dict[str, str]],
        profile_name: str,
    ) -> dict:
        raise RuntimeError("judge deliberately offline in unit tests")

    monkeypatch.setattr(additive_judge, "_call_judge_model", unavailable)


# ── Synthetic golden graph ────────────────────────────────────────────────────
# LoadImage (10) --IMAGE--> ManualSigmas (20) --SIGMAS--> KSampler (30)
SIGMA_SCHEDULE = "0.85, 0.7250, 0.4219, 0.0"
WRONG_SIGMA_SCHEDULE = "1.0, 0.99, 0.5, 0.0"


def _golden_graph() -> dict:
    return {
        "nodes": [
            {
                "id": 10,
                "type": "LoadImage",
                "widgets_values": ["example.png", "image"],
                "outputs": [
                    {"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0},
                ],
                "inputs": [],
            },
            {
                "id": 20,
                "type": "ManualSigmas",
                "widgets_values": [SIGMA_SCHEDULE],
                "outputs": [
                    {"name": "SIGMAS", "type": "SIGMAS", "links": [2], "slot_index": 0},
                ],
                "inputs": [
                    {"name": "IMAGE", "type": "IMAGE", "link": 1},
                ],
            },
            {
                "id": 30,
                "type": "KSampler",
                "widgets_values": [12345, "fixed", 20, 8.0, "euler", "normal"],
                "outputs": [],
                "inputs": [
                    {"name": "sigmas", "type": "SIGMAS", "link": 2},
                ],
            },
        ],
        # ComfyUI UI link shape: [link_id, from_node, from_slot, to_node, to_slot, type]
        "links": [
            [1, 10, 0, 20, 0, "IMAGE"],
            [2, 20, 0, 30, 0, "SIGMAS"],
        ],
    }


def _broken_from_golden(golden: dict) -> dict:
    """Remove ManualSigmas (id 20) and its two incident links."""
    broken = copy.deepcopy(golden)
    broken["nodes"] = [n for n in broken["nodes"] if n.get("id") != 20]
    broken["links"] = []
    # Clear dangling link refs on the surviving endpoints.
    for node in broken["nodes"]:
        if node.get("id") == 10:
            for out in node.get("outputs", []):
                if isinstance(out, dict):
                    out["links"] = []
        if node.get("id") == 30:
            for inp in node.get("inputs", []):
                if isinstance(inp, dict) and inp.get("name") == "sigmas":
                    inp["link"] = None
    return broken


def _broken_graph() -> dict:
    """Golden with ManualSigmas (id 20) and its two incident links removed."""
    return _broken_from_golden(_golden_graph())


def _fault_injection():
    return derive_repair_delta(_broken_graph(), _golden_graph())


def _fault_injection_for(golden: dict):
    return derive_repair_delta(_broken_from_golden(golden), golden)


def _alpha_rename(golden: dict) -> dict:
    """Return golden with ManualSigmas node id 20 -> 21 everywhere (links too)."""
    renamed = copy.deepcopy(golden)
    for node in renamed["nodes"]:
        if node.get("id") == 20:
            node["id"] = 21
    for link in renamed["links"]:
        if not isinstance(link, list):
            continue
        # [lid, from_node, from_slot, to_node, to_slot, type]
        if link[1] == 20:
            link[1] = 21
        if link[3] == 20:
            link[3] = 21
    return renamed


def _candidate_with_manual_sigmas(
    *,
    node_id: int = 20,
    sigma_schedule: str = SIGMA_SCHEDULE,
    edges: tuple = ("10->20", "20->30"),
) -> dict:
    """Build a candidate graph by re-adding a ManualSigmas node into broken.

    ``edges`` selects which incident links to create.  ``node_id`` controls the
    fresh id for the re-added node.  ``sigma_schedule`` controls the widget.
    """
    candidate = copy.deepcopy(_broken_graph())
    sigma_node = {
        "id": node_id,
        "type": "ManualSigmas",
        "widgets_values": [sigma_schedule],
        "outputs": [
            {"name": "SIGMAS", "type": "SIGMAS", "links": [], "slot_index": 0},
        ],
        "inputs": [
            {"name": "IMAGE", "type": "IMAGE", "link": None},
        ],
    }
    candidate["nodes"].append(sigma_node)
    next_link_id = 100

    def _set_link(from_id, from_slot, to_id, to_slot, ltype):
        nonlocal next_link_id
        lid = next_link_id
        next_link_id += 1
        candidate["links"].append([lid, from_id, from_slot, to_id, to_slot, ltype])
        return lid

    if "10->20" in edges:
        # LoadImage IMAGE -> ManualSigmas.IMAGE
        lid = _set_link(10, 0, node_id, 0, "IMAGE")
        sigma_node["inputs"][0]["link"] = lid
        for node in candidate["nodes"]:
            if node.get("id") == 10:
                for out in node.get("outputs", []):
                    if isinstance(out, dict) and out.get("name") == "IMAGE":
                        out["links"] = [lid]
    if "20->30" in edges:
        # ManualSigmas.SIGMAS -> KSampler.sigmas
        lid = _set_link(node_id, 0, 30, 0, "SIGMAS")
        sigma_node["outputs"][0]["links"] = [lid]
        for node in candidate["nodes"]:
            if node.get("id") == 30:
                for inp in node.get("inputs", []):
                    if isinstance(inp, dict) and inp.get("name") == "sigmas":
                        inp["link"] = lid
    return candidate


def _verdict(candidate: dict) -> Verdict:
    fi = _fault_injection()
    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(
        candidate,
        execution_safe=True,
        output_reachable=True,
    )
    return result.verdict


# ── Control 1: broken graph → REJECTED ────────────────────────────────────────


def test_control1_broken_graph_is_rejected() -> None:
    fi = _fault_injection()
    broken = fi.broken
    assert evaluate_predicate(broken, fi.fault_predicate) is True
    assert evaluate_predicate(broken, fi.repaired_predicate) is False
    assert _verdict(broken) is Verdict.REJECTED


# ── Control 2: golden graph → ACCEPTED ────────────────────────────────────────


def test_control2_golden_graph_is_accepted() -> None:
    fi = _fault_injection()
    golden = fi.golden
    assert evaluate_predicate(golden, fi.repaired_predicate) is True
    assert evaluate_predicate(golden, fi.fault_predicate) is False
    assert _verdict(golden) is Verdict.ACCEPTED


# ── Control 3: alpha-renamed golden → pass (ACCEPTED or ALTERNATIVE_REPAIR) ───


def test_control3_alpha_renamed_golden_is_a_pass() -> None:
    fi = _fault_injection()
    renamed = _alpha_rename(fi.golden)
    assert evaluate_predicate(renamed, fi.repaired_predicate) is True
    assert evaluate_predicate(renamed, fi.fault_predicate) is False
    verdict = _verdict(renamed)
    assert verdict in {Verdict.ACCEPTED, Verdict.ALTERNATIVE_REPAIR}, (
        f"alpha-renamed golden should pass, got {verdict}"
    )


# ── Control 4: wrong-branch (missing 20->30 edge) → REJECTED ──────────────────


def test_control4_wrong_branch_is_rejected() -> None:
    fi = _fault_injection()
    candidate = _candidate_with_manual_sigmas(edges=("10->20",))  # missing 20->30
    assert evaluate_predicate(candidate, fi.repaired_predicate) is False
    assert evaluate_predicate(candidate, fi.fault_predicate) is True
    assert _verdict(candidate) is Verdict.REJECTED


# ── Control 4b: wrong peer → REJECTED ─────────────────────────────────────────


def test_control4b_wrong_peer_is_rejected() -> None:
    fi = _fault_injection()
    # Connect 30's sigmas input to LoadImage (wrong source type) instead of the
    # re-added ManualSigmas.  Achieved by wiring 10->30 directly.
    candidate = copy.deepcopy(_broken_graph())
    candidate["links"] = [[101, 10, 0, 30, 0, "SIGMAS"]]
    for node in candidate["nodes"]:
        if node.get("id") == 10:
            for out in node.get("outputs", []):
                if isinstance(out, dict) and out.get("name") == "IMAGE":
                    out["links"] = [101]
        if node.get("id") == 30:
            for inp in node.get("inputs", []):
                if isinstance(inp, dict) and inp.get("name") == "sigmas":
                    inp["link"] = 101
    assert evaluate_predicate(candidate, fi.repaired_predicate) is False
    assert evaluate_predicate(candidate, fi.fault_predicate) is True
    assert _verdict(candidate) is Verdict.REJECTED


# ── Control 5: meaningful widget difference → ALTERNATIVE_REPAIR ─────────────


def test_control5_wrong_widgets_are_a_weaker_tier_not_a_failure() -> None:
    fi = _fault_injection()
    candidate = _candidate_with_manual_sigmas(
        sigma_schedule=WRONG_SIGMA_SCHEDULE,
        node_id=20,
        edges=("10->20", "20->30"),
    )
    witness = fi.repaired_predicate["locus"][0]
    grade = grade_additive_witness(candidate, witness)
    assert grade.verdict is AdditiveWitnessVerdict.ALTERNATIVE_REPAIR
    assert grade.widget_equivalence == "different"
    assert evaluate_predicate(candidate, fi.repaired_predicate) is True
    assert evaluate_predicate(candidate, fi.fault_predicate) is False
    assert _verdict(candidate) is Verdict.ALTERNATIVE_REPAIR

    # Restore-regression mode deliberately preserves the historical exact
    # widget-vector identity check.
    assert evaluate_predicate(
        candidate,
        fi.repaired_predicate,
        additive_mode="restore-exact",
    ) is False
    assert evaluate_predicate(
        candidate,
        fi.fault_predicate,
        additive_mode="restore-exact",
    ) is True


# ── Control 6: same-type decoy without right edges/widgets → REJECTED ─────────


def test_control6_same_type_decoy_is_rejected() -> None:
    fi = _fault_injection()
    # A DIFFERENT ManualSigmas node (id 25) with wrong widgets and no edges,
    # while the real target node 20 stays absent.
    candidate = copy.deepcopy(_broken_graph())
    candidate["nodes"].append({
        "id": 25,
        "type": "ManualSigmas",
        "widgets_values": [WRONG_SIGMA_SCHEDULE],
        "outputs": [{"name": "SIGMAS", "type": "SIGMAS", "links": [], "slot_index": 0}],
        "inputs": [{"name": "IMAGE", "type": "IMAGE", "link": None}],
    })
    assert evaluate_predicate(candidate, fi.repaired_predicate) is False
    assert evaluate_predicate(candidate, fi.fault_predicate) is True
    assert _verdict(candidate) is Verdict.REJECTED


# ── Practical widget equivalence controls ────────────────────────────────────


def test_path_separator_only_difference_is_accepted_by_additive_grade() -> None:
    golden = _golden_graph()
    golden["nodes"][1]["widgets_values"] = [
        "WanVid/wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors"
    ]
    fi = _fault_injection_for(golden)
    candidate = copy.deepcopy(golden)
    candidate["nodes"][1]["widgets_values"] = [
        r"WanVid\wan2.1-1.3b-control-lora-tile-v0.1_comfy.safetensors"
    ]

    witness = fi.repaired_predicate["locus"][0]
    grade = grade_additive_witness(candidate, witness)
    assert grade.verdict is AdditiveWitnessVerdict.ACCEPTED
    assert grade.widget_equivalence == "practical"
    assert evaluate_predicate(candidate, fi.repaired_predicate) is True
    assert evaluate_predicate(candidate, fi.fault_predicate) is False

    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(candidate, execution_safe=True, output_reachable=True)
    assert result.verdict is Verdict.ACCEPTED


def test_trailing_default_elision_is_accepted_by_additive_grade() -> None:
    golden = _golden_graph()
    golden["nodes"][1]["widgets_values"] = [SIGMA_SCHEDULE, None, "default"]
    fi = _fault_injection_for(golden)
    candidate = copy.deepcopy(golden)
    candidate["nodes"][1]["widgets_values"] = [SIGMA_SCHEDULE]

    witness = fi.repaired_predicate["locus"][0]
    grade = grade_additive_witness(candidate, witness)
    assert grade.verdict is AdditiveWitnessVerdict.ACCEPTED
    assert grade.widget_equivalence == "practical"
    assert evaluate_predicate(candidate, fi.repaired_predicate) is True
    assert evaluate_predicate(candidate, fi.fault_predicate) is False

    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(candidate, execution_safe=True, output_reachable=True)
    assert result.verdict is Verdict.ACCEPTED


# ── Qualitative judge controls ───────────────────────────────────────────────


def test_llm_judge_accepts_trivial_difference_with_grounded_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The primary grade is qualitative and never receives golden widgets."""
    golden = _golden_graph()
    golden_value = "models/feature/example.safetensors"
    candidate_value = r"models\feature\example.safetensors"
    golden["nodes"][1]["widgets_values"] = [golden_value]
    fi = _fault_injection_for(golden)
    candidate = copy.deepcopy(golden)
    candidate["nodes"][1]["widgets_values"] = [candidate_value]
    captured: dict[str, object] = {}

    def accepted(
        messages: list[dict[str, str]],
        profile_name: str,
    ) -> dict:
        captured["messages"] = messages
        captured["profile"] = profile_name
        return {
            "json": {
                "verdict": "accepted",
                "reason": (
                    "ManualSigmas node 20 is wired from the LoadImage node 10 "
                    "IMAGE output into its IMAGE input and from its SIGMAS "
                    "output to the KSampler node 30 sigmas input; the candidate "
                    "path spelling is practically equivalent and preserves the "
                    "feature's effect. UI-to-API conversion and output "
                    "reachability make the graph runnable, while actual runtime "
                    "execution remains runtime_unverified."
                ),
            }
        }

    monkeypatch.setenv("VIBECOMFY_JUDGE_PROFILE", "judge-test")
    monkeypatch.setattr(additive_judge, "_call_judge_model", accepted)
    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(candidate, execution_safe=True, output_reachable=True)

    assert result.verdict is Verdict.ACCEPTED
    judge_gate = next(g for g in result.gates if g.name == "additive_llm_judge")
    assert judge_gate.passed is True
    assert judge_gate.detail["source"] == "llm"
    assert judge_gate.detail["profile"] == "judge-test"
    assert "ManualSigmas" in judge_gate.reason
    assert "LoadImage" in judge_gate.reason
    assert "KSampler" in judge_gate.reason
    assert "runtime_unverified" in judge_gate.reason

    messages = captured["messages"]
    assert isinstance(messages, list)
    evidence = json.loads(messages[1]["content"])
    witness_values = evidence["intended_features_and_candidate_evidence"][0][
        "candidate_witness"
    ]["widget_values"]
    assert witness_values == [candidate_value]
    assert golden_value not in messages[1]["content"]


@pytest.mark.parametrize("bad_edit", ["wrong_type", "wrong_wiring"])
def test_hard_floor_rejects_before_llm_judge(
    monkeypatch: pytest.MonkeyPatch,
    bad_edit: str,
) -> None:
    fi = _fault_injection()
    if bad_edit == "wrong_type":
        candidate = _candidate_with_manual_sigmas()
        next(node for node in candidate["nodes"] if node["id"] == 20)[
            "type"
        ] = "WrongNode"
    else:
        candidate = _candidate_with_manual_sigmas(edges=("10->20",))
    calls = 0

    def should_not_run(
        messages: list[dict[str, str]],
        profile_name: str,
    ) -> dict:
        nonlocal calls
        calls += 1
        raise AssertionError("judge must not run before the hard floor passes")

    monkeypatch.setattr(additive_judge, "_call_judge_model", should_not_run)
    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(candidate, execution_safe=True, output_reachable=True)

    assert result.verdict is Verdict.REJECTED
    assert calls == 0
    assert all(g.name != "additive_llm_judge" for g in result.gates)


def test_dead_additive_branch_rejects_before_llm_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated/global output flag cannot hide a severed feature branch."""
    golden = _golden_graph()
    sampler = next(node for node in golden["nodes"] if node["id"] == 30)
    sampler["outputs"] = [
        {"name": "IMAGE", "type": "IMAGE", "links": [3], "slot_index": 0}
    ]
    golden["nodes"].append(
        {
            "id": 40,
            "type": "SaveImage",
            "widgets_values": ["output"],
            "outputs": [],
            "inputs": [{"name": "images", "type": "IMAGE", "link": 3}],
        }
    )
    golden["links"].append([3, 30, 0, 40, 0, "IMAGE"])
    broken = copy.deepcopy(golden)
    broken["nodes"] = [node for node in broken["nodes"] if node["id"] != 20]
    broken["links"] = [
        link for link in broken["links"] if 20 not in {link[1], link[3]}
    ]
    next(node for node in broken["nodes"] if node["id"] == 10)[
        "outputs"
    ][0]["links"] = []
    next(node for node in broken["nodes"] if node["id"] == 30)[
        "inputs"
    ][0]["link"] = None
    fi = derive_repair_delta(broken, golden)
    candidate = copy.deepcopy(golden)
    candidate["links"] = [link for link in candidate["links"] if link[0] != 3]
    next(node for node in candidate["nodes"] if node["id"] == 30)[
        "outputs"
    ][0]["links"] = []
    next(node for node in candidate["nodes"] if node["id"] == 40)[
        "inputs"
    ][0]["link"] = None
    calls = 0

    def should_not_run(
        messages: list[dict[str, str]],
        profile_name: str,
    ) -> dict:
        nonlocal calls
        calls += 1
        raise AssertionError("dead feature branches must fail mechanically")

    monkeypatch.setattr(additive_judge, "_call_judge_model", should_not_run)
    assert evaluate_predicate(candidate, fi.repaired_predicate) is True

    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(
        candidate,
        execution_safe=True,
        # Simulate a graph-global reachability signal kept true by another
        # branch; the additive branch itself must still be proven.
        output_reachable=True,
    )

    assert result.verdict is Verdict.REJECTED
    assert calls == 0
    repair_gate = next(g for g in result.gates if g.name == "repair_postcondition")
    assert repair_gate.detail["additive_output_path"] is False
    assert "terminal node(s): 40" in repair_gate.reason


def test_llm_judge_failure_falls_back_to_rule_grade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    golden = _golden_graph()
    golden["nodes"][1]["widgets_values"] = [SIGMA_SCHEDULE, None, "default"]
    fi = _fault_injection_for(golden)
    candidate = copy.deepcopy(golden)
    candidate["nodes"][1]["widgets_values"] = [SIGMA_SCHEDULE]

    def provider_failure(
        messages: list[dict[str, str]],
        profile_name: str,
    ) -> dict:
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(additive_judge, "_call_judge_model", provider_failure)
    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(candidate, execution_safe=True, output_reachable=True)

    assert result.verdict is Verdict.ACCEPTED
    judge_gate = next(g for g in result.gates if g.name == "additive_llm_judge")
    assert judge_gate.passed is True
    assert judge_gate.detail["source"] == "rule_fallback"
    assert "TimeoutError" in judge_gate.detail["fallback_error"]
    assert "ManualSigmas node 20" in judge_gate.reason
    assert "runtime_unverified" in judge_gate.reason


def test_restore_exact_mode_accepts_identical_candidate() -> None:
    fi = _fault_injection()
    assert evaluate_predicate(
        fi.golden,
        fi.repaired_predicate,
        additive_mode="restore-exact",
    ) is True
    assert evaluate_predicate(
        fi.golden,
        fi.fault_predicate,
        additive_mode="restore-exact",
    ) is False
    assert _verdict(fi.golden) is Verdict.ACCEPTED


# ── Hard gates remain hard ───────────────────────────────────────────────────


def test_wrong_node_type_with_expected_edges_is_rejected() -> None:
    fi = _fault_injection()
    candidate = _candidate_with_manual_sigmas()
    next(node for node in candidate["nodes"] if node["id"] == 20)["type"] = "WrongNode"
    assert evaluate_predicate(candidate, fi.repaired_predicate) is False
    assert evaluate_predicate(candidate, fi.fault_predicate) is True
    assert _verdict(candidate) is Verdict.REJECTED


@pytest.mark.parametrize(
    ("execution_safe", "output_reachable"),
    [(False, True), (True, False)],
)
def test_correct_additive_structure_still_rejects_when_not_runnable(
    execution_safe: bool,
    output_reachable: bool,
) -> None:
    fi = _fault_injection()
    candidate = _candidate_with_manual_sigmas()
    oracle = Oracle(fi.fault_predicate, fi.repaired_predicate, fi.broken, fi.golden)
    result = oracle.evaluate(
        candidate,
        execution_safe=execution_safe,
        output_reachable=output_reachable,
    )
    assert result.verdict is Verdict.REJECTED


# ── Sanity: the witness contract is actually emitted (guards regressions) ─────


def test_witness_loci_are_emitted_by_delta_builder() -> None:
    """The repair delta for the additive case must produce exactly one
    additive_witness (repaired) and one additive_absence (fault) locus, and NO
    node_type_present locus (the old tautology)."""
    fi = _fault_injection()
    fault_locus = fi.fault_predicate["locus"]
    repaired_locus = fi.repaired_predicate["locus"]
    assert any(item.get("type") == "additive_absence" for item in fault_locus), (
        f"fault predicate missing additive_absence locus: {fault_locus}"
    )
    assert any(item.get("type") == "additive_witness" for item in repaired_locus), (
        f"repaired predicate missing additive_witness locus: {repaired_locus}"
    )
    assert all(item.get("type") != "node_type_present" for item in fault_locus), (
        f"old node_type_present tautology still present in fault locus: {fault_locus}"
    )
    assert all(item.get("type") != "node_type_present" for item in repaired_locus), (
        f"old node_type_present still present in repaired locus: {repaired_locus}"
    )


def test_witness_locus_carries_edges_and_widgets() -> None:
    """The witness locus must carry both edges AND the golden widgets_values."""
    fi = _fault_injection()
    witness = next(
        item for item in fi.repaired_predicate["locus"]
        if item.get("type") == "additive_witness"
    )
    assert witness["node_type"] == "ManualSigmas"
    assert witness["widgets_values"] == [SIGMA_SCHEDULE], (
        f"witness must capture golden sigma schedule, got {witness['widgets_values']}"
    )
    # Two edges: one in (LoadImage→ManualSigmas), one out (ManualSigmas→KSampler).
    assert len(witness["edges"]) == 2, (
        f"expected 2 witness edges (in + out), got {witness['edges']}"
    )
    directions = sorted(e["direction"] for e in witness["edges"])
    assert directions == ["in", "out"], (
        f"witness edges must cover one in + one out, got {witness['edges']}"
    )
