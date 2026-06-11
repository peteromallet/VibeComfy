"""Characterization-gate agent-edit roundtrip tests.

Drives ``EditSession`` through five representative DSL batches — widget-set,
add-node, connect, disconnect, and multi-op — and asserts the structural
identity of the resulting ``working_ui`` and the ``done()`` summary against
committed fixtures.

Set ``VIBECOMFY_CHARACTERIZATION_WRITE=1`` to bootstrap fixture expected.json
files from the current behaviour.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from vibecomfy.porting.edit.session import EditSession

from . import _canon

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "agent_edit"
WRITE_MODE = os.environ.get("VIBECOMFY_CHARACTERIZATION_WRITE") == "1"

# The flat.json fixture provides a minimal schema provider (copied from the
# harness tests so we stay offline and deterministic).
_FLAT_SCHEMA = None


def _flat_schema_provider():
    """Return a minimal schema provider for the flat.json fixture."""
    from vibecomfy.schema import InputSpec, NodeSchema, OutputSpec

    class SP:
        def get_schema(self, ct: str) -> Any:
            return {
                "CheckpointLoaderSimple": NodeSchema(
                    "CheckpointLoaderSimple",
                    "core",
                    {"ckpt_name": InputSpec(type="STRING", required=True)},
                    [
                        OutputSpec("MODEL", "MODEL"),
                        OutputSpec("CLIP", "CLIP"),
                        OutputSpec("VAE", "VAE"),
                    ],
                ),
                "CLIPTextEncode": NodeSchema(
                    "CLIPTextEncode",
                    "core",
                    {
                        "text": InputSpec("STRING", required=True),
                        "clip": InputSpec("CLIP", required=True),
                    },
                    [OutputSpec("CONDITIONING", "CONDITIONING")],
                ),
                "EmptyLatentImage": NodeSchema(
                    "EmptyLatentImage",
                    "core",
                    {
                        "width": InputSpec("INT"),
                        "height": InputSpec("INT"),
                        "batch_size": InputSpec("INT"),
                    },
                    [OutputSpec("LATENT", "LATENT")],
                ),
                "KSampler": NodeSchema(
                    "KSampler",
                    "core",
                    {
                        "seed": InputSpec("INT"),
                        "steps": InputSpec("INT"),
                        "cfg": InputSpec("FLOAT"),
                        "sampler_name": InputSpec("STRING"),
                        "scheduler": InputSpec("STRING"),
                        "denoise": InputSpec("FLOAT"),
                        "model": InputSpec("MODEL", required=True),
                        "positive": InputSpec("CONDITIONING", required=True),
                        "negative": InputSpec("CONDITIONING", required=True),
                        "latent_image": InputSpec("LATENT", required=True),
                    },
                    [OutputSpec("LATENT", "LATENT")],
                ),
                "VAEDecode": NodeSchema(
                    "VAEDecode",
                    "core",
                    {
                        "samples": InputSpec("LATENT", required=True),
                        "vae": InputSpec("VAE", required=True),
                    },
                    [OutputSpec("IMAGE", "IMAGE")],
                ),
                "SaveImage": NodeSchema(
                    "SaveImage",
                    "core",
                    {
                        "images": InputSpec("IMAGE", required=True),
                        "filename_prefix": InputSpec("STRING", required=True),
                    },
                    [],
                ),
                "PrimitiveInt": NodeSchema(
                    "PrimitiveInt",
                    "core",
                    {"value": InputSpec("INT")},
                    [OutputSpec("INT", "value")],
                ),
                "Reroute": NodeSchema(
                    "Reroute",
                    "core",
                    {"": InputSpec("*")},
                    [OutputSpec("*", "")],
                ),
            }.get(ct)

    return SP()


# ---------------------------------------------------------------------------
# Expected shape
# ---------------------------------------------------------------------------


def _make_expected(
    session: EditSession, batch_result: Any, done_result: Any
) -> dict[str, Any]:
    """Produce the canonical ``expected.json`` dict for a case."""
    return {
        "working_ui_structural_hash": _canon.structural_hash(
            _canon.strip_volatile_ui(session.working_ui)
        ),
        "sorted_diagnostic_codes": sorted(
            d.code for d in batch_result.diagnostics
        ),
        "ok": batch_result.ok,
        "landed_op_kinds": [
            getattr(op, "op", type(op).__name__) for op in batch_result.landed_ops
        ],
        "done_summary_prefix_120": done_result.summary[:120],
    }


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

_CASES = sorted(
    d.name
    for d in FIXTURE_ROOT.iterdir()
    if d.is_dir() and d.name.startswith("case_")
)


@pytest.mark.characterization
@pytest.mark.parametrize("case_name", _CASES)
def test_agent_edit_roundtrip(case_name: str) -> None:
    """Load a fixture triplet, apply the DSL batch, and assert expected results."""
    case_dir = FIXTURE_ROOT / case_name

    # --- Load fixtures ---
    input_ui = json.loads(
        (case_dir / "input_ui.json").read_text(encoding="utf-8")
    )
    batch_code = (case_dir / "batch.py.txt").read_text(encoding="utf-8").strip()

    # --- Create session ---
    session = EditSession(input_ui, schema_provider=_flat_schema_provider())
    session.render()

    # --- Apply batch ---
    batch_result = session.apply_batch(code=batch_code)

    # --- Done ---
    done_result = session.done()

    expected = _make_expected(session, batch_result, done_result)

    expected_path = case_dir / "expected.json"

    if WRITE_MODE:
        expected_path.write_text(
            json.dumps(expected, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return

    # --- Assert against committed expected.json ---
    if not expected_path.exists():
        pytest.fail(
            f"No expected.json for {case_name}. "
            f"Run with VIBECOMFY_CHARACTERIZATION_WRITE=1 to bootstrap."
        )

    committed = json.loads(expected_path.read_text(encoding="utf-8"))

    # Compare field-by-field for clear error messages.
    assert (
        expected["working_ui_structural_hash"]
        == committed["working_ui_structural_hash"]
    ), (
        f"{case_name}: working_ui_structural_hash mismatch. "
        f"Expected {committed['working_ui_structural_hash']}, "
        f"got {expected['working_ui_structural_hash']}."
    )

    assert (
        expected["sorted_diagnostic_codes"]
        == committed["sorted_diagnostic_codes"]
    ), (
        f"{case_name}: sorted_diagnostic_codes mismatch. "
        f"Expected {committed['sorted_diagnostic_codes']}, "
        f"got {expected['sorted_diagnostic_codes']}."
    )

    assert expected["ok"] == committed["ok"], (
        f"{case_name}: ok mismatch. "
        f"Expected {committed['ok']}, got {expected['ok']}."
    )

    assert (
        expected["landed_op_kinds"] == committed["landed_op_kinds"]
    ), (
        f"{case_name}: landed_op_kinds mismatch. "
        f"Expected {committed['landed_op_kinds']}, "
        f"got {expected['landed_op_kinds']}."
    )

    assert (
        expected["done_summary_prefix_120"]
        == committed["done_summary_prefix_120"]
    ), (
        f"{case_name}: done_summary_prefix_120 mismatch.\n"
        f"Expected: {committed['done_summary_prefix_120']}\n"
        f"Got:      {expected['done_summary_prefix_120']}"
    )
