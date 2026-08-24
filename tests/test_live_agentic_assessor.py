"""ADJUDICATION-4 grounded expected-no-candidate adjudication + audit artifact.

Every assessor test calls the REAL ``assess_live_output_dir`` — no
monkeypatching of the assessor, the canonical contract parser, JSON loading,
matching helpers, judge results, or verdict authority.  Audit-artifact tests
replay every structured claim against the actual corpus graphs and the
authoritative object_info index/caches.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.live_agentic_harness.assessor import assess_live_output_dir
from tests.live_agentic_harness.scenario_obligations import (
    descriptor_contract_violations,
    load_scenario_obligation,
)

SCENARIOS_DIR = Path(__file__).parent / "live_agentic_harness" / "scenarios"
HARNESS_DIR = Path(__file__).parent / "live_agentic_harness"

D813FE = "image-kolors-image-generation-with-segs-detailer-and-d813fe"
RIG_352066 = "3d-3d-model-generation-and-rigging-from-image-352066"
HOTSHOT = "hotshot-16-frames-agent-edit"
B55994 = "audio-audio-processing-with-chatterbox-tts-and-vc-b55994"
ONE_B1360 = "audio-acestep-audio-generation-and-processing-workfl-1b1360"
C80BBF = "audio-ltx-video-and-audio-generation-with-lora-and-m-c80bbf"
NINE_49658 = "image-face-detection-and-cropping-workflow-949658"

OBJECT_INFO_ROOT = (
    Path(__file__).parent.parent / "vibecomfy" / "porting" / "cache" / "object_info"
)


def _descriptor(scenario_id: str) -> dict:
    return json.loads((SCENARIOS_DIR / f"{scenario_id}.json").read_text(encoding="utf-8"))


def _write_response(output_dir: Path, response: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "response.json").write_text(
        json.dumps(response, indent=2), encoding="utf-8"
    )


def _generic_clarify(*, kind: str = "clarify", route: str | None = None) -> dict:
    """The behavioral proof case: a generic clarify without any evidence."""
    return {
        "ok": True,
        "route": route or kind,
        "graph_unchanged": True,
        "outcome": {"kind": kind},
        "message": "Which detector should be used instead?",
        "no_candidate_reason": "no_changes",
    }


def _issues(assessment: dict, check: str | None = None) -> list[dict]:
    return [
        i
        for i in assessment["issues"]
        if i["severity"] in {"error", "undetermined"}
        and (check is None or i["check"] == check)
    ]


def _errors(assessment: dict) -> list[str]:
    return [i["check"] for i in assessment["issues"] if i["severity"] == "error"]


# ---------------------------------------------------------------------------
# 1-11: the tri-state adjudication contract (real assess_live_output_dir)
# ---------------------------------------------------------------------------


def test_expected_no_candidate_without_response_is_undetermined(tmp_path: Path) -> None:
    """ADJUDICATION-4 ruling 1.1a: no response.json grades undetermined —
    never pass — via ``expected_no_candidate_response_missing``, adjudicated
    OUTSIDE the response guard."""
    scenario = _descriptor(D813FE)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    missing = [
        i for i in assessment["issues"]
        if i["check"] == "expected_no_candidate_response_missing"
    ]
    assert len(missing) == 1 and missing[0]["severity"] == "undetermined"


def test_named_contract_no_changes_without_class_evidence_is_undetermined(
    tmp_path: Path,
) -> None:
    """Ruling 1.1c: a generic clarify whose only label is the terminal-state
    ``no_changes`` can NEVER satisfy a named-class contract."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        _generic_clarify(kind="requires_custom_nodes"),
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    ungrounded = _issues(assessment, "expected_no_candidate_ungrounded")
    assert len(ungrounded) == 1


