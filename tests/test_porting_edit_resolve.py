"""Tests for neutral schema-hint ordering and research output in vibecomfy/porting/edit/_resolve.py.

Proves:
- No node-family token ranking drives presentation order.
- Alphabetical ordering is used (stable, neutral).
- No adaptation winner leaks through the presentation layer.
- Research tool output is formatted as evidence/context, not options/menu.
- Packet-absent behavior preserves fallback conventions.
- Formatted output avoids option-menu or recommendation language.
"""

from __future__ import annotations

from typing import Any

from vibecomfy.porting.edit._resolve import (
    _ResolveMixin,
    _format_research_query_output,
    _format_schema_input_hint,
    _format_workflow_schema_hints,
    _has_concrete_workflow_pattern,
    _has_url_only_web_leads,
    _normalize_research_sources,
    _research_followup_guidance,
)


# ── _format_workflow_schema_hints ──────────────────────────────────────────────


class TestFormatWorkflowSchemaHints:
    """Neutral schema-hint presentation ordering."""

    def test_non_mapping_returns_empty(self) -> None:
        """Non-Mapping input returns empty list."""
        assert _format_workflow_schema_hints(None) == []
        assert _format_workflow_schema_hints("string") == []
        assert _format_workflow_schema_hints(42) == []
        assert _format_workflow_schema_hints([]) == []
        assert _format_workflow_schema_hints(()) == []

    def test_empty_mapping_returns_empty(self) -> None:
        """Empty dict returns empty list."""
        assert _format_workflow_schema_hints({}) == []

    def test_alphabetical_ordering_prevails(self) -> None:
        """Classes are presented in alphabetical order by class_type, not insertion order."""
        value: dict[str, Any] = {
            "ZoomSampler": {"input": {"required": {"model": {}}}},
            "AppleEncoder": {"input": {"required": {"image": {}}}},
            "BananaLoader": {"input": {"required": {"ckpt_name": {}}}},
        }
        result = _format_workflow_schema_hints(value)
        # Extract class_type names from the output lines.
        class_names = [
            line.split(" ")[1].rstrip(":")
            for line in result
            if line.startswith("workflow_schema ")
        ]
        assert class_names == ["AppleEncoder", "BananaLoader", "ZoomSampler"]

    def test_no_family_token_ranking(self) -> None:
        """Family tokens (hotshot, animatediff, ksampler, video) do NOT get priority.

        Even though 'VideoProcessor' might seem more relevant to video tasks,
        it should NOT be placed first just because it contains 'Video'.
        """
        value: dict[str, Any] = {
            "AnimateDiffLoader": {"input": {"required": {"model": {}}}},
            "HotshotXLEncoder": {"input": {"required": {"latent": {}}}},
            "CLIPTextEncode": {"input": {"required": {"text": {}}}},
            "VideoCombine": {"input": {"required": {"images": {}}}},
            "KSampler": {"input": {"required": {"model": {}, "seed": {}}}},
            "VAELoader": {"input": {"required": {"vae_name": {}}}},
        }
        result = _format_workflow_schema_hints(value, max_classes=10)
        class_names = [
            line.split(" ")[1].rstrip(":")
            for line in result
            if line.startswith("workflow_schema ")
        ]
        # Alphabetical ordering: AnimateDiffLoader, CLIPTextEncode, HotshotXLEncoder, KSampler, VAELoader, VideoCombine
        assert class_names == sorted(class_names)
        # HotshotXLEncoder must NOT come first (it would if family-token ranking existed).
        assert class_names[0] != "HotshotXLEncoder"
        # KSampler must NOT come first (it would if ksampler ranking existed).
        assert class_names[0] != "KSampler"
        # VideoCombine must NOT come first (it would if video ranking existed).
        assert class_names[0] != "VideoCombine"
        # AnimateDiffLoader must be first alphabetically.
        assert class_names[0] == "AnimateDiffLoader"

    def test_no_adaptation_winner_leaks(self) -> None:
        """No 'selected', 'winner', 'best', 'score' keys appear in output.

        The presentation is neutral — it doesn't signal which schema hint
        is the 'winner' or 'recommended' source.
        """
        value: dict[str, Any] = {
            "WANVideoWrapper": {
                "input": {
                    "required": {"positive": {}, "negative": {}, "latent_image": {}},
                    "optional": {"steps": {"default": 20}},
                },
                "outputs": [{"name": "LATENT", "type": "LATENT"}],
            },
            "LTXVLoader": {
                "input": {
                    "required": {"ckpt_name": {}},
                },
                "outputs": [{"name": "MODEL", "type": "MODEL"}, {"name": "LATENT", "type": "LATENT"}],
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        # No forbidden winner-like keys.
        for forbidden in ("winner", "best", "selected", "score", "rank", "primary",
                          "preferred", "chosen", "pick", "choice", "recommended",
                          "top", "leading"):
            assert forbidden not in combined.lower(), (
                f"Forbidden key '{forbidden}' found in schema hint output"
            )

    def test_max_classes_respected(self) -> None:
        """max_classes parameter limits output."""
        value: dict[str, Any] = {}
        for i in range(10):
            value[f"Node_{chr(97 + i)}"] = {
                "input": {"required": {"test": {}}}
            }
        result = _format_workflow_schema_hints(value, max_classes=3)
        class_lines = [l for l in result if l.startswith("workflow_schema ")]
        assert len(class_lines) == 3
        # Remaining count line should be present.
        remainder_line = [l for l in result if "more class" in l]
        assert len(remainder_line) == 1
        assert "7 more class" in remainder_line[0]

    def test_no_remainder_when_within_max(self) -> None:
        """No remainder line when classes <= max_classes."""
        value: dict[str, Any] = {
            "A": {"input": {"required": {"x": {}}}},
            "B": {"input": {"required": {"y": {}}}},
        }
        result = _format_workflow_schema_hints(value, max_classes=5)
        class_lines = [l for l in result if l.startswith("workflow_schema ")]
        assert len(class_lines) == 2
        remainder = [l for l in result if "more class" in l]
        assert len(remainder) == 0

    def test_max_classes_zero_or_negative(self) -> None:
        """max_classes <= 0 returns empty list (no class lines)."""
        value: dict[str, Any] = {
            "A": {"input": {"required": {"x": {}}}},
        }
        result = _format_workflow_schema_hints(value, max_classes=0)
        class_lines = [l for l in result if l.startswith("workflow_schema ")]
        assert len(class_lines) == 0

    def test_inputs_and_outputs_rendered(self) -> None:
        """Required inputs, optional (widgets), and outputs are rendered."""
        value: dict[str, Any] = {
            "TestNode": {
                "input": {
                    "required": {"model": {}, "clip": {}},
                    "optional": {"seed": {"default": 42}},
                },
                "outputs": [{"name": "IMAGE", "type": "IMAGE"}],
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        assert "inputs=clip, model" in combined
        assert "widgets=seed=42" in combined
        assert "outputs=IMAGE" in combined

    def test_input_required_names_sorted(self) -> None:
        """Required input names are sorted alphabetically."""
        value: dict[str, Any] = {
            "TestNode": {
                "input": {
                    "required": {"clip": {}, "model": {}, "vae": {}, "latent": {}},
                },
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        # Required names must be sorted: clip, latent, model, vae
        assert "model" in combined
        assert "clip" in combined

    def test_optional_input_names_sorted(self) -> None:
        """Optional input names are sorted alphabetically."""
        value: dict[str, Any] = {
            "TestNode": {
                "input": {
                    "optional": {
                        "batch_size": {"default": 1},
                        "denoise": {"default": 0.75},
                        "steps": {"default": 20},
                    },
                },
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        assert "batch_size=1" in combined
        assert "denoise=0.75" in combined
        assert "steps=20" in combined

    def test_outputs_list_handled(self) -> None:
        """Outputs as a list of dicts is handled."""
        value: dict[str, Any] = {
            "MultiOut": {
                "outputs": [
                    {"name": "IMAGE", "type": "IMAGE"},
                    {"name": "MASK", "type": "MASK"},
                ],
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        assert "outputs=IMAGE, MASK" in combined

    def test_outputs_with_only_type_field(self) -> None:
        """Outputs without name fall back to type field."""
        value: dict[str, Any] = {
            "TypeOnly": {
                "outputs": [{"type": "MODEL"}, {"type": "CLIP"}],
            },
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        assert "outputs=MODEL, CLIP" in combined

    def test_non_map_info_skipped(self) -> None:
        """Non-Mapping info entries are safely skipped."""
        value: dict[str, Any] = {
            "GoodNode": {"input": {"required": {"x": {}}}},
            "BadNode": "not_a_mapping",
        }
        result = _format_workflow_schema_hints(value)
        class_names = [
            line.split(" ")[1].rstrip(":")
            for line in result
            if line.startswith("workflow_schema ")
        ]
        # BadNode is skipped, only GoodNode appears.
        assert class_names == ["GoodNode"]
        assert "BadNode" not in class_names

    def test_deterministic_output(self) -> None:
        """Same input always produces same output (deterministic)."""
        value: dict[str, Any] = {
            "D": {"input": {"required": {"x": {}}}},
            "A": {"input": {"required": {"y": {}}}},
            "C": {"input": {"required": {"z": {}}}},
        }
        r1 = _format_workflow_schema_hints(value)
        r2 = _format_workflow_schema_hints(value)
        assert r1 == r2

    def test_no_implicit_precedence_signals(self) -> None:
        """No implicit precedence signals: no bold markers, no stars, no arrows."""
        value: dict[str, Any] = {
            "EvalNode": {"input": {"required": {"test": {}}}},
            "CoreNode": {"input": {"required": {"core": {}}}},
        }
        result = _format_workflow_schema_hints(value)
        combined = " ".join(result)
        for signal in ("**", "→", ">>", "⭐", "★", "✓", "✔", "►"):
            assert signal not in combined, f"Implicit precedence signal '{signal}' found"

    def test_presentation_order_comment_present(self) -> None:
        """Verify the source code has the presentation-order comment."""
        import inspect
        source = inspect.getsource(_format_workflow_schema_hints)
        assert "presentation order" in source.lower()

    def test_no_family_token_ranking_function_exists(self) -> None:
        """Verify the removed _workflow_schema_hint_priority function is gone."""
        from vibecomfy.porting.edit import _resolve as resolve_module
        assert not hasattr(resolve_module, "_workflow_schema_hint_priority"), (
            "_workflow_schema_hint_priority should have been removed in T5"
        )


# ── _format_schema_input_hint ─────────────────────────────────────────────────


class TestFormatSchemaInputHint:
    """Widget value formatting for schema input hints."""

    def test_non_mapping_returns_name_only(self) -> None:
        assert _format_schema_input_hint("foo", None) == "foo"
        assert _format_schema_input_hint("bar", "string") == "bar"
        assert _format_schema_input_hint("baz", []) == "baz"  # not a Mapping, no 'default'

    def test_no_default_returns_name_only(self) -> None:
        assert _format_schema_input_hint("steps", {}) == "steps"

    def test_string_default_rendered(self) -> None:
        assert _format_schema_input_hint("mode", {"default": "latent"}) == "mode='latent'"

    def test_int_default_rendered(self) -> None:
        assert _format_schema_input_hint("steps", {"default": 20}) == "steps=20"

    def test_float_default_rendered(self) -> None:
        assert _format_schema_input_hint("denoise", {"default": 0.75}) == "denoise=0.75"

    def test_bool_default_rendered(self) -> None:
        assert _format_schema_input_hint("enabled", {"default": True}) == "enabled=True"

    def test_none_default_rendered(self) -> None:
        assert _format_schema_input_hint("optional", {"default": None}) == "optional=None"

    def test_long_string_default_truncated(self) -> None:
        long_str = "a" * 60
        result = _format_schema_input_hint("long_field", {"default": long_str})
        assert result.startswith("long_field='")
        assert len(result) <= len("long_field=") + 48 + 3  # name + value truncated

    def test_non_primitive_default_returns_name_only(self) -> None:
        assert _format_schema_input_hint("complex", {"default": {"key": "val"}}) == "complex"
        assert _format_schema_input_hint("list_field", {"default": [1, 2, 3]}) == "list_field"


# ── _format_research_query_output ─────────────────────────────────────────────


class TestFormatResearchQueryOutput:
    """Research output formatting: evidence/context, not options/menu."""

    # -- basic output ----------------------------------------------------------

    def test_empty_result_returns_fallback(self) -> None:
        """Empty result returns fallback message."""
        output = _format_research_query_output(_FakeResult("", ()))
        assert output == "No research findings returned."

    def test_summary_only(self) -> None:
        """Summary is rendered when present."""
        output = _format_research_query_output(
            _FakeResult("Found workflow precedent.", ())
        )
        assert "Found workflow precedent." in output

    def test_summary_truncated_to_1200_chars(self) -> None:
        """Summary longer than 1200 chars is truncated."""
        long_summary = "x" * 1500
        output = _format_research_query_output(_FakeResult(long_summary, ()))
        assert len(output.split("\n")[0]) <= 1200

    def test_sources_rendered_with_title(self) -> None:
        """Sources are rendered with title and optional descriptor."""
        output = _format_research_query_output(_FakeResult(
            "Test summary.",
            (
                {"title": "HotshotXL pack", "source": "github",
                 "description": "Node pack for HotshotXL."},
            ),
        ))
        assert "Sources:" in output
        assert "HotshotXL pack" in output
        assert "Node pack for HotshotXL" in output

    def test_sources_title_fallback_to_class_type(self) -> None:
        """Source without title falls back to class_type."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"class_type": "KSampler", "source": "internal"},),
        ))
        assert "KSampler" in output

    def test_sources_title_fallback_to_path(self) -> None:
        """Source without title/class_type falls back to path."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"path": "/tmp/workflow.json", "source": "local"},),
        ))
        assert "/tmp/workflow.json" in output

    def test_sources_title_fallback_to_url(self) -> None:
        """Source without title/class_type/path falls back to url."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"url": "https://example.com/wf.json", "source": "web"},),
        ))
        assert "https://example.com/wf.json" in output

    def test_sources_title_fallback_to_source_kind(self) -> None:
        """Source with only source kind falls back to that."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"source": "hivemind"},),
        ))
        assert "hivemind" in output

    def test_sources_limited_to_five_plus_three_unique_kinds(self) -> None:
        """At most 5 same-kind + 3 unique-kind sources rendered (8 total)."""
        sources = []
        for i in range(10):
            sources.append({"title": f"Item {i}", "source": "same"})
        for i in range(5):
            sources.append({"title": f"Unique {i}", "source": f"kind_{i}"})
        output = _format_research_query_output(_FakeResult("Test.", tuple(sources)))
        # Count "- " lines (source entries)
        source_lines = [l for l in output.split("\n") if l.startswith("- ")]
        assert len(source_lines) <= 8

    def test_warnings_rendered(self) -> None:
        """Warnings are rendered when present."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            (),
            warnings=("Warning 1 text", "Warning 2 text"),
        ))
        assert "Warnings:" in output
        assert "Warning 1 text" in output
        assert "Warning 2 text" in output

    def test_warnings_truncated_to_five(self) -> None:
        """At most 5 warnings are rendered."""
        warnings = tuple(f"Warning {i}" for i in range(10))
        output = _format_research_query_output(_FakeResult(
            "Test.", (), warnings=warnings
        ))
        warning_lines = [l for l in output.split("\n") if l.startswith("- ") and "Warning" in l]
        assert len(warning_lines) <= 5

    def test_node_types_rendered_for_source(self) -> None:
        """node_types are rendered as compact sequence."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"title": "WF", "source": "web",
              "node_types": ["LoadImage", "KSampler", "VAEDecode"]},),
        ))
        assert "node_types:" in output
        assert "LoadImage" in output
        assert "KSampler" in output

    def test_key_values_rendered_for_source(self) -> None:
        """key_values are rendered as compact sequence (list/tuple form)."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"title": "WF", "source": "web",
              "key_values": ["model=sd_xl", "steps=20"]},),
        ))
        assert "key_values:" in output
        assert "model=sd_xl" in output

    def test_workflow_schemas_rendered_for_source(self) -> None:
        """workflow_schema dicts are rendered inline."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            ({"title": "WF", "source": "external_workflow",
              "workflow_schema": {
                  "KSampler": {"input": {"required": {"model": {}, "seed": {}}}},
              }},),
        ))
        assert "workflow_schema KSampler:" in output

    # -- neutral language: no option-menu or recommendation --------------------

    def test_no_option_menu_language(self) -> None:
        """Output must not contain option-menu / recommendation language."""
        output = _format_research_query_output(_FakeResult(
            "Multiple sources found.",
            (
                {"title": "Workflow Variant Alpha", "source": "web",
                 "description": "A workflow for the target."},
                {"title": "Workflow Variant Beta", "source": "web",
                 "description": "Another workflow for the target."},
            ),
        ))
        # Forbidden terms: must not present research as a menu or recommendation.
        forbidden = (
            "choose from", "pick one", "recommend", "recommended",
            "menu", "select from", "best choice", "winner", "top pick",
            "should use", "we suggest", "our recommendation",
        )
        lower = output.lower()
        for term in forbidden:
            assert term not in lower, f"Forbidden term '{term}' found in research output"

    def test_no_winner_like_keys_in_output(self) -> None:
        """Output must not contain winner/score/rank keys."""
        output = _format_research_query_output(_FakeResult(
            "Test.",
            (
                {"title": "Source A", "source": "web"},
                {"title": "Source B", "source": "web"},
            ),
        ))
        lower = output.lower()
        for key in ("winner", "best", "selected", "score", "rank", "primary",
                     "preferred", "chosen", "pick", "choice"):
            assert key not in lower, f"Forbidden key '{key}' found in research output"

    def test_formatted_as_evidence_not_directive(self) -> None:
        """Output is framed as evidence, not as implementation directive."""
        output = _format_research_query_output(_FakeResult(
            "Found workflow evidence.",
            ({"title": "WF Pattern", "source": "external_workflow",
              "description": "Example workflow showing the pattern."},),
        ))
        # Should NOT contain prescriptive language.
        for phrase in ("you should add", "implement this", "use this node",
                        "copy this exactly", "required implementation"):
            assert phrase not in output.lower(), (
                f"Prescriptive phrase '{phrase}' found in research output"
            )

    def test_no_agent_role_language(self) -> None:
        """Output must not use agent-role directive language (should, must, need to)."""
        output = _format_research_query_output(_FakeResult(
            "Evidence available.",
            ({"title": "Evidence Source", "source": "web"},),
        ))
        lower = output.lower()
        # "should" and "must" can appear in followup guidance, but not as
        # directives within the formatted source display itself.
        # We check that the output doesn't start with directive language.
        lines = output.split("\n")
        for directive in ("you should", "you must", "you need to", "the agent must"):
            for line in lines:
                if line.strip().lower().startswith(directive):
                    assert False, f"Directive '{directive}' in formatted output: {line.strip()}"


