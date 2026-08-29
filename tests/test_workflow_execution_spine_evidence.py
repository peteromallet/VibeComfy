from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_workflow_execution_spine_evidence.py"
spec = importlib.util.spec_from_file_location("vcspine_validator", VALIDATOR_PATH)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

WRAPPER_PATH = ROOT / "scripts" / "run_workflow_execution_spine_agent.py"
wrapper_spec = importlib.util.spec_from_file_location("vcspine_wrapper", WRAPPER_PATH)
assert wrapper_spec and wrapper_spec.loader
wrapper = importlib.util.module_from_spec(wrapper_spec)
wrapper_spec.loader.exec_module(wrapper)

DISPOSABLE_ROOT = Path("/tmp/g0-revision-wrapper-revision2")

def _git(project: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _run_wrapper_case(
    mode: str,
    *,
    ignore_rules: str = "",
    allowed: list[str],
    forbidden: list[str],
) -> tuple[subprocess.CompletedProcess[str], dict, dict | None]:
    DISPOSABLE_ROOT.mkdir(parents=True, exist_ok=True)
    case_root = Path(tempfile.mkdtemp(prefix="case-", dir=DISPOSABLE_ROOT))
    project = case_root / "project"
    evidence = case_root / "evidence"
    project.mkdir()
    evidence.mkdir()
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "G0 wrapper test")
    (project / "seed.txt").write_text("seed\n", encoding="utf-8")
    if ignore_rules:
        (project / ".gitignore").write_text(ignore_rules, encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "seed")
    brief = case_root / "brief.md"
    brief.write_text("brief\n", encoding="utf-8")
    allowance = case_root / "allowance.json"
    allowance.write_text(json.dumps({"allowed": allowed, "forbidden": forbidden}), encoding="utf-8")
    fake = case_root / "fake_launcher.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib\n"
        "import sys\n"
        "project = pathlib.Path(next(a.split('=', 1)[1] for a in sys.argv if a.startswith('--project-dir=')))\n"
        f"mode = {mode!r}\n"
        "if mode == 'cache':\n"
        "    (project / '.pytest_cache' / 'v' / 'cache').mkdir(parents=True)\n"
        "    (project / '.pytest_cache' / 'v' / 'cache' / 'nodeids').write_text('[]')\n"
        "    (project / '__pycache__').mkdir()\n"
        "    (project / '__pycache__' / 'module.pyc').write_bytes(b'pyc')\n"
        "elif mode == 'tracked':\n"
        "    (project / 'seed.txt').write_text('child update')\n"
        "elif mode == 'untracked':\n"
        "    (project / 'untracked.txt').write_text('child create')\n"
        "elif mode == 'hidden':\n"
        "    (project / '.gitignore').write_text('hidden-created/\\n')\n"
        "    (project / 'hidden-created').mkdir()\n"
        "    (project / 'hidden-created' / 'secret.txt').write_text('hidden')\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=sys.stderr)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["VCSPINE_FAKE_LAUNCHER"] = str(fake)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(WRAPPER_PATH),
                "--task-id=G0-wrapper-test",
                "--role=implementer",
                "--label=G0 [HARD-REVISION] wrapper accounting test",
                "--model-route=codex:gpt-5.6-luna",
                f"--query-file={brief}",
                f"--project-dir={project}",
                f"--allowance-file={allowance}",
                f"--evidence-dir={evidence}",
                "--timeout=30",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        receipt_path = evidence / "G0-wrapper-test-receipt.json"
        assert receipt_path.exists(), f"wrapper failed: {result.returncode} {result.stderr}"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        violation_path = evidence / "G0-wrapper-test-violation.json"
        violation = json.loads(violation_path.read_text(encoding="utf-8")) if violation_path.exists() else None
        return result, receipt, violation
    finally:
        shutil.rmtree(case_root)


def test_preexisting_ignore_rules_exclude_pytest_cache_artifacts() -> None:
    result, receipt, violation = _run_wrapper_case(
        "cache",
        ignore_rules=".pytest_cache/\n__pycache__/\n*.pyc\n",
        allowed=["allowed.txt"],
        forbidden=["*"],
    )
    assert result.returncode == 0, result.stderr
    assert receipt["changed_files"] == []
    assert violation is None