def test_named_contract_exact_missing_class_evidence_passes(tmp_path: Path) -> None:
    """Ruling 1.1b: the authoritative authoring_blocker citing the exact
    declared class grounds the leg with outcome_class expected_no_candidate."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "requires_custom_nodes",
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "missing_classes": ["GroundingDINO"],
            },
            "report": {
                "authoring_blocker": {
                    "reason": "named_class_absent_from_schema",
                    "missing_runtime_classes": ["GroundingDINO"],
                    "message": "Which detector should be used instead?",
                },
            },
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]
    assert assessment["outcome_class"] == "expected_no_candidate"
    grounded = [
        i for i in assessment["issues"]
        if i["check"] == "expected_no_candidate_grounded"
    ]
    assert len(grounded) == 1 and grounded[0]["severity"] == "info"


def test_named_contract_declared_family_prefix_evidence_passes(tmp_path: Path) -> None:
    """Ruling 1.1b: the DECLARED token may be a family prefix of the cited
    full runtime class (Hotshot ⊢ HotshotXLImg2Img)."""
    scenario = _descriptor(HOTSHOT)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "requires_custom_nodes",
            "graph_unchanged": True,
            "outcome": {
                "kind": "requires_custom_nodes",
                "missing_classes": ["HotshotXLImg2Img"],
            },
            "report": {
                "authoring_blocker": {
                    "reason": "named_class_absent_from_schema",
                    "missing_runtime_classes": ["HotshotXLImg2Img"],
                    "message": "Install a Hotshot generation node to proceed.",
                },
            },
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]
    assert assessment["outcome_class"] == "expected_no_candidate"


def test_named_contract_reverse_substring_class_is_undetermined(
    tmp_path: Path,
) -> None:
    """Ruling 1.1b: NO reverse-prefix and NO inner-substring matching —
    cited 'DINO'/'SomeGroundingDINOWrapper' do NOT satisfy declared
    'GroundingDINO'; mismatched grounding evidence is undetermined."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "requires_custom_nodes",
            "graph_unchanged": True,
            "outcome": {"kind": "requires_custom_nodes"},
            "report": {
                "authoring_blocker": {
                    "reason": "named_class_absent_from_schema",
                    "missing_runtime_classes": ["DINO", "SomeGroundingDINOWrapper"],
                    "message": "Missing.",
                },
            },
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    assert assessment["outcome_class"] != "expected_no_candidate"
    assert _issues(assessment, "expected_no_candidate_ungrounded")


def test_named_contract_unrelated_missing_class_is_undetermined(tmp_path: Path) -> None:
    """Ruling 1.1e: unrelated missing classes are evidence-mismatch
    (undetermined), never a pass."""
    scenario = _descriptor(D813FE)
    response = _generic_clarify()
    response["route"] = "requires_custom_nodes"
    response["outcome"] = {
        "kind": "requires_custom_nodes",
        "missing_classes": ["SomeUnrelatedPackNode"],
    }
    response["report"] = {
        "authoring_blocker": {
            "reason": "named_class_absent_from_schema",
            "missing_runtime_classes": ["SomeUnrelatedPackNode"],
        }
    }
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    assert "expected_no_candidate_ungrounded" in {
        i["check"] for i in _issues(assessment)
    }


def test_named_contract_requires_authoring_blocker_not_outcome_projection_alone(
    tmp_path: Path,
) -> None:
    """Ruling 1.1b: ``outcome.missing_classes`` is only the public projection;
    without the authoritative report.authoring_blocker carrier it can never
    ground the contract."""
    scenario = _descriptor(D813FE)
    response = _generic_clarify()
    response["route"] = "requires_custom_nodes"
    response["outcome"] = {
        "kind": "requires_custom_nodes",
        "missing_classes": ["GroundingDINO"],
    }
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    assert "only the public projection" in "\n".join(
        i["detail"] for i in assessment["issues"]
    )


def test_structural_contract_no_changes_without_premise_evidence_is_undetermined(
    tmp_path: Path,
) -> None:
    """Ruling 1.1d: for structural contracts a reason string plus a generic
    ``no_changes`` label is insufficient — undetermined, never pass."""
    scenario = _descriptor(RIG_352066)
    assert scenario["assessment"].get("expected_no_candidate_absent_features")
    response = _generic_clarify()
    response["message"] = (
        "No node controls knee orientation: TripoRigNode takes only a task id."
    )
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    assert _issues(assessment, "expected_no_candidate_ungrounded")