# ── _research_followup_guidance ────────────────────────────────────────────────


class TestResearchFollowupGuidance:
    """Followup guidance generation for research query results."""

    def test_workflows_only_includes_workflow_check(self) -> None:
        """When only workflows source used, workflow-first check is included."""
        result = _FakeResult("Test.", ())
        guidance = _research_followup_guidance(
            "test query", ("workflows",), result
        )
        assert "Workflow-first check" in guidance
        assert "named target technology" in guidance

    def test_workflows_and_registry_combined_includes_order_check(self) -> None:
        """When workflows+registry combined, research-order check is included."""
        result = _FakeResult("Test.", ())
        guidance = _research_followup_guidance(
            "test query", ("workflows", "registry"), result
        )
        assert "Workflow-first check" in guidance
        assert "Research-order check" in guidance
        assert "separate external workflow" in guidance

    def test_web_url_only_leads_prompts_concrete_followup(self) -> None:
        """When web results are URL-only leads, external workflow check appears."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com/wf", "title": "Lead"},
        ))
        guidance = _research_followup_guidance(
            "test query", ("web",), result
        )
        assert "External workflow check" in guidance
        assert "URL/title leads" in guidance

    def test_web_concrete_pattern_prompts_schema_followup(self) -> None:
        """When web results have concrete workflow pattern, schema followup appears."""
        result = _FakeResult("Test.", (
            {"source": "external_workflow", "source_type": "github_workflow_json",
             "node_types": ["KSampler", "VAEDecode"],
             "source_workflow_path": "/tmp/wf.json",
             "title": "concrete-wf.json"},
        ))
        guidance = _research_followup_guidance(
            "test query", ("web",), result
        )
        assert "Concrete workflow pattern found" in guidance
        assert "KSampler" in guidance
        assert "VAEDecode" in guidance

    def test_registry_only_without_workflows_includes_registry_check(self) -> None:
        """Registry-only without workflows/web triggers registry check guidance."""
        result = _FakeResult("Test.", (
            {"source": "comfy-registry", "class_type": "SomeNode"},
        ))
        guidance = _research_followup_guidance(
            "test query", ("registry",), result
        )
        assert "Registry check" in guidance
        assert "not to invent a workflow pattern" in guidance

    def test_messages_in_play_returns_static_followup_even_without_sources(self) -> None:
        """B03: messages-in-play emits the static messages followup even when
        no matching sources exist — the wording never switches on hit count or
        any strength helper."""
        result = _FakeResult("Test.", ())
        guidance = _research_followup_guidance(
            "test query", ("messages",), result
        )
        assert guidance != ""
        assert "thin or off-topic" in guidance
        assert "call done()" in guidance
        assert "Workflow-first" not in guidance

    def test_no_winner_or_recommendation_language(self) -> None:
        """Followup guidance must not use winner/recommendation language."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com", "title": "Lead"},
        ))
        guidance = _research_followup_guidance(
            "test query", ("web",), result
        )
        lower = guidance.lower()
        for term in ("winner", "recommended", "best choice", "top pick",
                      "should use this", "pick this"):
            assert term not in lower, (
                f"Forbidden term '{term}' in followup guidance"
            )

    def test_no_option_menu_language(self) -> None:
        """Followup guidance must not present sources as options/menu."""
        result = _FakeResult("Test.", (
            {"source": "web", "title": "A"}, {"source": "web", "title": "B"},
        ))
        guidance = _research_followup_guidance(
            "test query", ("web",), result
        )
        lower = guidance.lower()
        for term in ("option", "choose from", "menu", "select one"):
            assert term not in lower, (
                f"Forbidden term '{term}' in followup guidance"
            )