def test_tracked_mutation_is_reported_and_rejected() -> None:
    result, receipt, violation = _run_wrapper_case(
        "tracked",
        allowed=["allowed.txt"],
        forbidden=["seed.txt"],
    )
    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    assert receipt["changed_files"] == ["seed.txt"]
    assert violation and violation["violations"] == ["seed.txt"]


def test_nonignored_untracked_create_is_reported_and_rejected() -> None:
    result, receipt, violation = _run_wrapper_case(
        "untracked",
        allowed=["allowed.txt"],
        forbidden=["untracked.txt"],
    )
    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    assert receipt["changed_files"] == ["untracked.txt"]
    assert violation and violation["violations"] == ["untracked.txt"]


def test_child_created_path_under_new_ignore_rule_is_reported_and_rejected() -> None:
    result, receipt, violation = _run_wrapper_case(
        "hidden",
        allowed=["*"],
        forbidden=["hidden-created/**"],
    )
    assert result.returncode == 2
    assert "ALLOWANCE_VIOLATION" in result.stderr
    assert "hidden-created/secret.txt" in receipt["changed_files"]
    assert violation and "hidden-created/secret.txt" in violation["violations"]


def test_probe_cleanup_failure_releases_registry_and_returns_typed_failure(monkeypatch, capsys) -> None:
    DISPOSABLE_ROOT.mkdir(parents=True, exist_ok=True)
    case_root = Path(tempfile.mkdtemp(prefix="cleanup-failure-", dir=DISPOSABLE_ROOT))
    project = case_root / "project"
    evidence = case_root / "evidence"
    project.mkdir()
    evidence.mkdir()
    _git(project, "init", "-q")
    _git(project, "config", "user.email", "test@example.invalid")
    _git(project, "config", "user.name", "G0 cleanup failure test")
    (project / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "seed")
    brief = case_root / "brief.md"
    brief.write_text("brief\n", encoding="utf-8")
    allowance = case_root / "allowance.json"
    allowance.write_text(json.dumps({"allowed": ["allowed.txt"], "forbidden": []}), encoding="utf-8")
    fake = case_root / "fake_launcher.py"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "print('fake result')\n"
        "print('resolved=fake-model', file=__import__('sys').stderr)\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    real_probe = wrapper._capture_ignore_baseline(project)
    probe_path = Path(real_probe.name)

    class FailingProbe:
        name = real_probe.name

        def cleanup(self) -> None:
            real_probe.cleanup()
            raise RuntimeError("simulated ignore-probe cleanup failure")

    monkeypatch.setattr(wrapper, "_capture_ignore_baseline", lambda _project: FailingProbe())
    monkeypatch.setenv("VCSPINE_FAKE_LAUNCHER", str(fake))
    task_id = "G0-wrapper-cleanup-failure"
    result = wrapper.main([
        f"--task-id={task_id}",
        "--role=implementer",
        "--label=G0 [HARD-REVISION] cleanup failure test",
        "--model-route=codex:gpt-5.6-luna",
        f"--query-file={brief}",
        f"--project-dir={project}",
        f"--allowance-file={allowance}",
        f"--evidence-dir={evidence}",
        "--timeout=30",
    ])
    captured = capsys.readouterr()

    try:
        receipt_path = evidence / f"{task_id}-receipt.json"
        failure_path = evidence / f"{task_id}-finalization-failure.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        registry = json.loads((evidence / "active-allowances.json").read_text(encoding="utf-8"))
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        assert result == 2
        assert "FINALIZATION_FAILED" in captured.err
        assert "Traceback" not in captured.err
        assert receipt["finalization"]["type"] == "WRAPPER_FINALIZATION_FAILURE"
        assert receipt["finalization"]["cleanup"] == {
            "attempted": True,
            "succeeded": False,
            "error": {
                "type": "RuntimeError",
                "message": "simulated ignore-probe cleanup failure",
            },
        }
        assert failure == receipt["finalization"]
        assert task_id not in registry
        assert not probe_path.exists()
    finally:
        shutil.rmtree(case_root)