def test_structural_contract_verified_member_absence_passes(tmp_path: Path) -> None:
    """Ruling 1.1d: an independently verifiable typed feature-absence blocker
    (present=false, available members agreeing with the frozen schema, class
    present in the source graph) passes the structural contract."""
    scenario = _descriptor(RIG_352066)
    (tmp_path / "original.ui.json").write_text(
        json.dumps(
            {
                "nodes": {
                    "41": {"id": "41", "class_type": "TripoRigNode"},
                    "42": {"id": "42", "class_type": "TripoRetargetNode"},
                }
            }
        ),
        encoding="utf-8",
    )
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "clarify",
            "graph_unchanged": True,
            "outcome": {"kind": "clarify"},
            "report": {
                "authoring_blocker": {
                    "reason": "structural_feature_absent",
                    "feature_absences": [
                        {
                            "feature": "joint_orientation",
                            "checks": [
                                {
                                    "class_type": "TripoRigNode",
                                    "member_kind": "input",
                                    "member": "joint_orientation",
                                    "present": False,
                                    "available_members": ["original_model_task_id"],
                                },
                                {
                                    "class_type": "TripoRetargetNode",
                                    "member_kind": "input",
                                    "member": "joint_orientation",
                                    "present": False,
                                    "available_members": [
                                        "animation",
                                        "original_model_task_id",
                                    ],
                                },
                            ],
                        }
                    ],
                },
            },
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "pass", assessment["issues"]
    assert assessment["outcome_class"] == "expected_no_candidate"
    grounded = [
        i for i in assessment["issues"]
        if i["check"] == "expected_no_candidate_grounded"
    ]
    assert len(grounded) == 1


def test_bare_non_edit_edit_scenario_is_undetermined(tmp_path: Path) -> None:
    """Ruling 1.1f (inverted regression guard): apply/expect_graph_changed
    false WITHOUT a declared contract or explicit non-edit lane is an invalid
    untyped no-edit obligation — direct assessor invocation grades it
    ``undetermined``, never pass."""
    scenario = {
        "id": "synthetic-bare-non-edit",
        "apply": False,
        "assessment": {"expect_graph_changed": False},
    }
    _write_response(tmp_path, _generic_clarify())

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "undetermined", assessment["issues"]
    assert assessment["outcome_class"] != "non_edit_route_answered"
    untyped = [
        i for i in assessment["issues"]
        if i["check"] == "untyped_non_edit_expectation"
    ]
    assert len(untyped) == 1 and untyped[0]["severity"] == "undetermined"


def test_expected_no_candidate_explicit_edit_is_fail(tmp_path: Path) -> None:
    """A declared expected-no-candidate scenario requires graph_unchanged;
    a fabricated or landed edit contradicts the refusal contract (fail)."""
    scenario = _descriptor(D813FE)
    _write_response(
        tmp_path,
        {
            "ok": True,
            "route": "adapt",
            "graph_unchanged": False,
            "outcome": {"kind": "candidate"},
        },
    )

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    assert "expected_no_candidate_graph_unchanged" in _errors(assessment)


def test_expected_no_candidate_wrong_refusal_kind_is_fail(tmp_path: Path) -> None:
    """KEPT contract: even with grounding evidence present, an undeclared
    outcome kind cannot satisfy the refusal contract."""
    scenario = _descriptor(D813FE)
    response = _generic_clarify()
    response["route"] = "respond"
    response["outcome"] = {"kind": "noop"}
    response["report"] = {
        "authoring_blocker": {
            "reason": "named_class_absent_from_schema",
            "missing_runtime_classes": ["GroundingDINO"],
        }
    }
    _write_response(tmp_path, response)

    assessment = assess_live_output_dir(tmp_path, scenario)

    assert assessment["verdict"] == "fail", assessment["issues"]
    assert "expected_no_candidate_refusal_kind" in _errors(assessment)


