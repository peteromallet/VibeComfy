"""Parity tests: LintIndexBackend vs EditLedgerBackend return identical results.

Covers the 5 required cases from M4 SC2:
  1. canonical uid  — node exists under its stamped uid
  2. LG-int-id "42" — uid_str is a decimal string that maps to a different canonical uid
  3. unknown uid    — uid_str does not exist in the graph
  4. widget-only target — input field absent from raw node inputs (no schema_provider)
  5. int + str output_slot — resolve_output_slot_index with both flavours

Verifies that EditLedgerBackend.__init__ builds the reverse LG-id index via
the shared build_lg_id_maps helper (by asserting correct LG-id aliasing).
"""

from __future__ import annotations

from typing import Any

import pytest

from vibecomfy.porting.edit.ledger import EditLedger
from vibecomfy.porting.edit.lint import LintIndex
from vibecomfy.porting.edit.ops import LinkSourceRef, LinkTargetRef
from vibecomfy.porting.resolution import (
    EditLedgerBackend,
    LintIndexBackend,
    NodeBackend,
    ResolutionContext,
    build_lg_id_maps,
)


# ── synthetic graph ───────────────────────────────────────────────────────────
#
# Node id=1  → canonical uid "1"   (no vibecomfy_uid, stamped from integer id)
# Node id=42 → canonical uid "my_sampler"  (vibecomfy_uid overrides int id)
#   This is the linchpin: "42" as uid_str must alias to "my_sampler" via LG-id.

_SYNTHETIC_UI: dict[str, Any] = {
    "nodes": [
        {
            "id": 1,
            "type": "CheckpointLoader",
            "properties": {},
            "inputs": [],
            "outputs": [
                {"name": "MODEL", "type": "MODEL", "slot_index": 0},
                {"name": "CLIP", "type": "CLIP", "slot_index": 1},
            ],
            "widgets_values": ["model.safetensors"],
        },
        {
            "id": 42,
            "type": "KSampler",
            "properties": {"vibecomfy_uid": "my_sampler"},
            "inputs": [
                {"name": "model", "type": "MODEL"},
                {"name": "positive", "type": "CONDITIONING"},
            ],
            "outputs": [
                {"name": "LATENT", "type": "LATENT", "slot_index": 0},
            ],
            "widgets_values": [42, "euler", "normal", 20, 7.0],
        },
    ],
    "links": [],
}


@pytest.fixture()
def lint_backend() -> LintIndexBackend:
    idx = LintIndex.build(_SYNTHETIC_UI)
    return LintIndexBackend(idx)


@pytest.fixture()
def ledger_backend() -> EditLedgerBackend:
    ledger = EditLedger.ingest(_SYNTHETIC_UI)
    return EditLedgerBackend(ledger)


@pytest.fixture(params=["lint", "ledger"])
def backend(request: pytest.FixtureRequest) -> NodeBackend:
    if request.param == "lint":
        return LintIndexBackend(LintIndex.build(_SYNTHETIC_UI))
    return EditLedgerBackend(EditLedger.ingest(_SYNTHETIC_UI))


ctx = ResolutionContext()


# ── case 1: canonical uid ─────────────────────────────────────────────────────

def test_canonical_uid_resolves(backend: NodeBackend) -> None:
    result = ctx.resolve_uid(backend, "", "1")
    assert result.value == "1"
    assert result.issues == []


def test_canonical_uid_my_sampler(backend: NodeBackend) -> None:
    result = ctx.resolve_uid(backend, "", "my_sampler")
    assert result.value == "my_sampler"
    assert result.issues == []


# ── case 2: LG-int-id "42" aliases to canonical uid "my_sampler" ─────────────

def test_lg_int_id_aliases_to_canonical_uid(backend: NodeBackend) -> None:
    """uid_str "42" must resolve to "my_sampler" on both backends via LG-id lookup.

    This is the primary divergence D1 that M4 closes: both backends now build
    the LG-id reverse index via the shared build_lg_id_maps helper.
    """
    result = ctx.resolve_uid(backend, "", "42")
    assert result.value == "my_sampler", (
        f"Expected 'my_sampler' but got {result.value!r}; "
        "EditLedgerBackend must build LG-id reverse index via build_lg_id_maps"
    )
    assert result.issues == []


def test_uid_for_lg_id_direct(backend: NodeBackend) -> None:
    assert backend.uid_for_lg_id("", 42) == "my_sampler"
    assert backend.uid_for_lg_id("", 1) == "1"
    assert backend.uid_for_lg_id("", 999) is None


# ── case 3: unknown uid ───────────────────────────────────────────────────────