def _manifest() -> dict:
    return {
        "schema_version": "1",
        "final_five": dict(validator.FINAL_FIVE),
        "gates": [], "shards": [], "live_runs": [], "findings": [],
        "tasks": [
            {"task_id": "T0.0", "label": "T0.0 [HARD] source", "model_route": "codex:gpt-5.6-luna"},
            {"task_id": "T0.1", "label": "T0.1 [HARD] freeze", "model_route": "codex:gpt-5.6-luna"},
            {"task_id": "T0.3", "label": "T0.3 [HARD] wrapper", "model_route": "codex:gpt-5.6-luna"},
        ],
    }


def _error(manifest: dict, check: str) -> str:
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.validate_manifest(manifest, ROOT / "manifest.json")
    assert caught.value.error_type == check
    return str(caught.value)


def _nested_receipt_fixture(tmp_path: Path) -> tuple[dict, Path, dict]:
    """Build one nested evidence record and its truthful local receipt."""
    evidence = tmp_path / "evidence"
    receipts = evidence / "receipts"
    receipts.mkdir(parents=True)
    receipt_path = receipts / "nested-receipt.json"
    payload = {
        "task_id": "nested-task",
        "role": "reviewer",
        "label": "nested review",
        "model_route": "grok-4.6",
        "exit": 0,
        "disposition": "continue",
        "result_sha256": "b" * 64,
    }
    receipt_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    receipt_path.write_bytes(receipt_bytes)
    entry = {
        "task_id": "nested-task",
        "receipt_path": "receipts/nested-receipt.json",
        "sha256": hashlib.sha256(receipt_bytes).hexdigest(),
        "result_sha256": payload["result_sha256"],
        "role": payload["role"],
        "label": payload["label"],
        "model_route": payload["model_route"],
        "exit": payload["exit"],
        "disposition": payload["disposition"],
    }
    manifest = {
        "tasks": [],
        "gates": [{"gate_id": "G0", "evidence_sequence": [entry]}],
    }
    return manifest, evidence / "manifest.json", entry


def test_nested_receipt_accounting_accepts_truthful_receipt(tmp_path: Path) -> None:
    manifest, manifest_path, _entry = _nested_receipt_fixture(tmp_path)
    validator.check_nested_record_accounting(manifest, manifest_path)


@pytest.mark.parametrize(
    ("case", "contents", "expected"),
    [
        ("missing", None, "receipt is missing"),
        ("malformed", b"{not-json", "receipt is malformed JSON"),
        ("non-object", b"[]", "receipt must be a JSON object"),
    ],
)
def test_nested_receipt_accounting_rejects_missing_malformed_and_non_object(
    tmp_path: Path, case: str, contents: bytes | None, expected: str
) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    receipt_path = tmp_path / "evidence" / "receipts" / "nested-receipt.json"
    if contents is None:
        receipt_path.unlink()
    else:
        receipt_path.write_bytes(contents)
        entry["sha256"] = hashlib.sha256(contents).hexdigest()
    with pytest.raises(validator.EvidenceValidationError, match="^NESTED_RECORD_ACCOUNTING:") as caught:
        validator.check_nested_record_accounting(manifest, manifest_path)
    assert expected in str(caught.value), case


def test_nested_receipt_accounting_rejects_unreadable_receipt(tmp_path: Path, monkeypatch) -> None:
    manifest, manifest_path, _entry = _nested_receipt_fixture(tmp_path)
    receipt_path = tmp_path / "evidence" / "receipts" / "nested-receipt.json"
    real_read_bytes = Path.read_bytes

    def unreadable(path: Path) -> bytes:
        if path == receipt_path:
            raise OSError("simulated unreadable receipt")
        return real_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", unreadable)
    with pytest.raises(validator.EvidenceValidationError, match="receipt is unreadable"):
        validator.check_nested_record_accounting(manifest, manifest_path)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("sha256", "f" * 64, "receipt digest mismatch"),
        ("result_sha256", "f" * 64, "result_sha256 mismatch"),
        ("role", "implementer", "entry field role untruthful"),
    ],
)
def test_nested_receipt_accounting_rejects_claimed_field_or_digest_mismatch(
    tmp_path: Path, field: str, value: str, expected: str
) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    entry[field] = value
    with pytest.raises(validator.EvidenceValidationError, match="^NESTED_RECORD_ACCOUNTING:") as caught:
        validator.check_nested_record_accounting(manifest, manifest_path)
    assert expected in str(caught.value)


