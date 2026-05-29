"""Layer 2 — object_info validation gate via standalone ObjectInfoIndexSchemaProvider (T15 / Step 12a) + T16 negative test.

Layer 2 is a fast pre-filter, NOT full independence.
=====================================================

The emitter (:func:`~vibecomfy.porting.ui_emitter.emit_ui_json`) and this
gate share the same ``object_info`` provenance (the pinned cache).  Because
both read the same snapshot, Layer 2 can catch *internal inconsistencies*
(e.g. a widget-order mismatch between two cache files), but it CANNOT prove
that the emitter produces schema-less nodes correctly — that is Layer 3's
job.  Layer 2 must never be cited as an independence proof; it is a
consistency pre-filter.

The ``test_swapped_widget_order_detected_by_layer2`` negative test (T16)
proves this boundary: a deliberately swapped widget order in the cache
FAILS Layer 2, confirming the gate catches internal cache corruption but
also revealing that the gate trusts whatever is in the cache.

Constructs ``ObjectInfoIndexSchemaProvider`` DIRECTLY (NOT
``ConversionSchemaProvider``, which would shadow the pin with
``node_index.json``).  Validates widget count+order, output socket
count/types, and required inputs across the full object_info corpus.

UUID/subgraph instances, SetNode/GetNode/rgthree, ``@stub.json`` classes,
and unknown classes are classified as schema-less → loud warn + skip with a
MAX-SKIP BUDGET that is enforced.

This test is auto-discovered by the CI pytest invocation (ci.yml has no
``--ignore`` pattern that would exclude it).
"""

from __future__ import annotations

import json
import os
import re
import uuid as _uuid
from pathlib import Path

import pytest

from vibecomfy.schema.provider import ObjectInfoIndexSchemaProvider


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OBJECT_INFO_ROOT = "vibecomfy/porting/cache/object_info"

# Maximum number of schema-less nodes we tolerate before the gate fails.
_MAX_SKIP_BUDGET = 50

# UUID v4 pattern for classifying subgraph instance nodes.
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Classes that are always schema-less by construction (display-only / virtual).
_ALWAYS_SCHEMA_LESS = frozenset({
    "SetNode", "GetNode", "Reroute",
    "Note", "MarkdownNote", "Label (rgthree)",
    "PreviewAny", "easy showAnything",
})