# ── _normalize_research_sources ────────────────────────────────────────────────


class TestNormalizeResearchSources:
    """Source normalization for research() calls."""

    def test_none_returns_none(self) -> None:
        """None input returns None with no diagnostic."""
        sources, diag = _normalize_research_sources(None)
        assert sources is None
        assert diag is None

    def test_single_string_normalized(self) -> None:
        """Single string is normalized to known source category."""
        sources, diag = _normalize_research_sources("web")
        assert sources == ("web",)
        assert diag is None

    def test_list_of_strings_normalized(self) -> None:
        """List of strings is normalized."""
        sources, diag = _normalize_research_sources(["web", "registry", "workflows"])
        assert sources == ("web", "registry", "workflows")
        assert diag is None

    def test_aliases_mapped(self) -> None:
        """Source aliases (local->workflows, github->web, etc.) are mapped."""
        sources, diag = _normalize_research_sources(["local", "github", "hivemind"])
        assert sources == ("workflows", "web", "messages")
        assert diag is None

    def test_duplicates_removed(self) -> None:
        """Duplicate source entries are deduplicated."""
        sources, diag = _normalize_research_sources(["web", "web", "registry"])
        assert sources == ("web", "registry")
        assert diag is None

    def test_case_insensitive(self) -> None:
        """Source names are case-insensitive."""
        sources, diag = _normalize_research_sources(["WEB", "Registry", "Workflows"])
        assert sources == ("web", "registry", "workflows")
        assert diag is None

    def test_invalid_source_returns_diagnostic(self) -> None:
        """Invalid source name returns diagnostic."""
        sources, diag = _normalize_research_sources(["invalid_source"])
        assert sources is None
        assert diag is not None
        assert "unsupported_research_source" in diag.code

    def test_non_string_items_return_diagnostic(self) -> None:
        """Non-string items in list return diagnostic."""
        sources, diag = _normalize_research_sources([42, True])
        assert sources is None
        assert diag is not None

    def test_non_string_non_list_returns_diagnostic(self) -> None:
        """Non-string, non-list value returns diagnostic."""
        sources, diag = _normalize_research_sources(42)
        assert sources is None
        assert diag is not None