# ---------------------------------------------------------------------------
# 12: metadata integrity on the corrected d813fe descriptor
# ---------------------------------------------------------------------------


def test_d813fe_metadata_matches_image_corpus_intent() -> None:
    """Ruling 1.2: every retained _tags field describes the CURRENT
    descriptor — image corpus intent, restored source, narrowed typed
    terminal, retained named-class premise."""
    d = _descriptor(D813FE)
    tags = d["_tags"]
    assert tags["modality"] == "image"
    assert tags["task_type"] == "text_to_image"
    assert tags["source"] == "external_workflows/corpus"
    assert tags["source_workflow_id"] == "d813fedaabea87b7"
    assert d["workflow_path"].endswith("d813fedaabea87b7.json")
    kinds = d["assessment"]["allow_safe_refusal_outcome_kinds"]
    assert kinds == ["requires_custom_nodes"]
    assert d["assessment"]["expected_no_candidate_absent_classes"] == ["GroundingDINO"]
    assert "GroundingDINO" in d["query"]
    assert "GroundingDINO" in tags["author_rationale"]
    assert descriptor_contract_violations(d) == ()


# ---------------------------------------------------------------------------
# 13-15: machine-readable audit artifact over the locked final50
# ---------------------------------------------------------------------------


def _audit() -> dict:
    return json.loads(
        (HARNESS_DIR / "scenario_data_audit.json").read_text(encoding="utf-8")
    )


def _final50_ids() -> list[str]:
    manifest = json.loads(
        (HARNESS_DIR / "threaded_comparison_manifest_final50.json").read_text(
            encoding="utf-8"
        )
    )
    return [str(e["id"]) for e in manifest["entries"]]


def test_scenario_data_audit_exactly_covers_final50_with_exact_ids() -> None:
    """Ruling 1.3: exactly one row per final50 ID, exact IDs (no ellipses),
    exact queries/workflow paths, bounded decision vocabulary, and a rendered
    dispatch table that mirrors the rows."""
    audit = _audit()
    ids = _final50_ids()
    rows = audit["rows"]
    assert [r["scenario_id"] for r in rows] == ids
    assert len(rows) == 50
    assert len({r["scenario_id"] for r in rows}) == 50
    for r in rows:
        assert "…" not in r["scenario_id"]
        d = _descriptor(r["scenario_id"])
        assert r["query"] == d["query"]
        assert r["workflow_path"] == d.get("workflow_path")
        assert r["decision"] in {"no-change", "ALIGN", "ANNOTATE"}
        assert isinstance(r["checks"], list) and r["checks"]
        assert r["determination"].strip()
    table_lines = [
        line
        for line in audit["dispatch_table"].splitlines()
        if line.startswith("| ") and "---" not in line
    ][1:]
    assert len(table_lines) == 50
    for r, line in zip(rows, table_lines):
        cells = [c.strip() for c in line.split("|")[1:-1]]
        assert cells[1] == r["scenario_id"], line
        assert cells[2] == r["decision"], line


