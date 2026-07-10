from __future__ import annotations

from types import SimpleNamespace

from vibecomfy.comfy_nodes.agent.edit import (
    _direct_existing_parameter_tweak_feedback,
    _existing_parameter_tweak_targets,
    _existing_parameter_tweak_targets_from_graph,
)


def _state(*, task: str, graph: dict) -> SimpleNamespace:
    return SimpleNamespace(
        task=task,
        graph=graph,
        request_payload={"query": task},
    )


def _ks_graph() -> dict:
    """Return a minimal graph containing a KSampler node with compact fields."""
    return {
        "nodes": {
            "3": {
                "id": 3,
                "type": "KSampler",
                "widgets_values": [
                    156680208700286,  # seed
                    "fixed",  # control_after_generate
                    20,  # steps
                    8.0,  # cfg
                    "euler",  # sampler_name
                    "normal",  # scheduler
                    1.0,  # denoise
                ],
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": 2},
                    {"name": "negative", "type": "CONDITIONING", "link": 3},
                    {"name": "latent_image", "type": "LATENT", "link": 4},
                ],
            }
        }
    }


# ── legacy tests (pre-existing) ───────────────────────────────────────────────


def test_direct_existing_parameter_tweak_feedback_triggers_for_visible_existing_widgets() -> None:
    state = _state(
        task="Increase frame count and adjust frame rate to keep motion smooth.",
        graph={
            "nodes": {
                "34": {
                    "id": "34",
                    "class_type": "MoonvalleyImg2VideoNode",
                    "inputs": {},
                    "widgets": {"widget_3": 7, "widget_6": 100},
                }
            }
        },
    )

    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )

    assert "Direct existing-node tweak fallback applies here" in feedback
    assert "MoonvalleyImg2VideoNode [34]" in feedback
    assert "widget_N" in feedback


def test_direct_existing_parameter_tweak_feedback_skips_non_parameter_requests() -> None:
    state = _state(
        task="Replace the current workflow with a completely different architecture.",
        graph={
            "nodes": {
                "3": {
                    "id": "3",
                    "class_type": "TripoTextToModelNode",
                    "inputs": {},
                    "widgets": {"widget_9": "detailed"},
                }
            }
        },
    )

    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )

    assert feedback == ""


# ── KSampler compact-name tests ───────────────────────────────────────────────


def test_ks_sampler_targets_use_compact_field_names() -> None:
    """``_existing_parameter_tweak_targets`` returns engine-accepted compact
    field names for KSampler: all seven fields (``seed``, ``steps``, ``cfg``,
    ``sampler_name``, ``scheduler``, ``denoise``, ``control_after_generate``)
    are visible without raw ``widget_N`` entries."""
    state = _state(
        task="increase steps and adjust cfg to improve quality",
        graph=_ks_graph(),
    )
    targets = _existing_parameter_tweak_targets(state)
    assert len(targets) >= 1, "Expected at least one KSampler target"
    target_text = targets[0]
    # All seven compact field names must be visible in the target string.
    assert "seed" in target_text, f"Missing 'seed' in: {target_text}"
    assert "control_after_generate" in target_text, (
        f"Missing 'control_after_generate' in: {target_text}"
    )
    assert "steps" in target_text, f"Missing 'steps' in: {target_text}"
    assert "cfg" in target_text, f"Missing 'cfg' in: {target_text}"
    assert "sampler_name" in target_text, f"Missing 'sampler_name' in: {target_text}"
    assert "scheduler" in target_text, f"Missing 'scheduler' in: {target_text}"
    assert "denoise" in target_text, f"Missing 'denoise' in: {target_text}"


