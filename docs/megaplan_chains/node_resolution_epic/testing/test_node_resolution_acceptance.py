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
@pytest.mark.skip(reason="Sprint A — testing.md scenario 1")
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
@pytest.mark.skip(reason="Sprint A — testing.md scenario 2")
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
@pytest.mark.skip(reason="Sprint A — testing.md scenario 3")
def test_a3_core_refresh_does_not_clobber_custom_packs():
    """After refreshing core schema, custom-pack classes still resolve (merge)."""
    from vibecomfy.porting.object_info import class_is_known
    # refresh core from evidence/object_info_comfyui_0.24.0.1.json (merge mode) ...
    assert class_is_known("ComfyMathExpression")          # core updated
    assert class_is_known("WanVideoModelLoader")          # custom pack preserved


@pytest.mark.sprint_a
@pytest.mark.skip(reason="Sprint A — testing.md scenario 4")
def test_a4_io_schema_nodes_covered():
    """Executed introspection (not AST) yields correct outputs for io.Schema nodes."""
    from vibecomfy.porting.object_info import output_names
    assert output_names("ComfyMathExpression") == ["FLOAT", "INT", "BOOL"]


@pytest.mark.sprint_a
@pytest.mark.skip(reason="Sprint A — testing.md scenario 5")
def test_a5_identity_keyed_cache_and_drift():
    """Cache key is (pack_slug, git_commit); schema-hash wired; drift uses one algo."""
    # compute_schema_hash wired at install; drift.py compares the same projection.
    from vibecomfy.node_packs_lockfile import compute_schema_hash  # noqa: F401
    pytest.fail("assert (pack, commit) lookup + consistent drift hash — see testing.md §5")


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
@pytest.mark.skip(reason="Sprint C — testing.md scenario 9")
def test_c9_faithful_version_pinning():
    """Installs the authored commit (from `ver`), not latest; aux_id path works."""
    pytest.fail("resolve_pack(pin_version=sha) + git checkout — see testing.md §9")


@pytest.mark.sprint_c
@pytest.mark.skip(reason="Sprint C — testing.md scenario 10")
def test_c10_provenance_less_warns_never_silent_latest():
    """A provenance-less workflow resolves with an explicit warning, low-confidence."""
    corpus = Path("workflow_corpus/official/video/wan_t2v.json")
    assert corpus.exists()
    pytest.fail("resolve with warning (not silent latest) — see testing.md §10")


@pytest.mark.sprint_c
@pytest.mark.skip(reason="Sprint C — testing.md scenario 11")
def test_c11_snapshot_regenerable_per_pack():
    """Core schema regenerable from pinned pip-comfy; per-pack versioned; no monolith."""
    pytest.fail("schemas regen-core --comfy-version + per-pack files — see testing.md §11")


@pytest.mark.sprint_c
@pytest.mark.skip(reason="Sprint C — testing.md scenario 12 (faithful)")
def test_c12_ideogram_ports_at_authored_versions():
    pytest.fail("port pins each node to its cnr_id/ver commit — see testing.md §12")