def test_scenario_data_audit_evidence_replays_against_graph_and_index() -> None:
    """The audit replay: resolve every referenced graph node/class against the
    actual workflow file and every lookup/schema claim against the
    authoritative index and its pack caches. Non-empty fields are not
    sufficient — claims must RESOLVE."""
    audit = _audit()

    def load_graph(wf: str) -> dict:
        data = json.loads((REPO_ROOT / wf).read_text(encoding="utf-8"))
        nodes: dict[str, dict] = {}
        if isinstance(data.get("nodes"), dict):
            items = [(str(k), v) for k, v in data["nodes"].items()]
        elif isinstance(data.get("nodes"), list):
            items = [(str(n.get("id")), n) for n in data["nodes"]]
        else:
            items = [
                (str(k), v)
                for k, v in data.items()
                if isinstance(v, dict) and ("class_type" in v or "type" in v)
            ]
        for nid, n in items:
            nodes[nid] = n
        return nodes

    def cache_entry(cls: str) -> dict:
        idx = json.loads((OBJECT_INFO_ROOT / "index.json").read_text(encoding="utf-8"))
        fname = idx.get(cls)
        assert fname, cls
        return json.loads((OBJECT_INFO_ROOT / fname).read_text(encoding="utf-8"))[cls]

    def surface(entry: dict, mk: str) -> list[str]:
        if mk == "output":
            outs = []
            for o in entry.get("outputs") or []:
                if isinstance(o, dict):
                    outs.append(str(o.get("name") or o.get("type")))
                elif isinstance(o, str):
                    outs.append(o)
            return outs
        names = []
        ins = entry.get("inputs") or {}
        for grp in ("required", "optional"):
            block = ins.get(grp)
            if isinstance(block, dict):
                names.extend(str(k) for k in block)
        return names

    for row in audit["rows"]:
        sid = row["scenario_id"]
        gnodes = None
        for check in row["checks"]:
            surface_name = check["surface"]
            if surface_name == "descriptor_contract":
                d = _descriptor(sid)
                a = d.get("assessment") or {}
                if check["lane"] == "expected_no_candidate":
                    assert a.get("expected_no_candidate_reason")
                    assert sorted(check["refusal_kinds"]) == sorted(
                        a["allow_safe_refusal_outcome_kinds"]
                    )
                    assert sorted(check["absent_classes"] or []) == sorted(
                        a.get("expected_no_candidate_absent_classes") or []
                    )
                else:
                    assert check["apply"] == d.get("apply")
                continue
            if surface_name == "graph":
                if gnodes is None:
                    gnodes = load_graph(check["source"])
                node = gnodes.get(str(check["node_id"]))
                assert node is not None, (sid, check)
                cls = node.get("class_type") or node.get("type")
                assert cls == check["class_type"], (sid, check)
                mem = check.get("member")
                if check.get("member_kind") == "node_mode":
                    assert node.get("mode") == check["observed"], (sid, check)
                elif mem:
                    ins = node.get("inputs") or {}
                    if mem in ins and not isinstance(ins[mem], list):
                        if check["observed"] is not None:
                            assert ins[mem] == check["observed"], (sid, check)
                    elif check["observed"] is not None:
                        entry = cache_entry(cls)
                        vals = (
                            (node.get("raw_widgets") or {}).get("values")
                            or (node.get("metadata", {}).get("_ui", {}) or {}).get(
                                "widgets_values"
                            )
                            or node.get("widgets_values")
                            or [
                                v
                                for k, v in sorted(ins.items())
                                if k.startswith("widget_")
                            ]
                        )
                        assert check["observed"] in vals, (sid, check)
            elif surface_name == "authoritative_index":
                lk = check["lookup"]
                idx = json.loads(
                    (OBJECT_INFO_ROOT / "index.json").read_text(encoding="utf-8")
                )
                term = lk["term"]
                if lk["mode"] == "exact":
                    recomputed = [term] if term in idx else []
                else:
                    recomputed = sorted(
                        k for k in idx if k.casefold().startswith(term.casefold())
                    )
                assert check["matches"] == recomputed, (sid, lk)
                mem = check.get("schema_member")
                ev = check.get("schema_evidence")
                if mem is None and ev is None:
                    continue
                assert recomputed, (sid, lk)
                entry = cache_entry(recomputed[0])
                mk = check.get("member_kind") or "input"
                if ev and ev.get("present") is False:
                    surf = sorted(surface(entry, mk))
                    assert mem not in surf, (sid, check)
                    assert ev["available_members"] == surf, (sid, check)
                    continue
                surf = surface(entry, mk)
                assert mem in surf, (sid, check, surf)
                if ev:
                    ins = entry.get("inputs") or {}
                    spec = None
                    for grp in ("required", "optional"):
                        block = ins.get(grp)
                        if isinstance(block, dict) and mem in block:
                            spec = block[mem]
                            break
                    real_type = None
                    options = None
                    if isinstance(spec, list) and spec:
                        if isinstance(spec[0], list):
                            real_type = "COMBO"
                            options = [str(x) for x in spec[0]]
                        else:
                            real_type = spec[0]
                    if len(spec or ()) > 1 and isinstance(spec[1], dict):
                        o2 = spec[1].get("options")
                        if o2 is not None:
                            options = [str(x) for x in o2]
                    assert ev.get("type") == real_type or real_type is None, (
                        sid,
                        check,
                        spec,
                    )
                    if options is not None:
                        assert ev.get("options") == options, (sid, check, spec)
                    if ev.get("display_name"):
                        assert ev["display_name"] == entry.get("display_name")