def test_unknown_uid_returns_none_with_issue(backend: NodeBackend) -> None:
    result = ctx.resolve_uid(backend, "", "xyz_does_not_exist")
    assert result.value is None
    assert len(result.issues) == 1
    assert result.issues[0].code == "unknown_target"


def test_unknown_lg_id_returns_none_with_issue(backend: NodeBackend) -> None:
    # "999" is not a known LiteGraph id
    result = ctx.resolve_uid(backend, "", "999")
    assert result.value is None
    assert len(result.issues) == 1
    assert result.issues[0].code == "unknown_target"


# ── case 4: widget-only target (field absent from raw inputs) ─────────────────

def test_widget_only_target_absent_input(backend: NodeBackend) -> None:
    """A field that is not in raw node inputs returns None+unknown_target_input.

    Without a schema_provider both backends should reject widget-only fields
    identically (D3 notes that apply is more permissive when schema_provider
    is supplied, but without one the result must be identical).
    """
    ref = LinkTargetRef(scope_path="", uid="my_sampler", input_field="sampler_name")
    result = ctx.resolve_target_endpoint(backend, ref, schema_provider=None)
    assert result.value is None
    assert len(result.issues) == 1
    assert result.issues[0].code == "unknown_target_input"


def test_known_input_target_resolves(backend: NodeBackend) -> None:
    ref = LinkTargetRef(scope_path="", uid="my_sampler", input_field="model")
    result = ctx.resolve_target_endpoint(backend, ref, schema_provider=None)
    assert result.value is not None
    assert result.value.slot_name == "model"
    assert result.issues == []


# ── case 5: int + str output_slot ─────────────────────────────────────────────

def test_int_output_slot_resolves(backend: NodeBackend) -> None:
    result = ctx.resolve_output_slot_index(backend, "", "1", 0)
    assert result.value == 0
    assert result.issues == []


def test_str_output_slot_resolves(backend: NodeBackend) -> None:
    result = ctx.resolve_output_slot_index(backend, "", "1", "MODEL")
    assert result.value == 0
    assert result.issues == []


def test_int_output_slot_out_of_bounds(backend: NodeBackend) -> None:
    result = ctx.resolve_output_slot_index(backend, "", "1", 99)
    assert result.value is None
    assert result.issues[0].code == "unknown_output_slot"


def test_str_output_slot_unknown(backend: NodeBackend) -> None:
    result = ctx.resolve_output_slot_index(backend, "", "1", "NONEXISTENT")
    assert result.value is None
    assert result.issues[0].code == "unknown_output_slot"


# ── node_meta_for parity (used by slot resolution internally) ─────────────────

def test_node_meta_for_parity(
    lint_backend: LintIndexBackend, ledger_backend: EditLedgerBackend
) -> None:
    """Both backends return identical _NodeMeta for the same node."""
    for uid, expected_class, expected_inputs, expected_outputs in [
        ("1", "CheckpointLoader", (), ("MODEL", "CLIP")),
        ("my_sampler", "KSampler", ("model", "positive"), ("LATENT",)),
    ]:
        lint_meta = lint_backend.node_meta_for("", uid)
        ledger_meta = ledger_backend.node_meta_for("", uid)
        assert lint_meta is not None, f"lint_backend missing meta for {uid}"
        assert ledger_meta is not None, f"ledger_backend missing meta for {uid}"
        assert lint_meta.class_type == expected_class
        assert lint_meta.input_names == expected_inputs
        assert lint_meta.output_names == expected_outputs
        # parity: both backends agree on every field
        assert lint_meta.class_type == ledger_meta.class_type
        assert lint_meta.input_names == ledger_meta.input_names
        assert lint_meta.output_names == ledger_meta.output_names
        assert lint_meta.lg_id == ledger_meta.lg_id


# ── build_lg_id_maps helper used by EditLedgerBackend.__init__ ─────────────────

def test_edit_ledger_backend_uses_shared_build_lg_id_maps() -> None:
    """EditLedgerBackend.__init__ must build its reverse index via the shared
    build_lg_id_maps(node_index) helper — verified by asserting the result
    matches what build_lg_id_maps returns directly.
    """
    ledger = EditLedger.ingest(_SYNTHETIC_UI)
    backend = EditLedgerBackend(ledger)
    expected_lg_to_uid, expected_uid_to_lg = build_lg_id_maps(ledger.node_index)
    # backend's internal maps must match
    assert backend._lg_id_to_uid == expected_lg_to_uid
    assert backend._uid_to_lg_id == expected_uid_to_lg