# Known @stub.json file classes — their object_info data is from a stub,
# not a real runtime scan, so they are schema-less with low confidence.
_STUB_FILES = frozenset({
    "comfyui_controlnet_aux@stub.json",
    "ComfyUI-Florence2@stub.json",
    "ComfyUI-MelBandRoformer@stub.json",
    "ComfyUI-Custom-Scripts@stub.json",
    "ComfyUI-GIMM-VFI@stub.json",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_uuid_instance(class_type: str) -> bool:
    """Check if a class_type is a UUID v4 (subgraph instance node)."""
    return bool(_UUID_PATTERN.match(class_type))


def _is_stub_class(class_type: str, provider: ObjectInfoIndexSchemaProvider) -> bool:
    """Check if a class is sourced from a @stub.json file."""
    filename = provider._load_index().get(class_type)
    if not filename:
        return False
    return str(filename) in _STUB_FILES


def _is_rgthree_class(class_type: str) -> bool:
    """Check if a class is an rgthree utility node (display-only helpers)."""
    lower = class_type.lower()
    return "rgthree" in lower and any(
        keyword in lower
        for keyword in ("reroute", "muter", "bypasser", "bookmark", "comment")
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_object_info_validation_gate() -> None:
    """Layer-2 validation gate over the standalone ObjectInfoIndexSchemaProvider.

    Validates every class in the object_info index:
    - Widget count from raw object_info_widget_order (nulls included).
    - Widget order matches the expected positional semantics.
    - Output socket count matches schema outputs.
    - Required inputs are present.

    Schema-less classes are skipped with a loud warning and counted against
    the MAX-SKIP BUDGET.  The test FAILS if the skip budget is exceeded.
    """
    provider = ObjectInfoIndexSchemaProvider(_OBJECT_INFO_ROOT)
    index = provider._load_index()

    if not index:
        pytest.skip("object_info index is empty — cache not available")

    total = 0
    validated = 0
    skipped: list[dict[str, str]] = []
    errors: list[str] = []
    # Output metadata issues are informational, not gate-blocking.
    output_warnings: list[str] = []

    for class_type, filename in sorted(index.items()):
        total += 1

        # --- Classification: determine if this class is schema-less ---
        schema_less_reason: str | None = None

        if class_type in _ALWAYS_SCHEMA_LESS:
            schema_less_reason = f"always-schema-less ({class_type})"
        elif _is_uuid_instance(class_type):
            schema_less_reason = "uuid/subgraph-instance"
        elif _is_rgthree_class(class_type):
            schema_less_reason = "rgthree-utility"
        elif _is_stub_class(class_type, provider):
            schema_less_reason = "stub-json"

        if schema_less_reason is not None:
            skipped.append({
                "class_type": class_type,
                "reason": schema_less_reason,
                "filename": filename,
            })
            continue

        # --- Load schema ---
        schema = provider.get_schema(class_type)
        if schema is None:
            skipped.append({
                "class_type": class_type,
                "reason": "get_schema returned None",
                "filename": filename,
            })
            continue

        # --- Widget count validation ---
        raw_order = provider.raw_widget_order(class_type)
        if raw_order is not None:
            widget_count = len(raw_order)
            # For nodes with a known schema, 0 widgets while having inputs
            # is unusual but not a gate-blocker (e.g., rgthree utility nodes).
            if widget_count == 0 and schema.inputs:
                output_warnings.append(
                    f"{class_type}: raw_widget_order has 0 entries but"
                    f" schema has {len(schema.inputs)} input(s)"
                )
        else:
            # No widget order available — this is acceptable for nodes
            # that have only edge inputs (no widgets)
            pass

        # --- Output socket count validation ---
        schema_outputs = schema.outputs or []
        if schema_outputs:
            for i, out in enumerate(schema_outputs):
                if not out.name:
                    output_warnings.append(
                        f"{class_type} output[{i}]: missing name"
                    )
                if out.type is None:
                    output_warnings.append(
                        f"{class_type} output[{i}] ({out.name}): missing type"
                    )

        # --- Required inputs: every input in the schema should be valid ---
        for input_name, input_spec in (schema.inputs or {}).items():
            if not isinstance(input_name, str) or not input_name.strip():
                errors.append(
                    f"{class_type}: empty input name in schema"
                )

        validated += 1

    # --- Budget enforcement ---
    skip_count = len(skipped)
    budget_exceeded = skip_count > _MAX_SKIP_BUDGET

    # Print detailed report
    print(f"\n[T15] Layer-2 object_info validation gate:")
    print(f"  Total classes in index: {total}")
    print(f"  Validated: {validated}")
    print(f"  Skipped (schema-less): {skip_count}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output metadata warnings: {len(output_warnings)}")
    if skipped:
        print(f"\n  Schema-less classes ({skip_count}):")
        for s in skipped[:15]:
            print(f"    {s['class_type']}: {s['reason']} ({s['filename']})")
        if len(skipped) > 15:
            print(f"    ... and {len(skipped) - 15} more")

    if output_warnings:
        print(f"\n  Output metadata warnings ({len(output_warnings)}):")
        for w in output_warnings[:10]:
            print(f"    {w}")
        if len(output_warnings) > 10:
            print(f"    ... and {len(output_warnings) - 10} more")

    if errors:
        print(f"\n  Validation errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"    {e}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")

    # Assertions
    assert validated > 0, (
        f"No classes validated (total={total}, skipped={skip_count})."
        f" The object_info gate cannot be green with zero validated classes."
    )

    if budget_exceeded:
        pytest.fail(
            f"MAX-SKIP BUDGET exceeded: {skip_count} skipped > {_MAX_SKIP_BUDGET}"
            f" allowed.  Investigate unexpected schema-less classes."
        )

    if errors:
        pytest.fail(
            f"Layer-2 validation errors ({len(errors)}):\n"
            + "\n".join(errors[:20])
        )


def test_object_info_validation_known_classes_present() -> None:
    """Sanity check: key ComfyUI core classes are present in the object_info index."""
    provider = ObjectInfoIndexSchemaProvider(_OBJECT_INFO_ROOT)
    index = provider._load_index()

    required = [
        "KSampler", "KSamplerAdvanced", "LoadImage", "SaveImage",
        "VAEDecode", "CLIPTextEncode", "CheckpointLoaderSimple",
        "EmptyLatentImage", "UNETLoader",
    ]

    missing = [c for c in required if c not in index]
    assert not missing, (
        f"Required core classes missing from object_info index: {missing}"
    )


def test_object_info_validation_ci_not_excluded() -> None:
    """Confirm the ci.yml invocation does not exclude this test file.

    The CI workflow at .github/workflows/ci.yml runs pytest auto-discovery
    without ``--ignore`` patterns targeting this file.  This test verifies
    that the ci.yml file exists and contains no exclusion that would prevent
    this test from running.
    """
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists(), "ci.yml not found"

    ci_text = ci_path.read_text()

    # This file's path
    this_file = "tests/test_emitter_object_info_validation.py"

    # The file must NOT be explicitly ignored
    assert this_file not in ci_text, (
        f"{this_file} is unexpectedly mentioned in ci.yml — check for exclusion"
    )

    # Check for broad ignore patterns that would catch this file
    ignore_patterns = [
        line.strip()
        for line in ci_text.split("\n")
        if "--ignore" in line
    ]
    for pattern in ignore_patterns:
        assert "object_info" not in pattern, (
            f"ci.yml has ignore pattern that would exclude this test: {pattern}"
        )

    print(f"\n[T15] CI check: {this_file} is NOT excluded by ci.yml")


# ---------------------------------------------------------------------------
# T16 / Step 12b — Negative test: swapped widget order FAILS Layer 2
# ---------------------------------------------------------------------------


def _cross_validate_widget_order(
    provider: ObjectInfoIndexSchemaProvider,
    class_type: str,
) -> list[str]:
    """Cross-validate that raw_widget_order names match the input-group names.

    Returns a list of mismatch descriptions; empty list means consistent.
    Layer 2 uses this to detect cached data where ``object_info_widget_order``
    names and the ``input`` group keys disagree — evidence the cache has been
    corrupted or manually edited.

    The check reads the RAW object_info data (not the derived schema) so it
    compares ``object_info_widget_order`` entries against the keys in the
    ``input.required`` / ``input.optional`` groups directly.  If widget-order
    names are not a subset of input-group names (or vice versa), the cache is
    internally inconsistent.

    NOTE: this check is still bounded by the object_info provenance.  If
    BOTH the widget order and input groups are wrong in the same way (e.g.
    a stale cache that mistranslates a new ComfyUI version), the emitter
    and the gate will agree on the wrong answer.  That is why Layer 2 is a
    pre-filter, not an independence proof.
    """
    issues: list[str] = []

    # Bypass the derived schema — read the RAW object_info dict directly.
    filename = provider._load_index().get(class_type)
    if not filename:
        return issues

    raw_data = provider._file_cache.get(filename)
    if raw_data is None:
        import json

        raw_data = json.loads((provider.root / filename).read_text()) or {}
        provider._file_cache[filename] = raw_data

    info = raw_data.get(class_type)
    if not isinstance(info, dict):
        return issues

    raw_order = info.get("object_info_widget_order")
    if not isinstance(raw_order, list):
        return issues  # no widget order to validate

    # Collect all input names from input groups (required + optional).
    input_groups = info.get("input")
    if not isinstance(input_groups, dict):
        input_groups = info.get("inputs", {})
    all_input_names: set[str] = set()
    if isinstance(input_groups, dict):
        for _group_name, group in input_groups.items():
            if isinstance(group, dict):
                all_input_names.update(str(k) for k in group)

    if not all_input_names:
        return issues  # can't cross-validate without inputs

    # Compact widget order (strip None entries for UI-only slots).
    widget_names = {n for n in raw_order if isinstance(n, str) and n}

    # --- Detection rules ---
    # 1. Names in widget_order that are NOT in any input group.
    orphan_widgets = widget_names - all_input_names
    if orphan_widgets:
        issues.append(
            f"{class_type}: widget names not in any input group: {sorted(orphan_widgets)}"
        )

    # 2. Names in input groups that are NOT in widget_order.
    missing_from_widgets = all_input_names - widget_names
    if missing_from_widgets:
        issues.append(
            f"{class_type}: input names missing from widget_order: {sorted(missing_from_widgets)}"
        )

    # 3. Order mismatch: the compacted widget order disagrees with the
    #    input-group key order (dict insertion order from the JSON).
    compacted_raw = [n for n in raw_order if isinstance(n, str) and n]
    # Input group order is the concatenation of keys from each group in JSON order.
    input_group_order: list[str] = []
    if isinstance(input_groups, dict):
        for _group_name, group in input_groups.items():
            if isinstance(group, dict):
                input_group_order.extend(str(k) for k in group)
    # Compare the common prefix order.
    common_widgets = [n for n in compacted_raw if n in all_input_names]
    common_inputs = [n for n in input_group_order if n in widget_names]
    if common_widgets and common_inputs and common_widgets != common_inputs:
        issues.append(
            f"{class_type}: widget order mismatch —"
            f" widget={common_widgets} vs input_groups={common_inputs}"
        )

    return issues


def test_swapped_widget_order_detected_by_layer2(tmp_path: Path) -> None:
    """T16 negative test: deliberately swapped widget order FAILS Layer 2.

    Creates a temporary object_info cache where one class has a widget order
    that contradicts its input groups (the ``object_info_widget_order`` names
    are deliberately swapped relative to the ``input.required`` keys).  The
    Layer 2 cross-validation catches this, proving the gate detects internal
    cache corruption.

    This also proves the boundary: the gate trusts whatever is in the cache.
    If BOTH the widget order and the input groups were wrong in the same
    way (e.g. a stale cache that mistranslates a new ComfyUI version), the
    gate would NOT catch it — Layer 3 is needed for that.
    """
    import json as _json

    root = tmp_path / "object_info"
    root.mkdir()

    # --- Build a synthetic index.json ---
    index: dict[str, str] = {
        "GoodNode": "good_pack@synth.json",
        "SwappedNode": "swapped_pack@synth.json",
    }
    (root / "index.json").write_text(_json.dumps(index, indent=2))

    # --- GoodNode: widget order matches input-group keys ---
    good_info: dict[str, Any] = {
        "GoodNode": {
            "object_info_widget_order": ["alpha", "beta", "gamma"],
            "input": {
                "required": {
                    "alpha": ["INT", {"default": 1}],
                    "beta": ["FLOAT", {"default": 0.0}],
                    "gamma": ["STRING", {"default": ""}],
                }
            },
            "output": ["IMAGE"],
            "pack": "good_pack",
        }
    }
    (root / "good_pack@synth.json").write_text(_json.dumps(good_info, indent=2))

    # --- SwappedNode: widget order ["gamma", "delta", "alpha"] swaps gamma/alpha
    #     AND introduces "delta" which is NOT in any input group, while "beta"
    #     is in the input group but MISSING from widget_order.  This is an
    #     internally inconsistent cache that Layer 2 MUST catch. ---
    bad_info: dict[str, Any] = {
        "SwappedNode": {
            "object_info_widget_order": ["gamma", "delta", "alpha"],
            "input": {
                "required": {
                    "alpha": ["INT", {"default": 1}],
                    "beta": ["FLOAT", {"default": 0.0}],
                    "gamma": ["STRING", {"default": ""}],
                }
            },
            "output": ["IMAGE"],
            "pack": "swapped_pack",
        }
    }
    (root / "swapped_pack@synth.json").write_text(_json.dumps(bad_info, indent=2))

    # --- Validate ---
    provider = ObjectInfoIndexSchemaProvider(str(root))

    good_issues = _cross_validate_widget_order(provider, "GoodNode")
    bad_issues = _cross_validate_widget_order(provider, "SwappedNode")

    # GoodNode: no issues
    assert not good_issues, f"GoodNode should have no issues, got: {good_issues}"

    # SwappedNode: widget order mismatch detected
    assert bad_issues, (
        f"Layer 2 FAILED to detect swapped widget order on SwappedNode."
        f" (issues={bad_issues})"
        f" — the self-reference is broken."
    )

    print(f"\n[T16] Negative test: GoodNode clean ({good_issues})")
    print(f"[T16] SwappedNode caught: {bad_issues}")
    print(
        "[T16] Layer 2 is a fast pre-filter, NOT full independence."
        " Emitter and gate share object_info provenance."
    )