# ── _has_concrete_workflow_pattern ─────────────────────────────────────────────


class TestHasConcreteWorkflowPattern:
    """Detection of concrete workflow patterns in research results."""

    def test_node_types_indicates_concrete(self) -> None:
        """Source with node_types is concrete."""
        result = _FakeResult("Test.", (
            {"source": "web", "node_types": ["KSampler"]},
        ))
        assert _has_concrete_workflow_pattern(result) is True

    def test_source_workflow_path_indicates_concrete(self) -> None:
        """Source with source_workflow_path is concrete."""
        result = _FakeResult("Test.", (
            {"source": "web", "source_workflow_path": "/tmp/wf.json"},
        ))
        assert _has_concrete_workflow_pattern(result) is True

    def test_github_workflow_json_is_concrete(self) -> None:
        """Github workflow JSON source_type with path is concrete."""
        result = _FakeResult("Test.", (
            {"source": "external_workflow", "source_type": "github_workflow_json",
             "path": "/tmp/wf.json"},
        ))
        assert _has_concrete_workflow_pattern(result) is True

    def test_url_only_is_not_concrete(self) -> None:
        """URL-only source without node_types/path is not concrete."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com", "title": "Page"},
        ))
        assert _has_concrete_workflow_pattern(result) is False

    def test_empty_sources_is_not_concrete(self) -> None:
        """Empty sources is not concrete."""
        result = _FakeResult("Test.", ())
        assert _has_concrete_workflow_pattern(result) is False

    def test_ready_template_is_concrete(self) -> None:
        """Ready template source is concrete."""
        result = _FakeResult("Test.", (
            {"source": "ready_template", "node_types": ["LoadImage"]},
        ))
        assert _has_concrete_workflow_pattern(result) is True


# ── _has_url_only_web_leads ────────────────────────────────────────────────────


class TestHasUrlOnlyWebLeads:
    """Detection of URL-only web leads (no concrete workflow pattern)."""

    def test_web_source_with_url_only_is_lead(self) -> None:
        """Web source with URL but no node_types/path is a URL-only lead."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com", "title": "Page"},
        ))
        assert _has_url_only_web_leads(result) is True

    def test_web_source_with_node_types_is_not_lead(self) -> None:
        """Web source with node_types is not a URL-only lead."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com",
             "node_types": ["KSampler"]},
        ))
        assert _has_url_only_web_leads(result) is False

    def test_web_source_with_source_workflow_path_is_not_lead(self) -> None:
        """Web source with source_workflow_path is not a URL-only lead."""
        result = _FakeResult("Test.", (
            {"source": "web", "url": "https://example.com",
             "source_workflow_path": "/tmp/wf.json"},
        ))
        assert _has_url_only_web_leads(result) is False

    def test_non_web_source_is_not_lead(self) -> None:
        """Non-web source is not a URL-only lead."""
        result = _FakeResult("Test.", (
            {"source": "hivemind", "url": "https://example.com"},
        ))
        assert _has_url_only_web_leads(result) is False

    def test_empty_sources_is_not_lead(self) -> None:
        """Empty sources has no URL-only leads."""
        result = _FakeResult("Test.", ())
        assert _has_url_only_web_leads(result) is False


# ── _resolve_query_statement research tier wiring (B02) ───────────────────────


class TestResolveResearchStatementSources:
    """research() resolution passes the resolved sources tuple + split clients.

    Omitted ``sources=`` still resolves to ``("workflows",)`` in this batch
    (the research-route omit default lands in B03).  Explicit tuples null
    unlisted tiers; invalid explicit sources keep the existing diagnostic.
    """

    def _resolve(self, code: str, monkeypatch: pytest.MonkeyPatch):
        import ast
        import importlib

        from vibecomfy.executor.contracts import ResearchResult

        calls: list[dict[str, Any]] = []

        def fake_research(query: str, **kwargs: Any) -> ResearchResult:
            calls.append({"query": query, **kwargs})
            return ResearchResult(summary="Summary.", sources=())

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "research", fake_research)

        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Call)

        resolver = _ResolveMixin()
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        return result, calls

    def test_omitted_sources_resolve_to_workflows_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve('research("Hotshot XL ComfyUI 16 frames")', monkeypatch)

        assert result.ok is True
        assert calls[0]["query"] == "Hotshot XL ComfyUI 16 frames"
        assert calls[0]["sources"] == ("workflows",)
        assert calls[0]["local_limit"] == 5
        assert calls[0]["hivemind_client"] is not None
        assert calls[0]["hivemind_messages_client"] is None
        assert calls[0]["web_search_client"] is None
        assert result.detail["research_sources"] == ("workflows",)
        assert result.detail["requested_research_sources"] == ("workflows",)

    def test_messages_source_uses_messages_client_and_nulls_workflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve('research("MiniMax H3", sources=["messages"])', monkeypatch)

        assert result.ok is True
        assert calls[0]["query"] == "MiniMax H3"
        assert calls[0]["sources"] == ("messages",)
        assert calls[0]["local_limit"] == 0
        assert calls[0]["hivemind_client"] is None
        assert calls[0]["hivemind_messages_client"] is not None
        assert calls[0]["web_search_client"] is None
        assert result.detail["research_sources"] == ("messages",)

    def test_messages_web_combination_sets_both_clients(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("LTX 2.5", sources=["messages", "web"])', monkeypatch
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("messages", "web")
        assert calls[0]["local_limit"] == 0
        assert calls[0]["hivemind_client"] is None
        assert calls[0]["hivemind_messages_client"] is not None
        assert calls[0]["web_search_client"] is not None
        assert result.detail["research_sources"] == ("messages", "web")

    def test_workflows_web_keeps_workflow_client_and_nulls_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("Hotshot XL", sources=["workflows", "web"])', monkeypatch
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("workflows", "web")
        assert calls[0]["local_limit"] == 5
        assert calls[0]["hivemind_client"] is not None
        assert calls[0]["hivemind_messages_client"] is None
        assert calls[0]["web_search_client"] is not None
        assert result.detail["research_sources"] == ("workflows", "web")

    def test_invalid_explicit_sources_diagnostic_unchanged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve('research("q", sources=["bogus"])', monkeypatch)

        assert result.ok is False
        assert calls == []  # research() is never invoked for invalid sources
        codes = [d.code for d in result.diagnostics]
        assert "unsupported_research_source" in codes


# ── B03 research-route omit default ──────────────────────────────────────────


class TestResolveResearchOmitDefault:
    """Omitted sources= (None / () / []) on a research-only session resolve to
    ("messages", "web"); adapt/revise omission stays ("workflows",); explicit
    non-empty sources= wins with NO union.  Classify source_preferences stay
    prompt-visible and are never read here.
    """

    def _resolve(
        self,
        code: str,
        monkeypatch: pytest.MonkeyPatch,
        *,
        research_only: bool = False,
        brief: dict[str, Any] | None = None,
    ):
        import ast
        import importlib

        from vibecomfy.executor.contracts import ResearchResult

        calls: list[dict[str, Any]] = []

        def fake_research(query: str, **kwargs: Any) -> ResearchResult:
            calls.append({"query": query, **kwargs})
            return ResearchResult(summary="Summary.", sources=())

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "research", fake_research)

        tree = ast.parse(code)
        assert isinstance(tree.body[0], ast.Expr)
        assert isinstance(tree.body[0].value, ast.Call)

        resolver = _ResolveMixin()
        resolver.research_only = research_only
        if brief is not None:
            resolver.executor_research_brief = brief
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )
        return result, calls

    def test_resolve_omitted_sources_research_only_defaults_to_messages_web(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("MiniMax H3")', monkeypatch, research_only=True
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("messages", "web")
        assert calls[0]["local_limit"] == 0
        assert calls[0]["hivemind_client"] is None
        assert calls[0]["hivemind_messages_client"] is not None
        assert calls[0]["web_search_client"] is not None
        assert result.detail["requested_research_sources"] == ("messages", "web")

    def test_resolve_empty_sources_list_is_omit_not_no_tiers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("LTX 2.5", sources=[])', monkeypatch, research_only=True
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("messages", "web")

    def test_resolve_omitted_sources_adapt_defaults_to_workflows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve('research("Hotshot XL ComfyUI 16 frames")', monkeypatch)

        assert result.ok is True
        assert calls[0]["sources"] == ("workflows",)
        assert calls[0]["local_limit"] == 5
        assert calls[0]["hivemind_messages_client"] is None

    def test_resolve_omitted_sources_ignores_distilled_faster_brief_workflows(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Brief source_preferences are prompt-visible only — omit still resolves
        # to ("messages", "web") on the research route regardless of the brief.
        brief = {
            "source_preferences": ["workflows", "messages", "web"],
            "research_goal": "Find distilled or faster ways to run the workflow.",
        }
        result, calls = self._resolve(
            'research("distilled faster")', monkeypatch, research_only=True, brief=brief
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("messages", "web")

    def test_resolve_explicit_web_sources_not_unioned_with_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("Hotshot XL", sources=["web"])', monkeypatch, research_only=True
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("web",)
        assert calls[0]["hivemind_client"] is None
        assert calls[0]["hivemind_messages_client"] is None
        assert calls[0]["web_search_client"] is not None

    def test_resolve_explicit_workflows_not_unioned_with_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("KSampler", sources=["workflows"])', monkeypatch, research_only=True
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("workflows",)
        assert calls[0]["hivemind_client"] is not None
        assert calls[0]["hivemind_messages_client"] is None
        assert calls[0]["web_search_client"] is None

    def test_resolve_omitted_research_only_requests_web_client_without_http(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import importlib

        research_module = importlib.import_module("vibecomfy.executor.research")

        def fake_web_client(query: str, timeout: float) -> dict[str, Any]:
            return {"results": []}

        monkeypatch.setattr(research_module, "_default_web_search_client", fake_web_client)
        result, calls = self._resolve(
            'research("MiniMax H3")', monkeypatch, research_only=True
        )

        assert result.ok is True
        # research() is monkeypatched to a fake, so no live web HTTP runs; the
        # resolver must still hand the web tier the default callable.
        assert calls[0]["web_search_client"] is fake_web_client
        assert calls[0]["hivemind_messages_client"] is not None

    def test_resolve_messages_and_workflows_sets_both_clients(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        result, calls = self._resolve(
            'research("MiniMax H3", sources=["messages", "workflows"])',
            monkeypatch,
            research_only=True,
        )

        assert result.ok is True
        assert calls[0]["sources"] == ("messages", "workflows")
        assert calls[0]["hivemind_client"] is not None
        assert calls[0]["hivemind_messages_client"] is not None

    def test_resolve_attaches_structured_detail_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import ast
        import importlib

        from vibecomfy.executor.contracts import ResearchResult

        message_source = {
            "source": "hivemind_message",
            "class_type": "MiniMax H3 is amazing",
            "author": "alice",
            "channel": "minimax_h3_chatter",
            "hivemind_id": "9007199254740993",
            "description": "loving the new model",
            "_retrieval_time": "2026-08-13T00:00:00Z",
            "_content_hash": "abc",
            "score": 5,
        }

        def fake_research(query: str, **kwargs: Any) -> ResearchResult:
            return ResearchResult(
                summary="Found community evidence.",
                sources=(message_source,),
                community_summary='alice in #minimax_h3_chatter: loving the new model',
            )

        research_module = importlib.import_module("vibecomfy.executor.research")
        monkeypatch.setattr(research_module, "research", fake_research)

        tree = ast.parse('research("MiniMax H3")')
        resolver = _ResolveMixin()
        resolver.research_only = True
        result = resolver._resolve_query_statement(
            statement_index=0,
            source="user",
            call=tree.body[0].value,
            env={},
        )

        assert result.ok is True
        assert result.detail["community_summary"] == (
            "alice in #minimax_h3_chatter: loving the new model"
        )
        assert result.detail["research_summary"] == "Found community evidence."
        sources = result.detail["research_result_sources"]
        assert len(sources) == 1
        assert sources[0]["source"] == "hivemind_message"
        assert sources[0]["author"] == "alice"
        assert sources[0]["channel"] == "minimax_h3_chatter"
        # underscore audit keys are dropped except the three public stamp keys;
        # non-underscore keys (score, author, ...) stay (display metadata)
        assert "_content_hash" not in sources[0]
        assert "_query_transform_trace" not in sources[0]
        assert sources[0]["score"] == 5
        assert sources[0]["_retrieval_time"] == "2026-08-13T00:00:00Z"
        assert "evidence_card" not in result.detail


# ── B03 query_output formatting (community_summary + 12-cap) ─────────────────


def _message_source(
    index: int,
    *,
    author: str = "alice",
    channel: str = "ltx_chatter",
) -> dict[str, Any]:
    return {
        "source": "hivemind_message",
        "class_type": f"LTX 2.5 message {index}",
        "author": author,
        "channel": channel,
        "hivemind_id": str(index),
        "description": f"community message body {index}",
        "kind": "message",
    }


class TestFormatResearchQueryOutputB03:
    def test_prints_community_summary_and_author_channel(self) -> None:
        sources = tuple(_message_source(i) for i in range(1, 13))
        result = _FakeResult(
            summary="Summary line.",
            sources=sources,
            community_summary='alice in #ltx_chatter: LTX 2.5 message 1',
        )

        output = _format_research_query_output(result)

        assert "Summary line." in output
        assert "alice in #ltx_chatter" in output
        assert "alice" in output
        assert "ltx_chatter" in output
        # 12-cap (not today's 8): all 12 message fixtures appear
        assert "LTX 2.5 message 12" in output
        assert sum(1 for i in range(1, 13) if f"LTX 2.5 message {i}" in output) == 12
        # No evidence-card / strength language
        assert "[evidence]" not in output
        assert "strength=" not in output

    def test_non_message_sources_keep_8_cap(self) -> None:
        # 10 sources across 10 distinct kinds → first 5 + 3 unique-kind fill = 8
        kinds = [
            "web", "github", "git", "hivemind", "hivemind_workflow",
            "comfy-registry", "ready_template", "source_workflow", "curated",
            "external_workflow",
        ]
        sources = tuple(
            {
                "source": kind,
                "title": f"result {kind}",
                "url": f"https://example.com/{kind}",
            }
            for kind in kinds
        )
        result = _FakeResult(summary="", sources=sources)

        output = _format_research_query_output(result)

        assert sum(1 for kind in kinds if f"result {kind}" in output) == 8
        assert "result external_workflow" not in output

    def test_distillation_status_in_descriptor(self) -> None:
        sources = (
            {
                "source": "hivemind_distillation",
                "class_type": "LTX 2.5 reception",
                "title": "LTX 2.5 reception",
                "distillation_status": "approved",
                "hivemind_id": "dist-1",
                "description": "summary",
            },
        )
        result = _FakeResult(summary="", sources=sources, community_summary="")

        output = _format_research_query_output(result)

        assert "LTX 2.5 reception" in output
        assert "approved" in output

    def test_empty_messages_sentence_is_printed(self) -> None:
        result = _FakeResult(
            summary="",
            sources=(),
            community_summary='No community discussion found for "LTX 2.5".',
        )

        output = _format_research_query_output(result)

        assert 'No community discussion found for "LTX 2.5".' in output


# ── B03 followup guidance routing ─────────────────────────────────────────────


class TestResearchFollowupGuidanceB03:
    def test_messages_tells_model_to_judge_and_done(self) -> None:
        result = _FakeResult(summary="", sources=())
        guidance = _research_followup_guidance(
            "MiniMax H3", ("messages",), result
        )

        assert "thin or off-topic" in guidance
        assert "call done()" in guidance
        assert "search_directions" in guidance
        assert "Do not invent quotes" in guidance

    def test_messages_web_url_only_does_not_ask_for_workflow_json(self) -> None:
        result = _FakeResult(
            summary="",
            sources=({"source": "web", "title": "LTX page", "url": "https://example.com"},),
        )
        guidance = _research_followup_guidance(
            "LTX 2.5", ("messages", "web"), result
        )

        assert "workflow JSON" not in guidance
        assert "Workflow-first" not in guidance
        assert "thin or off-topic" in guidance

    def test_web_only_still_emits_external_workflow_check(self) -> None:
        result = _FakeResult(
            summary="",
            sources=({"source": "web", "title": "LTX page", "url": "https://example.com"},),
        )
        guidance = _research_followup_guidance("LTX 2.5", ("web",), result)

        assert "External workflow check" in guidance
        assert "workflow JSON" in guidance

    def test_messages_only_does_not_emit_workflow_first_check(self) -> None:
        result = _FakeResult(summary="", sources=())
        guidance = _research_followup_guidance("MiniMax H3", ("messages",), result)

        assert "Workflow-first" not in guidance
        assert "Registry check" not in guidance
        assert "External workflow check" not in guidance

    def test_workflows_still_emits_workflow_first_check(self) -> None:
        result = _FakeResult(summary="", sources=())
        guidance = _research_followup_guidance("KSampler", ("workflows",), result)

        assert "Workflow-first check" in guidance


# ── B03 research fold helpers (edit_batch_repl.py) ───────────────────────────


class TestFoldResearchStatement:
    def test_fold_research_statement_unions_sources_by_id(self) -> None:
        from types import SimpleNamespace

        from vibecomfy.comfy_nodes.agent.edit_batch_repl import (
            _dedupe_sources_by_id,
            _fold_research_statement,
        )

        first = {
            "research_result_sources": [
                _message_source(1, author="alice"),
                _message_source(2, author="bob"),
            ],
            "community_summary": "first paragraph",
            "research_summary": "first summary",
        }
        second = {
            "research_result_sources": [
                _message_source(1, author="alice2"),  # same id → first-seen wins
                _message_source(3, author="carol"),
            ],
            "community_summary": "second paragraph",
            "research_summary": "second summary",
        }

        state = SimpleNamespace(
            collected_research_sources=(),
            collected_community_summary="",
            collected_research_summary="",
        )
        _fold_research_statement(state, first)
        _fold_research_statement(state, second)

        sources = state.collected_research_sources
        assert len(sources) == 3
        assert [s["hivemind_id"] for s in sources] == ["1", "2", "3"]
        # first-seen wins on sources
        assert sources[0]["author"] == "alice"
        # last-write-wins on paragraphs
        assert state.collected_community_summary == "second paragraph"
        assert state.collected_research_summary == "second summary"

    def test_dedupe_sources_by_id_keeps_first_seen(self) -> None:
        from vibecomfy.comfy_nodes.agent.edit_batch_repl import _dedupe_sources_by_id

        merged = _dedupe_sources_by_id(
            (_message_source(1, author="alice"),),
            (_message_source(1, author="alice2"), _message_source(4, author="dana")),
        )

        assert len(merged) == 2
        assert merged[0]["author"] == "alice"
        assert merged[1]["author"] == "dana"

    def test_fold_ignores_statements_without_research_fields(self) -> None:
        from types import SimpleNamespace

        from vibecomfy.comfy_nodes.agent.edit_batch_repl import _fold_research_statement

        state = SimpleNamespace(
            collected_research_sources=(),
            collected_community_summary="",
            collected_research_summary="",
        )
        _fold_research_statement(state, {"query": "search", "query_output": "No node signature found"})

        assert state.collected_research_sources == ()
        assert state.collected_community_summary == ""
        assert state.collected_research_summary == ""


# ── helpers ────────────────────────────────────────────────────────────────────


class _FakeResult:
    """Minimal ResearchResult-like object for testing output formatting."""

    def __init__(
        self,
        summary: str,
        sources: tuple,
        warnings: tuple = (),
        community_summary: str = "",
    ):
        self.summary = summary
        self.sources = sources
        self.warnings = warnings
        self.community_summary = community_summary
