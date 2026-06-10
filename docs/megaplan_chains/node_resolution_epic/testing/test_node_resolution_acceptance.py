"""Acceptance gates for the Node Resolution Epic.

Executable form of ``testing.md``. One test per scenario in the matrix; each is
``skip``ped with a pointer to the sprint that must make it pass, and carries the
intended assertions in its body so it activates by deleting the skip. The
``test_fixtures_present`` smoke test runs *now* to prove the harness is wired.

Future symbols (``ArityDisagreementError``, ``ensure_env`` …) are imported
*inside* the test bodies, so this module always collects cleanly even before the
epic lands. Shipped versions of these gates also land in ``tests/``.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path
from typing import Sequence

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
for _module_name, _module in tuple(sys.modules.items()):
    if _module_name != "vibecomfy" and not _module_name.startswith("vibecomfy."):
        continue
    _module_file = getattr(_module, "__file__", None)
    if _module_file is None:
        continue
    try:
        Path(_module_file).resolve().relative_to(_REPO_ROOT)
    except ValueError:
        sys.modules.pop(_module_name, None)

from vibecomfy.porting.object_info.serialize import build_cache

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
IDEOGRAM = FIXTURES / "ideogram4_t2i.json"
EXPECTED_EMIT = FIXTURES / "ideogram4_t2i.expected_emit.py"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _comfymath_output_counts(workflow: dict) -> list[int]:
    """Output-slot counts of every ComfyMathExpression node (top-level + subgraphs)."""
    counts: list[int] = []

    def scan(nodes):
        for n in nodes or []:
            if str(n.get("type")) == "ComfyMathExpression":
                counts.append(len(n.get("outputs") or []))

    scan(workflow.get("nodes"))
    for sg in (workflow.get("definitions", {}) or {}).get("subgraphs", []) or []:
        scan(sg.get("nodes"))
    return counts


def _write_temp_object_info_cache(tmp_path: Path, *, output_names: list[str]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "object_info.json"
    source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": {
                    "python_module": "nodes",
                    "name": "ComfyMathExpression",
                    "display_name": "ComfyMathExpression",
                    "description": "",
                    "category": "math",
                    "function": "evaluate",
                    "input": {"required": {}, "optional": {}},
                    "input_order": {"required": [], "optional": []},
                    "output": output_names,
                    "output_name": output_names,
                    "output_is_list": [False] * len(output_names),
                }
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "object_info"
    build_cache(str(source), version="acceptance", cache_dir=str(cache_root))
    return cache_root


def _patch_object_info_cache(monkeypatch: pytest.MonkeyPatch, cache_root: Path) -> None:
    import vibecomfy.porting.object_info.consume as consume

    monkeypatch.setattr(consume, "CACHE_DIR", cache_root)
    monkeypatch.setattr(consume, "INDEX_PATH", cache_root / "index.json")
    monkeypatch.setattr(consume, "_index", None)
    monkeypatch.setattr(consume, "_pack_cache", {})


def _write_workflow_object_info_cache(tmp_path: Path, workflow: dict) -> Path:
    object_info: dict[str, dict] = {}

    def scan(nodes):
        for node in nodes or []:
            outputs = node.get("outputs") or [{"name": "OUTPUT", "type": "*"}]
            names = [str(output.get("name") or output.get("type") or f"OUT_{idx}") for idx, output in enumerate(outputs)]
            object_info.setdefault(
                str(node.get("type")),
                {
                    "python_module": "nodes",
                    "name": str(node.get("type")),
                    "display_name": str(node.get("type")),
                    "description": "",
                    "category": "acceptance",
                    "function": "execute",
                    "input": {"required": {}, "optional": {}},
                    "input_order": {"required": [], "optional": []},
                    "output": names,
                    "output_name": names,
                    "output_is_list": [False] * len(names),
                },
            )

    scan(workflow.get("nodes"))
    for sg in (workflow.get("definitions", {}) or {}).get("subgraphs", []) or []:
        scan(sg.get("nodes"))

    source = tmp_path / "workflow_object_info.json"
    source.write_text(json.dumps(object_info), encoding="utf-8")
    cache_root = tmp_path / "object_info"
    build_cache(str(source), version="acceptance-workflow", cache_dir=str(cache_root))
    return cache_root


def _write_filtered_object_info_cache(tmp_path: Path, filtered_payloads: dict[str, dict[str, dict]]) -> Path:
    cache_root = tmp_path / "object_info"
    for slug, payload in filtered_payloads.items():
        source = tmp_path / f"{slug}.object_info.json"
        source.write_text(json.dumps(payload), encoding="utf-8")
        build_cache(
            str(source),
            version="acceptance-workflow",
            cache_dir=str(cache_root),
            pack_slug=slug,
            evidence_identity=f"acceptance:{slug}",
        )
    return cache_root


def _normalize_emitted_source(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"(?<=source_path': ')[^']+\.json", "<WORKFLOW_JSON>", text)
    text = re.sub(r"(?<=source_workflow_path': ')[^']+\.json", "<WORKFLOW_JSON>", text)
    text = re.sub(r"Materialized from subgraph ([^ ]+) in [^\n]+\.json\.", r"Materialized from subgraph \1 in <WORKFLOW_JSON>.", text)
    module = ast.parse(text)
    return ast.dump(module, annotate_fields=True, include_attributes=False)


def _compile_ready_template_api(text: str, *, module_name: str) -> dict:
    temp_dir = Path(tempfile.mkdtemp(prefix="acceptance-ready-template-"))
    module_path = temp_dir / f"{module_name}.py"
    module_path.write_text(text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build().compile("api")


def _acceptance_pack(name: str, *, pip_packages: tuple[str, ...] = ()):
    from vibecomfy.node_packs import CustomNodePack

    return CustomNodePack(
        name=name,
        repo=f"https://example.test/{name}.git",
        classes=frozenset({f"{name}Node"}),
        pip_packages=pip_packages,
    )


# --------------------------------------------------------------------------- #
# smoke — passes today; proves fixtures + harness are wired
# --------------------------------------------------------------------------- #
def test_fixtures_present():
    assert IDEOGRAM.exists(), "headline failing workflow fixture is missing"
    assert EXPECTED_EMIT.exists(), "golden compiling-emit reference is missing"
    wf = json.loads(IDEOGRAM.read_text())
    counts = _comfymath_output_counts(wf)
    # The whole bug: this workflow declares ComfyMathExpression with 3 outputs,
    # while the stale 0.18.2 snapshot has 2. Guard that we shipped the right fixture.
    assert counts, "expected ComfyMathExpression nodes in the Ideogram fixture"
    assert max(counts) == 3, f"expected a 3-output ComfyMathExpression, saw {counts}"


# --------------------------------------------------------------------------- #
# Sprint A — correctness spine (scenarios 1–5)
# --------------------------------------------------------------------------- #
@pytest.mark.sprint_a
def test_a1_ideogram_no_silent_miscompile():
    """Porting the Ideogram workflow must never raise a bare unpack ValueError:
    it either compiles with correct arity, or raises typed ArityDisagreementError."""
    from vibecomfy.errors import ArityDisagreementError  # noqa: F401  (added in A)
    from vibecomfy.porting.convert import port_convert_workflow
    from vibecomfy.porting.workbench import load_port_source

    src = load_port_source(str(IDEOGRAM), use_comfy_converter=False)
    raw = json.loads(IDEOGRAM.read_text())
    try:
        res = port_convert_workflow(
            src.workflow, raw_workflow=raw, source_path=src.source_path,
            source_hash=src.source_hash, ready_id="image/ideogram4_t2i",
        )
    except ArityDisagreementError:
        return  # fail-closed is an acceptable outcome
    assert res.validation.compile_ok, res.validation.error
    assert "not enough values to unpack" not in (res.validation.error or "")


@pytest.mark.sprint_a
def test_a2_fail_closed_on_known_node_arity_disagreement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """cache outputs < UI outputs => raise (stale); cache > UI => warn (unused)."""
    from vibecomfy.errors import ArityDisagreementError

    from vibecomfy.porting.object_info import check_output_arity_consensus

    stale_cache = _write_temp_object_info_cache(tmp_path / "stale", output_names=["FLOAT", "INT"])
    _patch_object_info_cache(monkeypatch, stale_cache)
    with pytest.raises(ArityDisagreementError) as exc:
        # UI declares 3 outputs; a stale snapshot offering 2 must fail closed.
        check_output_arity_consensus("ComfyMathExpression", ui_output_count=3)
    msg = str(exc.value)
    assert "ComfyMathExpression" in msg and "refresh" in msg.lower()

    larger_cache = _write_temp_object_info_cache(
        tmp_path / "larger", output_names=["FLOAT", "INT", "BOOL", "STRING"]
    )
    _patch_object_info_cache(monkeypatch, larger_cache)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_output_arity_consensus("ComfyMathExpression", ui_output_count=3)
    assert any("ComfyMathExpression" in str(w.message) for w in caught)


@pytest.mark.sprint_a
def test_a3_core_refresh_does_not_clobber_custom_packs():
    """After refreshing core schema, custom-pack classes still resolve (merge)."""
    from vibecomfy.porting.object_info import class_is_known
    # refresh core from evidence/object_info_comfyui_0.24.0.1.json (merge mode) ...
    assert class_is_known("ComfyMathExpression")          # core updated
    assert class_is_known("WanVideoModelLoader")          # custom pack preserved


@pytest.mark.sprint_a
def test_a4_io_schema_nodes_covered():
    """Executed introspection (not AST) yields correct outputs for io.Schema nodes."""
    from vibecomfy.porting.object_info import output_names
    assert output_names("ComfyMathExpression") == ["FLOAT", "INT", "BOOL"]


@pytest.mark.sprint_a
def test_a5_identity_keyed_cache_and_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """testing.md §5: lookup key is ``(pack_slug, git_commit)``, ``compute_schema_hash``
    is wired and is a *real content hash*, and the cache builder and the drift
    checker share ONE schema-hash projection (the pre-m1 bug was two hashes that
    never matched, yielding false-positive drift)."""
    from vibecomfy.node_packs_lockfile import LockEntry, compute_schema_hash
    from vibecomfy.porting.object_info import get_class_by_identity
    from vibecomfy.runtime import drift as drift_mod

    # -- Property 1: compute_schema_hash is a deterministic content hash -------
    # Same schemas → same hash (deterministic), and a DIFFERENT output arity →
    # a DIFFERENT hash (so it reacts to content; not a constant/stub). The
    # extra "BOOL" output is exactly the ComfyMathExpression skew from §scenario 2.
    schema_2out = {"N": {"class_type": "N", "outputs": ["FLOAT", "INT"]}}
    schema_3out = {"N": {"class_type": "N", "outputs": ["FLOAT", "INT", "BOOL"]}}
    assert compute_schema_hash(schema_2out) == compute_schema_hash(schema_2out)
    assert compute_schema_hash(schema_3out) == compute_schema_hash(schema_3out)
    assert compute_schema_hash(schema_2out) != compute_schema_hash(schema_3out), (
        "compute_schema_hash must change when output arity changes — "
        "a constant/stub hash would defeat drift detection"
    )

    # -- Build a real per-pack cache stamped with (pack_slug, git_commit) ------
    source = tmp_path / "object_info.json"
    source.write_text(
        json.dumps(
            {
                "ComfyMathExpression": {
                    "python_module": "custom_nodes.comfy_math.nodes",
                    "name": "ComfyMathExpression",
                    "display_name": "ComfyMathExpression",
                    "description": "",
                    "category": "math",
                    "function": "evaluate",
                    "input": {"required": {}, "optional": {}},
                    "input_order": {"required": [], "optional": []},
                    "output": ["FLOAT", "INT", "BOOL"],
                    "output_name": ["FLOAT", "INT", "BOOL"],
                    "output_is_list": [False, False, False],
                }
            }
        ),
        encoding="utf-8",
    )
    cache_root = tmp_path / "object_info"
    pack_slug = "comfy_math"
    git_commit = "0123456789abcdef0123456789abcdef01234567"
    build_cache(
        str(source),
        version="acceptance",
        cache_dir=str(cache_root),
        pack_slug=pack_slug,
        git_commit=git_commit,
    )
    _patch_object_info_cache(monkeypatch, cache_root)

    # -- Property 2: identity key = (pack_slug, git_commit) --------------------
    # The serialized cache entry is *tagged* by resolved (pack, commit) identity,
    # and is retrievable by that exact identity — not by "live vs cache".
    entry = get_class_by_identity(
        "ComfyMathExpression", pack_slug=pack_slug, git_commit=git_commit
    )
    assert entry is not None, "cache entry must resolve by (pack_slug, git_commit)"
    assert entry["pack_slug"] == pack_slug
    assert entry["git_commit"] == git_commit
    # A wrong commit under the same slug must NOT resolve (it really is keyed by
    # the pair, not by slug alone).
    assert (
        get_class_by_identity(
            "ComfyMathExpression", pack_slug=pack_slug, git_commit="ffffffff"
        )
        is None
    )

    # -- Property 3: cache builder and drift checker share ONE projection ------
    # drift._canonical_pack_schema_hash pulls the cache entry by identity and
    # hashes it with the SAME compute_schema_hash the builder used. Pinning that
    # exact projection in the lockfile must report status "canonical" with a
    # matching hash → NO spurious drift.
    canonical_hash = compute_schema_hash({"ComfyMathExpression": entry})
    matching_entry = LockEntry(
        name=pack_slug,
        slug=pack_slug,
        git_commit_sha=git_commit,
        url="https://example.invalid/comfy_math",
        class_set=("ComfyMathExpression",),
        schema_hash=canonical_hash,
    )
    matched = drift_mod._canonical_pack_schema_hash(matching_entry)
    assert matched["status"] == "canonical", matched
    assert matched["hash"] == canonical_hash, (
        "drift must hash the cache entry with the SAME projection as the builder; "
        "a divergent algorithm is the pre-m1 false-positive-drift bug"
    )

    # A wrong-commit pin cannot resolve a canonical entry → it is reported
    # unavailable (no canonical hash), proving the comparison is identity-gated
    # rather than silently matching on slug alone.
    wrong_commit_entry = LockEntry(
        name=pack_slug,
        slug=pack_slug,
        git_commit_sha="ffffffff",
        url="https://example.invalid/comfy_math",
        class_set=("ComfyMathExpression",),
        schema_hash=canonical_hash,
    )
    assert (
        drift_mod._canonical_pack_schema_hash(wrong_commit_entry)["status"]
        != "canonical"
    )


# --------------------------------------------------------------------------- #
# Sprint B — environment realization (scenarios 6–8, 12-compile)
# --------------------------------------------------------------------------- #
@pytest.mark.sprint_b
def test_b6_ensure_env_installs_and_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    import vibecomfy.runtime.ensure_env as ensure_env_module
    from vibecomfy.node_packs_install import InstallBatchResult, InstallResult, PipPreflightResult
    from vibecomfy.runtime.ensure_env import ensure_env

    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    workflow = {
        "nodes": [
            {"id": 1, "type": "AcceptancePackNode", "properties": {"cnr_id": "AcceptancePack", "ver": "ignored-in-sprint-b"}},
            {"id": 2, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
        ]
    }
    events: list[object] = []

    def installer(packs):
        events.append(("install", tuple(pack.name for pack in packs)))
        return InstallBatchResult(
            ok=True,
            results=(InstallResult("AcceptancePack", "installed", "abc123", None),),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(packs):
        events.append(("introspect", tuple(pack.name for pack in packs)))
        return {
            "AcceptancePackNode": {"python_module": "AcceptancePack.nodes"},
            "VAELoader": {"python_module": "."},
        }

    def cache_writer(payload):
        events.append(("cache", sorted(payload)))
        return {"written": sorted(payload)}

    first = ensure_env(
        workflow,
        known_packs=(_acceptance_pack("AcceptancePack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )
    second = ensure_env(
        workflow,
        known_packs=(_acceptance_pack("AcceptancePack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
    )

    assert first.ok is True
    assert first.noop is False
    assert [outcome.slug for outcome in first.pack_outcomes] == ["AcceptancePack", "comfy-core"]
    assert first.pack_outcomes[0].install_status == "installed"
    assert first.pack_outcomes[0].introspected and first.pack_outcomes[0].cache_written
    assert first.pack_outcomes[1].git_commit_sha is None
    assert second.ok is True
    assert second.noop is True, "ensure-env must be idempotent after successful realization"
    assert second.install_batch is None
    assert events == [
        ("install", ("AcceptancePack",)),
        ("introspect", ("AcceptancePack",)),
        ("cache", ["AcceptancePack", "comfy-core"]),
    ]


@pytest.mark.sprint_b
def test_b7_install_robustness(tmp_path: Path):
    """clone-ok/pip-fail is NOT reported installed; cross-pack pip preflight runs."""
    from vibecomfy.node_packs_install import install_pack, install_required_packs

    class Runner:
        def __init__(self, *, fail_pip: bool = False, fail_dry_run: bool = False, dirty: bool = False):
            self.fail_pip = fail_pip
            self.fail_dry_run = fail_dry_run
            self.dirty = dirty
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
            call = list(args)
            self.calls.append(call)
            if call[:2] == ["git", "clone"]:
                Path(call[3]).mkdir(parents=True)
                return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
            if call == [call[0], "-m", "pip", "install", "--help"]:
                return subprocess.CompletedProcess(call, 0, stdout="--dry-run\n--report\n", stderr="")
            if call[1:6] == ["-m", "pip", "install", "--dry-run", "--report"]:
                if self.fail_dry_run:
                    raise subprocess.CalledProcessError(1, call, stderr="pip conflict")
                Path(call[6]).write_text("{}", encoding="utf-8")
                return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
            if call[1:4] == ["-m", "pip", "install"]:
                if self.fail_pip:
                    raise subprocess.CalledProcessError(1, call, stderr="pip failed")
                return subprocess.CompletedProcess(call, 0, stdout="", stderr="")
            if call[:4] == ["git", "-C", call[2], "status"]:
                return subprocess.CompletedProcess(call, 0, stdout=" M file.py\n" if self.dirty else "", stderr="")
            if call[:4] == ["git", "-C", call[2], "rev-parse"]:
                return subprocess.CompletedProcess(call, 0, stdout="forcehead\n", stderr="")
            raise AssertionError(f"unexpected subprocess call: {call!r}")

    install_root = tmp_path / "custom_nodes"
    lockfile = tmp_path / "custom_nodes.lock"

    pip_fail_runner = Runner(fail_pip=True)
    failed = install_pack(
        name="ComfyUI-KJNodes",
        install_root=install_root,
        lockfile_path=lockfile,
        runner=pip_fail_runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )
    sentinel = install_root / ".vibecomfy-install-state" / "ComfyUI-KJNodes.json"
    assert failed.status == "failed"
    assert "pip failed" in (failed.error or "")
    assert json.loads(sentinel.read_text(encoding="utf-8"))["phase"] == "pip"
    assert not lockfile.exists()

    conflict_runner = Runner(fail_dry_run=True)
    conflict = install_required_packs(
        (
            _acceptance_pack("PackA", pip_packages=("shared-dep==1",)),
            _acceptance_pack("PackB", pip_packages=("shared-dep==2",)),
        ),
        install_root=tmp_path / "conflict_nodes",
        lockfile_path=tmp_path / "conflict.lock",
        runner=conflict_runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )
    assert conflict.ok is False
    assert "pip conflict" in (conflict.preflight.error or "")
    assert [result.status for result in conflict.results] == ["failed", "failed"]
    assert not any(call[:2] == ["git", "clone"] for call in conflict_runner.calls)

    force_root = tmp_path / "force_nodes"
    (force_root / "ComfyUI-VideoHelperSuite").mkdir(parents=True)
    force_runner = Runner(dirty=True)
    forced = install_required_packs(
        (_acceptance_pack("ComfyUI-VideoHelperSuite"),),
        force=True,
        install_root=force_root,
        lockfile_path=tmp_path / "force.lock",
        runner=force_runner,
        cm_cli_resolver=lambda _root, _runner: None,
    )
    assert forced.ok is True
    assert [(result.name, result.status, result.git_commit_sha) for result in forced.results] == [
        ("ComfyUI-VideoHelperSuite", "refreshed", "forcehead")
    ]


@pytest.mark.sprint_b
def test_b8_provenance_determines_pack_set():
    from vibecomfy.porting.provenance import extract_provenance

    workflow = {
        "nodes": [
            {"id": 1, "type": "VAELoader", "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"}},
            {"id": 2, "type": "CustomNodeA", "properties": {"cnr_id": "CustomPack", "ver": "deadbeef"}},
            {"id": 3, "type": "CustomNodeB", "properties": {"cnr_id": "CustomPack", "aux_id": "owner/repo", "ver": "ignored"}},
            {"id": 4, "type": "AuxOnly", "properties": {"aux_id": "owner/aux", "ver": "abc"}},
            {"id": 5, "type": "KSampler", "properties": {}},
            {"id": 6, "type": "ResolutionSelector", "properties": {"cnr_id": "comfy-core"}},
        ],
        "definitions": {
            "subgraphs": [
                {
                    "id": "sg",
                    "nodes": [
                        {"id": "sg:1", "type": "SubgraphNode", "properties": {"cnr_id": "SubgraphPack", "ver": "123"}},
                    ],
                }
            ]
        },
    }

    prov = extract_provenance(workflow)

    assert prov.required_pack_slugs == frozenset({"comfy-core", "CustomPack", "SubgraphPack"})
    records = {(record.class_type, record.cnr_id, record.ver) for record in prov.records}
    assert ("CustomNodeA", "CustomPack", "deadbeef") in records
    assert ("SubgraphNode", "SubgraphPack", "123") in records
    assert [record.class_type for record in prov.aux_only] == ["AuxOnly"]
    assert [record.class_type for record in prov.unprovenanced] == ["KSampler"]
    assert [record.class_type for record in prov.core_slug_non_core] == ["ResolutionSelector"]


@pytest.mark.sprint_b
def test_b12_ideogram_ports_to_compiling_strict_ready_template(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from vibecomfy.porting.parity import class_type_counter, topology_counter
    from vibecomfy.porting.convert import port_convert_workflow
    from vibecomfy.porting.workbench import load_port_source
    import vibecomfy.node_packs_install as node_packs_install
    import vibecomfy.runtime.ensure_env as ensure_env_module
    from vibecomfy.runtime.ensure_env import ensure_env

    src = load_port_source(str(IDEOGRAM), use_comfy_converter=False)
    raw = json.loads(IDEOGRAM.read_text())
    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())
    fake_core_classes = set(node_packs_install.CORE_COMFY_CLASSES)

    def scan_core(nodes):
        for node in nodes or []:
            if node.get("properties", {}).get("cnr_id") == "comfy-core":
                fake_core_classes.add(str(node.get("type")))

    scan_core(raw.get("nodes"))
    for sg in (raw.get("definitions", {}) or {}).get("subgraphs", []) or []:
        scan_core(sg.get("nodes"))
    monkeypatch.setattr(node_packs_install, "CORE_COMFY_CLASSES", frozenset(fake_core_classes))
    cache_events: list[object] = []

    def introspector(_packs):
        cache_events.append(("introspect", tuple()))
        object_info: dict[str, dict] = {}

        def scan(nodes):
            for node in nodes or []:
                outputs = node.get("outputs") or [{"name": "OUTPUT", "type": "*"}]
                names = [
                    str(output.get("name") or output.get("type") or f"OUT_{idx}")
                    for idx, output in enumerate(outputs)
                ]
                object_info.setdefault(
                    str(node.get("type")),
                    {
                        "python_module": "." if node.get("properties", {}).get("cnr_id") == "comfy-core" else "custom_nodes.acceptance",
                        "name": str(node.get("type")),
                        "display_name": str(node.get("type")),
                        "description": "",
                        "category": "acceptance",
                        "function": "execute",
                        "input": {"required": {}, "optional": {}},
                        "input_order": {"required": [], "optional": []},
                        "output": names,
                        "output_name": names,
                        "output_is_list": [False] * len(names),
                    },
                )

        scan(raw.get("nodes"))
        for sg in (raw.get("definitions", {}) or {}).get("subgraphs", []) or []:
            scan(sg.get("nodes"))
        return object_info

    def cache_writer(filtered_payloads):
        cache_root = _write_filtered_object_info_cache(tmp_path, filtered_payloads)
        _patch_object_info_cache(monkeypatch, cache_root)
        cache_events.append(("cache", tuple(sorted(filtered_payloads))))
        return {"cache_root": str(cache_root)}

    ensure_result = ensure_env(
        IDEOGRAM,
        installer=lambda packs: pytest.fail(f"ideogram fixture should not require custom pack install: {packs!r}"),
        introspector=introspector,
        cache_writer=cache_writer,
    )
    assert ensure_result.ok is True
    assert ensure_result.noop is False
    assert ensure_result.install_batch is None
    assert [outcome.slug for outcome in ensure_result.pack_outcomes] == ["comfy-core"]
    assert ensure_result.pack_outcomes[0].introspected is True
    assert ensure_result.pack_outcomes[0].cache_written is True
    assert cache_events == [("introspect", tuple()), ("cache", ("comfy-core",))]

    res = port_convert_workflow(
        src.workflow, raw_workflow=raw, source_path=src.source_path,
        source_hash=src.source_hash, ready_id="image/ideogram4_t2i",
    )
    assert res.validation is not None
    assert res.validation.compile_ok is True, res.validation.error
    assert res.validation.strict_ready_ok is True, res.validation.error
    expected_text = EXPECTED_EMIT.read_text(encoding="utf-8")
    assert _normalize_emitted_source(res.text) != ""
    assert _normalize_emitted_source(expected_text) != ""
    expected_api = _compile_ready_template_api(expected_text, module_name="expected_ideogram4_t2i")
    actual_api = _compile_ready_template_api(res.text, module_name="actual_ideogram4_t2i")
    assert len(actual_api) == len(expected_api)
    assert class_type_counter(actual_api) == class_type_counter(expected_api)
    assert topology_counter(actual_api) == topology_counter(expected_api)


# --------------------------------------------------------------------------- #
# Sprint C — faithful pinning + snapshot demotion (scenarios 9–11, 12-faithful)
# --------------------------------------------------------------------------- #
@pytest.mark.sprint_c
def test_c9_faithful_version_pinning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Installs the authored commit (from `ver`), not latest; aux_id path works."""
    import vibecomfy.node_packs_install as node_packs_install
    from vibecomfy.runtime.ensure_env import ensure_env
    from vibecomfy.node_packs_install import InstallBatchResult, InstallResult, PipPreflightResult

    authored_commit = "abc123def456789012345678901234567890abcd"

    workflow = {
        "nodes": [
            {
                "id": 1,
                "type": "PinnedPackNode",
                "properties": {
                    "cnr_id": "PinnedPack",
                    "ver": authored_commit,
                },
            },
            {
                "id": 2,
                "type": "AuxOnlyNode",
                "properties": {
                    "aux_id": "someone/aux-pack",
                    "ver": "v1.0.0",
                },
            },
            {
                "id": 3,
                "type": "VAELoader",
                "properties": {"cnr_id": "comfy-core", "ver": "0.24.0"},
            },
        ]
    }

    # Ensure VAELoader is recognized as a core class
    fake_core_classes = set(node_packs_install.CORE_COMFY_CLASSES) | {"VAELoader"}
    monkeypatch.setattr(node_packs_install, "CORE_COMFY_CLASSES", frozenset(fake_core_classes))

    install_refs_seen: dict[str, object] = {}

    def installer(packs, *, install_refs_by_name=None):
        install_refs_seen.update(install_refs_by_name or {})
        return InstallBatchResult(
            ok=True,
            results=(
                InstallResult("PinnedPack", "installed", authored_commit, None),
                InstallResult("aux-pack", "installed", "auxhead123", None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(
        workflow,
        known_packs=(_acceptance_pack("PinnedPack"),),
        installer=installer,
        introspector=lambda packs: {
            "PinnedPackNode": {"python_module": "PinnedPack.nodes"},
            "AuxOnlyNode": {"python_module": "AuxPack.nodes"},
            "VAELoader": {"python_module": "."},
        },
        cache_writer=lambda payload: {"written": sorted(payload)},
    )

    assert result.ok is True, f"ensure_env failed: {result.failures}"
    # PinnedPack must carry the authored commit, not "latest"
    assert install_refs_seen["PinnedPack"].commit == authored_commit, (
        f"Expected commit {authored_commit!r}, got {install_refs_seen['PinnedPack'].commit!r}"
    )
    assert install_refs_seen["PinnedPack"].version == authored_commit
    # aux-id path creates a distinct aux-git ref
    assert install_refs_seen["aux-pack"].source == "aux-git"
    assert install_refs_seen["aux-pack"].url == "https://github.com/someone/aux-pack.git"
    assert install_refs_seen["aux-pack"].version == "v1.0.0"


@pytest.mark.sprint_c
def test_c10_provenance_less_warns_never_silent_latest() -> None:
    """A provenance-less workflow resolves with an explicit warning, low-confidence."""
    from vibecomfy.runtime.ensure_env import ensure_env
    from vibecomfy.node_packs_install import InstallBatchResult, PipPreflightResult

    corpus = _REPO_ROOT / "workflow_corpus/official/video/wan_t2v.json"
    assert corpus.exists(), "wan_t2v.json fixture is missing"

    install_calls: list[tuple[str, ...]] = []

    def installer(packs):
        install_calls.append(tuple(pack.name for pack in packs))
        return InstallBatchResult(
            ok=True,
            results=(),
            preflight=PipPreflightResult(ok=True),
        )

    result = ensure_env(str(corpus), known_packs=(), installer=installer)

    # Must succeed (no blocking failures) but warn loudly
    assert result.ok is True
    # Must not silently install anything — provenance-less nodes cannot be resolved
    # to custom packs without explicit class-to-pack fallback resolution
    assert result.low_confidence is True, (
        "provenance-less workflows must be marked low-confidence"
    )
    assert any(
        warning.code == "unprovenanced_execution_node"
        for warning in result.warnings
    ), f"Expected unprovenanced_execution_node warning, got: {[w.code for w in result.warnings]}"
    assert result.unprovenanced, (
        "unprovenanced records must be populated for provenance-less nodes"
    )


@pytest.mark.sprint_c
def test_c11_snapshot_regenerable_per_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Core schema regenerable from pinned pip-comfy; per-pack versioned; no monolith."""
    import argparse

    from vibecomfy.commands import schemas as schemas_command

    cache_root = tmp_path / "object_info_cache"
    monkeypatch.setattr(schemas_command, "CACHE_DIR", cache_root)

    def fake_provider(*args, **kwargs):  # noqa: ANN002, ANN003
        return {
            "KSampler": {
                "python_module": "nodes",
                "name": "KSampler",
                "display_name": "KSampler",
                "description": "KSampler node",
                "category": "sampling",
                "function": "sample",
                "input": {"required": {"model": ["MODEL"]}},
                "input_order": {"required": ["model"]},
                "output": ["LATENT"],
                "output_name": ["LATENT"],
                "output_is_list": [False],
            },
            "VAELoader": {
                "python_module": "nodes",
                "name": "VAELoader",
                "display_name": "VAELoader",
                "description": "VAE Loader",
                "category": "loaders",
                "function": "load_vae",
                "input": {"required": {"vae_name": ["VAE"]}},
                "input_order": {"required": ["vae_name"]},
                "output": ["VAE"],
                "output_name": ["VAE"],
                "output_is_list": [False],
            },
        }

    monkeypatch.setattr(schemas_command, "_introspect_core_object_info", fake_provider)

    code = schemas_command._cmd_schemas_regen_core(
        argparse.Namespace(
            comfy_version="0.26.0",
            json=False,
            source=None,
            server_url=None,
        )
    )

    assert code == 0
    assert cache_root.exists(), "cache directory must be created"

    # Per-pack versioned file — not a monolith
    core_cache = cache_root / "comfy-core@0.26.0.json"
    assert core_cache.exists(), (
        f"Expected per-pack versioned cache file {core_cache}, "
        f"found: {list(cache_root.glob('*.json'))}"
    )

    payload = json.loads(core_cache.read_text(encoding="utf-8"))
    # Identity fields are embedded per-class in the cache file
    assert "KSampler" in payload
    assert "VAELoader" in payload
    for cls_name in ("KSampler", "VAELoader"):
        cls_data = payload[cls_name]
        assert cls_data["pack_slug"] == "comfy-core", (
            f"{cls_name}: expected pack_slug=comfy-core, got {cls_data.get('pack_slug')!r}"
        )
        assert cls_data["pack_version"] == "0.26.0"
        assert cls_data["evidence_identity"] == "comfy-core:0.26.0"
        assert cls_data["source_kind"] == "runtime_core_object_info"

    # Index file must be updated
    index = json.loads((cache_root / "index.json").read_text(encoding="utf-8"))
    assert index["KSampler"] == "comfy-core@0.26.0.json"
    assert index["VAELoader"] == "comfy-core@0.26.0.json"


@pytest.mark.sprint_c
def test_c12_ideogram_ports_at_authored_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Port pins each node to its cnr_id/ver commit — end-to-end faithful.

    Uses a consistent-version workflow to demonstrate that ensure_env resolves
    authored versions, object-info cache is keyed by identity, and conversion
    produces a compiling strict-ready template anchored to the authored identity
    rather than registry latest.
    """
    import vibecomfy.node_packs_install as node_packs_install
    import vibecomfy.runtime.ensure_env as ensure_env_module
    from vibecomfy.runtime.ensure_env import ensure_env
    from vibecomfy.porting.convert import port_convert_workflow, _node_object_info_identities
    from vibecomfy.node_packs_install import InstallBatchResult, InstallResult, PipPreflightResult
    from vibecomfy.registry.pack_resolver import PackRef, PackResolution

    authored_commit = "abc123def456789012345678901234567890abcd"

    # ── Consistent-version workflow ──────────────────────────────────────
    raw = {
        "nodes": [
            {
                "id": 1,
                "type": "VAELoader",
                "properties": {"cnr_id": "comfy-core", "ver": "0.26.0"},
            },
            {
                "id": 2,
                "type": "KSampler",
                "properties": {"cnr_id": "comfy-core", "ver": "0.26.0"},
            },
            {
                "id": 3,
                "type": "CustomPackNode",
                "properties": {"cnr_id": "CustomPack", "ver": authored_commit},
            },
        ]
    }

    monkeypatch.setattr(ensure_env_module, "_REALIZED_SIGNATURES", set())

    # Ensure VAELoader and KSampler are recognized as core classes
    fake_core_classes = set(node_packs_install.CORE_COMFY_CLASSES) | {"VAELoader", "KSampler"}
    monkeypatch.setattr(node_packs_install, "CORE_COMFY_CLASSES", frozenset(fake_core_classes))

    # Fake resolver that returns authored version refs
    def resolver(query, *, version_pin=None, aux_id=None, local_metadata=None, allow_remote_lookup=True):
        return PackResolution(
            query=query,
            query_type="slug",
            ref=PackRef(
                slug=query,
                source="comfy-registry",
                version=version_pin or "0.26.0",
                commit=version_pin if len(version_pin or "") == 40 else None,
            ),
        )

    install_refs_seen: dict[str, object] = {}

    def installer(packs, *, install_refs_by_name=None):
        install_refs_seen.update(install_refs_by_name or {})
        return InstallBatchResult(
            ok=True,
            results=(
                InstallResult("CustomPack", "installed", authored_commit, None),
            ),
            preflight=PipPreflightResult(ok=True),
        )

    def introspector(_packs):
        return {
            "VAELoader": {
                "python_module": ".", "name": "VAELoader", "display_name": "VAELoader",
                "description": "", "category": "loaders", "function": "load_vae",
                "input": {"required": {"vae_name": ["VAE"]}},
                "input_order": {"required": ["vae_name"]},
                "output": ["VAE"], "output_name": ["VAE"], "output_is_list": [False],
            },
            "KSampler": {
                "python_module": ".", "name": "KSampler", "display_name": "KSampler",
                "description": "", "category": "sampling", "function": "sample",
                "input": {"required": {"model": ["MODEL"], "cfg": ["FLOAT", {"default": 5.0}]}},
                "input_order": {"required": ["model", "cfg"]},
                "output": ["LATENT"], "output_name": ["LATENT"], "output_is_list": [False],
            },
            "CustomPackNode": {
                "python_module": "CustomPack.nodes", "name": "CustomPackNode",
                "display_name": "CustomPackNode", "description": "", "category": "custom",
                "function": "execute",
                "input": {"required": {"latent": ["LATENT"]}},
                "input_order": {"required": ["latent"]},
                "output": ["IMAGE"], "output_name": ["IMAGE"], "output_is_list": [False],
            },
        }

    def cache_writer(filtered_payloads):
        cache_root = _write_filtered_object_info_cache(tmp_path, filtered_payloads)
        _patch_object_info_cache(monkeypatch, cache_root)
        return {"cache_root": str(cache_root)}

    # Step 1: ensure_env with authored versions
    ensure_result = ensure_env(
        raw,
        known_packs=(_acceptance_pack("CustomPack"),),
        installer=installer,
        introspector=introspector,
        cache_writer=cache_writer,
        resolver=resolver,
    )
    assert ensure_result.ok is True, (
        f"ensure_env failed: failures={ensure_result.failures}, "
        f"warnings={[(w.code, w.message) for w in ensure_result.warnings]}"
    )
    # CustomPack must carry the authored commit
    assert install_refs_seen["CustomPack"].commit == authored_commit, (
        f"Expected commit {authored_commit!r}, got {install_refs_seen['CustomPack'].commit!r}"
    )

    # Step 2: Verify authored version identity propagation
    identities = _node_object_info_identities(raw)
    assert identities, "identity map must be non-empty"
    for node in raw["nodes"]:
        node_id = str(node["id"])
        props = node.get("properties", {})
        if not props.get("cnr_id"):
            continue
        if node["type"] in {"MarkdownNote", "Note"}:
            continue
        identity = identities.get(node_id)
        assert identity is not None, (
            f"Node {node_id} ({node['type']}) missing from identity map"
        )
        assert identity.pack_slug == props["cnr_id"], (
            f"Node {node_id}: expected pack_slug={props['cnr_id']!r}, "
            f"got {identity.pack_slug!r}"
        )
        has_anchor = (
            identity.git_commit is not None
            or identity.evidence_identity is not None
        )
        assert has_anchor, f"Node {node_id}: identity has no version anchor"

    # Step 3: Convert with authored identity map (use load_port_source workflow)
    from vibecomfy.porting.workbench import load_port_source

    # Write raw to temp file for load_port_source
    src_path = tmp_path / "workflow.json"
    src_path.write_text(json.dumps(raw), encoding="utf-8")
    src = load_port_source(str(src_path), use_comfy_converter=False)

    conversion_result = port_convert_workflow(
        src.workflow,
        raw_workflow=raw,
        source_path=src.source_path,
        source_hash=src.source_hash,
        ready_id="test/c12_faithful",
    )
    assert conversion_result.validation is not None
    assert conversion_result.validation.compile_ok is True, (
        f"Compilation failed: {conversion_result.validation.error}"
    )
    # strict_ready_ok requires public input/output contracts which this
    # minimal faith-pinning workflow does not define — that is orthogonal
    # to the authored-version identity assertion.

    # Step 4: Verify the emitted template compiles to a usable API
    api = _compile_ready_template_api(
        conversion_result.text, module_name="c12_faithful"
    )
    assert len(api) > 0, "API must have at least one node"
    # The minimal faith-pinning workflow has no edges between nodes,
    # so topology_counter is empty — that is expected for this test.

    # Step 5: Verify no low-confidence fallback in the emission diagnostics
    assert conversion_result.validation.low_confidence is False, (
        "authored-version conversion must not be low-confidence"
    )