REPO_ROOT = Path(__file__).parent.parent


def test_disputed_audio_audit_rows_have_supported_dispositions() -> None:
    """The four disputed audio/vision rows carry evidence-backed dispositions:
    b55994 ALIGN-to-FLAC (indexed saver, shared AUDIO input, NO WAV saver),
    1b1360 ANNOTATE structural spectral-gating absence, c80bbf/949658 ANNOTATE
    named-class absence covering every retained alternative."""
    audit = _audit()
    rows = {r["scenario_id"]: r for r in audit["rows"]}
    idx = json.loads((OBJECT_INFO_ROOT / "index.json").read_text(encoding="utf-8"))

    b = rows[B55994]
    assert b["decision"] == "ALIGN" and b["offending_phrase"] == "WAV"
    saveaudio_family = sorted(
        k for k in idx if k.casefold().startswith("saveaudio")
    )
    assert saveaudio_family == ["SaveAudio", "SaveAudioMP3", "SaveAudioOpus"]
    assert not any("wav" in k.casefold() for k in saveaudio_family)
    cache = json.loads(
        (OBJECT_INFO_ROOT / idx["SaveAudio"]).read_text(encoding="utf-8")
    )
    assert cache["SaveAudio"]["display_name"] == "Save Audio (FLAC)"
    assert cache["SaveAudio"]["inputs"]["required"]["audio"][0] == "AUDIO"
    assert cache["SaveAudioMP3"]["inputs"]["required"]["audio"][0] == "AUDIO"
    d = _descriptor(B55994)
    assert "FLAC" in d["query"] and "WAV" not in d["query"]

    one = rows[ONE_B1360]
    assert one["decision"] == "ANNOTATE"
    contract = _descriptor(ONE_B1360)["assessment"]
    features = contract["expected_no_candidate_absent_features"]
    assert features[0]["feature"] == "spectral_gating"
    ksampler = cache["KSampler"] if False else json.loads(
        (OBJECT_INFO_ROOT / idx["KSampler"]).read_text(encoding="utf-8")
    )["KSampler"]
    for check_spec in features[0]["checks"]:
        cls = check_spec["class_type"]
        entry = json.loads(
            (OBJECT_INFO_ROOT / idx[cls]).read_text(encoding="utf-8")
        )[cls]
        members = [
            str(k)
            for grp in ("required", "optional")
            for k in (entry["inputs"].get(grp) or {})
        ]
        assert check_spec["member"] not in members, cls
    assert "karras" in (
        ksampler["inputs"]["required"]["scheduler"][0]
        if isinstance(ksampler["inputs"]["required"]["scheduler"][0], list)
        else ksampler["inputs"]["required"]["scheduler"]
    ) or "karras" in (ksampler["inputs"]["required"]["scheduler"][1] or {}).get(
        "options", []
    )

    for sid, tokens in ((C80BBF, ["audioldm2"]), (NINE_49658, ["mtcnn", "retinaface"])):
        row = rows[sid]
        assert row["decision"] == "ANNOTATE", sid
        desc = _descriptor(sid)
        absent = desc["assessment"]["expected_no_candidate_absent_classes"]
        assert len(absent) == len(tokens), (sid, absent)
        for token in tokens:
            complete = sorted(k for k in idx if k.casefold().startswith(token))
            assert complete == [], (sid, token, complete)