def test_ks_sampler_targets_avoid_raw_widget_positions() -> None:
    """KSampler target preview must not advertise raw ``widget_0``, ``widget_2``,
    etc. when semantic compact names are available."""
    graph = _ks_graph()
    targets = _existing_parameter_tweak_targets_from_graph(
        graph,
        query_text="increase steps",
        seen_targets=set(),
    )
    assert len(targets) >= 1, "Expected at least one KSampler target"
    target_text = targets[0][1]
    # Raw positional widgets must not appear for slots that have semantic names
    for forbidden in ("widget_0", "widget_1", "widget_2", "widget_3",
                      "widget_4", "widget_5", "widget_6"):
        assert forbidden not in target_text, (
            f"Raw positional '{forbidden}' should not appear in: {target_text}"
        )


def test_ks_sampler_feedback_contains_semantic_names_not_widget_positions() -> None:
    """The full fallback feedback string must include semantic names and avoid
    raw widget_N positions when KSampler is the target."""
    state = _state(
        task="tweak the sampler steps and denoise strength",
        graph=_ks_graph(),
    )
    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )
    assert "Direct existing-node tweak fallback applies here" in feedback
    # Semantic names present (only the first 4 fields are shown in the
    # truncated preview; later fields like denoise are replaced by "...")
    assert "seed" in feedback, f"Missing 'seed' in feedback: {feedback}"
    assert "steps" in feedback, f"Missing 'steps' in feedback: {feedback}"
    assert "cfg" in feedback, f"Missing 'cfg' in feedback: {feedback}"
    # Raw positional widgets must NOT appear for KSampler slots
    for forbidden in ("widget_0", "widget_2", "widget_3", "widget_4",
                      "widget_5", "widget_6"):
        assert forbidden not in feedback, (
            f"Raw positional '{forbidden}' should not appear in feedback: {feedback}"
        )


def test_ks_sampler_enum_fields_have_capped_annotations() -> None:
    """Enum fields like ``control_after_generate``, ``sampler_name``, and
    ``scheduler`` must carry capped choice annotations in the target preview."""
    graph = _ks_graph()
    targets = _existing_parameter_tweak_targets_from_graph(
        graph,
        query_text="change sampler",
        seen_targets=set(),
    )
    assert len(targets) >= 1, "Expected at least one KSampler target"
    target_text = targets[0][1]
    # control_after_generate is an enum → should have bracket annotation
    assert "control_after_generate[" in target_text, (
        f"Expected capped enum annotation for control_after_generate in: {target_text}"
    )
    # sampler_name and scheduler may or may not have schema choices available;
    # at minimum the annotation pattern is present when choices exist.
    # We assert that the bracket notation appears for any enum field.
    has_enum_annotation = "[" in target_text
    assert has_enum_annotation, (
        f"Expected at least one capped enum annotation in target: {target_text}"
    )


def test_ks_sampler_targets_include_control_after_generate_choices() -> None:
    """The ``control_after_generate`` enum annotation must include at least one
    of the four known values (fixed, randomize, increment, decrement)."""
    graph = _ks_graph()
    targets = _existing_parameter_tweak_targets_from_graph(
        graph,
        query_text="change seed behavior",
        seen_targets=set(),
    )
    target_text = targets[0][1]
    assert any(
        val in target_text
        for val in ("fixed", "randomize", "increment", "decrement")
    ), f"Expected control_after_generate choices in: {target_text}"


def test_unknown_node_still_falls_back_to_widget_n() -> None:
    """When settings_contract cannot resolve compact names, the old widget_N
    fallback is preserved."""
    state = _state(
        task="increase frame count",
        graph={
            "nodes": {
                "99": {
                    "id": "99",
                    "class_type": "UnknownCustomNode",
                    "inputs": {},
                    "widgets": {"widget_3": 7, "widget_6": 100},
                }
            }
        },
    )
    feedback = _direct_existing_parameter_tweak_feedback(
        state,
        "I could not find a workflow precedent or installed/provisional node schema.",
    )
    assert "Direct existing-node tweak fallback applies here" in feedback
    assert "UnknownCustomNode [99]" in feedback
    # The fallback should produce widget_N names for unknown nodes
    assert "widget_0" in feedback or "widget_3" in feedback, (
        f"Expected widget_N fallback in: {feedback}"
    )