def test_nested_receipt_accounting_rejects_manifest_disposition_absent_from_receipt(tmp_path: Path) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    receipt_path = tmp_path / "evidence" / "receipts" / "nested-receipt.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload.pop("disposition")
    receipt_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    receipt_path.write_bytes(receipt_bytes)
    entry["sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    with pytest.raises(validator.EvidenceValidationError, match="entry field disposition untruthful"):
        validator.check_nested_record_accounting(manifest, manifest_path)


def test_nested_receipt_accounting_rejects_task_id_without_receipt_path(tmp_path: Path) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    del entry["receipt_path"]
    with pytest.raises(validator.EvidenceValidationError, match="lacks receipt_path"):
        validator.check_nested_record_accounting(manifest, manifest_path)


def test_nested_receipt_accounting_rejects_truncated_result_sha256(tmp_path: Path) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    entry["result_sha256"] = "f" * 63
    with pytest.raises(validator.EvidenceValidationError, match="no valid result_sha256 claim"):
        validator.check_nested_record_accounting(manifest, manifest_path)


def test_nested_receipt_accounting_rejects_receipt_task_id_mismatch(tmp_path: Path) -> None:
    manifest, manifest_path, entry = _nested_receipt_fixture(tmp_path)
    receipt_path = tmp_path / "evidence" / "receipts" / "nested-receipt.json"
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    payload["task_id"] = "different-task"
    receipt_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    receipt_path.write_bytes(receipt_bytes)
    entry["sha256"] = hashlib.sha256(receipt_bytes).hexdigest()
    with pytest.raises(validator.EvidenceValidationError, match="task_id mismatch"):
        validator.check_nested_record_accounting(manifest, manifest_path)


def test_canonical_receipt_custody_has_only_restored_truthful_set() -> None:
    receipt_dir = ROOT / "docs/plans/workflow-execution-spine-consolidation-evidence/receipts"
    restored = {path.name for path in receipt_dir.glob("*.json")} - {"t0-3-bootstrap-receipt.json"}
    assert len(restored) == 102
    assert not restored & {
        "DEEP-AUDIT-RE-RUN-20-receipt.json",
        "MANIFEST-REGEN-FIX4-receipt.json",
        "T29A-REDACT-WRITEPATH-receipt.json",
        "T29A-REVIEW-receipt.json",
        "T29A-REVISION-receipt.json",
        "T29A-REREVIEW-receipt.json",
        "T29A-ADJUDICATION-receipt.json",
        "T29A-REVISION-2-receipt.json",
    }


def test_dependency_order_rejects_reversed_cards() -> None:
    manifest = _manifest()
    manifest["tasks"] = [manifest["tasks"][1], manifest["tasks"][0], manifest["tasks"][2]]
    _error(manifest, "DEPENDENCY_ORDER")


def test_model_routing_accepts_legacy_routes_and_stealth_ox_alpha() -> None:
    # Historical records keep validating: [HARD] tasks on Luna (the _manifest default).
    validator.validate_manifest(_manifest(), ROOT / "manifest.json")
    for label, route in (
        ("T0.0 [XHARD] source", "grok-4.6"),
        ("T0.0 [XHARD] source", "codex:gpt-5.6-luna"),
        ("T0.0 [XHARD] source", "stealth/ox-alpha"),
        ("T0.0 [HARD] source", "grok-4.6"),
        ("T0.0 [HARD] source", "stealth/ox-alpha"),
    ):
        manifest = _manifest()
        manifest["tasks"][0]["label"] = label
        manifest["tasks"][0]["model_route"] = route
        validator.validate_manifest(manifest, ROOT / "manifest.json")


def test_model_routing_rejects_unknown_route_for_both_label_classes() -> None:
    for label in ("T0.0 [XHARD] source", "T0.0 [HARD] source"):
        manifest = _manifest()
        manifest["tasks"][0]["label"] = label
        manifest["tasks"][0]["model_route"] = "gpt-9-turbo"
        detail = _error(manifest, "MODEL_ROUTING")
        assert "gpt-9-turbo" in detail


def test_g7_recommendation_accepts_routed_set_and_rejects_unknown() -> None:
    for route in ("grok-4.6", "codex:gpt-5.6-luna", "stealth/ox-alpha"):
        manifest = _manifest()
        manifest["gates"] = [{"gate_id": "G7", "status": "open", "label": "G7 recommend", "model_route": route}]
        validator.validate_manifest(manifest, ROOT / "manifest.json")
    manifest = _manifest()
    manifest["gates"] = [{"gate_id": "G7", "status": "open", "label": "G7 recommend", "model_route": "gpt-9-turbo"}]
    _error(manifest, "MODEL_ROUTING")


def test_reviewer_independence_rejects_self_review() -> None:
    manifest = _manifest()
    manifest["tasks"].append({
        "task_id": "T0.2", "label": "T0.2 [XHARD-REVIEW] contract", "model_route": "grok-4.6",
        "role": "reviewer", "reviewer_agent_id": "agent-a", "implementer_agent_id": "agent-a",
    })
    _error(manifest, "REVIEWER_INDEPENDENCE")


def test_must_finding_requires_closed_revision_chain() -> None:
    manifest = _manifest()
    manifest["findings"] = [{"finding_id": "F1", "severity": "must", "classification": "XHARD"}]
    _error(manifest, "FINDING_CHAIN")


def test_final_five_identity_is_locked() -> None:
    manifest = _manifest()
    manifest["final_five"]["speed-distillation-research"] = "0" * 64
    _error(manifest, "FINAL_FIVE_INTEGRITY")


def _authoritative_run(count: int = 50, *, duplicate: bool = False, keyless: bool = False, split: dict | None = None) -> dict:
    receipts: list[dict] = []
    for i in range(count):
        if keyless:
            receipts.append({})
        elif duplicate:
            receipts.append({"leg_id": "0"})
        else:
            receipts.append({"leg_id": str(i)})
    run = {"task_id": "T7.2", "authoritative": True, "concurrency": 10, "split": {"staged": 25, "threaded": 25}, "leg_receipts": receipts}
    if split is not None:
        run["split"] = split
    return run


def test_live_run_accepts_one_authoritative_50_leg_split_record() -> None:
    manifest = _manifest()
    manifest["live_runs"] = [_authoritative_run()]
    validator.validate_manifest(manifest, ROOT / "manifest.json")


def test_live_run_rejects_49_or_51_duplicate_or_keyless_receipts() -> None:
    for count in (49, 51):
        _error({**_manifest(), "live_runs": [_authoritative_run(count)]}, "LIVE_RUN_SINGLETON")
    _error({**_manifest(), "live_runs": [_authoritative_run(duplicate=True)]}, "LIVE_RUN_SINGLETON")
    _error({**_manifest(), "live_runs": [_authoritative_run(keyless=True)]}, "LIVE_RUN_SINGLETON")


def test_live_run_rejects_legacy_100_leg_50x2_contract() -> None:
    run = _authoritative_run(100)
    run["mode"] = "50x2"
    detail = _error({**_manifest(), "live_runs": [run]}, "LIVE_RUN_SINGLETON")
    assert "50 unique leg_receipts" in detail


def test_live_run_rejects_missing_or_unbalanced_split_or_concurrency() -> None:
    missing = _authoritative_run()
    del missing["split"]
    _error({**_manifest(), "live_runs": [missing]}, "LIVE_RUN_SINGLETON")
    unbalanced = _authoritative_run(split={"staged": 40, "threaded": 10})
    _error({**_manifest(), "live_runs": [unbalanced]}, "LIVE_RUN_SINGLETON")
    slow = _authoritative_run()
    slow["concurrency"] = 20
    _error({**_manifest(), "live_runs": [slow]}, "LIVE_RUN_SINGLETON")


def test_live_run_rejects_two_authoritative_invocations() -> None:
    run = _authoritative_run()
    _error({**_manifest(), "live_runs": [run, copy.deepcopy(run)]}, "LIVE_RUN_SINGLETON")


def test_smoke_non_authoritative_run_does_not_trip_singleton() -> None:
    smoke = {"task_id": "smoke-final5x2", "authoritative": False, "concurrency": 10, "mode": "5x2", "leg_receipts": [{"leg_id": str(i)} for i in range(10)]}
    manifest = {**_manifest(), "live_runs": [_authoritative_run(), smoke]}
    validator.validate_manifest(manifest, ROOT / "manifest.json")
    flagged = dict(smoke, authoritative=True, status="non_authoritative")
    manifest = {**_manifest(), "live_runs": [_authoritative_run(), flagged]}
    validator.validate_manifest(manifest, ROOT / "manifest.json")


def test_card_order_places_t04_after_t02_before_g0() -> None:
    order = validator.CARD_ORDER
    assert order.index("T0.2") < order.index("T0.4") < order.index("G0")
    g0 = validator.GATE_CARDS["G0"]
    assert g0[-2:] == ["T0.2", "T0.4"]
    assert g0 == ["T0.0", "T0.1", "T0.3", "T0.2", "T0.4"]
    relative = [card for card in order if card != "T0.4"]
    assert relative == [
        "T0.0", "T0.1", "T0.3", "T0.2", "G0",
        "T1.1", "T1.2", "G1", "T2.1", "T2.2", "T2.3", "G2",
        "T3.1", "T3.2", "G3", "T4.1", "T4.2", "T4.3", "G4",
        "T5.1", "T5.2", "T5.3", "T5.4", "T5.5", "G5",
        "T6.1", "T6.2", "T6.3", "G6", "T7.1", "T7.2", "T7.3", "G7",
    ]


def test_dependency_order_accepts_t04_and_rejects_unknown_cards() -> None:
    manifest = _manifest()
    manifest["tasks"] = [
        *manifest["tasks"],
        {"task_id": "T0.2", "label": "T0.2 [XHARD-REVIEW] contract", "model_route": "grok-4.6"},
        {"task_id": "T0.4", "label": "T0.4 [XHARD] plan amendment 50", "model_route": "grok-4.6"},
    ]
    validator.validate_manifest(manifest, ROOT / "manifest.json")
    unknown = _manifest()
    unknown["tasks"].append({"task_id": "T9.9", "label": "T9.9 [HARD] unknown", "model_route": "codex:gpt-5.6-luna"})
    _error(unknown, "DEPENDENCY_ORDER")


def test_broad_suite_is_a_singleton() -> None:
    manifest = _manifest()
    manifest["shards"] = [{"shard_id": "broad_suite_once_v1"}, {"shard_id": "broad_suite_once_v1"}]
    _error(manifest, "TEST_SINGLETON")


def test_complete_g6_requires_broad_suite_record() -> None:
    manifest = _manifest()
    manifest["gates"] = [{"gate_id": "G6", "status": "complete"}]
    _error(manifest, "DEPENDENCY_ORDER")


def test_process_completion_is_not_a_product_verdict() -> None:
    manifest = _manifest()
    manifest["live_runs"] = [{"authoritative": False, "legs": [{"assessment": {"verdict": "process_completed"}}]}]
    _error(manifest, "PROCESS_COMPLETION_VERDICT")


EVIDENCE_DIR = ROOT / "docs" / "plans" / "workflow-execution-spine-consolidation-evidence"
EXECUTION_LOG_PATH = ROOT / "docs" / "plans" / validator._EXECUTION_LOG_DOC
PLAN_DOC_PATH = ROOT / "docs" / "plans" / validator._PLAN_DOC
GOAL_DOC_PATH = ROOT / "docs" / "plans" / validator._GOAL_DOC



def test_planted_receipt_secret_fails_credential_hygiene(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    (evidence / "receipts").mkdir(parents=True)
    receipt = evidence / "receipts" / "FAKE-LEAK-receipt.json"
    receipt.write_text(json.dumps({"task_id": "FAKE-LEAK", "env": "OPENROUTER_API_KEY=fake-rotated-key-value"}))
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.check_credential_hygiene(evidence, None)
    assert str(caught.value).startswith("CREDENTIAL_HYGIENE_VIOLATION")
    assert "FAKE-LEAK-receipt.json" in str(caught.value)


def test_planted_non_receipt_evidence_secret_also_fails(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    (evidence / "receipts").mkdir(parents=True)
    (evidence / "manifest.json").write_text(json.dumps({"tasks": []}))
    (evidence / "notes.json").write_text(json.dumps({"h": "sk-or-v1-FakeKeyFakeKeyFake12"}))
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.check_credential_hygiene(evidence, None)
    assert str(caught.value).startswith("CREDENTIAL_HYGIENE_VIOLATION")
    assert "notes.json" in str(caught.value)


def test_clean_synthetic_evidence_passes_hygiene_guard() -> None:
    evidence = DISPOSABLE_ROOT / "hygiene-clean-evidence"
    shutil.rmtree(evidence, ignore_errors=True)
    (evidence / "receipts").mkdir(parents=True)
    (evidence / "receipts" / "CLEAN-receipt.json").write_text(json.dumps({"task_id": "CLEAN", "status": "pass"}))
    (evidence / "manifest.json").write_text(json.dumps({"tasks": []}))
    validator.check_credential_hygiene(evidence, EXECUTION_LOG_PATH, [PLAN_DOC_PATH, GOAL_DOC_PATH])


def test_execution_log_baseline_matches_head_and_full_validation_stays_green() -> None:
    validator.check_credential_hygiene(EVIDENCE_DIR, EXECUTION_LOG_PATH, [PLAN_DOC_PATH, GOAL_DOC_PATH])
    manifest_path = EVIDENCE_DIR / "manifest.json"
    validator.validate_manifest(json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path)


def test_execution_log_extra_occurrence_exceeds_baseline(tmp_path: Path) -> None:
    drifted = tmp_path / validator._EXECUTION_LOG_DOC
    drifted.write_text(
        EXECUTION_LOG_PATH.read_text(encoding="utf-8") + "\nOPENROUTER_API_KEY=new-fake-occurrence\n",
        encoding="utf-8",
    )
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.check_credential_hygiene(None, drifted)
    assert str(caught.value).startswith("CREDENTIAL_HYGIENE_BASELINE")


def test_writer_canonical_output_passes_scan_but_raw_fakes_fail(tmp_path: Path) -> None:
    """MUST-002: writer/validator scan contract must agree on [REDACTED].

    A receipt produced through the wrapper's own _json_write (real-format fake
    secrets, some with embedded quotes) scans clean once sanitized, hand-written
    canonical placeholders pass, and raw fake keys still raise the typed
    CREDENTIAL_HYGIENE_VIOLATION.
    """
    evidence = tmp_path / "evidence"
    (evidence / "receipts").mkdir(parents=True)
    receipt = evidence / "receipts" / "WRITER-CANON-receipt.json"
    wrapper._json_write(
        receipt,
        {
            "env": 'OPENAI_API_KEY=fake-value"suffix',
            "openrouter": "OPENROUTER_API_KEY=fake-live-key-000111222",
            "deepseek": "DEEPSEEK_API_KEY=another-fake-value",
            "auth": "Authorization: Bearer fake-bearer-token",
            "token": "sk-or-v1-FakeKeyFakeKeyFake12",
        },
    )
    placeholder = evidence / "receipts" / "PLACEHOLDER-receipt.json"
    placeholder.write_text(json.dumps({"env": "OPENAI_API_KEY=[REDACTED]", "auth": "authorization: bearer [REDACTED]"}))
    validator.check_credential_hygiene(evidence, None)

    (evidence / "receipts" / "RAW-LEAK-receipt.json").write_text(
        json.dumps({"task_id": "RAW-LEAK", "env": "OPENROUTER_API_KEY=fake-rotated-key-value"})
    )
    with pytest.raises(validator.EvidenceValidationError) as caught:
        validator.check_credential_hygiene(evidence, None)
    assert str(caught.value).startswith("CREDENTIAL_HYGIENE_VIOLATION")
    assert "RAW-LEAK-receipt.json" in str(caught.value)


def test_validator_rejects_suffixed_placeholders(tmp_path: Path) -> None:
    """T29A-REVISION-2 F2: canonical placeholders pass the scan both as JSON
    values AND keys; suffixed placeholders are live material and fail typed,
    with env-var and Bearer classes failing independently.
    """
    evidence = tmp_path / "evidence"
    (evidence / "receipts").mkdir(parents=True)
    (evidence / "receipts" / "CANON-receipt.json").write_text(
        json.dumps(
            {
                "OPENROUTER_API_KEY=[REDACTED]": "OPENROUTER_API_KEY=[REDACTED]",
                "DEEPSEEK_API_KEY=[REDACTED]": "DEEPSEEK_API_KEY=[REDACTED]",
                "OPENAI_API_KEY=[REDACTED]": "OPENAI_API_KEY=[REDACTED]",
                "auth": "authorization: bearer [REDACTED]",
                "trailing": "OPENAI_API_KEY=[REDACTED] tail",
            }
        ),
        encoding="utf-8",
    )
    validator.check_credential_hygiene(evidence, None)

    suffixed = [
        ("env-openrouter", {"env": "OPENROUTER_API_KEY=[REDACTED]-suffix"}),
        ("env-deepseek", {"env": "DEEPSEEK_API_KEY=[REDACTED]junk"}),
        ("env-openai", {"env": "OPENAI_API_KEY=[REDACTED]<suffix>"}),
        ("bearer-upper", {"auth": "Authorization: Bearer [REDACTED]-suffix"}),
        ("bearer-lower", {"auth": "authorization: bearer [REDACTED]<suffix>"}),
    ]
    for label, payload in suffixed:
        path = evidence / "receipts" / f"SUFFIX-{label}-receipt.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(validator.EvidenceValidationError) as caught:
            validator.check_credential_hygiene(evidence, None)
        assert str(caught.value).startswith("CREDENTIAL_HYGIENE_VIOLATION"), label
        assert path.name in str(caught.value)
        path.unlink()


def test_execution_log_baseline_identity_matches_head() -> None:
    """T29A-REVISION-2 F3: the computed matching-line identity set equals the
    pinned five (line number, sha256) identities exactly, and canonical
    validation stays green.
    """
    computed = validator._execution_log_secret_line_identities(EXECUTION_LOG_PATH)
    assert len(computed) == len(validator.BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES) == 5
    assert computed == validator.BASELINE_EXECUTION_LOG_SECRET_LINE_IDENTITIES
    validator.check_credential_hygiene(EVIDENCE_DIR, EXECUTION_LOG_PATH, [PLAN_DOC_PATH, GOAL_DOC_PATH])


def test_execution_log_baseline_rejects_add_remove_replace_and_move(tmp_path: Path) -> None:
    """T29A-REVISION-2 F3: exact-set comparison — an added line, a removed
    line, a same-count replacement with a fake live-format secret, and an
    unchanged matching line moved elsewhere ALL fail CREDENTIAL_HYGIENE_BASELINE,
    not merely growth past a count.
    """
    original = EXECUTION_LOG_PATH.read_text(encoding="utf-8")
    matching_lines = validator._credential_hygiene_hits(EXECUTION_LOG_PATH)
    assert len(matching_lines) == 5

    def expect_baseline_failure(name: str, mutate) -> None:
        lines = original.splitlines(keepends=True)
        mutate(lines)
        drifted = tmp_path / f"drifted-{name}.md"
        drifted.write_text("".join(lines), encoding="utf-8")
        with pytest.raises(validator.EvidenceValidationError) as caught:
            validator.check_credential_hygiene(None, drifted)
        assert str(caught.value).startswith("CREDENTIAL_HYGIENE_BASELINE"), name

    target_index = matching_lines[0] - 1
    expect_baseline_failure("added", lambda lines: lines.append("OPENROUTER_API_KEY=new-fake-occurrence\n"))

    def remove(lines):
        del lines[target_index]

    expect_baseline_failure("removed", remove)

    def replace(lines):
        lines[target_index] = "OPENROUTER_API_KEY=replacement-fake-live-format-value\n"

    expect_baseline_failure("replaced", replace)

    def move(lines):
        lines.append(lines.pop(target_index))

    expect_baseline_failure("moved", move)
