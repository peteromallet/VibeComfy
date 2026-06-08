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

import json
from pathlib import Path

import pytest

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
def test_a2_fail_closed_on_known_node_arity_disagreement():
    """cache outputs < UI outputs => raise (stale); cache > UI => warn (unused)."""
    from vibecomfy.errors import ArityDisagreementError
    with pytest.raises(ArityDisagreementError) as exc:
        # UI declares 3 outputs; a stale snapshot offering 2 must fail closed.
        from vibecomfy.porting.object_info import check_output_arity_consensus
        check_output_arity_consensus("ComfyMathExpression", ui_output_count=3)
    msg = str(exc.value)
    assert "ComfyMathExpression" in msg and "refresh" in msg.lower()


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
@pytest.mark.skip(reason="Sprint B — testing.md scenario 6")
def test_b6_ensure_env_installs_and_is_idempotent():
    from vibecomfy.runtime.ensure_env import ensure_env  # added in B
    result = ensure_env(str(IDEOGRAM))
    assert result.ok and result.installed is not None
    again = ensure_env(str(IDEOGRAM))
    assert again.noop, "ensure-env must be idempotent"


@pytest.mark.sprint_b
@pytest.mark.skip(reason="Sprint B — testing.md scenario 7")
def test_b7_install_robustness():
    """clone-ok/pip-fail is NOT reported installed; cross-pack pip preflight runs."""
    pytest.fail("simulate clone-ok/pip-fail + multi-pack conflict — see testing.md §7")


@pytest.mark.sprint_b
@pytest.mark.skip(reason="Sprint B — testing.md scenario 8")
def test_b8_provenance_determines_pack_set():
    from vibecomfy.porting.provenance import extract_provenance  # added in B
    prov = extract_provenance(json.loads(IDEOGRAM.read_text()))
    assert prov, "must parse cnr_id/aux_id/ver into a per-class pack set"


@pytest.mark.sprint_b
@pytest.mark.skip(reason="Sprint B — testing.md scenario 12 (compile)")
def test_b12_ideogram_ports_to_compiling_strict_ready_template():
    from vibecomfy.porting.convert import port_convert_workflow
    from vibecomfy.porting.workbench import load_port_source
    src = load_port_source(str(IDEOGRAM), use_comfy_converter=False)
    raw = json.loads(IDEOGRAM.read_text())
    res = port_convert_workflow(
        src.workflow, raw_workflow=raw, source_path=src.source_path,
        source_hash=src.source_hash, ready_id="image/ideogram4_t2i",
    )
    assert res.validation.compile_ok and res.validation.strict_ready_ok, res.validation.error


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
